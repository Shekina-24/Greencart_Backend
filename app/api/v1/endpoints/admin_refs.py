from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models import ReferenceKind
from app.schemas import ReferenceValueCreate, ReferenceValueList, ReferenceValueRead, ReferenceValueUpdate
from app.services import audit as audit_service
from app.services import references as references_service

router = APIRouter(prefix="/admin/refs", tags=["admin-refs"])


def _parse_kind(kind: str) -> ReferenceKind:
    try:
        return ReferenceKind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid reference kind") from exc


@router.get("/{kind}", response_model=ReferenceValueList)
async def list_references(
    kind: str = Path(...),
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ReferenceValueList:
    ref_kind = _parse_kind(kind)
    items, total = await references_service.list_reference_values(
        db, kind=ref_kind, limit=limit, offset=offset
    )
    return ReferenceValueList(
        items=[ReferenceValueRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{kind}", response_model=ReferenceValueRead, status_code=status.HTTP_201_CREATED)
async def create_reference(
    request: Request,
    payload: ReferenceValueCreate,
    kind: str = Path(...),
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
) -> ReferenceValueRead:
    ref_kind = _parse_kind(kind)
    try:
        item = await references_service.create_reference_value(db, kind=ref_kind, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="refs.create",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"kind": kind, "id": item.id},
    )
    return ReferenceValueRead.model_validate(item)


@router.put("/{kind}/{value_id}", response_model=ReferenceValueRead)
async def update_reference(
    request: Request,
    kind: str,
    value_id: int,
    payload: ReferenceValueUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
) -> ReferenceValueRead:
    ref_kind = _parse_kind(kind)
    item = await references_service.get_reference_value(db, kind=ref_kind, value_id=value_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reference not found")
    try:
        updated = await references_service.update_reference_value(db, item=item, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="refs.update",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"kind": kind, "id": value_id},
    )
    return ReferenceValueRead.model_validate(updated)


@router.delete("/{kind}/{value_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reference(
    request: Request,
    kind: str,
    value_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
) -> None:
    ref_kind = _parse_kind(kind)
    item = await references_service.get_reference_value(db, kind=ref_kind, value_id=value_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reference not found")
    await references_service.delete_reference_value(db, item=item)
    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="refs.delete",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"kind": kind, "id": value_id},
    )
