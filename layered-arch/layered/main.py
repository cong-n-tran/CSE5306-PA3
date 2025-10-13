from fastapi import FastAPI
from layered.api.routes import router
from layered.config.settings import get_settings

app = FastAPI(title="Layered Ride-Sharing (HTTP)")
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok", "node": get_settings().node_id}
