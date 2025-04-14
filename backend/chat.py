import os
from dotenv import load_dotenv
import google.generativeai as genai
import requests
import uvicorn
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import pytesseract
import fitz  # PyMuPDF for PDF reading
import io
# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
app = FastAPI()
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# MCP server URL
MCP_SERVER_URL = "http://localhost:8000/mcp/call_tool"

# Email content storage
email_context = {}

def call_mcp_tool(name, arguments=None):
    """Call a tool on the MCP server"""
    if arguments is None:
        arguments = {}
    
    try:
        response = requests.post(
            MCP_SERVER_URL,
            json={"name": name, "arguments": arguments}
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
    except requests.RequestException as e:
        return f"Error contacting MCP server: {str(e)}"

def check_emails():
    """Check for the latest emails with image attachments"""
    return call_mcp_tool("check_latest_emails", {"limit": 5})
def send_email(mailContent):
    return call_mcp_tool('send_mail',{"query": mailContent})

def answer_based_on_email_content(query):
    """Get an answer based on the content of image attachments in the latest email"""
    return call_mcp_tool("answer_from_latest_email_images", {"query": query})

def is_email_query(user_input):
    """Determine if the user is asking about emails or their content"""
    email_keywords = [
        "email", "mail", "inbox", "message", "attachment",
        "image", "picture", "photo", "check email", "read email",
        "latest email", "recent email", "what's in my email"
    ]
    
    lower_input = user_input.lower()
    
    # Check for email keywords
    for keyword in email_keywords:
        if keyword in lower_input:
            return True
    
    # If we have email context and the user appears to be asking a question about it
    # if email_context and any(q in lower_input for q in ["what", "who", "when", "where", "why", "how", "is", "are", "can", "could", "what's"]):
    #     return True
    
    return False

def process_with_gemini(prompt, email_content=None):
    """Process a request with Gemini, optionally including email content context"""
    try:
        # If we have email content to provide as context
        if email_content:
            system_prompt = f"""
            You are an assistant who helps users understand the content of emails, particularly those with image attachments.
            The following text was extracted from an image attachment in an email. 
            Use this information to answer the user's question as accurately as possible:
            
            EMAIL CONTENT:
            {email_content}
            
            Remember to base your answers only on the information provided in the email content.
            If the email content doesn't contain the information needed to answer the question,
            say that you cannot find that information in the email.
            """
            
            # Use the system prompt as context and the user's prompt as the query
            full_prompt = f"{system_prompt}\n\nUser question: {prompt}"
            response = model.generate_content(full_prompt)
        else:
            # Just use the user's prompt directly
            response = model.generate_content(prompt)
        print('response tex ',response.text)
        return response.text
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"


def read_image(file_bytes):
    image = Image.open(io.BytesIO(file_bytes))
    text = pytesseract.image_to_string(image)
    return text

def read_pdf(file_bytes):
    text = ""
    pdf_file = fitz.open("pdf", file_bytes)
    for page in pdf_file:
        text += page.get_text()
    return text


@app.post('/api/v1/chat')
def chatbot_response(user_input: str = Form(...), file: UploadFile = File(None)):
    """Generate a response based on user input"""
    global email_context
    user_input =str(user_input)
    # Check if the user is asking about emails
    if file:
        file_bytes = file.file.read()
        file_type = file.content_type

        if "image" in file_type:
            extracted_text = read_image(file_bytes)
        elif "pdf" in file_type:
            extracted_text = read_pdf(file_bytes)
        else:
            extracted_text = f"File type {file_type} is not supported yet."

        # Respond based on extracted text from file
        return process_with_gemini(f"{user_input}\n\nHere is the content from the uploaded file:\n{extracted_text}")
    if 'send a mail' in user_input:
        prompt='''
Given the following inputs:
to: the recipient's email address
subject: the subject of the email
body: the message content of the email which you have you generate as content writer

Generate a stringified JSON containing only JSON data, with the following structure:
[{
  "email": {
    "to": "<to>",
    "subject": "<subject>"
    "body": "<body>"
  }
}'''
        response=process_with_gemini(f'{prompt} {user_input}')
        send_email(response)
        return 'mail sent successfully'   
    if is_email_query(user_input):
        # If they're asking to check emails
        if any(term in user_input.lower() for term in ["check", "get", "latest", "recent", "new"]):
            result = check_emails()
            # Store the email content for context in future queries
            if not "Error" in result and not "No emails" in result:
                email_context["content"] = result
                email_context["timestamp"] = "now"  # You could use a real timestamp here
                
            return process_with_gemini(f"{user_input}\n\nHere is the content from the mail:\n{result}")
        
        # If they're asking a question about emails we've already retrieved
        elif email_context and "content" in email_context:
            # Get an answer based on the email content
            result = answer_based_on_email_content(user_input)
            
            # Process with Gemini for a more natural response
            return process_with_gemini(f"{user_input}\n\nHere is the content from the mail:\n{result}")
        
        # If they're asking about emails but we haven't checked any yet
        else:
            result = check_emails()
            if not "Error" in result and not "No emails" in result:
                email_context["content"] = result
                email_context["timestamp"] = "now"
                return f"I've checked your recent emails:\n\n{result}\n\nIs there something specific you'd like to know about these emails?"
            return result
    # i want to know read attachments here with python libary
 
    return process_with_gemini(user_input)

if __name__ == "__main__":
    """Main chatbot loop"""
    print("Welcome to the Email Assistant! Type 'exit' to quit.")
    print("I can check your emails and read the content of image attachments.")
    print("Try asking me to 'check my emails' or 'what's in my latest email'")

    uvicorn.run(app, host="localhost", port=8001)