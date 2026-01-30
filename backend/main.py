import logging
from typing import Any, Dict, List

from fastapi import Depends, FastAPI

from core import auth, config
from routers import clients, datasets, reports

app = FastAPI()
logging.basicConfig(level=logging.INFO)


@app.on_event("startup")
async def validate_environment() -> None:
    config.validate_env()


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/me")
async def get_me(current_user: Dict[str, Any] = Depends(auth.get_current_user)) -> Dict[str, Any]:
    return current_user


@app.get("/clients")
async def list_clients(
    current_user: Dict[str, Any] = Depends(auth.get_current_user),
) -> List[Dict[str, Any]]:
    supabase = config.get_supabase_client()
    response = (
        supabase.table("clients")
        .select("id, name, firm_id, client_user_access!inner(user_id, firm_id)")
        .eq("client_user_access.user_id", current_user["app_user_id"])
        .eq("client_user_access.firm_id", current_user["firm_id"])
        .execute()
    )
    clients_payload = [
        {
            "client_id": client.get("id"),
            "name": client.get("name"),
            "firm_id": client.get("firm_id"),
        }
        for client in response.data or []
    ]
    return clients_payload


app.include_router(datasets.router)
app.include_router(clients.router)
app.include_router(reports.router)
