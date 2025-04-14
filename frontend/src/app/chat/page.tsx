"use client";

import { useState, useRef, useEffect } from "react";
import { Bot, FileUp, Send, Trash2, User, File } from "lucide-react";
import axios from 'axios';
import './page.css';

interface Message {
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
  fileName?: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop =
        messagesContainerRef.current.scrollHeight -
        messagesContainerRef.current.clientHeight;
    }
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() && files.length === 0) return;
    const newMessage: Message = {
      role: "user",
      content: input,
      attachments: files?.map(file => URL.createObjectURL(file)),
      fileName: files[0]?.name,
    };

    setMessages(prev => [...prev, newMessage]);
    setInput("");
    // setFiles([]);
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('user_input', input);
      files.forEach((file) => {
        formData.append('file', file);
      });

      const response = await axios.post('http://localhost:8001/api/v1/chat', formData, {
        headers: {
         'Content-Type': 'multipart/form-data',
       },
     });
     const botResponse: Message = {
       role: "assistant",
       content: response.data
     }

     setMessages(prev => [...prev, botResponse]);
     setIsLoading(false)
    } catch (error: any) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        role: "assistant",
        content: 'Error processing your request.',
      };
      setMessages(prev => [...prev, errorMessage]);
      setIsLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <main>
      <div className="card">
        <div className="messages-container" ref={messagesContainerRef}>
          <div className="messages">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`message ${message.role === "user" ? "user" : ""}`}
              >
                <div className="message-content">
                  <div className="avatar">
                    {message.role === "user" ? (
                      <User className="w-5 h-5" />
                    ) : (
                      <Bot className="w-5 h-5" />
                    )}
                  </div>
                  <div className="message-bubble">
                    <p>{message.content}</p>
                    {message.attachments && message.attachments.length > 0 && (
                      <div className="attachments">
                        <div className="attachmen-file-css">
                          <File />
                          <p>{message.fileName}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="message">
                <div className="typing-indicator">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="input-container">
          {files.length > 0 && (
            <div className="file-list">
              {files.map((file, index) => (
                <div key={index} className="file-chip">
                  <span className="file-name">{file.name}</span>
                  <button
                    className="remove-file"
                    onClick={() => removeFile(index)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
          <form onSubmit={handleSend} className="input-form">
            <input
              type="file"
              id="file-upload"
              className="file-upload"
              onChange={handleFileChange}
              multiple
            />
            <button
              type="button"
              className="button outline"
              onClick={() => document.getElementById("file-upload")?.click()}
            >
              <FileUp className="w-5 h-5" />
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..."
              className="input"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="button"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}