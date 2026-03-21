# Fabric MCP Server - Layered Architecture Refactor

## Current Problem
- Tools are hardcoded in `builtin_tools.py` 
- Adding a tool requires modifying core Fabric code
- No separation between A2A (core) and Tools (extensions)
- Agents.yaml mixes tools and agents without clear boundaries

## Proposed 3-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FABRIC GATEWAY (Core)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   A2A Core  │  │   Registry  │  │    Plugin Manager       │  │
│  │  (MCP Router)│  │  (Agents)   │  │  (Tools + Skills)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└────────────────────┬─────────────────────┬──────────────────────┘
                     │                     │
        ┌────────────┘                     └────────────┐
        │                                               │
┌───────▼────────┐                          ┌──────────▼──────────┐
│  TOOL LAYER    │                          │   SKILLS LAYER      │
│  (pluggable)   │                          │   (pluggable)       │
│                │                          │                     │
│ ┌───────────┐  │                          │  ┌───────────────┐  │
│ │ Built-in  │  │                          │  │ Seed Skills   │  │
│ │  Tools    │  │                          │  │ (in-memory)   │  │
│ │(io, web,  │  │                          │  └───────────────┘  │
│ │ math, etc)│  │                          │  ┌───────────────┐  │
│ └───────────┘  │                          │  │ Ext Skills    │  │
│ ┌───────────┐  │                          │  │ (yaml-defined)│  │
│ │ External  │  │                          │  └───────────────┘  │
│ │  Tools    │  │                          │                     │
│ │(custom)   │  │                          └─────────────────────┘
│ └───────────┘  │
└────────────────┘
```

## Layer 1: Fabric Gateway Core (Unchanged)
- **A2A Router**: MCP protocol handling, agent discovery, message routing
- **Agent Registry**: External agents from `agents.yaml` (the ORIGINAL purpose)
- **Plugin Manager**: Loads and manages Tools and Skills as plugins

## Layer 2: Tool Layer (Pluggable)
Tools are **execution units** - simple functions that do one thing well.

### Tool Registry Structure
```yaml
# tools/registry.yaml - Separate from agents.yaml
tools:
  - tool_id: io.read_file
    provider: builtin           # builtin | external | mcp
    entrypoint: io.read_file    # For builtin: maps to BUILTIN_TOOLS
    category: io
    # Schema defined here or referenced
    
  - tool_id: web.brave_search
    provider: builtin
    entrypoint: web.brave_search
    category: web
    
  - tool_id: custom.my_tool
    provider: external          # External = custom code in tools/plugins/
    entrypoint: custom_plugin.my_tool
    category: custom
    
  - tool_id: stripe.create_customer
    provider: mcp               # MCP server as tool provider
    endpoint: http://stripe-mcp:8000/mcp
    category: integration
```

### Tool Template (for creating new tools)
```python
# tools/plugins/TEMPLATE.py
"""
Tool Template - Copy this to create new tools

1. Create file: tools/plugins/my_tool.py
2. Implement your tool class inheriting from BaseTool
3. Register in tools/registry.yaml
4. Restart Fabric - no core code changes needed
"""

from typing import Dict, Any, Optional
from tools.base import BaseTool, ToolResult, ToolError

class MyTool(BaseTool):
    """Description of what this tool does"""
    
    # Unique identifier: category.action
    TOOL_ID = "custom.my_tool"
    
    # Capabilities this tool provides
    CAPABILITIES = {
        "do_something": "execute",
        # capability_name: method_name
    }
    
    async def execute(self, param1: str, param2: int = 10, **kwargs) -> ToolResult:
        """
        Execute the tool
        
        Args:
            param1: Required parameter description
            param2: Optional parameter with default
            
        Returns:
            ToolResult with success data
        """
        try:
            # Your implementation here
            result = await self._do_work(param1, param2)
            
            return ToolResult({
                "output": result,
                "status": "success"
            })
            
        except Exception as e:
            raise ToolError("EXECUTION_ERROR", str(e))
    
    async def _do_work(self, p1: str, p2: int):
        # Internal helper
        pass

# Auto-registration - no manual registration needed
BaseTool.register(MyTool)
```

### Auto-Discovery System
```python
# tools/base.py
import importlib
from pathlib import Path
from typing import Dict, Type

class BaseTool:
    """Base class for all tools with auto-discovery"""
    
    _registry: Dict[str, Type['BaseTool']] = {}
    
    TOOL_ID: str = None  # Override in subclass
    CAPABILITIES: Dict[str, str] = {}
    
    @classmethod
    def register(cls, tool_class: Type['BaseTool']):
        """Register a tool class"""
        if tool_class.TOOL_ID:
            cls._registry[tool_class.TOOL_ID] = tool_class
    
    @classmethod
    def load_plugins(cls, plugins_dir: str = "tools/plugins"):
        """Auto-discover and load all tool plugins"""
        plugins_path = Path(plugins_dir)
        if not plugins_path.exists():
            return
            
        for file in plugins_path.glob("*.py"):
            if file.name.startswith("_"):
                continue
            module_name = f"tools.plugins.{file.stem}"
            importlib.import_module(module_name)
    
    @classmethod
    def get_tool(cls, tool_id: str) -> Optional[Type['BaseTool']]:
        return cls._registry.get(tool_id)
    
    @classmethod
    def list_tools(cls) -> list:
        return list(cls._registry.keys())
```

## Layer 3: Skills Layer (Future)
Skills are **composable workflows** that combine tools + logic.

```yaml
# skills/registry.yaml
skills:
  - skill_id: research_and_summarize
    description: Search web, fetch pages, and summarize
    workflow:
      - step: 1
        tool: web.brave_search
        input:
          query: "${user_query}"
        output: search_results
        
      - step: 2
        tool: web.fetch_page
        loop: "${search_results[:3]}"
        input:
          url: "${item.url}"
        output: pages
        
      - step: 3
        tool: text.transform
        input:
          text: "${pages}"
          operations: [{type: "summarize"}]
        output: summary
        
      - step: 4
        return:
          summary: "${summary}"
          sources: "${search_results}"
```

## Refactor Implementation Plan

### Phase 1: Extract Tools to Plugin System
1. Create `tools/base.py` with BaseTool class
2. Create `tools/plugins/` directory
3. Move existing tools to `tools/plugins/builtin_io.py`, `builtin_web.py`, etc.
4. Create `tools/registry.yaml` (separate from agents.yaml)
5. Update `server.py` to use plugin loader
6. Update `agents.yaml` to remove tools section

### Phase 2: Clean Separation
1. Rename `agents.yaml` → `registry.yaml` with sections:
   ```yaml
   agents: []      # A2A remote agents (original purpose)
   tools: []       # References to tool plugins
   skills: []      # Future composable workflows
   ```
2. Update server to handle each section separately

### Phase 3: Documentation
1. `TOOL_DEVELOPER.md` - How to create tools
2. `SKILL_DEVELOPER.md` - How to create skills (future)
3. Update main README to emphasize A2A-first architecture

## File Structure After Refactor

```
fabric/
├── server.py                 # Core A2A + Plugin Manager
├── registry.yaml             # Agents, Tools (refs), Skills
├── architecture.md           # This document
│
├── fabric/                   # Core package
│   ├── __init__.py
│   ├── a2a/                  # A2A Core (original)
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── registry.py
│   │   └── protocols/
│   └── plugins/              # Plugin Manager
│       ├── __init__.py
│       ├── loader.py
│       └── registry.py
│
├── tools/                    # Tool Layer (plugins)
│   ├── base.py               # BaseTool class
│   ├── registry.yaml         # Tool registry
│   └── plugins/              # Tool implementations
│       ├── __init__.py
│       ├── builtin_io.py     # Moved from builtin_tools.py
│       ├── builtin_web.py    # Includes brave_search
│       ├── builtin_math.py
│       ├── builtin_text.py
│       ├── builtin_system.py
│       ├── builtin_data.py
│       ├── builtin_security.py
│       └── custom/           # User custom tools
│           └── README.md
│
├── skills/                   # Skills Layer (future)
│   ├── base.py
│   ├── registry.yaml
│   └── workflows/            # YAML-defined skills
│       └── research_and_summarize.yaml
│
└── sdk/                      # Client SDKs
    └── ...
```

## Key Principles

1. **A2A is Core**: Agent-to-agent communication is Fabric's primary purpose
2. **Tools are Plugins**: Tools extend Fabric but don't define it
3. **Zero Core Changes**: Adding tools requires only:
   - Create file in `tools/plugins/`
   - Register in `tools/registry.yaml` (or auto-register)
4. **Future-Proof**: Skills layer follows same pattern
5. **Backward Compatible**: Existing API stays the same

## Migration Path

Current → Phase 1 → Phase 2 → Phase 3

Each phase maintains backward compatibility. Can stop at any phase.

---

**Want me to implement Phase 1?** This would:
1. Create the plugin infrastructure
2. Move existing tools to plugins
3. Make `agents.yaml` tools section optional
4. Allow new tools via `tools/plugins/` without touching core code
