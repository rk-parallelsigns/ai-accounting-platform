from fastapi import FastAPI

from routers import clients, datasets, reports

app = FastAPI()


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/me")
async def get_me() -> dict:
    return {"status": "not implemented"}


@app.get("/clients")
async def list_clients() -> dict:
    return {"status": "not implemented"}


app.include_router(datasets.router)
app.include_router(clients.router)
app.include_router(reports.router)
