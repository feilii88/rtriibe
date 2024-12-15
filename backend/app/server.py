from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers.qualification import router as qualification_router

# Create the FastAPI app
app = FastAPI()

# Index route
@app.get("/")
async def index():
    return {"message": "Master Server API"}

app.include_router(qualification_router, prefix="/api")

# Mount static directory
app.mount("/static", StaticFiles(directory="app/static"), name="static") 