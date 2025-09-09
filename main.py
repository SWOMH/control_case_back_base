from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from endpoints.auth.auth import router as auth_router
from endpoints.documents.document import router as document_router
from endpoints.news.news import router as news_router
from endpoints.stages.stage import router as stage_router
from endpoints.payments_schedule.schedule import router as schedule_router
from endpoints.payments_schedule.schedule_admin import router as schedule_admin_router



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
app.include_router(document_router)
app.include_router(news_router)
app.include_router(stage_router)
app.include_router(schedule_router)
app.include_router(schedule_admin_router)
