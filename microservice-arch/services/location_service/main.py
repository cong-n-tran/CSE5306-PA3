import os
from fastapi import FastAPI
from pydantic import BaseModel
import redis

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
app = FastAPI(title="Location Service")

class Location(BaseModel):
    driver_id: str
    lat: float
    lon: float
    available: bool = True

@app.post("/drivers/location")
def update_location(payload: Location):
    r.geoadd("drivers:geo", (payload.lon, payload.lat, payload.driver_id))
    if payload.available:
        r.sadd("drivers:available", payload.driver_id)
    else:
        r.srem("drivers:available", payload.driver_id)
    return {"ok": True}

@app.get("/drivers/nearby")
def nearby(lat: float, lon: float, radius_km: float = 5.0, count: int = 5):
    ids = r.execute_command(
        "GEOSEARCH", "drivers:geo", "FROMLONLAT", lon, lat, "BYRADIUS", radius_km, "km", "ASC", "COUNT", count
    )
    avail = set(r.smembers("drivers:available"))
    return [d for d in ids if d in avail]
