import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, TrendingUp, Activity } from 'lucide-react';
import { fetchAnomalies, fetchMarkets } from '../services/api';
import AnomalyCard from '../components/AnomalyCard';
import FilterBar from '../components/FilterBar';

export default function Dashboard() {
  const [severityFilter, setSeverityFilter] = useState(null);
  const [daysFilter, setDaysFilter] = useState(7);

  const { data: anomalies, isLoading } = useQuery({
    queryKey: ['anomalies', severityFilter, daysFilter],
    queryFn: () => fetchAnomalies(severityFilter, daysFilter),
    refetchInterval: 60000,
  });

  const { data: markets } = useQuery({
    queryKey: ['markets'],
    queryFn: fetchMarkets,
  });

  const highAlerts = anomalies?.filter(a => a.severity === 'high').length || 0;
  const mediumAlerts = anomalies?.filter(a => a.severity === 'medium').length || 0;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Kalshi Anomaly Detection
          </h1>
          <p className="text-gray-600 mt-2">
            Real-time monitoring for suspicious trading patterns
          </p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <StatsCard
            icon={<AlertTriangle className="text-red-500" />}
            title="High Severity"
            value={highAlerts}
            color="red"
          />
          <StatsCard
            icon={<TrendingUp className="text-yellow-500" />}
            title="Medium Severity"
            value={mediumAlerts}
            color="yellow"
          />
          <StatsCard
            icon={<Activity className="text-blue-500" />}
            title="Active Markets"
            value={markets?.length || 0}
            color="blue"
          />
        </div>

        <FilterBar
          severityFilter={severityFilter}
          setSeverityFilter={setSeverityFilter}
          daysFilter={daysFilter}
          setDaysFilter={setDaysFilter}
        />

        <div className="bg-white rounded-lg shadow">
          <div className="p-6">
            <h2 className="text-xl font-semibold mb-4">Recent Anomalies</h2>
            {isLoading ? (
              <div className="text-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
              </div>
            ) : anomalies?.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                No anomalies detected in the selected timeframe
              </div>
            ) : (
              <div className="space-y-4">
                {anomalies?.map(anomaly => (
                  <AnomalyCard key={anomaly.id} anomaly={anomaly} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatsCard({ icon, title, value, color }) {
  const colorClasses = {
    red: 'bg-red-50 border-red-200',
    yellow: 'bg-yellow-50 border-yellow-200',
    blue: 'bg-blue-50 border-blue-200',
  };

  return (
    <div className={`${colorClasses[color]} border rounded-lg p-6`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 mb-1">{title}</p>
          <p className="text-3xl font-bold">{value}</p>
        </div>
        {icon}
      </div>
    </div>
  );
}
