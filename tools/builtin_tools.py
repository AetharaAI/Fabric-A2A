"""
Fabric MCP Server - Built-in Tool Inventory (Legacy Compatibility)

⚠️  DEPRECATION NOTICE:
This file is maintained for backward compatibility.
New code should import from tools.base and tools.plugins directly.

NEW IMPORT PATHS:
- from tools.base import ToolResult, ToolError, execute_tool
- Tools are now in tools/plugins/builtin_*.py

MIGRATION GUIDE:
1. Replace: from tools.builtin_tools import execute_tool, ToolResult
   With:     from tools.base import execute_tool, ToolResult
   
2. Tools are auto-discovered from tools/plugins/ directory
   No need to import individual tool classes

ARCHITECTURE:
- Core: tools/base.py - BaseTool class and registry
- Plugins: tools/plugins/builtin_*.py - Individual tool implementations
- Registry: tools/registry.yaml - Tool metadata
"""

import logging
from typing import Dict, Any, List, Optional

# Import from new location for re-export
from tools.base import (
    BaseTool,
    ToolError,
    ToolResult,
    execute_tool,
    list_builtin_tools,
    get_tool_info
)

# Import and register all builtin plugins
# This ensures they're available in the registry
from tools.plugins import builtin_io
from tools.plugins import builtin_web

logger = logging.getLogger(__name__)

# Legacy BUILTIN_TOOLS dict - now dynamically built from registry
# This maintains compatibility with code that imports BUILTIN_TOOLS
BUILTIN_TOOLS = {}

def _build_legacy_registry():
    """Build legacy BUILTIN_TOOLS dict from new registry"""
    global BUILTIN_TOOLS
    
    # Map from new registry format to old format
    # Old: "io.read_file": (IOTools, "read")
    # New: Auto-discovered via BaseTool._registry
    
    # Since we moved to class-based registry, we'll create a shim
    # that maps to the new system
    
    tool_mapping = {
        "io.read_file": (builtin_io.IOTools, "read"),
        "io.write_file": (builtin_io.IOTools, "write"),
        "io.list_directory": (builtin_io.IOTools, "list"),
        "io.search_files": (builtin_io.IOTools, "search"),
        "web.http_request": (builtin_web.WebTools, "request"),
        "web.fetch_page": (builtin_web.WebTools, "fetch"),
        "web.parse_url": (builtin_web.WebTools, "parse_url"),
        "web.brave_search": (builtin_web.WebTools, "brave_search"),
    }
    
    BUILTIN_TOOLS.update(tool_mapping)

# Build legacy registry on import
_build_legacy_registry()

logger.info(f"Loaded {len(BUILTIN_TOOLS)} tools (legacy compatibility mode)")

# Re-export for backward compatibility
__all__ = [
    'ToolError',
    'ToolResult', 
    'execute_tool',
    'list_builtin_tools',
    'get_tool_info',
    'BUILTIN_TOOLS',
    # Legacy classes for direct access
    'IOTools',
    'WebTools',
]

# Re-export tool classes for direct access (legacy)
IOTools = builtin_io.IOTools
WebTools = builtin_web.WebTools

# TODO: Add remaining tool categories as they're refactored:
# - builtin_math (MathTools)
# - builtin_text (TextTools)  
# - builtin_system (SystemTools)
# - builtin_data (DataTools)
# - builtin_security (SecurityTools)
# - builtin_encode (EncodeTools)
# - builtin_docs (DocsTools)
