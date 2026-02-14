import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchMarkets, fetchWhales } from '../services/api';
import { DollarSign, TrendingUp, Users, Clock, ArrowUp, ArrowDown } from 'lucide-react';

export default function WhaleTracker() {
  const { data: markets = [], isLoading: marketsLoading } = useQuery({
    queryKey: ['markets'],
    queryFn: fetchMarkets,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // NEW: Fetch live whale trades
  const { data: whales = [], isLoading: whalesLoading } = useQuery({
    queryKey: ['whales'],
    queryFn: () => fetchWhales({ hours: 168, min_usd: 500 }),
    refetchInterval: 60000, // Refresh every minute
  });

  // Calculate whale statistics (your existing logic)
  const whaleStats = markets.reduce((acc, market) => {
    const whaleCount = market.whale_trades_count || 0;
    if (whaleCount > 0) {
      acc.marketsWithWhales++;
      acc.totalWhales += whaleCount;
    }
    return acc;
  }, { marketsWithWhales: 0, totalWhales: 0 });

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
        <Users className="w-5 h-5" />
        Whale Tracker
      </h2>
      
      {/* Existing stats cards */}
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
            <span className="text-sm font-medium text-gray-600">Avg per Market</span>
          </div>
          <p className="text-2xl font-bold text-green-600">
            {whaleStats.marketsWithWhales > 0 
              ? (whaleStats.totalWhales / whaleStats.marketsWithWhales).toFixed(1)
              : '0'}
          </p>
        </div>
      </div>

      {/* NEW: Live whale tape */}
      <div className="border-t pt-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <Clock className="w-4 h-4" />
          Live Whale Trades (Last 7 Days, ≥$500)
        </h3>
        
        {whales.length === 0 ? (
          <p className="text-sm text-gray-500">No whale trades detected recently</p>
        ) : (
          <div className="space-y-2">
            {whales.slice(0, 10).map((whale, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{whale.ticker}</p>
                  <p className="text-xs text-gray-500">
                    {whale.volume} @ {whale.price}¢
                  </p>
                </div>
                
                <div className="flex items-center gap-3">
                  <div className={`flex items-center gap-1 px-2 py-1 rounded ${
                    whale.side === 'yes' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {whale.side === 'yes' ? (
                      <ArrowUp className="w-3 h-3" />
                    ) : (
                      <ArrowDown className="w-3 h-3" />
                    )}
                    <span className="text-xs font-semibold">{whale.side?.toUpperCase()}</span>
                  </div>
                  
                  <span className="text-sm font-bold text-gray-900">
                    ${whale.usd_value?.toFixed(0)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
