from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Annotated
from fastapi.security import OAuth2PasswordBearer
from platform.server.services.auth_service import create_jwt, verify_jwt
from platform.server.services.github_service import validate_token

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

class TokenRequest(BaseModel):
    pat: str

@router.post("/token")
async def login_for_access_token(req: TokenRequest):
    try:
        user_info = await validate_token(req.pat)
        jwt_token = create_jwt({
            "github_username": user_info["login"],
            "github_id": user_info["id"],
            "pat": req.pat # we temporarily store this in token to use in setup, in a real app would save encrypted in session
        })
        return {"access_token": jwt_token, "token_type": "bearer"}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        return verify_jwt(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/me")
async def read_users_me(current_user: Annotated[dict, Depends(get_current_user)]):
    # Do not return the PAT
    return {
        "github_username": current_user["github_username"],
        "github_id": current_user["github_id"]
    }
