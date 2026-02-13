# Kalshi Anomaly Detector - Deployment Guide

## Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- Kalshi API credentials
- 2GB+ RAM, 10GB+ disk space

### Installation Steps

1. Clone repository:
   git clone https://github.com/Meebo7881/kalshi-anomaly-detector.git
   cd kalshi-anomaly-detector

2. Configure environment:
   cp backend/.env.example backend/.env
   nano backend/.env

3. Add your Kalshi credentials in .env file

4. Place private key:
   cp /path/to/kalshi_private_key.key backend/

5. Start services:
   docker-compose up -d

6. Verify (wait 30 seconds):
   curl http://localhost:8000/health
   docker-compose ps

7. Access dashboard:
   http://localhost:3000

## Services

| Service    | Port | URL                          |
|------------|------|------------------------------|
| Dashboard  | 3000 | http://localhost:3000        |
| API        | 8000 | http://localhost:8000        |
| API Docs   | 8000 | http://localhost:8000/docs   |
| PostgreSQL | 5432 | Internal                     |
| Redis      | 6379 | Internal                     |

## System Status (v1.2.2 - Feb 13, 2026)

- 348 markets monitored
- 41,637+ trades collected
- 5 anomalies detected
- All containers healthy
- Tasks running every 5 minutes

## Monitoring Commands

Check system health:
  docker-compose ps
  curl http://localhost:8000/health
  curl http://localhost:8000/api/v1/anomalies

View logs:
  docker-compose logs -f worker
  docker-compose logs -f api

Check database:
  docker-compose exec postgres psql -U kalshi_user -d kalshi_detector
  SELECT COUNT(*) FROM anomalies;

## Troubleshooting

### API not starting
  docker-compose logs api --tail=50
  docker-compose restart api
  docker-compose build api

### No anomalies detected
  docker-compose exec worker python3 -c "import sys; sys.path.insert(0, '/app'); from app.tasks.monitor import run_anomaly_detection; run_anomaly_detection()"

### Dashboard empty
  docker-compose exec frontend wget -qO- http://kalshi-api:8000/api/v1/anomalies
  docker-compose restart frontend

## Maintenance

Update code:
  git pull origin main
  docker-compose build
  docker-compose up -d

Backup database:
  docker-compose exec postgres pg_dump -U kalshi_user kalshi_detector > backup.sql

Restart services:
  docker-compose restart

## Support

Repository: https://github.com/Meebo7881/kalshi-anomaly-detector
Issues: https://github.com/Meebo7881/kalshi-anomaly-detector/issues
