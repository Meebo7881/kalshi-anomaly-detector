import React from 'react';

export default function AnomalyCard({ anomaly }) {
  const details = anomaly.details || {};
  
  // Severity badge color
  const severityColor = {
    critical: 'bg-red-600',
    high: 'bg-orange-500',
    medium: 'bg-yellow-500',
    low: 'bg-gray-400'
  }[anomaly.severity] || 'bg-gray-400';
  
  return (
    <div className="bg-white rounded-lg shadow p-6 mb-4 border-l-4 border-blue-500">
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <h3 className="text-lg font-semibold text-gray-900">{anomaly.ticker}</h3>
        <span className={`${severityColor} text-white text-xs px-3 py-1 rounded-full`}>
          {anomaly.severity.toUpperCase()}
        </span>
      </div>
      
      {/* Score */}
      <div className="mb-4">
        <span className="text-2xl font-bold text-blue-600">{anomaly.score.toFixed(2)}</span>
        <span className="text-gray-500 text-sm ml-2">/ 10.0</span>
      </div>
      
      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-xs text-gray-500">Volume Z-Score</p>
          <p className="text-lg font-semibold">{details.zscore?.toFixed(2) || 'N/A'}</p>
        </div>
        
        <div>
          <p className="text-xs text-gray-500">VPIN (Toxicity)</p>
          <p className="text-lg font-semibold">{details.vpin ? (details.vpin * 100).toFixed(1) + '%' : 'N/A'}</p>
        </div>
        
        <div>
          <p className="text-xs text-gray-500">Days to Close</p>
          <p className="text-lg font-semibold">{details.days_to_close || 'N/A'}</p>
        </div>
        
        <div>
          <p className="text-xs text-gray-500">Whale Trades</p>
          <p className="text-lg font-semibold">{details.whale_trades || 0}</p>
        </div>
      </div>
      
      {/* Price-Volume Correlation Badge */}
      {details.price_volume_corr > 0 && (
        <div className="bg-red-50 border border-red-200 rounded p-2 mb-3">
          <p className="text-xs text-red-700">
            ⚠️ Price-volume correlation detected (score: {details.price_volume_corr.toFixed(2)})
          </p>
        </div>
      )}
      
      {/* Whale Details */}
      {details.whale_details && details.whale_details.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mb-3">
          <p className="text-xs font-semibold text-yellow-800 mb-2">🐋 Large Trades Detected</p>
          {details.whale_details.map((whale, idx) => (
            <p key={idx} className="text-xs text-yellow-700">
              ${whale.value_usd.toFixed(0)} at {new Date(whale.timestamp).toLocaleTimeString()}
            </p>
          ))}
        </div>
      )}
      
      {/* Timestamp */}
      <p className="text-xs text-gray-400 mt-3">
        Detected: {new Date(anomaly.detected_at).toLocaleString()}
      </p>
    </div>
  );
}
