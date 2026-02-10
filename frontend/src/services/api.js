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
  return response.data;
};

export const fetchMarkets = async () => {
  const response = await api.get('/markets');
  return response.data;
};

export const fetchMarketAnomalies = async (ticker) => {
  const response = await api.get(`/markets/${ticker}/anomalies`);
  return response.data;
};
