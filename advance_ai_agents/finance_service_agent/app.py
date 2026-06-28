from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from utils.redisCache import lifespan, get_cache
from routes.stockRoutes import router as stock_router
from routes.agentRoutes import router as agent_router

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8501",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(stock_router)
app.include_router(agent_router)