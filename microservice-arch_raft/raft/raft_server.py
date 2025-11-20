import os
import time
import random
import threading
import grpc
from concurrent import futures

import raft_pb2
import raft_pb2_grpc

HEARTBEAT_INTERVAL = 1.0
ELECTION_TIMEOUT_MIN = 1.5
ELECTION_TIMEOUT_MAX = 3.0

def log(msg):
    print(msg, flush=True)

class RaftServicer(raft_pb2_grpc.RaftServicer):
    def __init__(self, node):
        self.node = node

    def RequestVote(self, request, context):
        log(f"Node {self.node.node_id} runs RPC RequestVote called by Node {request.candidate_id}")
        return self.node.handle_request_vote(request)

    def AppendEntries(self, request, context):
        log(f"Node {self.node.node_id} runs RPC AppendEntries called by Node {request.leader_id}")
        return self.node.handle_append_entries(request)

class RaftNode:
    def __init__(self, node_id, peers, port):
        self.node_id = node_id
        self.peers = peers
        self.port = port

        self.current_term = 0
        self.voted_for = None

        self.state = "follower"
        self.state_lock = threading.Lock()
        self.leader_id = None
        self.votes_received = set()

        self.log = []  # full log of operations: (op, term, index)
        self.commit_index = -1  # last committed operation

        self.reset_election_timeout()

        self.stop_event = threading.Event()
        threading.Thread(target=self.election_daemon, daemon=True).start()

    # -------------------------------
    # Election Timeout
    # -------------------------------
    def reset_election_timeout(self):
        self.election_timeout = time.time() + random.uniform(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)

    # -------------------------------
    # RPC Handlers
    # -------------------------------
    def handle_request_vote(self, req):
        with self.state_lock:
            if req.term > self.current_term:
                self.current_term = req.term
                self.voted_for = None
                self.state = "follower"

            vote_granted = False
            if req.term < self.current_term:
                vote_granted = False
            else:
                if self.voted_for is None or self.voted_for == req.candidate_id:
                    self.voted_for = req.candidate_id
                    vote_granted = True
                    self.reset_election_timeout()

        return raft_pb2.RequestVoteReply(term=self.current_term, vote_granted=vote_granted)

    def handle_append_entries(self, req):
        """
        req.entries: full log from leader
        req.commit_index: leader's commit index
        """
        with self.state_lock:
            if req.term >= self.current_term:
                self.current_term = req.term
                self.state = "follower"
                self.leader_id = req.leader_id
                self.voted_for = None
                self.reset_election_timeout()

                # Replace follower log with leader's full log
                self.log = list(req.entries)
                self.execute_operations_up_to(req.commit_index)
                self.commit_index = req.commit_index

                return raft_pb2.AppendEntriesReply(term=self.current_term, success=True)
            else:
                return raft_pb2.AppendEntriesReply(term=self.current_term, success=False)

    # -------------------------------
    # Client RPC Calls
    # -------------------------------
    def send_request_vote(self, peer_id, addr):
        log(f"Node {self.node_id} sends RPC RequestVote to Node {peer_id}")
        try:
            with grpc.insecure_channel(addr) as chan:
                stub = raft_pb2_grpc.RaftStub(chan)
                return stub.RequestVote(
                    raft_pb2.RequestVoteRequest(term=self.current_term, candidate_id=self.node_id),
                    timeout=1.0
                )
        except Exception as e:
            log(f"Node {self.node_id} RequestVote to {peer_id} failed: {e}")
            return None

    def send_append_entries(self, peer_id, addr):
        log(f"Node {self.node_id} sends RPC AppendEntries to Node {peer_id}")
        try:
            with grpc.insecure_channel(addr) as chan:
                stub = raft_pb2_grpc.RaftStub(chan)
                return stub.AppendEntries(
                    raft_pb2.AppendEntriesRequest(
                        term=self.current_term,
                        leader_id=self.node_id,
                        entries=self.log,
                        commit_index=self.commit_index
                    ),
                    timeout=1.0
                )
        except Exception as e:
            log(f"Node {self.node_id} AppendEntries to {peer_id} failed: {e}")
            return None

    # -------------------------------
    # Execute committed operations
    # -------------------------------
    def execute_operations_up_to(self, index):
        for i in range(self.commit_index + 1, index + 1):
            entry = self.log[i]
            op, term, idx = entry
            log(f"Node {self.node_id} executes operation {op} at index {idx}")
        self.commit_index = max(self.commit_index, index)

    # -------------------------------
    # Election Logic
    # -------------------------------
    def election_daemon(self):
        while not self.stop_event.is_set():
            now = time.time()

            with self.state_lock:
                state = self.state
                timeout = self.election_timeout

            if state != "leader" and now >= timeout:
                self.start_election()

            time.sleep(0.05)

    def start_election(self):
        with self.state_lock:
            self.state = "candidate"
            self.current_term += 1
            self.voted_for = self.node_id
            self.votes_received = {self.node_id}
            term = self.current_term
            log(f"Node {self.node_id} becomes CANDIDATE (term {term})")
            self.reset_election_timeout()

        threads = []
        responses = []

        def vote(peer_id, addr):
            resp = self.send_request_vote(peer_id, addr)
            if resp:
                responses.append((peer_id, resp))

        for peer_id, addr in self.peers.items():
            t = threading.Thread(target=vote, args=(peer_id, addr))
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=1.2)

        with self.state_lock:
            for (peer_id, resp) in responses:
                if resp.term > self.current_term:
                    self.current_term = resp.term
                    self.state = "follower"
                    self.voted_for = None
                    self.reset_election_timeout()
                    log(f"Node {self.node_id} steps down (higher term {resp.term})")
                    return

                if resp.vote_granted:
                    self.votes_received.add(peer_id)

            majority = len(self.peers) // 2 + 1
            if len(self.votes_received) >= majority:
                self.state = "leader"
                self.leader_id = self.node_id
                log(f"Node {self.node_id} becomes LEADER (term {self.current_term})")
                threading.Thread(target=self.heartbeat_daemon, daemon=True).start()
            else:
                log(f"Node {self.node_id} loses election (votes {len(self.votes_received)}) → FOLLOWER")
                self.state = "follower"
                self.reset_election_timeout()

    # -------------------------------
    # Heartbeats
    # -------------------------------
    def heartbeat_daemon(self):
        while not self.stop_event.is_set():
            with self.state_lock:
                if self.state != "leader":
                    return

            threads = []
            responses = []

            def send(peer_id, addr):
                resp = self.send_append_entries(peer_id, addr)
                if resp:
                    responses.append(resp)

            for peer_id, addr in self.peers.items():
                t = threading.Thread(target=send, args=(peer_id, addr))
                t.start()
                threads.append(t)

            for t in threads:
                t.join(timeout=1.0)

            # Optional: commit entries if majority ACKs (can implement per-op tracking)

            time.sleep(HEARTBEAT_INTERVAL)

# -------------------------------------------------
# Start gRPC Server
# -------------------------------------------------
def start_server():
    NODE_ID = os.getenv("NODE_ID")
    PORT = int(os.getenv("PORT", 50051))
    PEERS = os.getenv("PEERS", "")  # comma separated list "raft2:50052,raft3:50053"

    peers = {}
    if PEERS.strip():
        for entry in PEERS.split(","):
            peer_id, addr = entry.split(":")
            peers[peer_id] = f"{peer_id}:{addr}"

    node = RaftNode(NODE_ID, peers, PORT)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    raft_pb2_grpc.add_RaftServicer_to_server(RaftServicer(node), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()

    log(f"Raft sidecar {NODE_ID} running on port {PORT}, peers={list(peers.keys())}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        node.stop_event.set()
        server.stop(0)

if __name__ == "__main__":
    start_server()
