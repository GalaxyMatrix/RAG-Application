import React, { useState } from 'react';
import './App.css';
import axios from 'axios';

function App() {
  const [pdfPath, setPdfPath] = useState('');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');

  const handleIngestPdf = async () => {
    setLoading(true);
    setUploadStatus('');
    try {
      const response = await axios.post('http://localhost:8000/ingest', {
        pdf_path: pdfPath
      });
      setUploadStatus('PDF ingested successfully!');
    } catch (error) {
      setUploadStatus('Error ingesting PDF: ' + error.message);
    }
    setLoading(false);
  };

  const handleQuery = async () => {
    setLoading(true);
    setAnswer('');
    setSources([]);
    try {
      const response = await axios.post('http://localhost:8000/query', {
        question: question,
        top_k: 5
      });
      setAnswer(response.data.answer);
      setSources(response.data.sources || []);
    } catch (error) {
      setAnswer('Error: ' + error.message);
    }
    setLoading(false);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>📚 RAG AI Study Q&A</h1>
      </header>

      <div className="container">
        {/* PDF Upload Section */}
        <div className="section upload-section">
          <h2>📄 Upload PDF</h2>
          <div className="input-group">
            <input
              type="text"
              placeholder="Enter PDF path (e.g., D:/Production AI Tutorial.pdf)"
              value={pdfPath}
              onChange={(e) => setPdfPath(e.target.value)}
              className="input-field"
            />
            <button 
              onClick={handleIngestPdf} 
              disabled={loading || !pdfPath}
              className="btn btn-primary"
            >
              {loading ? 'Processing...' : 'Ingest PDF'}
            </button>
          </div>
          {uploadStatus && (
            <div className={`status ${uploadStatus.includes('Error') ? 'error' : 'success'}`}>
              {uploadStatus}
            </div>
          )}
        </div>

        {/* Query Section */}
        <div className="section query-section">
          <h2>❓ Ask a Question</h2>
          <div className="input-group">
            <textarea
              placeholder="Enter your question about the PDF..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="textarea-field"
              rows="3"
            />
            <button 
              onClick={handleQuery} 
              disabled={loading || !question}
              className="btn btn-secondary"
            >
              {loading ? 'Searching...' : 'Ask Question'}
            </button>
          </div>
        </div>

        {/* Answer Section */}
        {answer && (
          <div className="section answer-section">
            <h2>💡 Answer</h2>
            <div className="answer-box">
              {answer}
            </div>
            {sources.length > 0 && (
              <div className="sources">
                <h3>📖 Sources:</h3>
                <ul>
                  {sources.map((source, idx) => (
                    <li key={idx}>{source}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;