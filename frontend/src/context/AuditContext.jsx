import React, { createContext, useState, useContext } from 'react';
// IMPORT WS_BASE to ensure dynamic switching between Localhost and Railway
import { auditService, WS_BASE } from '../services/api';

const AuditContext = createContext();

export const useAudit = () => useContext(AuditContext);

export const AuditProvider = ({ children }) => {
  // 1. BACKGROUND RUNNER STATE (The Engine)
  const [runner, setRunner] = useState({
    status: 'IDLE', // IDLE, PROCESSING, COMPLETED, ERROR
    company: '',
    progressMsg: '',
    progress: 0,
    result: null,
    error: null
  });

  // 2. VIEWER STATE (The Display)
  const [viewer, setViewer] = useState(null); 

  // --- ACTIONS ---
  const updateProgress = (msg) => {
    setRunner(prev => {
        if(prev.status === 'PROCESSING') return { ...prev, progressMsg: msg };
        return prev;
    });
  };

  // --- REAL-TIME WEBSOCKET AUDIT ---
  const startAudit = (companyName) => {
    setViewer(null);
    
    setRunner({
      status: 'PROCESSING',
      company: companyName,
      progressMsg: 'Initializing Secure Connection...',
      progress: 0,
      result: null,
      error: null
    });

    try {
      // 1. Use Dynamic WebSocket URL from api.js
      const ws = new WebSocket(`${WS_BASE}/audit`);

      ws.onopen = () => {
        console.log("🔌 Connected to Neural Core");
        ws.send(JSON.stringify({ company_name: companyName }));
      };

      ws.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        
        // 🛑 CRITICAL: Ignore Keep-Alive Pings from Backend 🛑
        if (data.status === 'ping') return;
        
        // Update Progress & Message
        setRunner(prev => ({
            ...prev,
            status: 'PROCESSING',
            progress: data.progress !== undefined ? data.progress : prev.progress,
            progressMsg: data.message || prev.progressMsg
        }));

        // Handle Completion
        if (data.status === 'completed') {
            ws.close();
            setRunner(prev => ({ ...prev, progressMsg: 'Finalizing Report...' }));

            // OPTIMIZATION: Our new backend sends the data directly in the WS message!
            if (data.report_data) {
                setRunner(prev => ({
                    ...prev,
                    status: 'COMPLETED',
                    progress: 100,
                    result: data.report_data,
                    progressMsg: 'Audit Complete!'
                }));
                setViewer(data.report_data);
            } else {
                // Fallback: Use dynamic auditService instead of hardcoded Railway fetch
                try {
                    const resData = await auditService.fetchReportDetails([companyName]);

                    if (resData.status === 'success' && resData.data.length > 0) {
                        const finalReport = resData.data[0];
                        setRunner(prev => ({
                            ...prev,
                            status: 'COMPLETED',
                            progress: 100,
                            result: finalReport,
                            progressMsg: 'Audit Complete!'
                        }));
                        setViewer(finalReport);
                    } else {
                        throw new Error("Report generated but could not be retrieved.");
                    }
                } catch (err) {
                    console.error("Fetch Error:", err);
                    setRunner(prev => ({
                        ...prev,
                        status: 'ERROR',
                        error: "Audit finished, but report fetch failed.",
                        progressMsg: 'Error'
                    }));
                }
            }
        }

        // Handle Backend Errors
        if (data.status === 'error') {
            ws.close();
            setRunner(prev => ({
                ...prev,
                status: 'ERROR',
                error: data.message || "Unknown Backend Error",
                progressMsg: 'Failed'
            }));
        }
      };

      ws.onerror = (err) => {
        console.error("WebSocket Error:", err);
        setRunner(prev => ({
            ...prev,
            status: 'ERROR',
            error: "Connection to Audit Core failed. Is the backend running?",
            progressMsg: 'Connection Failed'
        }));
      };

    } catch (err) {
      setRunner(prev => ({
        ...prev,
        status: 'ERROR',
        error: err.message || "Client Error",
        progressMsg: 'Failed'
      }));
    }
  };

  const viewHistoryReport = (data) => {
    setViewer(data); 
  };

  const clearViewer = () => {
    setViewer(null);
  };

  const resetAll = () => {
    setViewer(null);
    setRunner({
      status: 'IDLE',
      company: '',
      progressMsg: '',
      progress: 0,
      result: null,
      error: null
    });
  };

  return (
    <AuditContext.Provider value={{ 
      runner, 
      setRunner, 
      viewer, 
      setViewer,
      startAudit, 
      viewHistoryReport, 
      clearViewer,
      resetAll 
    }}>
      {children}
    </AuditContext.Provider>
  );
};