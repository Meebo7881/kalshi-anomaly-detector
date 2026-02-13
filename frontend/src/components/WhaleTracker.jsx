import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchMarkets } from '../services/api';
import { DollarSign, TrendingUp, Users } from 'lucide-react';

export default function WhaleTracker() {
  const { data: markets = [], isLoading } = useQuery({
    queryKey: ['markets'],
    queryFn: fetchMarkets,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Calculate whale statistics
  const whaleStats = markets.reduce((acc, market) => {
    const whaleCount = market.whale_trades_count || 0;
    if (whaleCount > 0) {
      acc.marketsWithWhales++;
      acc.totalWhales += whaleCount;
    }
    return acc;
  }, { marketsWithWhales: 0, totalWhales: 0 });

  if (isLoading) {
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
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
    </div>
  );
}
