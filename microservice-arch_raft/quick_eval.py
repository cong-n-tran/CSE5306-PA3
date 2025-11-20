# quick_eval_fixed.py  (run while layered stack is up)
import requests, random, time, statistics

GW = "http://localhost:8000"   # LAYERED URL

def jpost(path, payload=None):
    return requests.post(f"{GW}{path}", json=payload or {})

# ----- seed -----
requests.post(f"{GW}/auth/register", json={"user_id":"r","role":"rider"})
for i in range(50):
    d=f"d{i}"
    requests.post(f"{GW}/auth/register", json={"user_id":d,"role":"driver"})
    lat=32.73 + random.random()/100
    lon=-97.11 + random.random()/100
    requests.post(f"{GW}/drivers/location", json={"driver_id":d,"lat":lat,"lon":lon,"available":True})

# ----- load test -----
N = 200
lat, lon = 32.7357, -97.1081
ok = 0
latencies = []
t0 = time.time()
for _ in range(N):
    t_req = time.perf_counter()
    r = jpost("/rides/request", {
        "rider_id":"r",
        "pickup_lat": lat, "pickup_lon": lon,
        "dest_lat": lat+0.01, "dest_lon": lon+0.01
    })
    if r.status_code == 200:
        ok += 1
        ride_id = r.json()["ride_id"]
        # free the driver so next request can match
        jpost(f"/trips/{ride_id}/start")
        jpost(f"/trips/{ride_id}/complete")
    latencies.append((time.perf_counter() - t_req) * 1000.0)  # ms
elapsed = time.time() - t0
throughput = ok / elapsed if elapsed > 0 else 0
p50 = statistics.median(latencies)
p95 = sorted(latencies)[int(0.95 * len(latencies))]

print(f"requests: {N} ok: {ok} elapsed(s): {elapsed:.3f} throughput(req/s): {throughput:.2f}")
print(f"latency ms -> p50: {p50:.2f}  p95: {p95:.2f}")
