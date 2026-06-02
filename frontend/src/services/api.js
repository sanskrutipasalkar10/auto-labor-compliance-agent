import axios from 'axios';

// Vite pulls environment variables using import.meta.env
// The || (OR) provides a safe fallback to localhost just in case the .env is missing
export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
export const WS_BASE = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/ws';

export const auditService = {
  initiateAudit: async (companyName) => {
    const response = await axios.post(`${API_BASE}/audit`, { company_name: companyName });
    return response.data;
  },

  fetchReports: async () => {
    const response = await axios.get(`${API_BASE}/reports`);
    return response.data;
  },

  fetchReportDetails: async (companyNames) => {
    const response = await axios.post(`${API_BASE}/compare`, { companies: companyNames });
    return response.data;
  },

  downloadReport: async (companyName) => {
    const response = await axios.get(`${API_BASE}/download_report`, {
      params: { company: companyName },
      responseType: 'blob',
    });
    return response.data;
  }
};