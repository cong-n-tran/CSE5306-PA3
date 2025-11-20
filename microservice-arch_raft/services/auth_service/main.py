import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
app = FastAPI(title="Auth Service")

class Register(BaseModel):
    user_id: str
    role: str  # "rider" or "driver"

class Login(BaseModel):
    user_id: str

@app.post("/register")
def register(payload: Register):
    if payload.role not in {"rider", "driver"}:
        raise HTTPException(status_code=400, detail="role must be rider or driver")
    key = f"user:{payload.user_id}"
    if r.exists(key):
        raise HTTPException(status_code=409, detail="user exists")
    r.hset(key, mapping={"role": payload.role})
    return {"ok": True}

@app.post("/login")
def login(payload: Login):
    key = f"user:{payload.user_id}"
    if not r.exists(key):
        raise HTTPException(status_code=404, detail="user not found")
    return {"token": payload.user_id}

@app.get("/me/{user_id}")
def me(user_id: str):
    data = r.hgetall(f"user:{user_id}")
    if not data:
        raise HTTPException(status_code=404, detail="user not found")
    return {"user_id": user_id, **data}


from raft_client import get_leader

leader = get_leader()
if leader == "raft_auth":
    print("This instance is LEADER")
else:
    print("This instance is FOLLOWER")
