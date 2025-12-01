# 🤖 DocuMind AI - RAG Document Assistant

A production-ready Retrieval-Augmented Generation (RAG) application that allows users to upload PDF documents and ask questions to get AI-powered answers based on the document content.

## 🚀 Live Demo

**[Try it now!](https://cerebro-docs.streamlit.app/)**

## ✨ Features

- 📄 **PDF Document Upload** - Upload and process PDF files into searchable embeddings
- 🤖 **AI-Powered Q&A** - Ask questions and get instant answers from your documents
- 🎨 **Beautiful UI** - Modern gradient design with smooth animations
- ☁️ **Cloud Deployed** - Fully hosted on Render and Streamlit Cloud
- 🗑️ **Database Management** - Clear all documents with one click
- 📚 **Source Attribution** - See which documents your answers came from
- ⚡ **Instant Responses** - Direct synchronous query processing

## 🛠️ Tech Stack

### Backend
- **FastAPI** - High-performance API framework
- **Qdrant Cloud** - Vector database for semantic search
- **OpenAI GPT-4o-mini** - Language model for answer generation
- **Inngest** - Event-driven workflow orchestration
- **PyMuPDF** - PDF processing and text extraction

### Frontend
- **Streamlit** - Interactive web application framework
- **Custom CSS** - Gradient designs and modern styling

### Deployment
- **Render** - Backend API hosting ([documentai-416p.onrender.com](https://documentai-416p.onrender.com))
- **Streamlit Cloud** - Frontend hosting
- **Qdrant Cloud** - Managed vector database

## 🏗️ Architecture

```
┌─────────────────┐
│   Streamlit     │
│   Frontend      │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│   FastAPI       │
│   Backend       │
└────┬────┬───────┘
     │    │
     │    └──────────┐
     ▼               ▼
┌─────────┐   ┌──────────┐
│ Qdrant  │   │  OpenAI  │
│  Cloud  │   │  GPT-4   │
└─────────┘   └──────────┘
```

## 📋 API Endpoints

- `POST /upload` - Upload and process PDF documents
- `POST /query` - Query documents with natural language
- `DELETE /clear` - Clear all documents from database
- `GET /health` - Health check endpoint

## 🎯 Use Cases

- 📚 **Study Assistant** - Upload textbooks and lecture notes
- 📄 **Document Analysis** - Extract insights from research papers
- 💼 **Business Intelligence** - Query company documents and reports
- 🎓 **Educational Tool** - Help students understand complex materials

## 🔧 Local Development

### Prerequisites

- Python 3.12+
- OpenAI API key
- Qdrant Cloud account
- Inngest account



## 📦 Project Structure

```
RAG-Application/
├── main.py              # FastAPI backend
├── streamlit.py         # Streamlit frontend
├── vector_db.py         # Qdrant vector database client
├── data_loader.py       # PDF processing and chunking
├── customtypes.py       # Pydantic models
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables
└── README.md           # This file
```

## 🎨 Features Showcase

### Upload & Process
- Drag-and-drop PDF upload
- Real-time progress tracking
- Chunk count display
- Success animations

### Query Interface
- Natural language questions
- Adjustable context chunks (1-20)
- Auto-scrolling chat history
- Source document display

### Database Management
- Clear chat history
- Clear all documents
- Document count statistics
- Session persistence

## 🔒 Security

- API key authentication
- CORS configuration
- Environment variable management
- Secure file handling

## 📈 Performance

- **Vector Search**: Sub-second similarity search
- **Answer Generation**: ~2-5 seconds per query
- **Document Processing**: Depends on PDF size and complexity
- **Scalability**: Cloud-hosted with auto-scaling

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open source and available under the MIT License.

## 👨‍💻 Author

**GalaxyMatrix**
- GitHub: [@GalaxyMatrix](https://github.com/GalaxyMatrix)
- Project: [RAG-Application](https://github.com/GalaxyMatrix/RAG-Application)

## 🙏 Acknowledgments

- OpenAI for GPT-4o-mini
- Qdrant for vector search
- Streamlit for the amazing framework
- Inngest for workflow orchestration
- Render for hosting

---

**Built with ❤️ using Python, FastAPI, Streamlit, OpenAI, Qdrant & Inngest**

[Live Demo](https://cerebro-docs.streamlit.app/) | [Report Bug](https://github.com/GalaxyMatrix/RAG-Application/issues) | [Request Feature](https://github.com/GalaxyMatrix/RAG-Application/issues)
