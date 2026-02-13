import React from 'react';
import { AlertTriangle, TrendingUp, Activity, DollarSign } from 'lucide-react';

const severityColors = {
  critical: 'border-red-500 bg-red-50',
  high: 'border-orange-500 bg-orange-50',
  medium: 'border-yellow-500 bg-yellow-50',
  low: 'border-blue-500 bg-blue-50',
};

const severityBadges = {
  critical: 'bg-red-500 text-white',
  high: 'bg-orange-500 text-white',
  medium: 'bg-yellow-500 text-white',
  low: 'bg-blue-500 text-white',
};

export default function AnomalyCard({ anomaly }) {
  const details = typeof anomaly.details === 'string' 
    ? JSON.parse(anomaly.details) 
    : anomaly.details;

  return (
    <div className={`border-l-4 rounded-lg p-6 shadow-md ${severityColors[anomaly.severity]}`}>
      <div className="flex justify-between items-start mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {anomaly.ticker}
          </h3>
          <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${severityBadges[anomaly.severity]}`}>
            {anomaly.severity.toUpperCase()}
          </span>
        </div>
        <div className="text-right">
          <div className="flex items-center gap-2 text-gray-600">
            <AlertTriangle className="w-5 h-5" />
            <span className="text-2xl font-bold text-gray-900">
              {anomaly.score.toFixed(2)}
            </span>
          </div>
          <p className="text-sm text-gray-500">Anomaly Score</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div>
          <p className="text-sm text-gray-600 flex items-center gap-1">
            <Activity className="w-4 h-4" />
            Volume
          </p>
          <p className="text-lg font-semibold">{details?.volume || 'N/A'}</p>
        </div>

        <div>
          <p className="text-sm text-gray-600 flex items-center gap-1">
            <TrendingUp className="w-4 h-4" />
            VPIN
          </p>
          <p className="text-lg font-semibold">
            {details?.vpin ? `${(details.vpin * 100).toFixed(1)}%` : 'N/A'}
          </p>
        </div>

        <div>
          <p className="text-sm text-gray-600 flex items-center gap-1">
            <DollarSign className="w-4 h-4" />
            Whale Trades
          </p>
          <p className="text-lg font-semibold">{details?.whale_count || 0}</p>
        </div>

        <div>
          <p className="text-sm text-gray-600">Type</p>
          <p className="text-lg font-semibold capitalize">{anomaly.anomaly_type}</p>
        </div>
      </div>

      <div className="text-sm text-gray-600">
        <p>Detected: {new Date(anomaly.detected_at).toLocaleString()}</p>
      </div>
    </div>
  );
}
