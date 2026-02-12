import React from 'react';
import { AlertCircle, Clock } from 'lucide-react';

export default function AnomalyCard({ anomaly }) {
  const severityColors = {
    high: 'bg-red-100 text-red-800 border-red-300',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    low: 'bg-blue-100 text-blue-800 border-blue-300',
  };

  return (
    <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <AlertCircle className="text-gray-400" size={20} />
            <h3 className="font-semibold text-lg">{anomaly.ticker}</h3>
            <span className={`px-3 py-1 rounded-full text-xs font-medium border ${severityColors[anomaly.severity]}`}>
              {anomaly.severity.toUpperCase()}
            </span>
          </div>
          
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2 text-gray-600">
              <Clock size={16} />
              <span>{new Date(anomaly.detected_at).toLocaleString()}</span>
            </div>
            
            <div className="grid grid-cols-2 gap-4 mt-3">
              <div>
                <span className="text-gray-500">Score:</span>
                <span className="ml-2 font-semibold">{anomaly.score}/10</span>
              </div>
              <div>
                <span className="text-gray-500">Type:</span>
                <span className="ml-2 font-semibold capitalize">{anomaly.type}</span>
              </div>
            </div>

            {anomaly.details && (
              <div className="mt-3 p-3 bg-gray-50 rounded text-xs">
                <pre className="whitespace-pre-wrap">
                  {JSON.stringify(anomaly.details, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
