# 2nd Brain

AI-powered personal knowledge management system. Store, organize, and query your documents with AI assistance.

## Features

- **AI-Powered Chat**: Ask questions about your documents using RAG (Retrieval Augmented Generation)
- **Document Management**: Import and organize documents from multiple sources
- **Knowledge Gaps**: Automatically detect and track knowledge gaps in your content
- **Integrations**: Connect Google Drive, Slack, Notion, Gmail, and more
- **Vector Search**: Fast semantic search across all your documents

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Async database ORM with PostgreSQL
- **Pinecone** - Vector database for semantic search
- **OpenAI / Azure OpenAI** - AI completions and embeddings

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **TailwindCSS** - Utility-first CSS
- **React Query** - Data fetching and caching
- **Zustand** - Lightweight state management

## Key Improvements Over v1

This is a complete rebuild with significant performance improvements:

1. **Fixed N+1 Query Issues**: Bulk operations use single queries instead of one per item
2. **Proper Database Indexes**: Critical indexes for 5-10x faster queries
3. **Connection Pooling**: Configured pool to prevent connection exhaustion
4. **No Frontend Latency**: Proper state management, no polling spam
5. **Sync Progress**: Forward-only progress updates (no jumping back)
6. **Exponential Backoff**: Polling intervals increase to reduce server load

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis (optional, for caching)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp ../.env.example .env
# Edit .env with your credentials

# Run migrations
alembic upgrade head

# Start server
uvicorn main:app --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Visit `http://localhost:3000` to access the application.

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/secondbrain
SECRET_KEY=your-secret-key
OPENAI_API_KEY=sk-your-key
PINECONE_API_KEY=your-pinecone-key

# Optional integrations
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
```

## API Documentation

Once running, visit `http://localhost:8000/docs` for the interactive API documentation.

## Project Structure

```
2nd-Brains-/
├── backend/
│   ├── api/              # API routes
│   ├── core/             # Configuration
│   ├── database/         # Models and connection
│   ├── services/         # Business logic
│   ├── connectors/       # Integration connectors
│   └── main.py           # FastAPI app
├── frontend/
│   ├── app/              # Next.js pages
│   ├── components/       # React components
│   ├── lib/              # Utilities, hooks, API
│   └── public/           # Static assets
└── .env.example          # Environment template
```

## License

MIT
