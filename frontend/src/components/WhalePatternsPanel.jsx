import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, Users, Target, AlertTriangle, ExternalLink, CheckCircle } from 'lucide-react';

const fetchWhalePatterns = async ({ days = 7, minWhales = 2 }) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/stats/whale-patterns?days=${days}&min_whales=${minWhales}`
  );
  if (!response.ok) throw new Error('Failed to fetch whale patterns');
  return response.json();
};

export default function WhalePatternsPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['whale-patterns'],
    queryFn: () => fetchWhalePatterns({ days: 7, minWhales: 2 }),
    refetchInterval: 60000, // Refresh every minute
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Target className="w-5 h-5" />
          Whale Consensus Signals
        </h2>
        <p className="text-gray-500">Loading whale patterns...</p>
      </div>
    );
  }

  const patterns = data?.items || [];

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Target className="w-5 h-5 text-purple-600" />
        Whale Consensus Signals (Last 7 Days)
      </h2>

      <p className="text-sm text-gray-600 mb-6">
        Markets where <strong>multiple whales</strong> are aligned indicate high-confidence insider signals. 
        Higher consensus = stronger copy-trading opportunity.
      </p>

      {patterns.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-gray-400" />
          <p>No whale clustering detected yet.</p>
          <p className="text-sm">Check back later for consensus signals.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {patterns.map((pattern, idx) => {
            // Determine signal strength
            let strengthClass = 'bg-gray-100 text-gray-700';
            let strengthIcon = null;
            
            if (pattern.consensus_strength >= 80) {
              strengthClass = 'bg-green-100 text-green-800 border-green-500';
              strengthIcon = <CheckCircle className="w-4 h-4" />;
            } else if (pattern.consensus_strength >= 60) {
              strengthClass = 'bg-yellow-100 text-yellow-800 border-yellow-500';
              strengthIcon = <TrendingUp className="w-4 h-4" />;
            }

            // Urgency indicator
            let urgencyBadge = null;
            if (pattern.days_to_close !== null && pattern.days_to_close <= 7) {
              urgencyBadge = (
                <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded border border-red-500">
                  ⚡ Closes in {pattern.days_to_close}d
                </span>
              );
            }

            return (
              <div 
                key={idx} 
                className={`border-2 rounded-lg p-4 ${strengthClass.includes('green') ? 'border-green-500' : strengthClass.includes('yellow') ? 'border-yellow-500' : 'border-gray-300'} hover:shadow-lg transition`}
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 text-sm leading-tight mb-1">
                      {pattern.market_title}
                    </h3>
                    <p className="text-xs text-gray-500">{pattern.ticker}</p>
                  </div>
                  {urgencyBadge}
                </div>

                {/* Whale Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  <div>
                    <p className="text-xs text-gray-600">Total Whales</p>
                    <div className="flex items-center gap-1">
                      <Users className="w-4 h-4 text-purple-600" />
                      <span className="text-lg font-bold text-gray-900">{pattern.whale_count}</span>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-gray-600">Consensus</p>
                    <div className="flex items-center gap-1">
                      {strengthIcon}
                      <span className="text-lg font-bold text-gray-900">{pattern.consensus_strength}%</span>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-gray-600">Direction</p>
                    <span className={`text-sm font-bold ${pattern.consensus_side === 'yes' ? 'text-green-700' : pattern.consensus_side === 'no' ? 'text-red-700' : 'text-gray-700'}`}>
                      {pattern.consensus_side === 'yes' ? '✅ YES' : pattern.consensus_side === 'no' ? '🚫 NO' : '⚖️ MIXED'}
                    </span>
                  </div>

                  <div>
                    <p className="text-xs text-gray-600">Total Volume</p>
                    <span className="text-sm font-bold text-gray-900">${pattern.total_whale_volume_usd.toFixed(0)}</span>
                  </div>
                </div>

                {/* Breakdown */}
                <div className="bg-gray-50 rounded p-3 mb-3">
                  <p className="text-xs font-semibold text-gray-700 mb-2">Whale Breakdown:</p>
                  <div className="flex gap-4 text-sm">
                    <span className="text-green-700 font-medium">
                      {pattern.yes_whales} YES {pattern.yes_whales === 1 ? 'whale' : 'whales'}
                    </span>
                    <span className="text-red-700 font-medium">
                      {pattern.no_whales} NO {pattern.no_whales === 1 ? 'whale' : 'whales'}
                    </span>
                  </div>
                </div>

                {/* Action Button */}
                <a
                  href={pattern.kalshi_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded font-medium text-sm transition ${
                    pattern.consensus_strength >= 80
                      ? 'bg-green-600 text-white hover:bg-green-700'
                      : pattern.consensus_strength >= 60
                      ? 'bg-yellow-600 text-white hover:bg-yellow-700'
                      : 'bg-gray-600 text-white hover:bg-gray-700'
                  }`}
                >
                  {pattern.consensus_strength >= 80 ? '🎯 High Confidence Signal' : 'Copy Trade on Kalshi'}
                  <ExternalLink className="w-4 h-4" />
                </a>

                <p className="text-xs text-gray-500 mt-3">
                  Latest whale: {new Date(pattern.latest_whale_time).toLocaleString()}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
