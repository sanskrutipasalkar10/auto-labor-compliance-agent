import sys
import os

# --- CRITICAL PATH SETUP ---
# 1. Get the absolute path of the folder containing this script (auto-labor-compliance-agent)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Add it to the start of sys.path
# This ensures Python sees 'src' as a package inside this folder.
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import json
import glob
import uvicorn
import asyncio
import threading
import queue
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse 
from pydantic import BaseModel
from typing import List

# --- IMPORTS (MATCHING YOUR FOLDER STRUCTURE) ---
try:
    # Your pipeline.py is inside src/orchestration/
    from src.orchestration.pipeline import ComplianceOrchestrator
    # Your web_hunter.py is inside src/ingestion/
    from src.ingestion.web_hunter import WebHunter
    print("✅ Successfully imported ComplianceOrchestrator and WebHunter")
except ModuleNotFoundError as e:
    print(f"\n❌ CRITICAL IMPORT ERROR: {e}")
    print(f"   Looking in: {BASE_DIR}")
    print("   Please verify that 'src/orchestration/pipeline.py' exists.\n")
    raise e

app = FastAPI(title="AutoLabor Compliance API")

# Allow Frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GLOBAL QUEUE FOR REAL-TIME UPDATES ---
msg_queue = queue.Queue()

def pipeline_callback(data):
    """Bridge function to put pipeline updates into the queue"""
    msg_queue.put(data)

class AuditRequest(BaseModel):
    company_name: str

class CompareRequest(BaseModel):
    companies: List[str]

# Define paths relative to BASE_DIR to avoid "file not found" errors
DATA_DIR = os.path.join(BASE_DIR, "data", "03_structured")
RAW_DIR = os.path.join(BASE_DIR, "data", "01_raw")

@app.get("/")
def health_check():
    return {"status": "System Online", "module": "SANE-AI Auditor"}

# --- WEBSOCKET ENDPOINT (The Real-Time Bridge) ---
@app.websocket("/ws/audit")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    audit_thread = None
    
    try:
        # 1. Wait for frontend to send company name
        data = await websocket.receive_json()
        company_name = data.get("company_name")
        print(f"🔌 WebSocket received audit request for: {company_name}")
        
        # 2. Define the job wrapper
        def run_job():
            try:
                # Initialize Orchestrator
                orchestrator = ComplianceOrchestrator()
                
                # Ensure directories exist
                os.makedirs(RAW_DIR, exist_ok=True)
                os.makedirs(DATA_DIR, exist_ok=True)
                
                # Run the pipeline with the callback
                orchestrator.run_pipeline(
                    target_company=company_name, 
                    specific_files=None,
                    progress_callback=pipeline_callback 
                )
                
                # --- LOAD DATA IMMEDIATELY ---
                # This fixes the "Audit Failed" race condition by sending data with the completion signal
                safe_name = company_name.replace(" ", "_")
                json_path = os.path.join(DATA_DIR, f"{safe_name}_Consolidated_Report.json")
                report_payload = None
                
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        report_payload = json.load(f)

                # Signal completion WITH DATA
                msg_queue.put({
                    "status": "completed", 
                    "progress": 100, 
                    "message": "Audit Finalized.",
                    "report_data": report_payload 
                })
                
            except Exception as e:
                print(f"❌ Thread Error: {e}")
                msg_queue.put({"status": "error", "message": str(e)})

        # 3. Start the thread
        audit_thread = threading.Thread(target=run_job, daemon=True)
        audit_thread.start()

        # 4. Listen to Queue and Broadcast to Frontend
        while True:
            try:
                # Use get_nowait to keep the loop responsive
                while not msg_queue.empty():
                    msg = msg_queue.get_nowait()
                    await websocket.send_json(msg)
                    
                    if msg.get("status") in ["completed", "error"]:
                        return # Exit cleanly
                
                # Yield control to allow async tasks to run
                await asyncio.sleep(0.1)
                
            except queue.Empty:
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"❌ Queue Error: {e}")
                break
            
    except WebSocketDisconnect:
        print("⚠️ WebSocket Disconnected by client")
    except Exception as e:
        print(f"❌ WebSocket Critical Error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

# --- REST Endpoints ---

@app.get("/api/download_report")
async def download_report(company: str):
    try:
        clean_company = company.strip().rstrip('.')
        safe_name = clean_company.replace(" ", "_")
        filename = f"{safe_name}_Consolidated_Report.pdf"
        file_path = os.path.join(DATA_DIR, filename)

        # Fuzzy Fallback
        if not os.path.exists(file_path):
            base_pattern = safe_name.split("_")[0] + "*"
            search_pattern = os.path.join(DATA_DIR, f"*{base_pattern}*_Consolidated_Report.pdf")
            candidates = glob.glob(search_pattern)
            if candidates:
                file_path = candidates[0]
                filename = os.path.basename(file_path)
            else:
                raise HTTPException(status_code=404, detail="Report not found")

        return FileResponse(path=file_path, filename=filename, media_type='application/pdf')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reports")
def list_reports():
    if not os.path.exists(DATA_DIR):
        return {"reports": []}
    files = glob.glob(os.path.join(DATA_DIR, "*_Consolidated_Report.json"))
    reports = []
    for f in files:
        filename = os.path.basename(f)
        clean_name = filename.replace("_Consolidated_Report.json", "").replace("_", " ")
        reports.append({"filename": filename, "name": clean_name})
    return {"status": "success", "reports": reports}

@app.post("/api/compare")
def compare_reports(request: CompareRequest):
    comparison_data = []
    for company in request.companies:
        safe_name = company.replace(" ", "_")
        json_path = os.path.join(DATA_DIR, f"{safe_name}_Consolidated_Report.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                comparison_data.append(json.load(f))
    return {"status": "success", "data": comparison_data}

@app.post("/api/audit")
def run_audit(request: AuditRequest):
    # REST Fallback endpoint (if WebSocket fails)
    company = request.company_name
    print(f"🚀 REST API received request for: {company}")
    try:
        orchestrator = ComplianceOrchestrator()
        os.makedirs(RAW_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        
        orchestrator.run_pipeline(target_company=company, specific_files=None)
        
        safe_name = company.replace(" ", "_")
        json_path = os.path.join(DATA_DIR, f"{safe_name}_Consolidated_Report.json")
        
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                return {"status": "success", "data": json.load(f)}
        return {"status": "error", "message": "Report generation failed"}
    except Exception as e:
        print(f"❌ API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import socket

    def get_free_port(start_port=8000):
        port = start_port
        while port < 65535:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('0.0.0.0', port))
                    return port
                except OSError:
                    port += 1
        return start_port

    def update_frontend_env(port):
        env_path = os.path.join(os.path.dirname(BASE_DIR), "frontend", ".env")
        if os.path.exists(env_path):
            with open(env_path, "w") as f:
                f.write("# .env (Frontend Folder)\n")
                f.write(f"VITE_API_BASE_URL=http://localhost:{port}/api\n")
                f.write(f"VITE_WS_BASE_URL=ws://localhost:{port}/ws\n")
            print(f"✅ Updated frontend .env to use port {port}")
        else:
            print(f"⚠️ Frontend .env not found at {env_path}")

    port = get_free_port(8000)
    update_frontend_env(port)
    print(f"🚀 Starting backend server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)