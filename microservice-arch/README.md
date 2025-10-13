# Minimal Ride‑Sharing (HTTP) – Microservices

Super simple microservice version using FastAPI + Redis + Docker Compose.

## Run

```bash
cp .env.example .env
docker compose up --build
```

Services:
- Gateway: http://localhost:8000/docs
- Auth:    http://localhost:8001/docs
- Location:http://localhost:8002/docs
- Matching:http://localhost:8003/docs
- Trip:    http://localhost:8004/docs
- Redis:   localhost:6379

## Quick demo (via Gateway)

Register users
```bash
curl -X POST http://localhost:8000/auth/register -H 'Content-Type: application/json' -d '{"user_id":"alice","role":"rider"}'
curl -X POST http://localhost:8000/auth/register -H 'Content-Type: application/json' -d '{"user_id":"bob","role":"driver"}'
```

Driver sets location
```bash
curl -X POST http://localhost:8000/drivers/location -H 'Content-Type: application/json' -d '{"driver_id":"bob","lat":32.7357,"lon":-97.1081,"available":true}'
```

Rider requests a ride
```bash
curl -X POST http://localhost:8000/rides/request -H 'Content-Type: application/json' -d '{"rider_id":"alice","pickup_lat":32.7357,"pickup_lon":-97.1081,"dest_lat":32.75,"dest_lon":-97.12}'
```

Start + complete
```bash
curl -X POST http://localhost:8000/trips/1/start
curl -X POST http://localhost:8000/trips/1/complete
```
