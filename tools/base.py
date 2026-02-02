"""
Fabric Tool Base - Plugin infrastructure for tools

This module provides the foundation for Fabric's pluggable tool system.
Tools can be added without modifying core Fabric code.
"""

import importlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Type, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Error raised by tools"""
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


@dataclass
class ToolResult:
    """Standard result wrapper for tool execution"""
    data: Dict[str, Any]
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.success,
            "result": self.data if self.success else None,
            "error": self.data if not self.success else None
        }


@dataclass  
class ToolMetadata:
    """Metadata for a tool capability"""
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    streaming: bool = False
    max_timeout_ms: int = 60000


class BaseTool(ABC):
    """
    Base class for all Fabric tools.
    
    To create a new tool:
    1. Subclass BaseTool
    2. Define TOOL_ID and CAPABILITIES
    3. Implement capability methods
    4. Place file in tools/plugins/
    
    The tool will be auto-discovered on startup.
    """
    
    # Registry of all tool classes
    _registry: Dict[str, Type['BaseTool']] = {}
    _instances: Dict[str, 'BaseTool'] = {}
    
    # Override these in your subclass
    TOOL_ID: str = None  # e.g., "io.read_file", "web.search"
    CAPABILITIES: Dict[str, str] = {}  # capability_name -> method_name
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize tool with optional config"""
        self.config = config or {}
    
    @classmethod
    def register(cls, tool_class: Type['BaseTool']):
        """
        Register a tool class in the registry.
        Called automatically when module is imported.
        """
        if not tool_class.TOOL_ID:
            logger.warning(f"Tool class {tool_class.__name__} has no TOOL_ID, skipping registration")
            return
            
        cls._registry[tool_class.TOOL_ID] = tool_class
        logger.debug(f"Registered tool: {tool_class.TOOL_ID}")
    
    @classmethod
    def get_tool_class(cls, tool_id: str) -> Optional[Type['BaseTool']]:
        """Get tool class by ID"""
        return cls._registry.get(tool_id)
    
    @classmethod
    def get_tool_instance(cls, tool_id: str, config: Optional[Dict] = None) -> Optional['BaseTool']:
        """Get or create tool instance (singleton per tool_id)"""
        if tool_id not in cls._instances:
            tool_class = cls.get_tool_class(tool_id)
            if not tool_class:
                return None
            cls._instances[tool_id] = tool_class(config)
        return cls._instances[tool_id]
    
    @classmethod
    def list_tools(cls) -> List[str]:
        """List all registered tool IDs"""
        return list(cls._registry.keys())
    
    @classmethod
    def get_tool_info(cls, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata about a tool"""
        tool_class = cls.get_tool_class(tool_id)
        if not tool_class:
            return None
            
        return {
            "tool_id": tool_id,
            "capabilities": tool_class.CAPABILITIES,
            "doc": tool_class.__doc__
        }
    
    @classmethod
    def load_plugins(cls, plugins_dir: str = "tools/plugins"):
        """
        Auto-discover and load all tool plugins.
        
        Scans the plugins directory and imports all .py files,
        which triggers their registration.
        """
        plugins_path = Path(plugins_dir)
        if not plugins_path.exists():
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return
        
        loaded = 0
        for file in plugins_path.rglob("*.py"):
            # Skip __init__.py, private files, and templates
            if file.name.startswith(("_", "TEMPLATE")):
                continue
                
            # Convert path to module name
            relative = file.relative_to(Path("tools"))
            module_name = f"tools.{str(relative.with_suffix('')).replace('/', '.')}"
            
            try:
                importlib.import_module(module_name)
                loaded += 1
                logger.debug(f"Loaded plugin: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load plugin {module_name}: {e}")
        
        logger.info(f"Loaded {loaded} tool plugins, {len(cls._registry)} tools registered")
    
    async def execute_capability(self, capability: str, **kwargs) -> ToolResult:
        """
        Execute a capability by name.
        
        This maps capability names to methods via CAPABILITIES dict.
        Override if you need custom dispatch logic.
        """
        if capability not in self.CAPABILITIES:
            raise ToolError(
                "CAPABILITY_NOT_FOUND", 
                f"Capability '{capability}' not found on tool '{self.TOOL_ID}'"
            )
        
        method_name = self.CAPABILITIES[capability]
        method = getattr(self, method_name, None)
        
        if not method or not callable(method):
            raise ToolError(
                "CAPABILITY_NOT_IMPLEMENTED",
                f"Method '{method_name}' for capability '{capability}' not implemented"
            )
        
        return await method(**kwargs)


# Convenience function for executing tools
async def execute_tool(tool_id: str, capability: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool by ID and capability.
    
    This is the main entry point used by the Fabric server.
    """
    tool = BaseTool.get_tool_instance(tool_id)
    
    if not tool:
        return ToolResult({
            "code": "TOOL_NOT_FOUND",
            "message": f"Tool not found: {tool_id}"
        }, success=False).to_dict()
    
    try:
        result = await tool.execute_capability(capability, **arguments)
        return result.to_dict()
    except ToolError as e:
        return ToolResult({
            "code": e.code,
            "message": e.message,
            "details": e.details
        }, success=False).to_dict()
    except Exception as e:
        logger.exception(f"Unexpected error executing {tool_id}.{capability}")
        return ToolResult({
            "code": "EXECUTION_ERROR",
            "message": str(e)
        }, success=False).to_dict()


def list_builtin_tools() -> List[str]:
    """List all registered tool IDs"""
    return BaseTool.list_tools()


def get_tool_info(tool_id: str) -> Optional[Dict[str, Any]]:
    """Get info about a tool"""
    return BaseTool.get_tool_info(tool_id)
