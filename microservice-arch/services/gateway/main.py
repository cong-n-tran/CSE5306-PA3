import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

AUTH = os.getenv("AUTH_URL", "http://auth:8001")
LOC = os.getenv("LOCATION_URL", "http://location:8002")
MATCH = os.getenv("MATCHING_URL", "http://matching:8003")
TRIP = os.getenv("TRIP_URL", "http://trip:8004")

app = FastAPI(title="Gateway")

class Register(BaseModel):
    user_id: str
    role: str

class Login(BaseModel):
    user_id: str

class DriverLocation(BaseModel):
    driver_id: str
    lat: float
    lon: float
    available: bool = True

class RideReq(BaseModel):
    rider_id: str
    pickup_lat: float
    pickup_lon: float
    dest_lat: float
    dest_lon: float

@app.post("/auth/register")
async def gw_register(p: Register):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{AUTH}/register", json=p.model_dump())
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.json())
    return r.json()

@app.post("/auth/login")
async def gw_login(p: Login):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{AUTH}/login", json=p.model_dump())
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.json())
    return r.json()

@app.post("/drivers/location")
async def gw_loc(p: DriverLocation):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{LOC}/drivers/location", json=p.model_dump())
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.json())
    return r.json()

@app.post("/rides/request")
async def gw_request(p: RideReq):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{MATCH}/rides/request", json=p.model_dump())
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.json())
    return r.json()

@app.post("/trips/{ride_id}/start")
async def gw_start(ride_id: int):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{TRIP}/trips/{ride_id}/start")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.json())
    return r.json()

@app.post("/trips/{ride_id}/complete")
async def gw_complete(ride_id: int):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{TRIP}/trips/{ride_id}/complete")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.json())
    return r.json()
