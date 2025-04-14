import win32com.client
import os
import pytesseract
from PIL import Image
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
from mcp.server import Server
from mcp import types
from sse_starlette.sse import EventSourceResponse
import asyncio
from imap_tools import MailBox
import time
import json 
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Initialize MCP Server logic
mcp_server = Server("EmailOCRServer")

# Create FastAPI app
app = FastAPI(title="Email OCR MCP Server")

# Configure directories
TEMP_DIR = os.path.join(os.getcwd(), "temp_attachments")
os.makedirs(TEMP_DIR, exist_ok=True)

# Store extracted text from images to avoid re-processing
image_content_cache = {}

class EmailOCRTool:
    def __init__(self):
        # Set Tesseract path - update this to match your installation
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
        
    def _clean_temp_directory(self):
        """Clean up old temporary files"""
        if os.path.exists(TEMP_DIR):
            for file in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, file)
                if os.path.isfile(file_path):
                    try:
                        os.unlink(file_path)
                    except Exception as e:
                        print(f"Error deleting {file_path}: {e}")
    
    def _read_image_with_ocr(self, file_path):
        """Extract text from image using OCR"""
        try:
            # Check if we've already processed this image
            if file_path in image_content_cache:
                return image_content_cache[file_path]
            
            # Open the image file
            image = Image.open(file_path)
            
            # Perform OCR on the image
            text = pytesseract.image_to_string(image)
            
            # Cache the result
            image_content_cache[file_path] = text
            
            return text
        except Exception as e:
            return f"OCR Error: {str(e)}"
    
  
    def check_latest_emails(self, email_folder="BOT", limit=5):
        """Check the latest emails and extract text from image attachments"""
        try:
            results = []
            self._clean_temp_directory()
            timestamp = int(time.time())
            count = 0

            with MailBox('imap.fastmail.com').login('samarthlavhate@fastmail.com',os.getenv('IMAP') , 'Inbox') as mb:
                for message in mb.fetch(limit=5, reverse=True):
                    email_info = {
                        "subject": message.subject,
                        "sender": message.from_,
                        "received": message.date.strftime("%Y-%m-%d %H:%M:%S") if message.date else "Unknown",
                        "body": message.text or message.html or "No body content",
                        "has_attachments": bool(message.attachments),
                        "attachments": []
                    }

                    for i, attachment in enumerate(message.attachments):
                        if attachment.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                            safe_filename = f"{timestamp}_{count}_{i}_{attachment.filename}"
                            attachment_path = os.path.join(TEMP_DIR, safe_filename)

                            with open(attachment_path, 'wb') as f:
                                f.write(attachment.payload)

                            extracted_text = self._read_image_with_ocr(attachment_path)

                            attachment_info = {
                                "filename": attachment.filename,
                                "type": "image",
                                "text_content": extracted_text
                            }

                            email_info["attachments"].append(attachment_info)

                    results.append(email_info)
                    count += 1

            if not results:
                return "No emails with image attachments found."

            # Formatting
            formatted_results = []
            for i, email in enumerate(results):
                email_text = [
                    f"Email {i}:",
                    f"Subject: {email['subject']}",
                    f"From: {email['sender']}",
                    f"Received: {email['received']}",
                    f"Body: {email['body'][:100]}..." if len(email['body']) > 100 else f"Body: {email['body']}",
                    f"Attachments: {len(email['attachments'])}"
                ]

                for j, attachment in enumerate(email['attachments'], 1):
                    email_text.append(f"\nAttachment {j}: {attachment['filename']}")
                    email_text.append(f"Content:\n{attachment['text_content']}")

                formatted_results.append("\n".join(email_text))

            return "\n\n" + "\n\n".join(formatted_results)

        except Exception as e:
            return f"Error accessing emails: {str(e)}"
    
    def answer_from_latest_email_images(self, query):
        """Get the latest email with image attachments and answer a query based on the content"""
        try:
            email_info = self.check_latest_emails(limit=1)
            
            if "No emails" in email_info or "Error" in email_info:
                return f"Could not find recent emails with images. Error: {email_info}"
            
            return email_info
        except Exception as e:
            return f"Error processing email content: {str(e)}"
    
    def send_mail(self,query):
        cleaned = query.strip().removeprefix("```json").removesuffix("```").strip()
        json_data=json.loads(cleaned)
        msg = MIMEMultipart()
        msg['From'] = 'samarthlavhate@fastmail.com'
        msg['To'] = json_data[0]['email']['to']
        msg['Subject'] = json_data[0]['email']['subject']

        msg.attach(MIMEText(json_data[0]['email']['body'], 'plain'))

        # Connect to Fastmail SMTP serveros.getenv("SMTP")
        with smtplib.SMTP_SSL('smtp.fastmail.com', 465) as server:
            server.login('samarthlavhate@fastmail.com', os.getenv("SMTP"))
            server.send_message(msg)

        return "Email sent successfully!"

# Initialize the tool
tool = EmailOCRTool()

# Register tools with MCP server
@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="check_latest_emails",
            description="Check the latest emails and extract text from image attachments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_folder": {
                        "type": "string",
                        "description": "The Outlook folder to check (default: BOT)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of emails to check",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="answer_from_latest_email_images",
            description="Get text from latest email with image attachments and use it to answer a query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to answer based on the image content"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "check_latest_emails":
        email_folder = arguments.get("email_folder", "BOT")
        limit = min(max(arguments.get("limit", 5), 1), 20)  # Ensure limit is between 1 and 20
        result = tool.check_latest_emails(email_folder, limit)
        return [types.TextContent(type="text", text=result)]
    if name =='send_mail':
        query=arguments.get("query", "")
        tool.send_mail(query)
        return [types.TextContent(type="text", text='mail sent')]
               
    elif name == "answer_from_latest_email_images":
        query = arguments.get("query", "")
        if not query:
            return [types.TextContent(type="text", text="Error: Query parameter is required")]
        result = tool.answer_from_latest_email_images(query)
        return [types.TextContent(type="text", text=result)]
    
    raise ValueError(f"Tool not found: {name}")

# SSE endpoint for MCP (basic connectivity)
async def sse_endpoint():
    async def event_generator():
        yield {"data": f'{{"type": "server_ready", "server": "EmailOCRServer"}}'}
        while True:
            await asyncio.sleep(1)
            yield {"data": '{"type": "ping"}'}
    return EventSourceResponse(event_generator())

# Mount MCP endpoints
app.get("/mcp/sse")(sse_endpoint)

# Tools list endpoint
@app.get("/mcp/tools")
async def get_tools():
    tools = await list_tools()
    return {"tools": [tool.dict() for tool in tools]}

# Tool call endpoint
class ToolCallRequest(BaseModel):
    name: str
    arguments: dict = {}

@app.post("/mcp/call_tool")
async def call_tool_endpoint(request: ToolCallRequest):
    try:
        result = await call_tool(request.name, request.arguments)
        return {"content": [content.dict() for content in result]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)