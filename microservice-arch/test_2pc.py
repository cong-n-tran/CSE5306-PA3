import requests
import redis
import uuid
import time

# --- CONFIG ---
BASE_URL = "http://localhost:8000"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
# --------------

def print_status(message):
    print(f"\n[TEST] {message}")

def print_check(message):
    print(f"  ... {message}")

def test_ride_completion():
    # Generate unique IDs for this test run
    driver_id = f"test_driver_{uuid.uuid4().hex[:6]}"
    rider_id = f"test_rider_{uuid.uuid4().hex[:6]}"
    ride_key = ""
    ride_id = None

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        print_status(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        print_status(f"FATAL: Could not connect to Redis. Is it running? {e}")
        return

    try:
        # 1. SETUP: Register users
        print_status("Registering users...")
        resp = requests.post(f"{BASE_URL}/auth/register", json={"user_id": driver_id, "role": "driver"})
        resp.raise_for_status()
        resp = requests.post(f"{BASE_URL}/auth/register", json={"user_id": rider_id, "role": "rider"})
        resp.raise_for_status()
        print_check(f"Registered Driver: {driver_id}, Rider: {rider_id}")

        # 2. SETUP: Driver becomes available
        print_status("Updating driver location...")
        loc_data = {"driver_id": driver_id, "lat": 10.0, "lon": 10.0, "available": True}
        resp = requests.post(f"{BASE_URL}/drivers/location", json=loc_data)
        resp.raise_for_status()
        print_check(f"Driver {driver_id} is now available.")

        # 3. SETUP: Request a ride
        print_status("Requesting ride...")
        ride_req = {
            "rider_id": rider_id,
            "pickup_lat": 10.01,
            "pickup_lon": 10.01,
            "dest_lat": 10.05,  # Added destination lat
            "dest_lon": 10.05   # Added destination lon
        }
        resp = requests.post(f"{BASE_URL}/rides/request", json=ride_req)
        resp.raise_for_status()
        ride_id = resp.json().get("ride_id")
        ride_key = f"ride:{ride_id}"
        print_check(f"Ride {ride_id} created and matched with {driver_id}")

        # 4. SETUP: Start the trip
        print_status("Starting trip...")
        resp = requests.post(f"{BASE_URL}/trips/{ride_id}/start")
        resp.raise_for_status()
        print_check(f"Trip {ride_id} is 'ongoing'.")

        # 5. THE TEST: Complete the trip (triggers 2PC)
        print_status(f"Attempting to complete trip {ride_id} (Triggering 2PC)...")
        time.sleep(1) # Give a second for logs to catch up
        resp = requests.post(f"{BASE_URL}/trips/{ride_id}/complete")
        
        # This is the API-level check
        if resp.status_code == 500 and "Transaction aborted" in resp.text:
            print_check("API returned 500: Transaction Aborted (as expected in failure test)")
        elif resp.ok:
            print_check("API returned 200 OK (as expected in happy path test)")
        else:
            print(f"  !!! UNEXPECTED API RESPONSE: {resp.status_code} {resp.text}")
            resp.raise_for_status() # Raise exception if not 200 or 500

    except requests.exceptions.RequestException as e:
        print_status(f"TEST FAILED during HTTP step: {e}")
        return
    finally:
        # 6. VERIFICATION: Check Redis state (This is the most important part)
        print_status("--- Verification (Checking Redis) ---")
        if not ride_id:
            print_check("Test failed before ride_id was created. No verification.")
            return

        ride_status = r.hget(ride_key, "status")
        driver_available = r.sismember("drivers:available", driver_id)

        print_check(f"Redis ride status: '{ride_status}'")
        print_check(f"Redis driver available: {driver_available}")
        
        # Check for atomicity
        if ride_status == "completed" and driver_available:
            print("\n✅  PASSED: Transaction was successful. (Happy Path)")
        elif ride_status == "ongoing" and not driver_available:
            print("\n✅  PASSED: Transaction was aborted. (Failure Path)")
        elif ride_status == "completed" and not driver_available:
            print("\n❌  FAILED: Inconsistent state! Ride completed but driver is not available.")
        elif ride_status == "ongoing" and driver_available:
            print("\n❌  FAILED: Inconsistent state! Ride is ongoing but driver was made available.")
        else:
            print("\n❌  FAILED: Unknown state.")

        # Cleanup
        print_status("Cleaning up test data...")
        r.delete(ride_key, f"user:{driver_id}", f"user:{rider_id}")
        r.zrem("drivers:geo", driver_id)
        r.srem("drivers:available", driver_id)
        print_check("Cleanup complete.")


if __name__ == "__main__":
    # Ensure all services are up and running first
    print("Starting 2PC test in 3 seconds... (Make sure docker compose is running)")
    time.sleep(3)
    test_ride_completion()