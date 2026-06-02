# 🤖 AutoLabor Compliance Agent

**AutoLabor Compliance Agent** is an enterprise-grade AI auditor designed to automate labor compliance monitoring for large conglomerates. It leverages Gemini 2.0 Flash's 1M+ context window to perform forensic audits of Annual Reports, BRSR (Business Responsibility and Sustainability Reports), and financial statements in real-time.

---

## 🏗️ System Architecture

The system is built on a modular "Orchestration" protocol that bridges deep web search, forensic document analysis, and real-time visualization.

```mermaid
graph TD
    User((User)) -->|Input: Company Name| Frontend[React Dashboard]
    Frontend -->|WebSocket| Backend[FastAPI Server]
    Backend --> Orchestrator[Compliance Orchestrator]
    
    subgraph Data Hunting
        Orchestrator --> Hunter[Web Hunter]
        Hunter -->|Nuclear Query| Google[Search Engine]
        Google -->|PDFs| Gatekeeper[Semantic Gatekeeper]
    end
    
    subgraph Forensic Analysis
        Gatekeeper --> Parser[PDF Parser]
        Parser --> Engine[Audit Engine: Gemini 2.0 Flash]
        Engine -->|Cross-Validation| Financials[External Financial API]
    end
    
    subgraph Reporting
        Engine --> PDFGen[ReportLab PDF Engine]
        Engine --> JSON[Structured JSON]
        PDFGen --> User
    end
    
    Orchestrator -->|Real-time Updates| Frontend
```

---

## 🛠️ Core Technology Stack

### Backend (The "SANE-AI" Core)
- **FastAPI:** High-performance async API framework.
- **Gemini 2.0 Flash:** Used for "Monolithic Protocol" analysis, allowing the system to ingest thousands of pages of text in a single pass for cross-document validation.
- **WebHunter & Nuclear Search:** Customized scraping logic that optimizes search queries to bypass "subsidiary drift" (e.g., distinguishing between Mahindra & Mahindra parent vs. Mahindra Finance).
- **ReportLab:** A low-level PDF generation engine used to build professional, corporate-ready compliance reports with dynamic tables and risk badges.
- **WebSocket Protocol:** Ensures sub-second feedback loops between the AI pipeline and the user interface.

### Frontend (The Dashboard)
- **React + Vite:** Modern, fast, and responsive UI foundations.
- **Glassmorphism Design:** A premium, state-of-the-art interface utilizing HSL-tailored colors and smooth backdrop blurs.
- **Context API:** Manages global state for real-time audit progress and multi-company comparisons.
- **Framer Motion:** Implements subtle micro-animations for an interactive user experience.

---

## 🔍 Key Project Components

### 1. The Semantic Gatekeeper
A critical component in the `ComplianceOrchestrator` that uses "Nuclear Disambiguation" to ensure that the documents gathered belong *strictly* to the parent OEM. It filters out joint ventures, finance subsidiaries, and other "poison entities" that often contaminate corporate compliance datasets.

### 2. Forensic Cross-Validation
Unlike standard RAG systems, AutoLabor patches missing data in PDF reports with real-time external financial APIs (e.g., fetching actual EBITDA or Revenue if not clearly stated in the text).

### 3. Sector Analysis Engine
Aggregates compliance data across companies to provide an "Overall Risk Score" (Low, Moderate, High) and strategic recommendations for supply chain liability management.

---

## 📦 Detailed Setup & Deployment

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **Google Cloud API Key** (for Gemini AI)

### 2. Backend Installation
```bash
cd auto-labor-compliance-agent
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

### 3. Frontend Installation
```bash
cd frontend
npm install
npm run dev
```

### 4. Docker Deployment
The project includes a multi-stage `docker-compose.yml` that handles both the React frontend and FastAPI backend in isolated containers.
```bash
docker-compose up --build
```

---

## 📑 API Documentation

- **`WS /ws/audit`**: Primary real-time endpoint for triggering new audits.
- **`GET /api/reports`**: List all consolidated compliance reports.
- **`GET /api/download_report?company={name}`**: Download the professional PDF audit.
- **`POST /api/compare`**: Submit multiple company names for a side-by-side gap analysis.

---

## 🛡️ License & Contact
Developed as part of the **AutoLabor Compliance** initiative. 
For support or collaboration, please visit the [GitHub Repository](https://github.com/sanskrutipasalkar10/auto-labor-compliance-agent).


<img width="1000" height="610" alt="image" src="https://github.com/user-attachments/assets/14dafacf-aa6c-46eb-a30d-a141bd4815da" />

<img width="906" height="642" alt="image" src="https://github.com/user-attachments/assets/60204ffe-eb9f-4b89-a188-d00de2f65848" />

<img width="968" height="519" alt="image" src="https://github.com/user-attachments/assets/00f6fa78-d904-4668-882e-2a2b844a4c3b" />

<img width="908" height="495" alt="image" src="https://github.com/user-attachments/assets/c568ae7a-cbf7-4745-8b83-007ef852754c" />


