"""
Fabric A2A - Passport JWT Integration Shim
==========================================

When you're ready to wire Passport (your Keycloak clone) into Fabric,
drop this file in and update auth.py's validate() method.

Right now this is a stub. When Passport is live:
  1. Set PASSPORT_ISSUER and PASSPORT_AUDIENCE env vars
  2. Import PassportValidator in auth.py
  3. Uncomment the JWT validation in auth.py validate()

The client-facing key format does NOT change.
Developers still send: Authorization: Bearer fab_sk_live_...
Passport becomes the ISSUER of those tokens, not the validator pattern.

Architecture:
  Developer Portal (mcpfabric.space)
       ↓  "Give me a key"
  Passport (your identity layer)
       ↓  Issues signed JWT
  Fabric validates JWT on every request
  (no DB lookup needed — JWT is self-contained)

That's the PKCE flow you mentioned. You were right.
PKCE is for the browser-facing OAuth dance.
The resulting access token is what gets used as the API key.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

PASSPORT_ISSUER = os.environ.get("PASSPORT_ISSUER")       # e.g., "https://passport.perceptor.us"
PASSPORT_AUDIENCE = os.environ.get("PASSPORT_AUDIENCE", "fabric-a2a")
PASSPORT_JWKS_URL = os.environ.get("PASSPORT_JWKS_URL")   # e.g., "https://passport.perceptor.us/.well-known/jwks.json"


class PassportValidator:
    """
    Validates JWTs issued by AetherPro Passport (your Keycloak).

    Passport uses standard OIDC/OAuth2.1 — same as Keycloak.
    JWKS endpoint auto-rotates keys so you never hardcode certs.
    """

    def __init__(self, issuer: str, audience: str, jwks_url: str):
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
        self._jwks_cache = None

    async def initialize(self):
        """Pre-fetch JWKS public keys on startup"""
        if not self.jwks_url:
            logger.warning("PassportValidator: No JWKS URL configured, JWT validation disabled")
            return
        await self._refresh_jwks()
        logger.info(f"PassportValidator: Ready (issuer={self.issuer})")

    async def validate(self, token: str) -> Optional[dict]:
        """
        Validate a JWT token from Passport.

        Returns decoded payload on success, None on failure.

        Payload will contain:
          - sub: agent or user ID
          - scope: "fabric:full", "fabric:tools", etc.
          - iss: issuer (Passport URL)
          - aud: "fabric-a2a"
          - exp: expiry timestamp
          - fabric_agent_id: optional, for agent passports
        """
        if not self._jwks_cache:
            try:
                await self._refresh_jwks()
            except Exception as e:
                logger.error(f"PassportValidator: Could not fetch JWKS: {e}")
                return None

        try:
            import jwt  # PyJWT
            from jwt import PyJWKClient

            jwks_client = PyJWKClient(self.jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"verify_exp": True},
            )
            return payload

        except jwt.ExpiredSignatureError:
            logger.debug("PassportValidator: Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"PassportValidator: Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"PassportValidator: Unexpected error: {e}")
            return None

    async def _refresh_jwks(self):
        """Fetch JWKS from Passport — called on startup and periodically"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(self.jwks_url, timeout=10.0)
            response.raise_for_status()
            self._jwks_cache = response.json()
        logger.debug(f"PassportValidator: JWKS refreshed ({len(self._jwks_cache.get('keys', []))} keys)")


# ── To wire this into auth.py validate() ────────────────────────────────────
#
# In auth.py FabricAuth.__init__(), add:
#   if PASSPORT_ISSUER and PASSPORT_JWKS_URL:
#       from passport_shim import PassportValidator
#       self._passport = PassportValidator(PASSPORT_ISSUER, PASSPORT_AUDIENCE, PASSPORT_JWKS_URL)
#   else:
#       self._passport = None
#
# In auth.py FabricAuth.initialize(), add:
#   if self._passport:
#       await self._passport.initialize()
#
# In auth.py FabricAuth.validate(), replace the "Future: try Passport JWT" comment with:
#   if self._passport:
#       payload = await self._passport.validate(token)
#       if payload:
#           # Map Passport claims to ApiKey-like object for downstream code
#           from auth import ApiKey, KeyScope
#           from datetime import datetime, timezone
#           pseudo_key = ApiKey(
#               id=payload.get("jti", "jwt"),
#               name=payload.get("client_id", "passport-client"),
#               key_prefix="jwt:",
#               key_hash="",
#               scope=KeyScope.FULL,  # or map from payload["scope"]
#               owner_id=payload.get("sub", "unknown"),
#               created_at=datetime.now(timezone.utc),
#           )
#           return AuthResult(authenticated=True, api_key=pseudo_key, method="passport_jwt")
#   return AuthResult(authenticated=False, error="Invalid key format")
