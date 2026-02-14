import { useEffect, useRef } from 'react';

export function useWhaleNotifications(whales, enabled = true) {
  const previousWhalesRef = useRef([]);

  useEffect(() => {
    if (!enabled || !whales || whales.length === 0) return;

    // Request notification permission on first run
    if (Notification.permission === 'default') {
      Notification.requestPermission();
    }

    // Only notify if we have permission
    if (Notification.permission !== 'granted') return;

    // Find new whales (not in previous list)
    const previousWhaleIds = previousWhalesRef.current.map(w => `${w.ticker}-${w.timestamp}`);
    const newWhales = whales.filter(w => !previousWhaleIds.includes(`${w.ticker}-${w.timestamp}`));

    // Send notifications for new whales
    newWhales.forEach(whale => {
      // Only notify for whales ≥ $1000 or critical urgency
      const shouldNotify = whale.usd_value >= 1000 || whale.days_to_close <= 7;
      
      if (shouldNotify) {
        const notification = new Notification('🐋 Whale Trade Detected!', {
          body: `${whale.side?.toUpperCase()} $${whale.usd_value?.toFixed(0)} on ${whale.market_title || whale.ticker}`,
          icon: '/favicon.ico',
          tag: `whale-${whale.ticker}-${whale.timestamp}`,
          requireInteraction: whale.days_to_close <= 7, // Keep critical alerts on screen
        });

        notification.onclick = () => {
          window.open(whale.kalshi_url, '_blank');
          notification.close();
        };
      }
    });

    // Update reference for next comparison
    previousWhalesRef.current = whales;
  }, [whales, enabled]);
}
