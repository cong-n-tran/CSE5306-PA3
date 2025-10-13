
import os, json, time, random, csv, math, statistics, glob
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import requests

# Force headless Matplotlib backend to avoid Tk/Tkinter issues on Windows
try:
    import matplotlib
    matplotlib.use("Agg")
except Exception:
    pass


# ------------------ Config (no CLI needed) ------------------
CANDIDATE_GWS = ["http://localhost:8000", "http://localhost:8101"]
DEFAULT_DRIVERS = 50
PERF_REQUESTS = 200
MATRIX_REQUESTS_LIST = [100, 200, 400, 800, 1600]
MATRIX_CONCURRENCY_LIST = [1, 5, 10, 20]
DRIVER_SWEEP_LIST = [10, 50, 100, 200, 500]
PICKUP_LAT = 32.7357
PICKUP_LON = -97.1081

ROOT_OUTDIR = os.path.join(os.path.dirname(__file__), "results")

# ------------------ HTTP helpers ------------------
def jpost(gw: str, path: str, payload=None) -> requests.Response:
    url = f"{gw}{path}"
    try:
        return requests.post(url, json=payload or {}, timeout=10)
    except requests.exceptions.RequestException as e:
        return type("Resp", (), {"status_code": 599, "text": str(e), "json": lambda: {"error": str(e)}})()

def jget(gw: str, path: str, params=None) -> requests.Response:
    url = f"{gw}{path}"
    try:
        return requests.get(url, params=params or {}, timeout=5)
    except requests.exceptions.RequestException as e:
        return type("Resp", (), {"status_code": 599, "text": str(e), "json": lambda: {"error": str(e)}})()

# ------------------ Detection & Seeding ------------------
def detect_gateway() -> Tuple[str, str]:
    for gw in CANDIDATE_GWS:
        try:
            r = jget(gw, "/docs")
            if r.status_code in (200, 404, 307, 308):
                label = "microservice" if gw.endswith(":8000") else "layered"
                return gw, label
        except Exception:
            pass
    for gw in CANDIDATE_GWS:
        try:
            r = jget(gw, "/health")
            if r.status_code == 200:
                label = "microservice" if gw.endswith(":8000") else "layered"
                return gw, label
        except Exception:
            pass
    raise SystemExit("Could not detect a running gateway. Start microservice (8000) or layered (8101) first.")

def seed_system(gw: str, drivers: int, lat0: float, lon0: float) -> None:
    jpost(gw, "/auth/register", {"user_id": "r", "role": "rider"})
    for i in range(drivers):
        d = f"d{i}"
        jpost(gw, "/auth/register", {"user_id": d, "role": "driver"})
        lat = lat0 + random.random() / 100
        lon = lon0 + random.random() / 100
        jpost(gw, "/drivers/location", {"driver_id": d, "lat": lat, "lon": lon, "available": True})

# ------------------ Bench core ------------------
def ride_cycle(gw: str, lat: float, lon: float):
    t0 = time.perf_counter()
    r = jpost(gw, "/rides/request", {
        "rider_id": "r",
        "pickup_lat": lat, "pickup_lon": lon,
        "dest_lat": lat + 0.01, "dest_lon": lon + 0.01
    })
    t1 = time.perf_counter()
    ok = (r.status_code == 200)
    if ok:
        try:
            ride_id = r.json().get("ride_id")
        except Exception:
            ride_id = None
        if ride_id is None:
            ok = False
        else:
            jpost(gw, f"/trips/{ride_id}/start")
            jpost(gw, f"/trips/{ride_id}/complete")
    latency_ms = (t1 - t0) * 1000.0
    return ok, latency_ms

def run_performance_test(gw: str, N: int, concurrency: int, lat: float, lon: float) -> Dict:
    ok_count = 0
    latencies: List[float] = []

    def worker(_i: int):
        ok, l = ride_cycle(gw, lat, lon)
        return ok, l

    start = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(worker, i) for i in range(N)]
        for fut in as_completed(futures):
            ok, l = fut.result()
            if ok:
                ok_count += 1
            latencies.append(l)
    elapsed = time.time() - start

    throughput = ok_count / elapsed if elapsed > 0 else 0.0
    p50 = statistics.median(latencies) if latencies else math.nan
    p95 = sorted(latencies)[int(0.95 * len(latencies))] if latencies else math.nan

    return {
        "ok": ok_count,
        "total": N,
        "elapsed_s": round(elapsed, 3),
        "throughput_rps": round(throughput, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "concurrency": concurrency
    }

# ------------------ CSV / Plots ------------------
def ensure_outdir(label: str) -> str:
    outdir = os.path.join(ROOT_OUTDIR, label)
    os.makedirs(outdir, exist_ok=True)
    return outdir

def write_csv(rows: List[Dict], path: str):
    if not rows: return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

def plot_matrix(csv_path: str):
    try:
        import matplotlib.pyplot as plt
        import pandas as pd
    except Exception as e:
        print("Plotting skipped (matplotlib/pandas not available):", e)
        return
    df = pd.read_csv(csv_path)
    for metric, fname in [("throughput_rps", "throughput"), ("p50_ms", "latency_p50"), ("p95_ms", "latency_p95")]:
        plt.figure()
        for c in sorted(df["concurrency"].unique()):
            dfc = df[df["concurrency"] == c].sort_values("requests")
            plt.plot(dfc["requests"], dfc[metric], marker="o", label=f"concurrency={c}")
        plt.xlabel("Requests (N)")
        plt.ylabel(metric.replace("_", " "))
        plt.title(f"{metric} vs Requests")
        plt.legend()
        outpng = csv_path.replace(".csv", f"_{fname}.png")
        plt.savefig(outpng, bbox_inches="tight")
        plt.close()
        print(f"Saved plot: {outpng}")

def plot_driver_sweep(csv_path: str):
    try:
        import matplotlib.pyplot as plt
        import pandas as pd
    except Exception as e:
        print("Plotting skipped (matplotlib/pandas not available):", e)
        return
    df = pd.read_csv(csv_path).sort_values("drivers")
    for metric, fname in [("throughput_rps", "throughput"), ("p50_ms", "latency_p50"), ("p95_ms", "latency_p95")]:
        plt.figure()
        plt.plot(df["drivers"], df[metric], marker="o")
        plt.xlabel("Drivers seeded")
        plt.ylabel(metric.replace("_", " "))
        plt.title(f"{metric} vs Driver count")
        outpng = csv_path.replace(".csv", f"_{fname}.png")
        plt.savefig(outpng, bbox_inches="tight")
        plt.close()
        print(f"Saved plot: {outpng}")

def try_overall_comparison(root_outdir: str):
    # If both microservice and layered matrix CSVs exist, create comparative charts
    try:
        import matplotlib.pyplot as plt
        import pandas as pd
    except Exception as e:
        print("Overall comparison skipped (matplotlib/pandas not available):", e)
        return
    micro_csv = os.path.join(root_outdir, "microservice", "results_matrix_microservice.csv")
    layered_csv = os.path.join(root_outdir, "layered", "results_matrix_layered.csv")
    if not (os.path.exists(micro_csv) and os.path.exists(layered_csv)):
        print("Overall comparison: waiting for both matrix CSVs to exist.")
        return
    dm = pd.read_csv(micro_csv)
    dl = pd.read_csv(layered_csv)
    # Compare throughput at concurrency=1 across requests
    m1 = dm[dm["concurrency"] == 1].sort_values("requests")
    l1 = dl[dl["concurrency"] == 1].sort_values("requests")
    if m1.empty or l1.empty:
        print("Overall comparison: missing concurrency=1 rows.")
        return
    # Throughput comparison
    plt.figure()
    plt.plot(m1["requests"], m1["throughput_rps"], marker="o", label="Microservice (c=1)")
    plt.plot(l1["requests"], l1["throughput_rps"], marker="o", label="Layered (c=1)")
    plt.xlabel("Requests (N)")
    plt.ylabel("Throughput (req/s)")
    plt.title("Throughput vs Requests (Microservice vs Layered, concurrency=1)")
    plt.legend()
    outpng = os.path.join(root_outdir, "comparison_throughput_c1.png")
    plt.savefig(outpng, bbox_inches="tight")
    plt.close()
    print(f"Saved comparison plot: {outpng}")
    # p95 latency comparison
    plt.figure()
    plt.plot(m1["requests"], m1["p95_ms"], marker="o", label="Microservice p95 (c=1)")
    plt.plot(l1["requests"], l1["p95_ms"], marker="o", label="Layered p95 (c=1)")
    plt.xlabel("Requests (N)")
    plt.ylabel("Latency p95 (ms)")
    plt.title("p95 Latency vs Requests (Microservice vs Layered, concurrency=1)")
    plt.legend()
    outpng = os.path.join(root_outdir, "comparison_latency_p95_c1.png")
    plt.savefig(outpng, bbox_inches="tight")
    plt.close()
    print(f"Saved comparison plot: {outpng}")

# ------------------ Main workflow ------------------
def main():
    print("Detecting running gateway...")
    gw, label = detect_gateway()
    print(f"Detected: {label} at {gw}")
    outdir = ensure_outdir(label)

    # 1) Performance
    print("Seeding system for performance test...")
    seed_system(gw, DEFAULT_DRIVERS, PICKUP_LAT, PICKUP_LON)
    print("Running performance test...")
    perf = run_performance_test(gw, PERF_REQUESTS, concurrency=1, lat=PICKUP_LAT, lon=PICKUP_LON)
    perf.update({"gw": gw, "label": label, "requests": PERF_REQUESTS, "drivers": DEFAULT_DRIVERS})
    print("Performance:", json.dumps(perf, indent=2))
    perf_csv = os.path.join(outdir, f"results_single_{label}.csv")
    write_csv([perf], perf_csv)
    print(f"Saved: {perf_csv}")

    # 2) Scalability matrix
    print("Seeding system for scalability matrix...")
    seed_system(gw, max(DEFAULT_DRIVERS, 200), PICKUP_LAT, PICKUP_LON)
    rows = []
    for N in MATRIX_REQUESTS_LIST:
        for C in MATRIX_CONCURRENCY_LIST:
            print(f"Matrix run: N={N}, concurrency={C}")
            res = run_performance_test(gw, N, C, PICKUP_LAT, PICKUP_LON)
            res.update({"gw": gw, "label": label, "requests": N, "drivers": max(DEFAULT_DRIVERS, 200)})
            rows.append(res)
    matrix_csv = os.path.join(outdir, f"results_matrix_{label}.csv")
    write_csv(rows, matrix_csv)
    print(f"Saved: {matrix_csv}")
    plot_matrix(matrix_csv)

    # 3) Driver sweep
    print("Running driver-pool sweep...")
    rows = []
    for D in DRIVER_SWEEP_LIST:
        print(f"Seeding {D} drivers...")
        seed_system(gw, D, PICKUP_LAT, PICKUP_LON)
        res = run_performance_test(gw, PERF_REQUESTS, concurrency=10, lat=PICKUP_LAT, lon=PICKUP_LON)
        res.update({"gw": gw, "label": label, "drivers": D, "requests": PERF_REQUESTS, "concurrency": 10})
        rows.append(res)
    sweep_csv = os.path.join(outdir, f"results_driver_sweep_{label}.csv")
    write_csv(rows, sweep_csv)
    print(f"Saved: {sweep_csv}")
    plot_driver_sweep(sweep_csv)

    # 4) If both architectures have matrix CSVs, make overall comparison charts
    try_overall_comparison(ROOT_OUTDIR)

    print("== Summary ==")
    print(f"Performance: {perf['throughput_rps']} req/s, p50={perf['p50_ms']} ms, p95={perf['p95_ms']} ms")
    print(f"Matrix CSV: {matrix_csv}")
    print(f"Driver sweep CSV: {sweep_csv}")
    print(f"Per-architecture outputs in: {outdir}")
    print("If both microservice and layered results exist, comparison charts are in results/comparison_*.png")

if __name__ == "__main__":
    main()
