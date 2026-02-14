import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, TrendingUp, Activity } from 'lucide-react';
import { fetchAnomalies, fetchMarkets } from '../services/api';
import AnomalyCard from '../components/AnomalyCard';
import FilterBar from '../components/FilterBar';
import WhaleTracker from '../components/WhaleTracker';
import WhalePatternsPanel from '../components/WhalePatternsPanel';

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
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Kalshi Anomaly Detector
          </h1>
          <p className="text-gray-600">
            Real-time anomaly detection for prediction markets
          </p>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <StatCard
            icon={<AlertTriangle className="w-6 h-6 text-red-500" />}
            title="High Alerts"
            value={highAlerts}
            bgColor="bg-red-50"
          />
          <StatCard
            icon={<TrendingUp className="w-6 h-6 text-yellow-500" />}
            title="Medium Alerts"
            value={mediumAlerts}
            bgColor="bg-yellow-50"
          />
          <StatCard
            icon={<Activity className="w-6 h-6 text-blue-500" />}
            title="Markets Monitored"
            value={markets?.total || 0}
            bgColor="bg-blue-50"
          />
        </div>

        {/* NEW: Whale Tracker - now above anomalies */}
        <div className="mb-8">
          <WhaleTracker />
        </div>

        {/* NEW: Whale Patterns Panel */}
        <div className="mb-8">
          <WhalePatternsPanel />
        </div>

        {/* Filter Bar */}
        <FilterBar
          severityFilter={severityFilter}
          setSeverityFilter={setSeverityFilter}
          daysFilter={daysFilter}
          setDaysFilter={setDaysFilter}
          minVpin={minVpin}
          setMinVpin={setMinVpin}
          hasWhales={hasWhales}
          setHasWhales={setHasWhales}
        />

        {/* Anomalies List */}
        {isLoading ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-500">Loading anomalies...</p>
          </div>
        ) : filteredAnomalies && filteredAnomalies.length > 0 ? (
          <div className="grid grid-cols-1 gap-6">
            {filteredAnomalies.map((anomaly) => (
              <AnomalyCard key={anomaly.id} anomaly={anomaly} />
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <AlertTriangle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">No anomalies detected with current filters</p>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, title, value, bgColor }) {
  return (
    <div className={`${bgColor} rounded-lg p-6 shadow`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-gray-900">{value}</p>
        </div>
        <div>{icon}</div>
      </div>
    </div>
  );
}
