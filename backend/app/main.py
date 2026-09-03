from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.db import init_db
from backend.app.api.routes import router

app = FastAPI(title="UX Autopsy", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

@app.on_event("startup")
def startup():
    init_db()
