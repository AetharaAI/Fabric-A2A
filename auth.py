"""
Fabric A2A - API Key Authentication System
Replaces static FABRIC_PSK with proper API key management.

Drop-in replacement for whatever PSK check exists in server.py.
Integrates with PostgreSQL for key storage.
Passport-ready: designed to accept Passport JWTs in a future swap.

Usage in server.py:
    from auth import FabricAuth, require_auth

    auth = FabricAuth(database_url=DATABASE_URL, master_key=ADMIN_MASTER_KEY)
    await auth.initialize()

    # In your FastAPI middleware:
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        return await auth.middleware(request, call_next)
"""

import os
import secrets
import hashlib
import hmac
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Key prefix — like OpenAI's sk-... pattern
# fab_sk_live_ for production, fab_sk_test_ for test keys
# ─────────────────────────────────────────────────────────────────────────────
KEY_PREFIX_LIVE = "fab_sk_live_"
KEY_PREFIX_TEST = "fab_sk_test_"
KEY_BYTES = 32  # 256-bit key


class KeyScope(str, Enum):
    """What the key is allowed to do"""
    FULL = "full"               # All tools + all agents
    TOOLS_ONLY = "tools_only"   # Built-in tools only, no agent calls
    READ_ONLY = "read_only"     # List/info operations only
    ADMIN = "admin"             # Key management + full access


@dataclass
class ApiKey:
    """Represents a Fabric API key"""
    id: str
    name: str
    key_prefix: str          # First 12 chars (shown in UI)
    key_hash: str            # SHA-256 of the full key (stored in DB)
    scope: KeyScope
    owner_id: str            # Who created it (agent_id or user)
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    rate_limit_rpm: int = 60   # Requests per minute
    allowed_agents: List[str] = field(default_factory=list)  # Empty = all agents
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        if self.revoked:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    @property
    def is_test_key(self) -> bool:
        return self.key_prefix.startswith(KEY_PREFIX_TEST)


@dataclass
class AuthResult:
    """Result of an auth check"""
    authenticated: bool
    api_key: Optional[ApiKey] = None
    error: Optional[str] = None
    method: str = "api_key"  # "api_key" | "passport_jwt" | "master_key"


# ─────────────────────────────────────────────────────────────────────────────
# Key generation & hashing
# ─────────────────────────────────────────────────────────────────────────────

def generate_api_key(test: bool = False) -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns: (full_key, key_prefix_for_display, key_hash_for_storage)

    Example:
        key, prefix, hash_ = generate_api_key()
        # key = "fab_sk_live_a1b2c3d4...64chars"
        # prefix = "fab_sk_live_a1b2"  (shown in UI, non-secret)
        # hash_ = "sha256:abc123..."   (stored in DB, never the raw key)
    """
    prefix = KEY_PREFIX_TEST if test else KEY_PREFIX_LIVE
    raw = secrets.token_hex(KEY_BYTES)
    full_key = f"{prefix}{raw}"
    display_prefix = full_key[:16]  # Show first 16 chars in UI
    key_hash = _hash_key(full_key)
    return full_key, display_prefix, key_hash


def _hash_key(key: str) -> str:
    """SHA-256 the key for secure storage. We never store the raw key."""
    digest = hashlib.sha256(key.encode()).hexdigest()
    return f"sha256:{digest}"


def _verify_key(provided_key: str, stored_hash: str) -> bool:
    """Constant-time comparison to prevent timing attacks"""
    expected_hash = _hash_key(provided_key)
    return hmac.compare_digest(expected_hash, stored_hash)


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL key store
# ─────────────────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS fabric_api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    key_prefix      TEXT NOT NULL,          -- Non-secret display prefix
    key_hash        TEXT NOT NULL UNIQUE,   -- SHA-256 of full key
    scope           TEXT NOT NULL DEFAULT 'full',
    owner_id        TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    revoked         BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at      TIMESTAMPTZ,
    rate_limit_rpm  INTEGER NOT NULL DEFAULT 60,
    allowed_agents  TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_fabric_api_keys_hash ON fabric_api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_fabric_api_keys_owner ON fabric_api_keys(owner_id);
CREATE INDEX IF NOT EXISTS idx_fabric_api_keys_revoked ON fabric_api_keys(revoked);
"""


class PostgresKeyStore:
    """
    Async PostgreSQL-backed key store.
    Uses asyncpg for performance.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool = None

    async def initialize(self):
        """Create table and indexes if they don't exist"""
        import asyncpg
        from urllib.parse import urlparse

        parsed = urlparse(self.database_url)
        logger.info(
            f"FabricAuth: Connecting to PostgreSQL host={parsed.hostname} "
            f"port={parsed.port} db={(parsed.path or '').lstrip('/')}"
        )

        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLE_SQL)
        logger.info("FabricAuth: PostgreSQL key store initialized")

    async def close(self):
        if self._pool:
            await self._pool.close()

    async def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        """Look up a key by its hash"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM fabric_api_keys WHERE key_hash = $1",
                key_hash
            )
        if not row:
            return None
        return self._row_to_key(row)

    async def create(self, api_key: ApiKey) -> ApiKey:
        """Store a new API key"""
        import json
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO fabric_api_keys
                    (id, name, key_prefix, key_hash, scope, owner_id,
                     created_at, expires_at, rate_limit_rpm, allowed_agents, metadata)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            """,
                api_key.id,
                api_key.name,
                api_key.key_prefix,
                api_key.key_hash,
                api_key.scope.value,
                api_key.owner_id,
                api_key.created_at,
                api_key.expires_at,
                api_key.rate_limit_rpm,
                api_key.allowed_agents,
                json.dumps(api_key.metadata),
            )
        return api_key

    async def update_last_used(self, key_hash: str):
        """Update last_used_at timestamp — fire and forget"""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE fabric_api_keys SET last_used_at = NOW() WHERE key_hash = $1",
                key_hash
            )

    async def revoke(self, key_id: str) -> bool:
        """Revoke a key by its ID"""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE fabric_api_keys SET revoked=TRUE, revoked_at=NOW() WHERE id=$1",
                key_id
            )
        return result != "UPDATE 0"

    async def list_by_owner(self, owner_id: str) -> List[ApiKey]:
        """List all keys for an owner"""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM fabric_api_keys WHERE owner_id=$1 ORDER BY created_at DESC",
                owner_id
            )
        return [self._row_to_key(r) for r in rows]

    async def list_all(self, include_revoked: bool = False) -> List[ApiKey]:
        """Admin: list all keys"""
        async with self._pool.acquire() as conn:
            if include_revoked:
                rows = await conn.fetch("SELECT * FROM fabric_api_keys ORDER BY created_at DESC")
            else:
                rows = await conn.fetch(
                    "SELECT * FROM fabric_api_keys WHERE revoked=FALSE ORDER BY created_at DESC"
                )
        return [self._row_to_key(r) for r in rows]

    def _row_to_key(self, row) -> ApiKey:
        import json
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        return ApiKey(
            id=str(row["id"]),
            name=row["name"],
            key_prefix=row["key_prefix"],
            key_hash=row["key_hash"],
            scope=KeyScope(row["scope"]),
            owner_id=row["owner_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            last_used_at=row["last_used_at"],
            revoked=row["revoked"],
            revoked_at=row["revoked_at"],
            rate_limit_rpm=row["rate_limit_rpm"],
            allowed_agents=list(row["allowed_agents"] or []),
            metadata=meta or {},
        )


# ─────────────────────────────────────────────────────────────────────────────
# In-memory cache layer (avoids DB hit on every request)
# ─────────────────────────────────────────────────────────────────────────────

class KeyCache:
    """
    Simple TTL cache for API keys.
    Prevents a DB lookup on every single request.
    Cache TTL: 60 seconds (balances freshness vs performance)
    """

    def __init__(self, ttl_seconds: int = 60):
        self._cache: Dict[str, tuple[Optional[ApiKey], datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def get(self, key_hash: str) -> Optional[Optional[ApiKey]]:
        """Returns (ApiKey|None, found_in_cache). None result means 'key does not exist'."""
        if key_hash not in self._cache:
            return ...  # Sentinel: not in cache
        api_key, cached_at = self._cache[key_hash]
        if datetime.now(timezone.utc) - cached_at > self._ttl:
            del self._cache[key_hash]
            return ...  # Expired
        return api_key

    def set(self, key_hash: str, api_key: Optional[ApiKey]):
        self._cache[key_hash] = (api_key, datetime.now(timezone.utc))

    def invalidate(self, key_hash: str):
        self._cache.pop(key_hash, None)

    def clear(self):
        self._cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Main auth class
# ─────────────────────────────────────────────────────────────────────────────

# Paths that NEVER require auth
PUBLIC_PATHS = {
    "/",
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/mcp/health",
    "/mcp/docs",
    "/mcp/docs/json",
}

# Paths only the master key can access
ADMIN_PATHS = {"/admin/keys"}


class FabricAuth:
    """
    The main auth system for Fabric A2A.

    Validates requests in priority order:
    1. Master key (FABRIC_ADMIN_KEY env var) → admin-only endpoints
    2. API key (fab_sk_live_... or fab_sk_test_...) → normal usage
    3. [Future] Passport JWT → when you wire Passport in

    Installation in server.py:
        from auth import FabricAuth

        auth = FabricAuth(
            database_url=os.environ["DATABASE_URL"],
            master_key=os.environ.get("FABRIC_ADMIN_KEY"),
        )
        await auth.initialize()

        @app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            return await auth.middleware(request, call_next)
    """

    def __init__(
        self,
        database_url: str,
        master_key: Optional[str] = None,
        cache_ttl: int = 60,
    ):
        self._store = PostgresKeyStore(database_url)
        self._cache = KeyCache(ttl_seconds=cache_ttl)
        self._master_key = master_key or os.environ.get("FABRIC_ADMIN_KEY")

        if not self._master_key:
            logger.warning(
                "FabricAuth: No FABRIC_ADMIN_KEY set. Admin endpoints will be inaccessible."
            )

    async def initialize(self):
        """Call this on app startup"""
        await self._store.initialize()
        logger.info("FabricAuth: Ready")

    async def close(self):
        await self._store.close()

    # ── Middleware ────────────────────────────────────────────────────────────

    async def middleware(self, request: Request, call_next):
        """FastAPI middleware — attach to app with @app.middleware('http')"""
        path = request.url.path

        # Always allow public paths
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Extract token from Authorization header
        token = self._extract_token(request)

        if not token:
            return self._unauthorized("Missing Authorization header. Include: Authorization: Bearer fab_sk_live_...")

        # Validate
        result = await self.validate(token)

        if not result.authenticated:
            return self._unauthorized(result.error or "Invalid API key")

        # Admin path protection
        if any(path.startswith(p) for p in ADMIN_PATHS):
            if result.method != "master_key" and result.api_key and result.api_key.scope != KeyScope.ADMIN:
                return self._forbidden("Admin key required for this endpoint")

        # Attach auth info to request state for downstream use
        request.state.auth = result
        request.state.api_key = result.api_key

        # Update last_used_at async (non-blocking)
        if result.api_key:
            import asyncio
            asyncio.create_task(
                self._store.update_last_used(result.api_key.key_hash)
            )

        return await call_next(request)

    async def validate(self, token: str) -> AuthResult:
        """
        Validate a token. Call this directly if you're not using middleware.
        Returns AuthResult with api_key attached on success.
        """
        # 1. Check master key
        if self._master_key and hmac.compare_digest(token, self._master_key):
            return AuthResult(authenticated=True, method="master_key")

        # 2. Must look like a Fabric key
        if not (token.startswith(KEY_PREFIX_LIVE) or token.startswith(KEY_PREFIX_TEST)):
            # Future: try Passport JWT validation here
            return AuthResult(authenticated=False, error="Invalid key format")

        # 3. Hash and look up
        key_hash = _hash_key(token)

        # Check cache first
        cached = self._cache.get(key_hash)
        if cached is ...:
            # Not in cache — hit DB
            api_key = await self._store.get_by_hash(key_hash)
            self._cache.set(key_hash, api_key)
        else:
            api_key = cached

        if api_key is None:
            return AuthResult(authenticated=False, error="API key not found")

        if not api_key.is_valid:
            reason = "API key revoked" if api_key.revoked else "API key expired"
            return AuthResult(authenticated=False, error=reason)

        return AuthResult(authenticated=True, api_key=api_key, method="api_key")

    # ── Key management ────────────────────────────────────────────────────────

    async def create_key(
        self,
        name: str,
        owner_id: str,
        scope: KeyScope = KeyScope.FULL,
        expires_in_days: Optional[int] = None,
        rate_limit_rpm: int = 60,
        allowed_agents: Optional[List[str]] = None,
        test: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, ApiKey]:
        """
        Create a new API key.

        Returns: (full_key_to_show_once, ApiKey metadata)
        The full key is ONLY returned here. It is never stored or retrievable again.
        """
        import uuid

        full_key, display_prefix, key_hash = generate_api_key(test=test)

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        api_key = ApiKey(
            id=str(uuid.uuid4()),
            name=name,
            key_prefix=display_prefix,
            key_hash=key_hash,
            scope=scope,
            owner_id=owner_id,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            rate_limit_rpm=rate_limit_rpm,
            allowed_agents=allowed_agents or [],
            metadata=metadata or {},
        )

        await self._store.create(api_key)
        logger.info(f"FabricAuth: Created key '{name}' for owner '{owner_id}' (scope={scope})")

        return full_key, api_key

    async def revoke_key(self, key_id: str) -> bool:
        """Revoke a key by ID. Immediate effect (cache will expire within TTL)."""
        success = await self._store.revoke(key_id)
        if success:
            logger.info(f"FabricAuth: Revoked key {key_id}")
        return success

    async def list_keys(self, owner_id: Optional[str] = None) -> List[ApiKey]:
        """List keys. Owner_id=None returns all (admin only)."""
        if owner_id:
            return await self._store.list_by_owner(owner_id)
        return await self._store.list_all()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract Bearer token from Authorization header"""
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if not auth_header:
            return None
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        # Also accept raw key in header (some clients do this)
        return auth_header.strip()

    def _unauthorized(self, detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"ok": False, "error": {"type": "unauthorized", "message": detail}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _forbidden(self, detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"ok": False, "error": {"type": "forbidden", "message": detail}},
        )
