from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from core import auth, config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["datasets"])

DATASET_STATUS_CREATED = "created"
DATASET_STATUS_PROCESSING = "processing"
DATASET_STATUS_READY = "ready"
DATASET_STATUS_ERROR = "error"

FILE_STATUS_UPLOADED = "uploaded"
FILE_STATUS_PROCESSED = "processed"
FILE_STATUS_ERROR = "error"


class DatasetCreateRequest(BaseModel):
    client_id: str = Field(..., description="Client UUID")
    name: str = Field(..., description="Dataset name")
    notes: Optional[str] = Field(None, description="Optional notes")


class DatasetFileCreateRequest(BaseModel):
    filename: str
    file_type: str
    storage_path: str
    size_bytes: int


class DatasetProcessResponse(BaseModel):
    dataset_id: str
    status: str
    integrity: Dict[str, Any]


def _get_supabase():
    return config.get_supabase_client()


def _require_client_access(
    supabase, current_user: Dict[str, Any], client_id: str
) -> None:
    try:
        access_response = (
            supabase.table("client_user_access")
            .select("client_id")
            .eq("user_id", current_user["app_user_id"])
            .eq("firm_id", current_user["firm_id"])
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as exc:
        logger.exception("Supabase query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Supabase query failed") from exc

    if not access_response.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this client",
        )


def _get_accessible_client_ids(
    supabase, current_user: Dict[str, Any]
) -> List[str]:
    try:
        access_response = (
            supabase.table("client_user_access")
            .select("client_id")
            .eq("user_id", current_user["app_user_id"])
            .eq("firm_id", current_user["firm_id"])
            .execute()
        )
    except Exception as exc:
        logger.exception("Supabase query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Supabase query failed") from exc

    return [row.get("client_id") for row in access_response.data or [] if row.get("client_id")]


def _fetch_dataset(
    supabase, dataset_id: str, firm_id: str
) -> Dict[str, Any]:
    try:
        dataset_response = (
            supabase.table("upload_batches")
            .select("id, client_id, name, notes, status, created_at")
            .eq("id", dataset_id)
            .eq("firm_id", firm_id)
            .execute()
        )
    except Exception as exc:
        logger.exception("Supabase query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Supabase query failed") from exc

    if not dataset_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        )
    return dataset_response.data[0]


def _insert_dataset_with_user_reference(
    supabase, payload: Dict[str, Any]
) -> Dict[str, Any]:
    user_columns = ["created_by", "app_user_id", None]
    last_error: Optional[Exception] = None
    for user_column in user_columns:
        insert_payload = dict(payload)
        if user_column:
            insert_payload[user_column] = payload["__user_id__"]
        insert_payload.pop("__user_id__", None)
        try:
            response = (
                supabase.table("upload_batches")
                .insert(insert_payload)
                .execute()
            )
            if response.data:
                return response.data[0]
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            if user_column and "column" in message and "does not exist" in message:
                continue
            if user_column and user_column in message and "schema cache" in message:
                continue
            if user_column:
                continue
            logger.exception("Supabase query failed: %s", exc)
            raise HTTPException(status_code=500, detail="Supabase query failed") from exc

    logger.exception("Supabase query failed: %s", last_error)
    raise HTTPException(status_code=500, detail="Supabase query failed") from last_error


@router.post("/create")
async def create_dataset(
    payload: DatasetCreateRequest,
    current_user: Dict[str, Any] = Depends(auth.get_current_user),
) -> Dict[str, Any]:
    supabase = _get_supabase()
    _require_client_access(supabase, current_user, payload.client_id)

    insert_payload: Dict[str, Any] = {
        "firm_id": current_user["firm_id"],
        "client_id": payload.client_id,
        "name": payload.name,
        "notes": payload.notes,
        "status": DATASET_STATUS_CREATED,
        "__user_id__": current_user["app_user_id"],
    }

    dataset = _insert_dataset_with_user_reference(supabase, insert_payload)

    return {
        "dataset_id": dataset.get("id"),
        "status": dataset.get("status", DATASET_STATUS_CREATED),
    }


@router.get("")
async def list_datasets(
    current_user: Dict[str, Any] = Depends(auth.get_current_user),
) -> List[Dict[str, Any]]:
    supabase = _get_supabase()
    client_ids = _get_accessible_client_ids(supabase, current_user)
    if not client_ids:
        return []

    try:
        datasets_response = (
            supabase.table("upload_batches")
            .select("id, client_id, name, status, created_at")
            .eq("firm_id", current_user["firm_id"])
            .in_("client_id", client_ids)
            .execute()
        )
    except Exception as exc:
        logger.exception("Supabase query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Supabase query failed") from exc

    return [
        {
            "dataset_id": row.get("id"),
            "client_id": row.get("client_id"),
            "name": row.get("name"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
        }
        for row in datasets_response.data or []
    ]


@router.get("/{dataset_id}")
async def get_dataset_detail(
    dataset_id: str,
    current_user: Dict[str, Any] = Depends(auth.get_current_user),
) -> Dict[str, Any]:
    supabase = _get_supabase()
    dataset = _fetch_dataset(supabase, dataset_id, current_user["firm_id"])
    _require_client_access(supabase, current_user, dataset.get("client_id"))

    try:
        files_response = (
            supabase.table("uploaded_files")
            .select("id, filename, file_type, storage_path, size_bytes, status, created_at")
            .eq("dataset_id", dataset_id)
            .eq("firm_id", current_user["firm_id"])
            .execute()
        )
    except Exception as exc:
        logger.exception("Supabase query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Supabase query failed") from exc

    files = files_response.data or []

    return {
        "dataset_id": dataset.get("id"),
        "client_id": dataset.get("client_id"),
        "name": dataset.get("name"),
        "notes": dataset.get("notes"),
        "status": dataset.get("status"),
        "created_at": dataset.get("created_at"),
        "files": files,
        "integrity": {
            "files_total": len(files),
            "files_processed": 0,
            "errors": [],
            "warnings": [],
        },
    }


@router.post("/{dataset_id}/files")
async def add_dataset_file(
    dataset_id: str,
    payload: DatasetFileCreateRequest,
    current_user: Dict[str, Any] = Depends(auth.get_current_user),
) -> Dict[str, Any]:
    supabase = _get_supabase()
    dataset = _fetch_dataset(supabase, dataset_id, current_user["firm_id"])
    _require_client_access(supabase, current_user, dataset.get("client_id"))

    insert_payload = {
        "firm_id": current_user["firm_id"],
        "client_id": dataset.get("client_id"),
        "dataset_id": dataset_id,
        "filename": payload.filename,
        "file_type": payload.file_type,
        "storage_path": payload.storage_path,
        "size_bytes": payload.size_bytes,
        "status": FILE_STATUS_UPLOADED,
    }

    try:
        file_response = (
            supabase.table("uploaded_files")
            .insert(insert_payload)
            .execute()
        )
    except Exception as exc:
        logger.exception("Supabase query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Supabase query failed") from exc

    if not file_response.data:
        raise HTTPException(status_code=500, detail="Supabase query failed")

    return {"file_id": file_response.data[0].get("id")}


@router.post("/{dataset_id}/process", response_model=DatasetProcessResponse)
async def process_dataset(
    dataset_id: str,
    current_user: Dict[str, Any] = Depends(auth.get_current_user),
) -> DatasetProcessResponse:
    supabase = _get_supabase()
    dataset = _fetch_dataset(supabase, dataset_id, current_user["firm_id"])
    _require_client_access(supabase, current_user, dataset.get("client_id"))

    try:
        supabase.table("upload_batches").update({"status": DATASET_STATUS_READY}).eq(
            "id", dataset_id
        ).eq("firm_id", current_user["firm_id"]).execute()
        files_update_response = (
            supabase.table("uploaded_files")
            .update({"status": FILE_STATUS_PROCESSED})
            .eq("dataset_id", dataset_id)
            .eq("firm_id", current_user["firm_id"])
            .execute()
        )
    except Exception as exc:
        logger.exception("Supabase query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Supabase query failed") from exc

    files_processed = len(files_update_response.data or [])

    return DatasetProcessResponse(
        dataset_id=dataset_id,
        status=DATASET_STATUS_READY,
        integrity={
            "files_total": files_processed,
            "files_processed": files_processed,
            "errors": [],
            "warnings": [],
        },
    )
