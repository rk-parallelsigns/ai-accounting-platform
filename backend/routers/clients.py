from fastapi import APIRouter

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/stub")
async def clients_stub() -> dict:
    return {"status": "not implemented"}
