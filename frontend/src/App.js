import React, { useState, useRef } from 'react';
import './App.css';

function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { text: "Hi! Paste any YouTube URL and I'll summarize it for you. 📺", sender: 'bot' }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Configuration for different environments
  const API_BASE_URL = process.env.NODE_ENV === 'production' 
    ? 'https://summify-backend-mue3.onrender.com' 
    : 'http://localhost:8000';

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
      console.log("API URL:", `${API_BASE_URL}/summarize`);
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout for proxy requests
      
      const response = await fetch(`${API_BASE_URL}/summarize`, {
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
          errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
      }
      
      const data = await response.json();
      console.log("Response data:", data);
      
      if (!data.summary) {
        throw new Error("No summary received from server");
      }
      
      // Add proxy status info if available
      let summaryText = data.summary;
      if (data.proxies_status) {
        console.log("Proxy status:", data.proxies_status);
      }
      
      setMessages(prev => [...prev, { 
        text: summaryText, 
        sender: 'bot' 
      }]);
      
    } catch (error) {
      console.error('Error:', error);
      
      let errorMessage = "An unknown error occurred";
      
      if (error.name === 'AbortError') {
        errorMessage = "Request timed out. The video might be too long or the server is busy. Please try again.";
      } else if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
        errorMessage = `Couldn't connect to server. Please check if the backend is running at ${API_BASE_URL}`;
      } else if (error.message.includes('captions') || error.message.includes('transcript')) {
        errorMessage = "This video doesn't have English captions/subtitles available. Please try a different video.";
      } else if (error.message.includes('Invalid YouTube URL')) {
        errorMessage = "The YouTube URL format is not recognized. Please check the URL and try again.";
      } else if (error.message.includes('API key')) {
        errorMessage = "Server configuration error. Please contact support.";
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

  const handleClearChat = () => {
    setMessages([
      { text: "Hi! Paste any YouTube URL and I'll summarize it for you. 📺", sender: 'bot' }
    ]);
  };

  const formatMessage = (text) => {
    // Simple formatting for better readability
    return text.split('\n').map((line, index) => (
      <React.Fragment key={index}>
        {line}
        {index < text.split('\n').length - 1 && <br />}
      </React.Fragment>
    ));
  };

  React.useEffect(scrollToBottom, [messages]);

  return (
    <div className="app">
      <header className="header">
        <h1>🎬 SummifyAI</h1>
        <p>Get instant AI summaries of YouTube videos</p>
        <div className="header-actions">
          <button onClick={handleClearChat} className="clear-btn">
            🗑️ Clear Chat
          </button>
        </div>
      </header>
      
      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.sender}`}>
              <div className="message-content">
                {formatMessage(msg.text)}
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
                <span className="loading-text">
                  Analyzing video and generating summary...
                  <br />
                  <small>This may take up to 2 minutes for longer videos</small>
                </span>
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
            <br />
          </div>
        </form>
      </div>
      
      <footer className="footer">
        <p>© {new Date().getFullYear()} Hasan Himzawi. All Rights Reserved.</p>
        <div className="footer-info">
          <span>Environment: {process.env.NODE_ENV || 'development'}</span>
          <span>API: {API_BASE_URL}</span>
        </div>
      </footer>
    </div>
  );
}

export default App;