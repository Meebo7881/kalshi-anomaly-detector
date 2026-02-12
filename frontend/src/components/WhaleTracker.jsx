import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function WhaleTracker() {
  const [whales, setWhales] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchWhales();
  }, []);
  
  const fetchWhales = async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const res = await axios.get(`${apiUrl}/stats/whales`);
      setWhales(res.data.top_whales || []);
    } catch (error) {
      console.error('Error fetching whales:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) return <div className="text-center p-4">Loading whales...</div>;
  
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-4">🐋 Whale Tracker</h2>
      <p className="text-sm text-gray-600 mb-4">
        Large traders with $50k+ total volume
      </p>
      
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Trader ID</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Total Volume</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Avg Trade</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Trades</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">First Seen</th>
            </tr>
          </thead>
          <tbody>
            {whales.map((whale, idx) => (
              <tr key={idx} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-mono">{whale.trader_id.slice(0, 12)}...</td>
                <td className="px-4 py-2 text-sm font-semibold">${whale.total_volume_usd.toFixed(0)}</td>
                <td className="px-4 py-2 text-sm">${whale.avg_trade_size_usd.toFixed(0)}</td>
                <td className="px-4 py-2 text-sm">{whale.total_trades}</td>
                <td className="px-4 py-2 text-sm text-gray-500">
                  {whale.first_seen ? new Date(whale.first_seen).toLocaleDateString() : 'N/A'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
