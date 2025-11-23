# Distributed Ride-Sharing System (CSE5306 - Project Assignment 3)

## Author Information
* **Student 1:** Cong Tran (ID: 1002046419)
* **Student 2:** Mohamed Mohamed (ID: 1001375427)
* **GitHub Repository:** https://github.com/cong-n-tran/CSE5306-PA3

---

## Overview
This project implements distributed consensus and transaction protocols within a microservice architecture:
1.  **Two-Phase Commit (2PC):** Ensures atomic ride completion across the **Trip** and **Location** services.
2.  **Raft Consensus:** Implements a 5-node Raft cluster to manage leader election and log replication for high availability.

---

## Part 1: Two-Phase Commit (2PC) Implementation

The 2PC protocol ensures that when a ride is completed, the status update in the Trip service and the driver availability update in the Location service happen atomically.

### How to Compile and Run (2PC)
1.  **Navigate** to the `microservice-arch` folder.
2.  **Start the System** using Docker Compose:
    ```bash
    cd microservice-arch
    docker compose up --build
    ```
3.  **Run the Test Script:**
    Open a new terminal and run the provided Python test script to verify atomicity:
    ```bash
    python test_2pc.py
    ```
    *This script simulates a ride lifecycle and triggers the global commit/abort transaction.*

### 2PC Implementation Details
*   **Coordinator:** Hosted in `services/trip_service`. It initiates the transaction on the `/trips/{id}/complete` endpoint.
*   **Participants:** The **Trip Service** (managing its own local commit) and **Location Service** (managing driver availability).
*   **Communication:** gRPC is used for all `VoteRequest`, `GlobalCommit`, and `GlobalAbort` messages.

---

## Part 2: Raft Implementation

We implemented a custom 5-node Raft cluster that handles Leader Election, Log Replication, and Network Partitions.

### How to Compile and Run (Raft)
1.  **Navigate** to the `microservice-arch_raft` folder.
2.  **Start the Cluster:**
    ```bash
    cd microservice-arch_raft
    docker compose up --build -d
    ```
    *This starts 5 Raft nodes (`raft1` to `raft5`) alongside the microservices.*

### Running the 5 Test Cases
We have provided a comprehensive Python test suite (`raft_tests.py`) that verifies the 5 required scenarios:
1.  Leader Death (Re-election)
2.  Follower Death (Availability)
3.  Leader + Follower Death (Quorum Safety)
4.  New Node Insertion (Log Replication)
5.  Network Partition (Split-Brain Safety)

**To run the tests:**
```bash
python raft_tests.py