from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from layered.service import core

router = APIRouter()

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

@router.get("/")
def root():
    return {"ok": True}

@router.post("/auth/register")
def register(p: Register):
    try:
        core.register_user(p.user_id, p.role)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/auth/login")
def login(p: Login):
    try:
        token = core.login_user(p.user_id)
        return {"token": token}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/drivers/location")
def loc(p: DriverLocation):
    core.update_driver_location(p.driver_id, p.lat, p.lon, p.available)
    return {"ok": True}

@router.post("/rides/request")
def ride(p: RideReq):
    try:
        return core.request_ride(p.rider_id, p.pickup_lat, p.pickup_lon, p.dest_lat, p.dest_lon)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/rides/{ride_id}")
def get_ride(ride_id: int):
    from layered.data import repo
    data = repo.get_ride(ride_id)
    if not data:
        raise HTTPException(status_code=404, detail="ride not found")
    return {"ride_id": ride_id, **data}

@router.post("/trips/{ride_id}/start")
def start(ride_id: int):
    try:
        return core.start_trip(ride_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/trips/{ride_id}/complete")
def complete(ride_id: int):
    try:
        return core.complete_trip(ride_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
