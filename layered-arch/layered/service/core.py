from layered.data import repo

# Auth
def register_user(user_id: str, role: str):
    if role not in {"rider", "driver"}:
        raise ValueError("role must be rider or driver")
    if repo.user_exists(user_id):
        raise KeyError("user exists")
    repo.create_user(user_id, role)

def login_user(user_id: str) -> str:
    if not repo.user_exists(user_id):
        raise KeyError("user not found")
    return user_id  # trivial token

# Location
def update_driver_location(driver_id: str, lat: float, lon: float, available: bool = True):
    repo.set_driver_location(driver_id, lat, lon, available)

# Matching
def request_ride(rider_id: str, pickup_lat: float, pickup_lon: float, dest_lat: float, dest_lon: float) -> dict:
    drivers = repo.nearby_drivers(pickup_lat, pickup_lon, 10, 1)
    if not drivers:
        raise LookupError("no drivers available")
    driver_id = drivers[0]
    ride_id = repo.new_ride(rider_id, driver_id, pickup_lat, pickup_lon, dest_lat, dest_lon)
    return {"ride_id": ride_id, "driver_id": driver_id, "status": "matched"}

# Trips
def start_trip(ride_id: int) -> dict:
    ride = repo.get_ride(ride_id)
    if not ride:
        raise LookupError("ride not found")
    repo.set_ride_status(ride_id, "ongoing")
    return {"ride_id": ride_id, "status": "ongoing"}

def complete_trip(ride_id: int) -> dict:
    ride = repo.get_ride(ride_id)
    if not ride:
        raise LookupError("ride not found")
    repo.set_ride_status(ride_id, "completed")
    driver_id = ride.get("driver_id")
    if driver_id:
        repo.free_driver(driver_id)
    return {"ride_id": ride_id, "status": "completed"}
