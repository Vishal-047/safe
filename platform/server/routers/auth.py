import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import Annotated
from fastapi.security import OAuth2PasswordBearer
from server.services.auth_service import create_jwt, verify_jwt
from server.services.github_service import validate_token, exchange_code_for_token

logger = logging.getLogger('safelane.platform')
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

class TokenRequest(BaseModel):
    pat: str

@router.get("/config")
async def get_auth_config():
    client_id = os.environ.get("GITHUB_CLIENT_ID", "")
    return {
        "oauth_enabled": bool(client_id),
        "github_client_id": client_id
    }

@router.get("/github/login")
async def github_login(request: Request):
    client_id = os.environ.get("GITHUB_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=400, detail="GITHUB_CLIENT_ID is not configured on the server")
    redirect_uri = os.environ.get("GITHUB_REDIRECT_URI")
    if not redirect_uri:
        base_url = str(request.base_url).rstrip('/')
        base_url = base_url.replace("0.0.0.0", "localhost")
        redirect_uri = f"{base_url}/api/auth/github/callback"
    scope = "repo workflow read:user user:email"
    url = f"https://github.com/login/oauth/authorize?client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}"
    return RedirectResponse(url)

@router.get("/github/callback")
async def github_callback(code: str | None = None, error: str | None = None):
    if error or not code:
        err_msg = error or "No authorization code provided by GitHub"
        return HTMLResponse(content=f"<script>window.location.href='/?error={err_msg}';</script>")
    
    try:
        access_token = await exchange_code_for_token(code)
        user_info = await validate_token(access_token)
        jwt_token = create_jwt({
            "github_username": user_info["login"],
            "github_id": user_info["id"],
            "pat": access_token
        })
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>SafeLane — Authorizing...</title></head>
        <body style="background:#0b0f17; color:#fff; font-family:sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0;">
            <div style="text-align:center;">
                <h2>Authorizing SafeLane...</h2>
                <p>Redirecting back to dashboard...</p>
                <script>
                    localStorage.setItem('safelane_token', '{jwt_token}');
                    window.location.href = '/?token={jwt_token}';
                </script>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"OAuth error: {e}")
        err_str = str(e).replace("'", "\\'")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Authorization Failed</title></head>
        <body style="background:#0b0f17; color:#f87171; font-family:sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0;">
            <div style="text-align:center;">
                <h2>Authorization Error</h2>
                <p>{err_str}</p>
                <p><a href="/" style="color:#60a5fa;">Click here to return to SafeLane Setup</a></p>
                <script>
                    setTimeout(() => {{ window.location.href = '/?error={err_str}'; }}, 3000);
                </script>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=400)

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
