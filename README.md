# AutoLabor Compliance Agent

AutoLabor Compliance Agent is an AI-powered tool designed to automate labor compliance auditing for companies. It uses a sophisticated orchestration pipeline to gather, analyze, and report on compliance data in real-time.

## 🚀 Features

- **Real-time Auditing:** Professional compliance audits with real-time updates via WebSockets.
- **AI Orchestration:** A robust pipeline that manages data ingestion, structuring, and analysis.
- **Web Hunter:** Automated web scraping and data gathering for target companies.
- **Comprehensive Reporting:** Generates structured JSON and professional PDF reports.
- **Interactive Dashboard:** Modern React-based frontend for visualizing compliance data and sector analysis.
- **Comparison Engine:** Compare compliance reports across multiple companies.

## 🛠️ Tech Stack

### Backend
- **Framework:** FastAPI
- **Real-time:** WebSockets
- **Concurrency:** Threading and Asyncio
- **Data Processing:** Pydantic, JSON processing
- **Server:** Uvicorn

### Frontend
- **Framework:** React + Vite
- **Styling:** CSS (Modern, Glassmorphism design)
- **State Management:** React Context API
- **Visuals:** Framer Motion / Custom CSS effects

### Infrastructure
- **Containerization:** Docker & Docker Compose

## 📦 Setup & Installation

### Prerequisites
- Python 3.9+
- Node.js & npm
- Docker (optional)

### Backend Setup
1. Navigate to the `auto-labor-compliance-agent` directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the backend server:
   ```bash
   python main.py
   ```

### Frontend Setup
1. Navigate to the `frontend` directory.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```

### Docker Setup
To run the entire stack using Docker:
```bash
docker-compose up --build
```

## 🛠️ Usage

1. Open the frontend application in your browser (usually `http://localhost:5173`).
2. Enter the company name you wish to audit.
3. Monitor the real-time progress of the compliance check.
4. View and download the generated compliance report.

## 📄 License
[Specify License, e.g., MIT]

---
Developed by [Your Name/Organization]
