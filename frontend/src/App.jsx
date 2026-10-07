import React, { useState, useRef, useEffect } from 'react';
import './index.css';
import { v4 as uuidv4 } from 'uuid';

function App() {
  const [messages, setMessages] = useState([
    { id: 1, type: 'agent', content: "Hello! I'm your SQL assistant. How can I help you query the database today?" }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // State for the SQL Panel
  const [activeSQL, setActiveSQL] = useState('');
  const [activeExplanation, setActiveExplanation] = useState('');
  const [activeResults, setActiveResults] = useState(null);
  
  // A thread ID to maintain conversation context
  const [threadId] = useState(uuidv4());
  
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleCopy = () => {
    navigator.clipboard.writeText(activeSQL);
    // Could add a toast notification here
  };

  const parseResults = (resultsStr) => {
    if (!resultsStr) return null;
    try {
      // The backend returns a string representation of a list of dicts.
      // E.g. "[{'Name': 'Alice', 'Salary': 95000}, ...]"
      // We need to parse this properly. If it's valid JSON from backend:
      return JSON.parse(resultsStr.replace(/'/g, '"'));
    } catch (e) {
      console.error("Failed to parse results:", e);
      return null;
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { id: Date.now(), type: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, thread_id: threadId })
      });

      const data = await response.json();
      
      if (data.error) {
        setMessages(prev => [...prev, { id: Date.now(), type: 'agent', error: true, content: data.error }]);
      } else {
        setMessages(prev => [...prev, { 
          id: Date.now(), 
          type: 'agent', 
          content: "I've generated the query and results for you. Check the panel on the right." 
        }]);
        setActiveSQL(data.sql || '');
        setActiveExplanation(data.explanation || '');
        setActiveResults(parseResults(data.results));
      }
    } catch (error) {
      setMessages(prev => [...prev, { 
        id: Date.now(), 
        type: 'agent', 
        error: true, 
        content: "Sorry, I encountered an error connecting to the server." 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Chat Section */}
      <div className="chat-section glass-panel">
        <div className="header">
          <h1>SQL Assistant</h1>
        </div>
        
        <div className="message-list">
          {messages.map(msg => (
            <div key={msg.id} className={`message ${msg.type} ${msg.error ? 'message-error' : ''}`}>
              {msg.content}
            </div>
          ))}
          {isLoading && (
            <div className="message agent typing-indicator">
              <div className="dot"></div>
              <div className="dot"></div>
              <div className="dot"></div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="input-area" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about employees, customers, or departments..."
            disabled={isLoading}
          />
          <button type="submit" className="submit-btn" disabled={isLoading || !input.trim()}>
            Send
          </button>
        </form>
      </div>

      {/* SQL Output & Explanation Panel */}
      <div className="sql-section glass-panel">
        <div className="header">
          <h1>Query Details</h1>
        </div>
        <div className="sql-panel-content">
          {!activeSQL && !activeExplanation ? (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: '40px' }}>
              Your generated SQL and results will appear here.
            </div>
          ) : (
            <>
              <div>
                <div className="section-title">Generated SQL</div>
                <div className="sql-block-wrapper">
                  <pre className="sql-block">
                    <code>{activeSQL}</code>
                  </pre>
                  <button className="copy-btn" onClick={handleCopy}>Copy</button>
                </div>
              </div>
              
              {activeExplanation && (
                <div>
                  <div className="section-title">Explanation</div>
                  <div className="explanation-text">{activeExplanation}</div>
                </div>
              )}

              {activeResults && Array.isArray(activeResults) && activeResults.length > 0 && (
                <div>
                  <div className="section-title">Results</div>
                  <div className="results-table-wrapper">
                    <table>
                      <thead>
                        <tr>
                          {Object.keys(activeResults[0]).map(key => (
                            <th key={key}>{key}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {activeResults.map((row, i) => (
                          <tr key={i}>
                            {Object.values(row).map((val, j) => (
                              <td key={j}>{val !== null ? String(val) : 'NULL'}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
