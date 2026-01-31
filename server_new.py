#!/usr/bin/env python3
"""
Fabric MCP Server - Enhanced with PostgreSQL and Observability
Production-grade MCP server with database backend and monitoring.
"""

import os
import sys
import argparse
import asyncio
import logging
from typing import Optional

# Configure logging first
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_registry(config_path: str, use_postgres: bool = False, database_url: Optional[str] = None):
    """Create the appropriate registry based on configuration"""
    
    if use_postgres and database_url:
        logger.info("Using PostgreSQL registry")
        try:
            from database.postgres_registry import PostgresRegistry
            from database.models import init_database
            
            # Initialize database tables
            init_database(database_url)
            
            # Create registry
            registry = PostgresRegistry(database_url)
            
            # Load initial data from YAML if database is empty
            # This allows easy migration from YAML to PostgreSQL
            from server import load_registry_from_yaml, AgentRegistry
            temp_registry = AgentRegistry()
            try:
                load_registry_from_yaml(temp_registry, config_path)
                
                # Copy to PostgreSQL
                for agent_id in temp_registry.agents:
                    manifest = temp_registry.agents[agent_id]
                    registry.register(manifest)
                    logger.info(f"Migrated agent to PostgreSQL: {agent_id}")
                
                logger.info(f"Migrated {len(temp_registry.agents)} agents to PostgreSQL")
            except FileNotFoundError:
                logger.warning(f"Config file not found: {config_path}")
            
            return registry
            
        except ImportError as e:
            logger.error(f"PostgreSQL dependencies not installed: {e}")
            logger.warning("Falling back to YAML registry")
            use_postgres = False
    
    # Use YAML-based registry
    logger.info("Using YAML registry")
    from server import AgentRegistry, load_registry_from_yaml
    
    registry = AgentRegistry()
    try:
        load_registry_from_yaml(registry, config_path)
        logger.info(f"Loaded registry from {config_path}")
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}, starting with empty registry")
    
    return registry


def create_app():
    """Create and configure the FastAPI application"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    # Get configuration from environment
    use_postgres = os.getenv("USE_POSTGRES", "false").lower() == "true"
    database_url = os.getenv("DATABASE_URL")
    config_path = os.getenv("FABRIC_CONFIG", "agents.yaml")
    psk = os.getenv("FABRIC_PSK", "dev-shared-secret")
    
    # Create registry
    registry = create_registry(config_path, use_postgres, database_url)
    
    # Create auth service
    from server import AuthService
    auth_service = AuthService(psk=psk)
    
    # Create fabric server
    from server import FabricServer
    fabric = FabricServer(registry, auth_service)
    
    # Create FastAPI app
    from server import create_http_app
    app = create_http_app(fabric)
    
    # Add CORS middleware
    allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Store fabric instance for access in routes
    app.state.fabric = fabric
    
    # Add observability endpoints if enabled
    if os.getenv("ENABLE_METRICS", "true").lower() == "true":
        logger.info("Enabling observability endpoints")
        
        # Import and add monitoring routes
        from observability.dashboard import router as monitoring_router
        app.include_router(monitoring_router)
        
        # Add Prometheus metrics endpoint
        from observability.metrics import get_metrics
        
        @app.get("/metrics")
        async def prometheus_metrics():
            """Prometheus metrics endpoint"""
            from fastapi.responses import Response
            metrics = get_metrics()
            return Response(
                content=metrics.get_prometheus_metrics(),
                media_type=metrics.get_content_type()
            )
    
    # Add startup event to initialize health checks
    @app.on_event("startup")
    async def startup_event():
        logger.info("Fabric MCP Server starting up")
        logger.info(f"Registry type: {'PostgreSQL' if use_postgres else 'YAML'}")
        logger.info(f"Observability: {'enabled' if os.getenv('ENABLE_METRICS', 'true').lower() == 'true' else 'disabled'}")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Fabric MCP Server shutting down")
    
    return app


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Fabric MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], 
                       default=os.getenv("FABRIC_TRANSPORT", "http"),
                       help="Transport protocol")
    parser.add_argument("--port", type=int, 
                       default=int(os.getenv("FABRIC_PORT", "8000")),
                       help="HTTP port")
    parser.add_argument("--config", 
                       default=os.getenv("FABRIC_CONFIG", "agents.yaml"),
                       help="Path to agents configuration")
    parser.add_argument("--psk", 
                       default=os.getenv("FABRIC_PSK"),
                       help="Pre-shared key")
    parser.add_argument("--use-postgres", action="store_true",
                       default=os.getenv("USE_POSTGRES", "false").lower() == "true",
                       help="Use PostgreSQL registry")
    parser.add_argument("--database-url",
                       default=os.getenv("DATABASE_URL"),
                       help="PostgreSQL connection URL")
    
    args = parser.parse_args()
    
    # Set environment variables from args for consistency
    if args.psk:
        os.environ["FABRIC_PSK"] = args.psk
    if args.use_postgres:
        os.environ["USE_POSTGRES"] = "true"
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    
    if args.transport == "stdio":
        # STDIO mode - use original server
        logger.info("Starting in STDIO mode")
        from server import main as orig_main
        sys.argv = [sys.argv[0], "--transport", "stdio", "--config", args.config]
        if args.psk:
            sys.argv.extend(["--psk", args.psk])
        asyncio.run(orig_main())
    else:
        # HTTP mode - use enhanced server
        logger.info(f"Starting HTTP server on port {args.port}")
        
        import uvicorn
        
        # Create app (this sets up everything)
        app = create_app()
        
        # Configure uvicorn
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=args.port,
            log_level=os.getenv("LOG_LEVEL", "info").lower(),
            reload=os.getenv("RELOAD", "false").lower() == "true"
        )
        
        server = uvicorn.Server(config)
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()