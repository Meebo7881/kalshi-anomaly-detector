import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchMarkets, fetchWhales } from '../services/api';
import { useWhaleNotifications } from '../hooks/useWhaleNotifications';
import { DollarSign, TrendingUp, Users, Clock, ArrowUp, ArrowDown, ExternalLink, AlertCircle, Bell } from 'lucide-react';

export default function WhaleTracker() {
  const { data: markets = [], isLoading: marketsLoading } = useQuery({
    queryKey: ['markets'],
    queryFn: fetchMarkets,
    refetchInterval: 30000,
  });

  const { data: whales = [], isLoading: whalesLoading } = useQuery({
    queryKey: ['whales'],
    queryFn: () => fetchWhales({ hours: 168, min_usd: 500 }),
    refetchInterval: 60000,
  });

  const whaleStats = markets.reduce((acc, market) => {
    const whaleCount = market.whale_trades_count || 0;
    if (whaleCount > 0) {
      acc.marketsWithWhales++;
      acc.totalWhales += whaleCount;
    }
    return acc;
  }, { marketsWithWhales: 0, totalWhales: 0 });

  const enrichedWhales = whales.map(whale => {
    let urgency = 'low';
    let urgencyColor = 'text-green-600';
    let urgencyBg = 'bg-green-50';
    let urgencyBorder = 'border-green-500';

    if (whale.days_to_close !== null) {
      if (whale.days_to_close <= 7) {
        urgency = 'critical';
        urgencyColor = 'text-red-600';
        urgencyBg = 'bg-red-50';
        urgencyBorder = 'border-red-500';
      } else if (whale.days_to_close <= 30) {
        urgency = 'high';
        urgencyColor = 'text-orange-600';
        urgencyBg = 'bg-orange-50';
        urgencyBorder = 'border-orange-500';
      } else if (whale.days_to_close <= 90) {
        urgency = 'medium';
        urgencyColor = 'text-yellow-600';
        urgencyBg = 'bg-yellow-50';
        urgencyBorder = 'border-yellow-500';
      }
    }

    return { ...whale, urgency, urgencyColor, urgencyBg, urgencyBorder };
  });

  const sortedWhales = enrichedWhales.sort((a, b) => {
    const urgencyOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    if (urgencyOrder[a.urgency] !== urgencyOrder[b.urgency]) {
      return urgencyOrder[a.urgency] - urgencyOrder[b.urgency];
    }
    return b.usd_value - a.usd_value;
  });

  // NEW: Urgency filter
  const [urgencyFilter, setUrgencyFilter] = useState('all');
  const filteredWhales = sortedWhales.filter(whale => {
    if (urgencyFilter === 'all') return true;
    if (urgencyFilter === 'critical') return whale.urgency === 'critical';
    if (urgencyFilter === 'high') return whale.urgency === 'critical' || whale.urgency === 'high';
    return true;
  });

  // NEW: Browser notifications for new whales
  useWhaleNotifications(enrichedWhales, true);

  if (marketsLoading && whalesLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Users className="w-5 h-5" />
          Whale Tracker
        </h2>
        <p className="text-gray-500">Loading whale activity...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Bell className="w-5 h-5" />
        Whale Tracker - Copy Trading Signals
      </h2>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-medium text-gray-600">Total Whale Trades</span>
          </div>
          <p className="text-2xl font-bold text-blue-600">{whaleStats.totalWhales}</p>
        </div>

        <div className="bg-purple-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-purple-600" />
            <span className="text-sm font-medium text-gray-600">Markets with Whales</span>
          </div>
          <p className="text-2xl font-bold text-purple-600">{whaleStats.marketsWithWhales}</p>
        </div>

        <div className="bg-green-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-5 h-5 text-green-600" />
            <span className="text-sm font-medium text-gray-600">Active Signals (≥$500)</span>
          </div>
          <p className="text-2xl font-bold text-green-600">{whales.length}</p>
        </div>
      </div>

      <div className="border-t pt-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          Actionable Copy-Trading Signals (Last 7 Days)
        </h3>
        
        {/* NEW: Filter buttons */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setUrgencyFilter('all')}
            className={`px-3 py-1 text-sm rounded transition ${urgencyFilter === 'all' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            All ({sortedWhales.length})
          </button>
          <button
            onClick={() => setUrgencyFilter('critical')}
            className={`px-3 py-1 text-sm rounded transition ${urgencyFilter === 'critical' ? 'bg-red-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            Critical (≤7d)
          </button>
          <button
            onClick={() => setUrgencyFilter('high')}
            className={`px-3 py-1 text-sm rounded transition ${urgencyFilter === 'high' ? 'bg-orange-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            High+Critical (≤30d)
          </button>
        </div>

        {filteredWhales.length === 0 ? (
          <p className="text-sm text-gray-500">No whale trades match your filter</p>
        ) : (
          <div className="space-y-3">
            {filteredWhales.slice(0, 10).map((whale, idx) => (
              <div 
                key={idx} 
                className={`border-l-4 ${whale.urgencyBorder} p-4 rounded-lg ${whale.urgencyBg} hover:shadow-md transition`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <h4 className="text-sm font-semibold text-gray-900 mb-1 leading-tight">
                      {whale.market_title || whale.ticker}
                    </h4>
                    <p className="text-xs text-gray-500">{whale.ticker}</p>
                  </div>
                  <div className={`px-2 py-1 rounded text-xs font-semibold ${whale.urgencyColor} border ${whale.urgencyBorder}`}>
                    {whale.days_to_close !== null 
                      ? `${whale.days_to_close}d to close` 
                      : 'Unknown close'}
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                  <div>
                    <p className="text-xs text-gray-600">Direction</p>
                    <div className={`flex items-center gap-1 ${whale.side === 'yes' ? 'text-green-700 font-bold' : 'text-red-700 font-bold'}`}>
                      {whale.side === 'yes' ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
                      <span className="text-sm">{whale.side?.toUpperCase() || 'N/A'}</span>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-gray-600">Entry Price</p>
                    <p className="text-sm font-semibold text-gray-900">{whale.price}¢</p>
                  </div>

                  <div>
                    <p className="text-xs text-gray-600">Volume</p>
                    <p className="text-sm font-semibold text-gray-900">{whale.volume}</p>
                  </div>

                  <div>
                    <p className="text-xs text-gray-600">USD Value</p>
                    <p className="text-sm font-bold text-gray-900">${whale.usd_value?.toFixed(0)}</p>
                  </div>
                </div>

                <a 
                  href={whale.kalshi_url || `https://kalshi.com/markets/${whale.ticker}`}
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 transition"
                >
                  Trade on Kalshi
                  <ExternalLink className="w-4 h-4" />
                </a>

                <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(whale.timestamp).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
