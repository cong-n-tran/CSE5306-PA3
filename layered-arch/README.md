# Minimal Layered Ride‑Sharing (HTTP)

One FastAPI app with API → Service → Data layers. We run 5 replicas + Redis.

## Run

```bash
cp .env.example .env
docker compose up --build
```

Nodes:
- http://localhost:8101/docs
- http://localhost:8102/docs
- http://localhost:8103/docs
- http://localhost:8104/docs
- http://localhost:8105/docs

## Quick demo

Register users (any node):
```bash
curl -X POST http://localhost:8101/auth/register -H 'Content-Type: application/json' -d '{"user_id":"alice","role":"rider"}'
curl -X POST http://localhost:8101/auth/register -H 'Content-Type: application/json' -d '{"user_id":"bob","role":"driver"}'
```

Update driver location:
```bash
curl -X POST http://localhost:8102/drivers/location -H 'Content-Type: application/json' -d '{"driver_id":"bob","lat":32.7357,"lon":-97.1081,"available":true}'
```

Request a ride:
```bash
curl -X POST http://localhost:8103/rides/request -H 'Content-Type: application/json' -d '{"rider_id":"alice","pickup_lat":32.7357,"pickup_lon":-97.1081,"dest_lat":32.75,"dest_lon":-97.12}'
```

Start + complete trip:
```bash
curl -X POST http://localhost:8104/trips/1/start
curl -X POST http://localhost:8105/trips/1/complete
```

Because all state is in Redis, you can use any node for any step.
