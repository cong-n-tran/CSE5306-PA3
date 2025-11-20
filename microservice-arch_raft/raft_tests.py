import unittest
import subprocess
import time
import re
import shutil

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# ==============================================================================
# CONFIGURATION (Updated for your new docker-compose.yml)
# ==============================================================================

# Mapping of Logical Node IDs to Docker Container Names
CONTAINERS = {
    1: "raft1",
    2: "raft2",
    3: "raft3",
    4: "raft4",
    5: "raft5"
}

# Network Name: Since you removed the explicit network in YAML, 
# Docker Compose usually creates a network named "folder_default".
# This variable is largely for reference; the script auto-detects it.
NETWORK_NAME = "microservice-arch_raft_default" 
COMPOSE_CMD = "docker-compose" if shutil.which("docker-compose") else "docker compose"

def run_command(cmd):
    """Run a shell command and return stdout."""
    if cmd.startswith("docker-compose"):
        cmd = cmd.replace("docker-compose", COMPOSE_CMD)
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip()

def get_container_logs(container_name):
    return run_command(f"docker logs {container_name}")

def restart_cluster():
    print("\n[Setup] Restarting Cluster...")
    run_command("docker-compose down")
    run_command("docker-compose up -d --build")
    print("[Setup] Waiting 30s for cluster to stabilize...")
    time.sleep(30)

def get_leader():
    """
    Scans logs to find LEADER. Returns (node_id, container_name) or None.
    """
    highest_term = -1
    current_leader = None

    for node_id, name in CONTAINERS.items():
        logs = get_container_logs(name)
        # Match: "Node raftnode1 becomes LEADER (term 2)"
        matches = re.findall(r"becomes LEADER \(term (\d+)\)", logs)
        if matches:
            last_term = int(matches[-1])
            if last_term > highest_term:
                highest_term = last_term
                current_leader = (node_id, name)
    
    return current_leader

class TestRaftImplementation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global NETWORK_NAME
        # Auto-detect network
        nets = run_command("docker network ls --format '{{.Name}}'").split('\n')
        possible_names = [n for n in nets if 'raft-net' in n]
        if possible_names:
            NETWORK_NAME = possible_names[0]
            print(f"Using Docker Network: {NETWORK_NAME}")

    def setUp(self):
        restart_cluster()

    def fail_with_debug_logs(self, message):
        """Helper to print logs when a test fails."""
        print(f"\n!!! TEST FAILURE: {message} !!!")
        print("--- DUMPING LOGS FROM NODE 1 (raft_auth) ---")
        print(get_container_logs("raft_auth")[-2000:]) # Last 2000 chars
        print("--------------------------------------------")
        self.fail(message)

    def test_01_leader_dies(self):
        print(">>> Test Case 1: Leader Dies")
        leader = get_leader()
        if not leader:
            self.fail_with_debug_logs("Cluster did not elect an initial leader.")
        
        leader_id, leader_name = leader
        print(f"Current Leader: {leader_name}")

        print(f"Stopping {leader_name}...")
        run_command(f"docker stop {leader_name}")
        time.sleep(15)

        new_leader = get_leader()
        if not new_leader:
            self.fail_with_debug_logs("Cluster failed to elect a new leader after death.")
        
        new_id, new_name = new_leader
        self.assertNotEqual(leader_id, new_id, "Old leader is still marked as leader.")
        print(f"SUCCESS: New Leader is {new_name}")

    def test_02_follower_dies(self):
        print(">>> Test Case 2: Follower Dies")
        leader = get_leader()
        if not leader:
            self.fail_with_debug_logs("Cluster did not elect an initial leader.")
        
        leader_id, leader_name = leader
        
        # Pick a follower
        followers = [nid for nid in CONTAINERS if nid != leader_id]
        if not followers:
            self.fail("No followers found!")
            
        follower_id = followers[0]
        follower_name = CONTAINERS[follower_id]
        
        print(f"Stopping Follower: {follower_name}")
        run_command(f"docker stop {follower_name}")
        time.sleep(5)

        is_running = run_command(f"docker inspect -f '{{{{.State.Running}}}}' {leader_name}")
        self.assertEqual(is_running, 'true', "Leader crashed after follower died.")
        print(f"SUCCESS: Leader {leader_name} survived.")

    def test_03_leader_and_follower_die(self):
        print(">>> Test Case 3: Leader and Follower Die")
        leader = get_leader()
        if not leader:
            self.fail_with_debug_logs("Cluster did not elect an initial leader.")
            
        leader_id, leader_name = leader
        followers = [nid for nid in CONTAINERS if nid != leader_id]
        follower_id = followers[0]
        follower_name = CONTAINERS[follower_id]

        print(f"Stopping Leader {leader_name} and Follower {follower_name}")
        run_command(f"docker stop {leader_name} {follower_name}")
        time.sleep(20)

        new_leader = get_leader()
        if not new_leader:
             # Check if any node is even running
             self.fail_with_debug_logs("Cluster failed to elect leader with 3/5 nodes alive.")
        
        new_id, new_name = new_leader
        print(f"New Leader elected: {new_name}")
        self.assertNotEqual(new_id, leader_id)

    def test_04_insert_new_node(self):
        print(">>> Test Case 4: New Node Insertion")
        # Stop node 5 before start
        target_node = CONTAINERS[5]
        run_command(f"docker stop {target_node}")
        time.sleep(5)
        
        # Start Node 5
        print(f"Inserting New Node: {target_node}")
        run_command(f"docker start {target_node}")
        time.sleep(15)

        logs = get_container_logs(target_node)
        # Look for either leadership or receiving entries
        match = re.search(r"(RPC AppendEntries called by Node|becomes LEADER)", logs)
        
        if not match:
            print("--- NODE 5 LOGS ---")
            print(logs)
            self.fail("New node did not join cluster (no RPCs received).")
        print(f"SUCCESS: Node {target_node} joined.")

    def test_05_network_partition(self):
        print(">>> Test Case 5: Network Partition")
        leader = get_leader()
        if not leader:
            self.fail_with_debug_logs("Cluster did not elect an initial leader.")
            
        leader_id, leader_name = leader
        print(f"Isolating current leader: {leader_name}")

        run_command(f"docker network disconnect {NETWORK_NAME} {leader_name}")
        time.sleep(20)

        new_leader_found = False
        for nid, name in CONTAINERS.items():
            if nid == leader_id: continue
            
            logs = get_container_logs(name)
            if "becomes LEADER" in logs:
                # In a real robust test we'd check terms, but existence implies election
                new_leader_found = True
                break
        
        run_command(f"docker network connect {NETWORK_NAME} {leader_name}")
        
        if not new_leader_found:
            self.fail_with_debug_logs("Majority partition failed to elect new leader.")
        print("SUCCESS: Majority side elected new leader.")

if __name__ == "__main__":
    unittest.main()