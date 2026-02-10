import React from 'react';

export default function FilterBar({ severityFilter, setSeverityFilter, daysFilter, setDaysFilter }) {
  return (
    <div className="bg-white rounded-lg shadow p-4 mb-6 flex gap-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Severity</label>
        <select
          value={severityFilter || ''}
          onChange={(e) => setSeverityFilter(e.target.value || null)}
          className="border rounded px-3 py-2"
        >
          <option value="">All</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Time Period</label>
        <select
          value={daysFilter}
          onChange={(e) => setDaysFilter(Number(e.target.value))}
          className="border rounded px-3 py-2"
        >
          <option value={1}>Last 24 hours</option>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
        </select>
      </div>
    </div>
  );
}
