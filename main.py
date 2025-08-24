from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from endpoints.auth import router as auth_router

app = FastAPI()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Forwarded-Proto"] = "https"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check():
    return {"status": "running", "version": "1.0.0"}

app.include_router(auth_router)
