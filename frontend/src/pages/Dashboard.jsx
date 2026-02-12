import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, TrendingUp, Activity } from 'lucide-react';
import { fetchAnomalies, fetchMarkets } from '../services/api';
import AnomalyCard from '../components/AnomalyCard';
import FilterBar from '../components/FilterBar';
import WhaleTracker from '../components/WhaleTracker';

export default function Dashboard() {
  const [severityFilter, setSeverityFilter] = useState(null);
  const [daysFilter, setDaysFilter] = useState(7);
  
  // NEW: Additional filters for VPIN and whales
  const [minVpin, setMinVpin] = useState(0);
  const [hasWhales, setHasWhales] = useState(false);

  const { data: anomalies, isLoading } = useQuery({
    queryKey: ['anomalies', severityFilter, daysFilter],
    queryFn: () => fetchAnomalies(severityFilter, daysFilter),
    refetchInterval: 60000,
  });

  const { data: markets } = useQuery({
    queryKey: ['markets'],
    queryFn: fetchMarkets,
  });

  // NEW: Apply client-side filtering for VPIN and whales
  const filteredAnomalies = React.useMemo(() => {
    if (!anomalies) return [];
    
    return anomalies.filter(a => {
      // VPIN filter
      if (minVpin > 0) {
        const vpin = a.details?.vpin || 0;
        if (vpin < minVpin) return false;
      }
      
      // Whale filter
      if (hasWhales) {
        const whaleCount = a.details?.whale_trades || 0;
        if (whaleCount === 0) return false;
      }
      
      return true;
    });
  }, [anomalies, minVpin, hasWhales]);

  const highAlerts = filteredAnomalies?.filter(a => a.severity === 'high').length || 0;
  const mediumAlerts = filteredAnomalies?.filter(a => a.severity === 'medium').length || 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Kalshi Insider Trading Detection</h1>
          <p className="mt-2 text-sm text-gray-600">
            Real-time anomaly detection for prediction markets
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <StatCard
            icon={<AlertTriangle className="w-6 h-6 text-red-500" />}
            title="High Severity Alerts"
            value={highAlerts}
            color="red"
          />
          <StatCard
            icon={<TrendingUp className="w-6 h-6 text-orange-500" />}
            title="Medium Severity Alerts"
            value={mediumAlerts}
            color="orange"
          />
          <StatCard
            icon={<Activity className="w-6 h-6 text-blue-500" />}
            title="Active Markets"
            value={markets?.length || 0}
            color="blue"
          />
        </div>

        {/* Whale Tracker */}
        <div className="mb-8">
          <WhaleTracker />
        </div>

        {/* Filter Bar */}
        <FilterBar
          severityFilter={severityFilter}
          setSeverityFilter={setSeverityFilter}
          daysFilter={daysFilter}
          setDaysFilter={setDaysFilter}
        />

        {/* NEW: Advanced Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-8">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Advanced Filters</h3>
          <div className="flex flex-wrap gap-4">
            {/* Whale filter */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={hasWhales}
                onChange={(e) => setHasWhales(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Only show whale trades 🐋</span>
            </label>

            {/* VPIN filter */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-700">Min VPIN (toxicity):</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={minVpin}
                onChange={(e) => setMinVpin(parseFloat(e.target.value) || 0)}
                className="border border-gray-300 rounded px-3 py-1 w-24 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-xs text-gray-500">(0.0 - 1.0)</span>
            </div>

            {/* Reset button */}
            {(minVpin > 0 || hasWhales) && (
              <button
                onClick={() => {
                  setMinVpin(0);
                  setHasWhales(false);
                }}
                className="text-xs text-blue-600 hover:text-blue-800 underline"
              >
                Reset advanced filters
              </button>
            )}
          </div>
        </div>

        {/* Anomalies List */}
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-gray-900">
              Recent Anomalies ({filteredAnomalies?.length || 0})
            </h2>
          </div>

          {isLoading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
              <p className="mt-2 text-gray-600">Loading anomalies...</p>
            </div>
          ) : filteredAnomalies?.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <p className="text-gray-500">No anomalies detected with current filters</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredAnomalies?.map((anomaly) => (
                <AnomalyCard key={anomaly.id} anomaly={anomaly} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, title, value, color }) {
  const colorClasses = {
    red: 'bg-red-50 border-red-200',
    orange: 'bg-orange-50 border-orange-200',
    blue: 'bg-blue-50 border-blue-200',
  };

  return (
    <div className={`${colorClasses[color]} border rounded-lg p-6`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
        </div>
        {icon}
      </div>
    </div>
  );
}
