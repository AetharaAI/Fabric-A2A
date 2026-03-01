"""
Fabric A2A - Admin Key Management Routes
Plug these into your existing server.py FastAPI app.

Usage in server.py:
    from admin_routes import create_admin_router

    admin_router = create_admin_router(auth)
    app.include_router(admin_router, prefix="/admin")
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field

from auth import FabricAuth, KeyScope

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class CreateKeyRequest(BaseModel):
    name: str = Field(..., description="Human-readable name for this key", example="My Agent Production Key")
    owner_id: str = Field(..., description="Agent ID or user identifier", example="percy")
    scope: KeyScope = Field(KeyScope.FULL, description="Access scope for this key")
    expires_in_days: Optional[int] = Field(None, description="Days until expiry. Null = never expires", example=365)
    rate_limit_rpm: int = Field(60, description="Max requests per minute", ge=1, le=10000)
    allowed_agents: List[str] = Field(default_factory=list, description="Restrict to specific agent IDs. Empty = all agents")
    test: bool = Field(False, description="Generate a test key (fab_sk_test_...) instead of live key")
    metadata: dict = Field(default_factory=dict, description="Optional metadata (app name, environment, etc.)")


class CreateKeyResponse(BaseModel):
    """
    The full API key is ONLY shown in this response.
    It is hashed and never stored in plaintext.
    Save it now — you cannot retrieve it again.
    """
    key: str = Field(..., description="Your API key. Save this now — shown ONCE only.")
    id: str
    name: str
    prefix: str = Field(..., description="Non-secret prefix shown in key listings")
    scope: KeyScope
    owner_id: str
    created_at: datetime
    expires_at: Optional[datetime]
    rate_limit_rpm: int
    test: bool


class KeySummary(BaseModel):
    """Safe key listing — never exposes the raw key"""
    id: str
    name: str
    prefix: str
    scope: KeyScope
    owner_id: str
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    revoked: bool
    rate_limit_rpm: int
    allowed_agents: List[str]


class RevokeResponse(BaseModel):
    ok: bool
    key_id: str
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Router factory
# ─────────────────────────────────────────────────────────────────────────────

def create_admin_router(auth: FabricAuth) -> APIRouter:
    """
    Returns an APIRouter with all key management endpoints.

    Mount it in server.py:
        admin_router = create_admin_router(auth)
        app.include_router(admin_router, prefix="/admin", tags=["Key Management"])
    """
    router = APIRouter()

    def _require_admin(request: Request):
        """Dependency: ensures the caller is authenticated as admin or master key"""
        auth_result = getattr(request.state, "auth", None)
        if not auth_result:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if auth_result.method == "master_key":
            return auth_result
        if auth_result.api_key and auth_result.api_key.scope == KeyScope.ADMIN:
            return auth_result
        raise HTTPException(status_code=403, detail="Admin scope required")

    # ── POST /admin/keys ─────────────────────────────────────────────────────

    @router.post(
        "/keys",
        response_model=CreateKeyResponse,
        summary="Create API Key",
        description="""
Create a new Fabric API key.

**The full key is returned ONCE in this response and never stored in plaintext.**
Save it immediately.

Requires: Master key (`FABRIC_ADMIN_KEY`) or an API key with `admin` scope.
        """,
    )
    async def create_key(
        body: CreateKeyRequest,
        request: Request,
        _: None = Depends(_require_admin),
    ):
        full_key, api_key = await auth.create_key(
            name=body.name,
            owner_id=body.owner_id,
            scope=body.scope,
            expires_in_days=body.expires_in_days,
            rate_limit_rpm=body.rate_limit_rpm,
            allowed_agents=body.allowed_agents,
            test=body.test,
            metadata=body.metadata,
        )

        return CreateKeyResponse(
            key=full_key,
            id=api_key.id,
            name=api_key.name,
            prefix=api_key.key_prefix,
            scope=api_key.scope,
            owner_id=api_key.owner_id,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            rate_limit_rpm=api_key.rate_limit_rpm,
            test=api_key.is_test_key,
        )

    # ── GET /admin/keys ──────────────────────────────────────────────────────

    @router.get(
        "/keys",
        response_model=List[KeySummary],
        summary="List API Keys",
        description="List all API keys. Master key sees all; admin key sees own keys.",
    )
    async def list_keys(
        request: Request,
        owner_id: Optional[str] = None,
        _: None = Depends(_require_admin),
    ):
        auth_result = request.state.auth

        # Non-master admin keys can only see their own keys
        if auth_result.method != "master_key" and not owner_id:
            owner_id = auth_result.api_key.owner_id

        keys = await auth.list_keys(owner_id=owner_id)

        return [
            KeySummary(
                id=k.id,
                name=k.name,
                prefix=k.key_prefix,
                scope=k.scope,
                owner_id=k.owner_id,
                created_at=k.created_at,
                expires_at=k.expires_at,
                last_used_at=k.last_used_at,
                revoked=k.revoked,
                rate_limit_rpm=k.rate_limit_rpm,
                allowed_agents=k.allowed_agents,
            )
            for k in keys
        ]

    # ── DELETE /admin/keys/{key_id} ──────────────────────────────────────────

    @router.delete(
        "/keys/{key_id}",
        response_model=RevokeResponse,
        summary="Revoke API Key",
        description="Immediately revoke an API key. Takes effect within cache TTL (~60s).",
    )
    async def revoke_key(
        key_id: str,
        request: Request,
        _: None = Depends(_require_admin),
    ):
        success = await auth.revoke_key(key_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Key {key_id} not found")

        return RevokeResponse(
            ok=True,
            key_id=key_id,
            message="Key revoked. Active requests using this key will fail within 60 seconds.",
        )

    # ── GET /admin/verify ────────────────────────────────────────────────────

    @router.get(
        "/verify",
        summary="Verify Auth",
        description="Test that your key works and see what scope it has.",
    )
    async def verify_auth(request: Request):
        auth_result = getattr(request.state, "auth", None)
        if not auth_result or not auth_result.authenticated:
            raise HTTPException(status_code=401, detail="Not authenticated")

        if auth_result.method == "master_key":
            return {
                "ok": True,
                "method": "master_key",
                "scope": "admin",
                "owner_id": "system",
            }

        key = auth_result.api_key
        return {
            "ok": True,
            "method": "api_key",
            "key_id": key.id,
            "name": key.name,
            "scope": key.scope,
            "owner_id": key.owner_id,
            "rate_limit_rpm": key.rate_limit_rpm,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        }

    return router
