# UniMat AI

## How to Start the Application

### 1. Start the Backend (FastAPI)
Open a terminal and navigate to the `backend` folder, activate the virtual environment, and run the server.

```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the Frontend (Next.js)
Open a *new* terminal and navigate to the `frontend` folder, then run the development server.

```bash
cd frontend
npm run dev
```

Once both servers are running, open [http://localhost:3000](http://localhost:3000) in your web browser.
