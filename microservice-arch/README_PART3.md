# Distributed Ride-Sharing System (CSE5306 - Project Assignment 3)

## Author Information

* **Student 1 Name:** Cong Tran
* **Student 1 ID:** 1002046419
* **Student 2 Name:** Mohamed Mohamed
* **Student 2 ID:** 1001375427
* **GitHub Repository:** https://github.com/cong-n-tran/CSE5306-PA3

---

## Part 1: Implementation of Two-Phase Commit (2PC)

This section covers the implementation of the **Two-Phase Commit (2PC)** protocol (Q1 & Q2) within the existing Microservice Architecture. The goal is to ensure the **atomic completion** of a ride, where the ride status is updated in the **Trip Service** and the driver is made available in the **Location Service** simultaneously. 

### How to Compile and Run Your Program

1.  **Dependencies:** Ensure **Docker Desktop** is running on your system.
2.  **Navigate:** Open your terminal and navigate to the root directory of the project (`microservice-arch/`).
3.  **Build and Run:** Execute the following command to build the containers, install dependencies (including gRPC), compile the `.proto` files, and start all services:

    ```bash
    docker compose up --build
    ```
4.  **Access:** The system **Gateway** is accessible at `http://localhost:8000`. You can view the API documentation (Swagger UI) at `http://localhost:8000/docs`.

### 2PC Implementation Details (Q1 & Q2)

The 2PC protocol is implemented for the `POST /trips/{ride_id}/complete` endpoint.

| Component | Role in 2PC | Details |
| :--- | :--- | :--- |
| **Trip Service** (`main.py`) | **Coordinator** & **Participant** | The `/complete` endpoint acts as the Coordinator. It initiates the transaction via gRPC. It *also* hosts a gRPC server (on port **50051**) to manage its own database (Redis) commitment as a Participant (satisfying the intra-node gRPC requirement). |
| **Location Service** (`main.py`) | **Participant** | Hosts a gRPC server on port **50052**. Its responsibility is to check if the driver is valid (**Vote Request**) and then either execute the `r.sadd("drivers:available", ...)` command (**Global Commit**) or do nothing (**Global Abort**). |
| **Communication** | **gRPC** | Services communicate using gRPC for the 2PC protocol, which is used for network transactions between services. The `.proto` file defines the `VoteRequest`, `GlobalCommit`, and `GlobalAbort` messages. |

### Test Verification

To confirm atomicity, check the container logs for the two phases:

1.  **Voting Phase:** The Coordinator prints `Voting COMMIT` or `Voting ABORT` from all participants.
2.  **Decision Phase:** The Coordinator prints `GLOBAL COMMIT` or `GLOBAL ABORT` and sends the final command to all services.
3.  **Atomicity:** If the Coordinator decides to commit, both the ride status in Redis and the driver availability status in Redis must be updated. If it aborts, **neither** should be updated.

### External Sources Referenced

* **gRPC Official Documentation:** For setting up Python stubs and the basic server/client structure.
* **FastAPI Documentation:** For using the `@app.on_event("startup")` hook to run the gRPC server in a separate thread alongside the main Uvicorn server.
* **Redis-Py Documentation:** For understanding how to manage shared state (driver availability and ride status) which the transaction is trying to protect.

---

## Part 2: Implementation of Raft Consensus (Q3, Q4, Q5)

This section will cover the implementation of the Raft distributed consensus algorithm to provide **fault-tolerant, highly-available state replication**. 

### Q3: Leader Election and Consensus

* [**To be completed**]

### Q4: Log Replication and Safety

* [**To be completed**]

### Q5: Test Cases for Raft

* [**To be completed**]
