
# Distributed Ride-Sharing System

This project is a distributed ride-sharing system, similar to a simplified version of Uber or Lyft.  
It was developed as part of the **CSE 5306 – Distributed Systems** course at the University of Texas at Arlington.

The goal of this project is to design, implement, and evaluate a distributed system using **two different architectures** and compare their performance:
1. **Microservice Architecture (HTTP)**  
2. **Layered Architecture (HTTP)**

Both architectures implement the same idea (ride-sharing system), meet the same functional requirements, and use **Redis** for communication and shared data storage.

---

## 1. Project Overview

The distributed ride-sharing system allows **riders** and **drivers** to interact in real time across multiple nodes (Docker containers).  
Riders can request rides, and drivers update their locations to be matched with nearby riders.

The system has been implemented twice, each with a different architecture:
- **Microservice Architecture:** multiple smaller services that communicate with each other using HTTP requests.
- **Layered Architecture:** a single application divided logically into layers (API, Service, and Data) and deployed as five identical replicas.

Both implementations are containerized using **Docker Compose**, and each runs across **at least 5 nodes** as required.

---

## 2. Functional Requirements

The system supports five main functions:

1. **User Registration and Authentication**  
   - Riders and drivers can register on the system.
   - A simple login endpoint is provided (not real JWT authentication, just a proof of functionality).

2. **Real-Time Matching**  
   - When a rider requests a ride, the system finds the nearest available driver using Redis’s built-in geospatial indexing.

3. **Location Updates**  
   - Drivers can update their locations, and this information is synchronized across all nodes.

4. **Trip Management**  
   - Once a driver is matched, trips can be started and completed.
   - Completing a trip automatically frees up the driver for new requests.

5. **Fault Tolerance**  
   - Redis stores all shared data (users, rides, driver locations).
   - If one service or node fails, others can continue running without losing data.

These functions are consistent across both architectures.

---

## 3. Technologies Used

- **Programming Language:** Python 3.11  
- **Framework:** FastAPI (for building REST APIs)  
- **Database / Shared Store:** Redis  
- **Containerization:** Docker, Docker Compose  
- **Load Testing:** Python script using `requests` module  
- **Operating System:** Linux containers on Docker Desktop (Windows)

---

## 4. System Architecture

### (A) Microservice Architecture

In this version, the system is broken into five independent microservices:
1. **Auth Service** – Handles user registration and login.
2. **Location Service** – Updates and stores driver locations.
3. **Matching Service** – Finds nearby available drivers for ride requests.
4. **Trip Service** – Manages trip lifecycle (start, complete).
5. **Gateway Service** – Acts as the single entry point for all user interactions.

All services communicate using **HTTP requests**, and data is shared through **Redis**.

The diagram below summarizes it:

```

Client → Gateway (HTTP)
↳ Auth Service (HTTP)
↳ Location Service (HTTP)
↳ Matching Service (HTTP)
↳ Trip Service (HTTP)
↳ Redis (Shared State)

```

Each service is containerized and runs on its own port.  
Example ports:
- Gateway: 8000  
- Auth: 8001  
- Location: 8002  
- Matching: 8003  
- Trip: 8004  
- Redis: 6379

Only the gateway is accessed directly; it routes calls to other services.

---

### (B) Layered Architecture

In this version, the entire system is one FastAPI application organized into **layers**:
1. **API Layer** (`/layered/api/`)  
   Handles all HTTP routes (e.g., `/auth/register`, `/rides/request`).
2. **Service Layer** (`/layered/service/`)  
   Contains the business logic for matching, trip management, and location handling.
3. **Data Layer** (`/layered/data/`)  
   Manages database operations and stores everything in Redis.
4. **Config Layer** (`/layered/config/`)  
   Handles environment variables and Redis connection setup.

This single app is then **replicated into five nodes** (containers) using Docker Compose, all connected to the same Redis instance.  
Each node runs on a different port (8101–8105).

All nodes share the same Redis backend, which keeps state synchronized.

```

Client → Node1 (API→Service→Data→Redis)
→ Node2 (API→Service→Data→Redis)
→ Node3 (API→Service→Data→Redis)
→ ...

```

---

## 5. Communication Model

- Both architectures use **HTTP communication**.  
- **Microservices:** Inter-service communication happens over HTTP between containers (Gateway → other services).  
- **Layered:** Communication between layers is done through **function calls** inside the same process (no network cost).

Redis is used as the **shared communication backend** for both designs, ensuring all nodes can read/write shared data.

---

## 6. Data Flow and Storage

### Redis Key Structure:
| Key | Type | Description |
|-----|------|--------------|
| `user:<id>` | Hash | Stores user info like role (rider/driver) |
| `drivers:geo` | Geo | Stores driver coordinates (longitude, latitude) |
| `drivers:available` | Set | Stores all currently available driver IDs |
| `ride:<id>` | Hash | Stores ride info (rider_id, driver_id, status, pickup/destination) |
| `seq:ride` | Counter | Auto-increments ride IDs |

Example commands in Redis:
```

KEYS *
HGETALL ride:1
SMEMBERS drivers:available
GEOPOS drivers:geo bob

````

---

## 7. Running the System

### Requirements
- Docker Desktop running
- Python 3.11 installed (for the evaluation script)

### Run Microservice Architecture
```bash
cd microservice-arch
cp .env.example .env
docker compose up --build
````

Access gateway docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Run Layered Architecture

```bash
cd layered-arch
cp .env.example .env
docker compose up --build
```

Access any node docs:

* [http://localhost:8101/docs](http://localhost:8101/docs)
* [http://localhost:8102/docs](http://localhost:8102/docs)
* [http://localhost:8103/docs](http://localhost:8103/docs)

To stop:

```bash
Ctrl + C
docker compose down
```

---

## 8. Endpoints Overview

### Auth

| Endpoint         | Method | Description                                     |
| ---------------- | ------ | ----------------------------------------------- |
| `/auth/register` | POST   | Register new rider or driver                    |
| `/auth/login`    | POST   | Dummy login endpoint (returns user_id as token) |
| `/me/{user_id}`  | GET    | Get user details                                |

### Drivers

| Endpoint            | Method | Description                             |
| ------------------- | ------ | --------------------------------------- |
| `/drivers/location` | POST   | Update driver location and availability |
| `/drivers/nearby`   | GET    | Get nearby available drivers            |

### Rides

| Endpoint           | Method | Description                                           |
| ------------------ | ------ | ----------------------------------------------------- |
| `/rides/request`   | POST   | Request a new ride (matches rider with nearby driver) |
| `/rides/{ride_id}` | GET    | Get ride details                                      |

### Trips

| Endpoint                    | Method | Description                    |
| --------------------------- | ------ | ------------------------------ |
| `/trips/{ride_id}/start`    | POST   | Start a trip                   |
| `/trips/{ride_id}/complete` | POST   | Complete a trip (frees driver) |

### System

| Endpoint  | Method | Description                                                     |
| --------- | ------ | --------------------------------------------------------------- |
| `/health` | GET    | Returns `{status: ok, node: nodeX}` to show the node is running |

---

## 9. Evaluation and Results

A Python script (`quick_eval.py`) was used to send 200 ride requests to each architecture and measure:

* **Throughput (requests per second)**
* **Latency (p50 and p95 in milliseconds)**

Each architecture was run under identical conditions.

| Architecture        | OK/Total | Throughput (req/s) | p50 (ms) | p95 (ms) |
| ------------------- | -------- | ------------------ | -------- | -------- |
| Microservice (HTTP) | 200/200  | 18.14              | 53.90    | 71.27    |
| Layered (HTTP)      | 200/200  | 44.45              | 22.06    | 28.77    |

### Observations

* The **layered** architecture performed faster (≈2.4× higher throughput) because there’s no inter-service HTTP overhead.
* The **microservice** version had higher latency due to multiple network hops between containers.
* Both achieved full functionality, but with different trade-offs:

  * **Microservice:** modular, easier to scale individual components.
  * **Layered:** simpler, faster, easier to deploy.

---

## 10. Lessons Learned

1. **Architectural trade-offs:**
   Microservices offer clear modular separation but introduce communication overhead.
   Layered systems are easier to manage but less flexible for scaling specific parts.

2. **Redis as shared state:**
   Redis worked efficiently as a single point of truth across all nodes.
   It provided fault tolerance — data persisted even when individual nodes were stopped.

3. **Simplified authentication:**
   A full JWT-based system was unnecessary for this assignment, so simple role-based registration was enough to meet functional requirements.

4. **Containerization:**
   Docker Compose simplified multi-node deployment and ensured consistent environments.

5. **Evaluation:**
   Measuring throughput and latency using Python scripts helped visualize performance differences between architectures.

---

## 11. How Fault Tolerance Works

If one container crashes:

* Data remains safe in Redis.
* Other nodes continue handling requests.
* When the failed container restarts, it reconnects to Redis and resumes operation.

Example:

```bash
docker compose stop matching
# System still runs (Redis keeps data)
docker compose start matching
```

---

## 12. Conclusion

Both implementations successfully meet all five functional requirements:

1. User Registration and Authentication
2. Real-Time Matching
3. Location Updates
4. Trip Management
5. Fault Tolerance

The **layered architecture** was simpler and faster for this use case, while the **microservice architecture** provided better separation of concerns and realism for large-scale systems.

This project demonstrates how different architectures impact performance and complexity in distributed system design.

---

## 13. Author

**Faisal Ahmad - 1002239354**

M.S. in Computer Science, University of Texas at Arlington

Course: CSE 5306 — Distributed Systems
