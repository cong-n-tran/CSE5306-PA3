import os
from fastapi import FastAPI, HTTPException
import redis

import grpc
from concurrent import futures
import twophase_pb2
import twophase_pb2_grpc
import threading
import uuid

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
app = FastAPI(title="Trip Service")

# This is our Participant Servicer class (for this service's OWN data)
class ParticipantServicer(twophase_pb2_grpc.ParticipantServicer):
    def __init__(self, db_conn):
        self.r = db_conn
        self.pending_transactions = {}

    def VoteRequest(self, request, context):
        tx_id = request.transaction_id
        ride_id = request.ride_id
        print(f"[Trip: {tx_id}] Received VoteRequest for ride {ride_id}")

        # Our "vote" logic: does this ride exist?
        key = f"ride:{ride_id}"
        if self.r.exists(key):
            self.pending_transactions[tx_id] = ride_id
            print(f"[Trip: {tx_id}] Voting COMMIT")
            return twophase_pb2.VoteReply(vote_commit=True)
        else:
            print(f"[Trip: {tx_id}] Ride not found. Voting ABORT")
            return twophase_pb2.VoteReply(vote_commit=False)

    def GlobalCommit(self, request, context):
        tx_id = request.transaction_id
        print(f"[Trip: {tx_id}] Received GlobalCommit")
        
        ride_id = self.pending_transactions.pop(tx_id, None)
        
        if ride_id:
            print(f"[Trip: {tx_id}] Committing: Setting ride {ride_id} to completed")
            # This is the actual work
            key = f"ride:{ride_id}"
            self.r.hset(key, mapping={"status": "completed"})
        else:
            print(f"[Trip: {tx_id}] WARNING: No pending transaction found for commit.")
            
        return twophase_pb2.GlobalCommitReply()

    def GlobalAbort(self, request, context):
        tx_id = request.transaction_id
        print(f"[Trip: {tx_id}] Received GlobalAbort")
        
        self.pending_transactions.pop(tx_id, None)
        print(f"[Trip: {tx_id}] Aborted transaction.")
        return twophase_pb2.GlobalAbortReply()

# Function to run the gRPC server
def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    twophase_pb2_grpc.add_ParticipantServicer_to_server(ParticipantServicer(r), server)
    
    # Using port 50051 as planned (for intra-node communication)
    port = "50051"
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"Trip gRPC Participant server started on port {port}")
    server.wait_for_termination()

# Start the gRPC server in a separate thread when FastAPI starts
@app.on_event("startup")
def startup_event():
    threading.Thread(target=serve_grpc, daemon=True).start()

@app.post("/trips/{ride_id}/start")
def start_trip(ride_id: int):
    key = f"ride:{ride_id}"
    if not r.exists(key):
        raise HTTPException(status_code=404, detail="ride not found")
    r.hset(key, mapping={"status": "ongoing"})
    return {"ride_id": ride_id, "status": "ongoing"}

@app.post("/trips/{ride_id}/complete")
def complete_trip(ride_id: int):
    # This is now the 2PC COORDINATOR logic
    
    # 1. Get transaction data
    key = f"ride:{ride_id}"
    if not r.exists(key):
        raise HTTPException(status_code=404, detail="ride not found")
    
    data = r.hgetall(key)
    driver_id = data.get("driver_id")
    
    if not driver_id:
        # Cannot do 2PC without a driver to make available
        raise HTTPException(status_code=400, detail="Driver ID missing from ride")

    tx_id = str(uuid.uuid4())
    print(f"[Coordinator: {tx_id}] Starting 2PC for ride {ride_id}")

    # 2. Setup gRPC channels and stubs
    # Participant 1: Our own gRPC server (intra-node)
    channel_self = grpc.insecure_channel("localhost:50051")
    stub_self = twophase_pb2_grpc.ParticipantStub(channel_self)
    
    # Participant 2: The Location service (inter-node)
    # We use the docker compose service name 'location'
    channel_location = grpc.insecure_channel("location:50052")
    stub_location = twophase_pb2_grpc.ParticipantStub(channel_location)

    participants = [
        ("Trip", stub_self),
        ("Location", stub_location)
    ]
    
    vote_args = twophase_pb2.VoteRequestArgs(
        transaction_id=tx_id,
        ride_id=str(ride_id),
        driver_id=driver_id
    )

    # 3. PHASE 1: VOTING
    print(f"[Coordinator: {tx_id}] --- Voting Phase ---")
    all_votes_commit = True
    votes = []
    
    for name, stub in participants:
        try:
            print(f"[Coordinator: {tx_id}] Sending VoteRequest to {name}")
            reply = stub.VoteRequest(vote_args, timeout=2.0)
            print(f"[Coordinator: {tx_id}] Received vote from {name}: {'COMMIT' if reply.vote_commit else 'ABORT'}")
            votes.append(reply.vote_commit)
            if not reply.vote_commit:
                all_votes_commit = False
        except grpc.RpcError as e:
            print(f"[Coordinator: {tx_id}] RPC failed for {name}: {e.details()}")
            all_votes_commit = False
            votes.append(False)

    # 4. PHASE 2: DECISION
    print(f"[Coordinator: {tx_id}] --- Decision Phase ---")
    if all_votes_commit:
        # Send GlobalCommit
        print(f"[Coordinator: {tx_id}] Decision: GLOBAL COMMIT")
        commit_args = twophase_pb2.GlobalCommitArgs(
            transaction_id=tx_id,
            ride_id=str(ride_id),
            driver_id=driver_id
        )
        for name, stub in participants:
            try:
                print(f"[Coordinator: {tx_id}] Sending GlobalCommit to {name}")
                stub.GlobalCommit(commit_args, timeout=2.0)
            except grpc.RpcError as e:
                # This is a problem (a participant might not commit)
                # In a real system, you'd need a recovery protocol
                print(f"[Coordinator: {tx_id}] CRITICAL: GlobalCommit failed for {name}: {e.details()}")
        
        return {"ride_id": ride_id, "status": "completed", "note": "Transaction committed"}
        
    else:
        # Send GlobalAbort
        print(f"[Coordinator: {tx_id}] Decision: GLOBAL ABORT")
        abort_args = twophase_pb2.GlobalAbortArgs(transaction_id=tx_id)
        
        for name, stub in participants:
            # We only send abort to participants who *might* have voted commit
            # (or if we just failed to reach them)
            try:
                print(f"[Coordinator: {tx_id}] Sending GlobalAbort to {name}")
                stub.GlobalAbort(abort_args, timeout=2.0)
            except grpc.RpcError as e:
                print(f"[Coordinator: {tx_id}] GlobalAbort failed for {name}: {e.details()}")

        raise HTTPException(status_code=500, detail="Transaction aborted by a participant")