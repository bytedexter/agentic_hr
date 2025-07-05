from fastapi import FastAPI
from app.routers import jd_router

app = FastAPI(title="JD Scanner with Self-Reflection", version="1.0")

app.include_router(jd_router.router)
