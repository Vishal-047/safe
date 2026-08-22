import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Annotated
from server.routers.auth import get_current_user
from server.services.db import create_registration, list_registrations, async_session, Registration
from server.services.auth_service import encrypt_pat

router = APIRouter()

class RegistrationCreate(BaseModel):
    owner: str
    repo: str
    azure_search_endpoint: str | None = None
    azure_search_key: str | None = None
    azure_tenant_id: str | None = None
    azure_workspace_id: str | None = None

@router.get("/")
async def get_my_registrations(current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user["github_id"]
    regs = await list_registrations(user_id)
    return [{
        "id": r.id,
        "owner": r.owner,
        "repo": r.repo,
        "is_active": r.is_active,
        "created_at": r.created_at
    } for r in regs]

@router.post("/")
async def create_new_registration(req: RegistrationCreate, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user["github_id"]
    pat = current_user.get("pat")
    
    if not pat:
        raise HTTPException(status_code=401, detail="No PAT in session")
        
    encrypted_pat = encrypt_pat(pat)
    orchestrator_url = os.environ.get("SAFELANE_ORCHESTRATOR_URL")
    if not orchestrator_url:
        raise HTTPException(status_code=500, detail="SAFELANE_ORCHESTRATOR_URL environment variable is required")

    reg = await create_registration(
        user_id=user_id,
        owner=req.owner,
        repo=req.repo,
        encrypted_pat=encrypted_pat,
        orchestrator_url=orchestrator_url,
        azure_search_endpoint=req.azure_search_endpoint,
        azure_search_key=req.azure_search_key,
        azure_tenant_id=req.azure_tenant_id,
        azure_workspace_id=req.azure_workspace_id
    )
    return {"id": reg.id, "status": "created"}

@router.delete("/{id}")
async def deactivate_registration(id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user["github_id"]
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(Registration).where(Registration.id == id, Registration.user_id == user_id))
        reg = result.scalars().first()
        if not reg:
            raise HTTPException(status_code=404, detail="Registration not found")
            
        reg.is_active = False
        await session.commit()
        return {"status": "deactivated"}
