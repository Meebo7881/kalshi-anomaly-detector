import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchAnomalies = async (severity = null, days = 7) => {
  const params = { days };
  if (severity) params.severity = severity;
  
  const response = await api.get('/anomalies', { params });
  // FIX: Return the items array, not the whole response object
  return response.data.items || [];
};

export const fetchMarkets = async () => {
  const response = await api.get('/markets');
  // FIX: Return the items array, not the whole response object
  return response.data.items || [];
};

export const fetchMarketAnomalies = async (ticker) => {
  const response = await api.get(`/markets/${ticker}/anomalies`);
  // FIX: Return the items array, not the whole response object
  return response.data.items || [];
};

// NEW: Fetch whale trades from /stats/whales endpoint
export const fetchWhales = async ({ hours = 168, min_usd = 500, limit = 50 } = {}) => {
  const params = { 
    hours, 
    min_usd,  // Note: backend expects 'min_usd' snake_case
    limit 
  };
  const response = await api.get('/stats/whales', { params });
  return response.data.items || [];
};

export default api;
