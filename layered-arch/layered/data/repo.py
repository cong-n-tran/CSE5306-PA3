from layered.config.settings import get_redis

r = get_redis()

# Users
def user_exists(user_id: str) -> bool:
    return r.exists(f"user:{user_id}") == 1

def create_user(user_id: str, role: str):
    r.hset(f"user:{user_id}", mapping={"role": role})

def get_user(user_id: str):
    return r.hgetall(f"user:{user_id}")

# Drivers geo + availability
def set_driver_location(driver_id: str, lat: float, lon: float, available: bool):
    r.geoadd("drivers:geo", (lon, lat, driver_id))
    if available:
        r.sadd("drivers:available", driver_id)
    else:
        r.srem("drivers:available", driver_id)

def nearby_drivers(lat: float, lon: float, radius_km: float = 10, count: int = 1):
    ids = r.execute_command(
        "GEOSEARCH", "drivers:geo", "FROMLONLAT", lon, lat, "BYRADIUS", radius_km, "km", "ASC", "COUNT", count
    )
    avail = set(r.smembers("drivers:available"))
    return [d for d in ids if d in avail]

# Rides
def new_ride(rider_id: str, driver_id: str, pickup_lat: float, pickup_lon: float, dest_lat: float, dest_lon: float) -> int:
    ride_id = r.incr("seq:ride")
    key = f"ride:{ride_id}"
    r.hset(key, mapping={
        "rider_id": rider_id,
        "driver_id": driver_id,
        "status": "matched",
        "pickup_lat": pickup_lat,
        "pickup_lon": pickup_lon,
        "dest_lat": dest_lat,
        "dest_lon": dest_lon,
    })
    r.srem("drivers:available", driver_id)
    return ride_id

def get_ride(ride_id: int):
    return r.hgetall(f"ride:{ride_id}")

def set_ride_status(ride_id: int, status: str):
    r.hset(f"ride:{ride_id}", mapping={"status": status})

def free_driver(driver_id: str):
    r.sadd("drivers:available", driver_id)
