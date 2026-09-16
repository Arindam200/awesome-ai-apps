from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from utils.redisCache import lifespan, get_cache
from utils.cors import get_allowed_origins
from routes.stockRoutes import router as stock_router
from routes.agentRoutes import router as agent_router

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock_router)
app.include_router(agent_router)