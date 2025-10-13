import os
from fastapi import FastAPI, HTTPException
import redis

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
app = FastAPI(title="Trip Service")

@app.post("/trips/{ride_id}/start")
def start_trip(ride_id: int):
    key = f"ride:{ride_id}"
    if not r.exists(key):
        raise HTTPException(status_code=404, detail="ride not found")
    r.hset(key, mapping={"status": "ongoing"})
    return {"ride_id": ride_id, "status": "ongoing"}

@app.post("/trips/{ride_id}/complete")
def complete_trip(ride_id: int):
    key = f"ride:{ride_id}"
    if not r.exists(key):
        raise HTTPException(status_code=404, detail="ride not found")
    data = r.hgetall(key)
    r.hset(key, mapping={"status": "completed"})
    driver_id = data.get("driver_id")
    if driver_id:
        r.sadd("drivers:available", driver_id)
    return {"ride_id": ride_id, "status": "completed"}
