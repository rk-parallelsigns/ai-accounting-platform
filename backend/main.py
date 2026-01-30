import logging
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException

from core import auth, config
from routers import clients, datasets, reports

app = FastAPI()
logging.basicConfig(level=logging.INFO)


@app.on_event("startup")
async def validate_environment() -> None:
    missing = config.validate_env()
    if missing:
        logging.warning("Missing required environment variables: %s", ", ".join(missing))


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
    try:
        access_response = (
            supabase.table("client_user_access")
            .select("client_id")
            .eq("user_id", current_user["app_user_id"])
            .eq("firm_id", current_user["firm_id"])
            .execute()
        )
        client_ids = [row.get("client_id") for row in access_response.data or [] if row.get("client_id")]
        if not client_ids:
            return []

        clients_response = (
            supabase.table("clients")
            .select("id, name, firm_id")
            .in_("id", client_ids)
            .eq("firm_id", current_user["firm_id"])
            .execute()
        )
    except Exception as exc:
        logging.exception("Supabase query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Supabase query failed") from exc

    return [
        {
            "client_id": client.get("id"),
            "name": client.get("name"),
            "firm_id": client.get("firm_id"),
        }
        for client in clients_response.data or []
    ]


app.include_router(datasets.router)
app.include_router(clients.router)
app.include_router(reports.router)
