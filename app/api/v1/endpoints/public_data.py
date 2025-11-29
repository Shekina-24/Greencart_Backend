from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.api import deps
from app.config import settings
from app.jobs import import_public_data

router = APIRouter()


DATASETS: dict[str, dict[str, Any]] = {
    "producers": {"filename": "public_producers.json", "importer": import_public_data.import_producers},
    "consumption": {"filename": "consumption_stats.json", "importer": import_public_data.import_consumption},
    "waste": {"filename": "waste_stats.json", "importer": import_public_data.import_waste},
}


def _dataset_path(dataset: str) -> Path:
    filename = DATASETS[dataset]["filename"]
    base = Path(settings.reports_storage_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / filename


def _read_sample(path: Path, limit: int = 5) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[:limit]
    except Exception:
        return []
    return []


def _status(dataset: str) -> dict[str, Any]:
    path = _dataset_path(dataset)
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    updated_at = path.stat().st_mtime if exists else None
    sample = _read_sample(path)
    if exists:
        try:
            count = len(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            count = 0
    else:
        count = 0
    return {
        "dataset": dataset,
        "path": str(path),
        "exists": exists,
        "size_bytes": size,
        "updated_at": updated_at,
        "count": count,
        "sample": sample,
    }


@router.get("/admin/public-data")
async def list_public_datasets(current_admin=Depends(deps.get_current_admin)) -> dict:
    items = [_status(name) for name in DATASETS]
    return {"items": items}


@router.post("/admin/public-data/{dataset}/upload")
async def upload_public_dataset(
    dataset: str,
    file: UploadFile = File(...),
    current_admin=Depends(deps.get_current_admin),
):
    if dataset not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")

    dest = _dataset_path(dataset)
    tmp_path = dest.with_suffix(".upload")
    content = await file.read()
    tmp_path.write_bytes(content)

    importer = DATASETS[dataset]["importer"]
    try:
        await run_in_threadpool(importer, tmp_path, dest)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    return _status(dataset)


@router.get("/public/producers")
async def public_producers() -> dict:
    dataset = "producers"
    path = _dataset_path(dataset)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No public producers data")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load data: {exc}") from exc
    return {"items": data}
