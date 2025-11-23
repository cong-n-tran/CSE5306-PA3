import unittest
import subprocess
import time
import re
import shutil
import sys
import os

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Mapping of Logical Node IDs to Docker Container Names
CONTAINERS = {
    1: "raft1",
    2: "raft2",
    3: "raft3",
    4: "raft4",
    5: "raft5"
}

# Auto-detect docker compose command
COMPOSE_CMD = "docker-compose" if shutil.which("docker-compose") else "docker compose"
NETWORK_NAME = "microservice-arch_raft_default" 

# ==============================================================================
# UNIVERSAL HELPER FUNCTIONS
# ==============================================================================

def run_command(cmd):
    """Run a shell command and return stdout, compatible with Windows/Mac/Linux."""
    if cmd.startswith("docker-compose"):
        cmd = cmd.replace("docker-compose", COMPOSE_CMD)
        
    # Run command
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Command failed: {cmd}\nError: {e}")
        return ""

def clean_output(output):
    """
    Universal cleaner. 
    Removes single quotes (Mac/Linux artifact) and double quotes (Windows artifact).
    """
    if not output:
        return ""
    return output.strip().strip("'").strip('"')

def is_container_running(container_name):
    """
    Cross-platform check if a container is running.
    Uses double quotes for the format string to satisfy Windows CMD and Linux Bash.
    """
    # NOTE: We use double quotes around the format string for Windows compatibility
    cmd = f'docker inspect -f "{{{{.State.Running}}}}" {container_name}'
    output = run_command(cmd)
    cleaned = clean_output(output).lower()
    return cleaned == 'true'

def get_container_logs(container_name):
    return run_command(f"docker logs {container_name}")

def restart_cluster():
    print("\n[Setup] Restarting Cluster...")
    run_command("docker-compose down")
    run_command("docker-compose up -d --build")
    print("[Setup] Waiting 20s for cluster to stabilize...")
    time.sleep(20)

def get_leader():
    """
    Scans logs to find LEADER. Returns (node_id, container_name) or None.
    """
    highest_term = -1
    current_leader = None

    for node_id, name in CONTAINERS.items():
        logs = get_container_logs(name)
        # Match: "Node raftnode1 becomes LEADER (term 2)" or "Node 1 becomes..."
        # Adjust regex to be permissive of different log formats
        matches = re.findall(r"becomes LEADER \(term (\d+)\)", logs)
        if matches:
            last_term = int(matches[-1])
            if last_term > highest_term:
                highest_term = last_term
                current_leader = (node_id, name)
    
    return current_leader

# ==============================================================================
# TEST SUITE
# ==============================================================================

class TestRaftImplementation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global NETWORK_NAME
        print(f"OS Platform: {sys.platform}")
        print(f"Using Compose Command: {COMPOSE_CMD}")
        
        # Attempt to auto-detect network name
        nets = run_command("docker network ls --format \"{{.Name}}\"").split('\n')
        possible_names = [n for n in nets if 'raft' in n and 'default' in n] # looser match
        if possible_names:
            NETWORK_NAME = possible_names[0].strip()
            print(f"Auto-detected Network: {NETWORK_NAME}")
        else:
            print(f"Warning: Using default network name: {NETWORK_NAME}")

    def setUp(self):
        restart_cluster()

    def fail_with_debug_logs(self, message):
        print(f"\n!!! TEST FAILURE: {message} !!!")
        print("--- DUMPING LOGS FROM NODE 1 (raft1) ---")
        print(get_container_logs("raft1")[-2000:]) 
        print("----------------------------------------")
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

        # UNIVERSAL CHECK:
        running = is_container_running(leader_name)
        self.assertTrue(running, f"Leader {leader_name} crashed after follower died.")
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
            # Only count if they claimed leadership RECENTLY (check term logic ideally, but existence works for basic test)
            if "becomes LEADER" in logs:
                new_leader_found = True
                break
        
        # Cleanup
        run_command(f"docker network connect {NETWORK_NAME} {leader_name}")
        
        if not new_leader_found:
            self.fail_with_debug_logs("Majority partition failed to elect new leader.")
        print("SUCCESS: Majority side elected new leader.")

if __name__ == "__main__":
    unittest.main()