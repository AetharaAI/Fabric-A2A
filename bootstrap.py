#!/usr/bin/env python3
"""
Fabric A2A - Bootstrap Script
Run ONCE on the Fabric VM to initialize the auth system.

Usage:
    python bootstrap.py

This will:
  1. Create the fabric_api_keys table in your existing PostgreSQL
  2. Generate a strong FABRIC_ADMIN_KEY
  3. Create your first API key for AetherPro LiteLLM
  4. Print the .env additions you need
"""

import asyncio
import os
import secrets
import sys


async def bootstrap():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL not set")
        print("   Export it first: export DATABASE_URL='postgresql://user:pass@host:port/db'")
        sys.exit(1)

    print("🔧 Fabric A2A Auth Bootstrap")
    print("=" * 50)

    # ── Generate admin key ────────────────────────────────────────────────────
    admin_key = f"fab_admin_{secrets.token_hex(32)}"
    print("\n📋 Add these to your .env file on the Fabric VM:\n")
    print(f"FABRIC_ADMIN_KEY={admin_key}")
    print(f"# (also remove FABRIC_PSK if it exists)")

    # ── Initialize auth ───────────────────────────────────────────────────────
    from auth import FabricAuth, KeyScope

    auth = FabricAuth(database_url=database_url, master_key=admin_key)
    await auth.initialize()
    print("\n✅ PostgreSQL table 'fabric_api_keys' created")

    # ── Create first key for LiteLLM ──────────────────────────────────────────
    full_key, api_key = await auth.create_key(
        name="AetherPro LiteLLM Gateway",
        owner_id="aetherpro",
        scope=KeyScope.FULL,
        rate_limit_rpm=600,
        metadata={"environment": "production", "service": "litellm"},
    )

    print("\n🔑 Your first API key (SAVE THIS — shown once):\n")
    print(f"   {full_key}")
    print(f"\n   ID:     {api_key.id}")
    print(f"   Name:   {api_key.name}")
    print(f"   Prefix: {api_key.key_prefix}")
    print(f"   Scope:  {api_key.scope}")

    # ── Create test key ───────────────────────────────────────────────────────
    test_key, test_api_key = await auth.create_key(
        name="Development Test Key",
        owner_id="aetherpro",
        scope=KeyScope.FULL,
        rate_limit_rpm=60,
        test=True,
        metadata={"environment": "development"},
    )

    print(f"\n🧪 Test key for development:\n")
    print(f"   {test_key}")

    # ── Print LiteLLM config ──────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("📄 Add this to your litellm_config.yaml:\n")
    print("mcp_servers:")
    print("  fabric_gateway:")
    print('    url: "https://fabric.perceptor.us/mcp"')
    print('    transport: "http"')
    print("    headers:")
    print(f'      Authorization: "Bearer {full_key}"')

    print("\n" + "=" * 50)
    print("✅ Bootstrap complete. Next steps:")
    print("   1. Add FABRIC_ADMIN_KEY to .env on Fabric VM")
    print("   2. Deploy updated server.py/auth.py/admin_routes.py to the Fabric VM")
    print("   3. Restart: docker compose restart fabric-gateway")
    print("   4. Test: curl https://fabric.perceptor.us/admin/verify \\")
    print(f'           -H "Authorization: Bearer {full_key}"')
    print("   5. Update litellm_config.yaml with the key above")

    await auth.close()


if __name__ == "__main__":
    asyncio.run(bootstrap())
