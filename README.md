# Kalshi Anomaly Detector

Real-time anomaly detection system for Kalshi prediction markets to identify potential insider trading patterns.

## Quick Start

1. Install Docker and Docker Compose
2. Clone this repository
3. Add your Kalshi credentials to `.env` file
4. Run: `docker-compose up -d`
5. Access frontend at http://localhost:3000

## Services

- **Frontend**: React dashboard on port 3000
- **API**: FastAPI backend on port 8000
- **Worker**: Celery worker for data collection
- **Beat**: Celery scheduler for periodic tasks
- **PostgreSQL**: Database on port 5432
- **Redis**: Message broker on port 6379

## Development

```bash
# View logs
docker-compose logs -f

# Rebuild services
docker-compose build

# Stop all services
docker-compose down

## Current Status (Feb 13, 2026)

✅ **System Operational**
- 348 markets monitored
- 41,637 trades collected
- 5 anomalies detected
- API: http://localhost:8000
- Dashboard: http://localhost:3000
- Docs: http://localhost:8000/docs

### Recent Fixes
- Restored complete backend from feature branch
- Verified full data pipeline functionality
- Confirmed anomaly detection running every 5 minutes
