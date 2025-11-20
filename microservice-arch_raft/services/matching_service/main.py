import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
app = FastAPI(title="Matching Service")

class RideRequest(BaseModel):
    rider_id: str
    pickup_lat: float
    pickup_lon: float
    dest_lat: float
    dest_lon: float

@app.post("/rides/request")
def request_ride(req: RideRequest):
    candidates = r.execute_command(
        "GEOSEARCH", "drivers:geo", "FROMLONLAT", req.pickup_lon, req.pickup_lat, "BYRADIUS", 10, "km", "ASC", "COUNT", 1
    )
    avail = set(r.smembers("drivers:available"))
    candidates = [d for d in candidates if d in avail]
    if not candidates:
        raise HTTPException(status_code=404, detail="no drivers available")
    driver_id = candidates[0]

    ride_id = r.incr("seq:ride")
    ride_key = f"ride:{ride_id}"
    r.hset(ride_key, mapping={
        "rider_id": req.rider_id,
        "driver_id": driver_id,
        "status": "matched",
        "pickup_lat": req.pickup_lat,
        "pickup_lon": req.pickup_lon,
        "dest_lat": req.dest_lat,
        "dest_lon": req.dest_lon,
    })
    r.srem("drivers:available", driver_id)
    return {"ride_id": ride_id, "driver_id": driver_id, "status": "matched"}

@app.get("/rides/{ride_id}")
def get_ride(ride_id: int):
    data = r.hgetall(f"ride:{ride_id}")
    if not data:
        raise HTTPException(status_code=404, detail="ride not found")
    return {"ride_id": ride_id, **data}

from raft_client import get_leader

leader = get_leader()
if leader == "raft_auth":
    print("This instance is LEADER")
else:
    print("This instance is FOLLOWER")
