import os
from fastapi import FastAPI
from pydantic import BaseModel
import redis

import grpc
from concurrent import futures
import twophase_pb2
import twophase_pb2_grpc
import threading


r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
app = FastAPI(title="Location Service")

# This is our Participant Servicer class
class ParticipantServicer(twophase_pb2_grpc.ParticipantServicer):
    def __init__(self, db_conn):
        self.r = db_conn
        # We need to store the driver_id between vote and commit
        self.pending_transactions = {}

    def VoteRequest(self, request, context):
        tx_id = request.transaction_id
        driver_id = request.driver_id
        print(f"[Location: {tx_id}] Received VoteRequest for driver {driver_id}")

        # Our "vote" logic: can we do this?
        # For this simple system, we just check if a driver_id was provided.
        # A real system might check r.exists(f"user:{driver_id}")
        if driver_id:
            # Store the driver_id, ready for commit
            self.pending_transactions[tx_id] = driver_id
            print(f"[Location: {tx_id}] Voting COMMIT")
            return twophase_pb2.VoteReply(vote_commit=True)
        else:
            print(f"[Location: {tx_id}] driver_id missing. Voting ABORT")
            return twophase_pb2.VoteReply(vote_commit=False)

    def GlobalCommit(self, request, context):
        tx_id = request.transaction_id
        print(f"[Location: {tx_id}] Received GlobalCommit")
        
        driver_id = self.pending_transactions.pop(tx_id, None)
        
        if driver_id:
            print(f"[Location: {tx_id}] Committing: Making driver {driver_id} available")
            # This is the actual work
            self.r.sadd("drivers:available", driver_id)
        else:
            print(f"[Location: {tx_id}] WARNING: No pending transaction found for commit.")
            
        return twophase_pb2.GlobalCommitReply()

    def GlobalAbort(self, request, context):
        tx_id = request.transaction_id
        print(f"[Location: {tx_id}] Received GlobalAbort")
        
        # Simple cleanup
        self.pending_transactions.pop(tx_id, None)
        print(f"[Location: {tx_id}] Aborted transaction.")
        return twophase_pb2.GlobalAbortReply()

# Function to run the gRPC server
def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    twophase_pb2_grpc.add_ParticipantServicer_to_server(ParticipantServicer(r), server)
    
    # Using port 50052 as planned in docker-compose
    port = "50052"
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"Location gRPC Participant server started on port {port}")
    server.wait_for_termination()

# Start the gRPC server in a separate thread when FastAPI starts
@app.on_event("startup")
def startup_event():
    threading.Thread(target=serve_grpc, daemon=True).start()

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
