import React, { useState, useRef } from 'react';
import './App.css';

function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { text: "Hi! Paste any YouTube URL and I'll summarize it for you. 📺", sender: 'bot' }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const isValidYouTubeUrl = (url) => {
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/;
    return youtubeRegex.test(url);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    
    // Validate YouTube URL before sending
    if (!isValidYouTubeUrl(input.trim())) {
      setMessages(prev => [...prev, 
        { text: input.trim(), sender: 'user' },
        { text: "Please provide a valid YouTube URL (youtube.com or youtu.be)", sender: 'bot' }
      ]);
      setInput('');
      return;
    }
    
    setIsLoading(true);
    const userMessage = { text: input.trim(), sender: 'user' };
    setMessages(prev => [...prev, userMessage]);
    
    try {
      console.log("Sending request to backend...");
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout
      
      const response = await fetch('http://localhost:8000/summarize', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: input.trim() }),
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      console.log("Response status:", response.status);
      
      if (!response.ok) {
        let errorMessage = "Failed to get summary";
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          // If can't parse JSON, use status text
          errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
      }
      
      const data = await response.json();
      console.log("Response data:", data);
      
      if (!data.summary) {
        throw new Error("No summary received from server");
      }
      
      setMessages(prev => [...prev, { 
        text: data.summary, 
        sender: 'bot' 
      }]);
      
    } catch (error) {
      console.error('Error:', error);
      
      let errorMessage = "An unknown error occurred";
      
      if (error.name === 'AbortError') {
        errorMessage = "Request timed out. The video might be too long or the server is busy. Please try again.";
      } else if (error.message.includes('Failed to fetch')) {
        errorMessage = "Couldn't connect to server. Make sure the backend is running on http://localhost:8000";
      } else if (error.message.includes('NetworkError')) {
        errorMessage = "Network error. Please check your connection and try again.";
      } else {
        errorMessage = error.message;
      }
      
      setMessages(prev => [...prev, { 
        text: `❌ ${errorMessage}`,
        sender: 'bot' 
      }]);
    } finally {
      setIsLoading(false);
      setInput('');
    }
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  React.useEffect(scrollToBottom, [messages]);

  return (
    <div className="app">
      <header className="header">
        <h1>🎬 SummifyAI</h1>
        <p>Get instant AI summaries of YouTube videos</p>
      </header>
      
      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.sender}`}>
              <div className="message-content">
                {msg.text}
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="message bot">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span className="loading-text">Analyzing video and generating summary...</span>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
        
        <form onSubmit={handleSubmit} className="input-area">
          <div className="input-wrapper">
            <input
              type="text"
              value={input}
              onChange={handleInputChange}
              onKeyPress={handleKeyPress}
              placeholder="Paste YouTube URL here (youtube.com or youtu.be)..."
              disabled={isLoading}
              className="url-input"
            />
            <button 
              type="submit" 
              disabled={isLoading || !input.trim()}
              className={`submit-btn ${isLoading ? 'loading' : ''}`}
            >
              {isLoading ? '⏳ Summarizing...' : '🚀 Summarize'}
            </button>
          </div>
          
          <div className="input-hint">
            💡 Tip: Works best with videos that have captions/subtitles
          </div>
        </form>
      </div>
      <footer className="footer">
      <p>© {new Date().getFullYear()} Hasan Himzawi. All Rights Reserved.</p>
    </footer>
  </div>
);
}

export default App;