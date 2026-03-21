"""
Tool Template - Use this as a starting point for new tools

QUICK START:
1. Copy this file: cp TEMPLATE.py my_tool.py
2. Replace all TODO comments with your implementation
3. Place my_tool.py in tools/plugins/ (or tools/plugins/custom/)
4. Restart Fabric - your tool is automatically discovered
5. No changes to core Fabric code needed!

EXAMPLE - Weather Tool:
    TOOL_ID = "weather.get_forecast"
    CAPABILITIES = {
        "current": "get_current_weather",
        "forecast": "get_forecast"
    }
    
    async def get_current_weather(self, city: str, **kwargs) -> ToolResult:
        # Call weather API
        data = await fetch_weather(city)
        return ToolResult({"temperature": data.temp, "conditions": data.desc})
"""

from typing import Dict, Any, Optional
from tools.base import BaseTool, ToolResult, ToolError


class MyTool(BaseTool):  # TODO: Rename class to something descriptive
    """
    TODO: Write a clear description of what this tool does.
    
    This description appears in tool listings and helps users
    understand when to use this tool.
    
    Example:
        "Fetches current weather and forecasts from OpenWeatherMap API.
        Supports cities worldwide and returns temperature, conditions,
        humidity, and wind speed."
    """
    
    # TODO: Define unique tool identifier
    # Format: "category.action" (lowercase, no spaces)
    # Examples: "web.search", "io.read_file", "stripe.create_customer"
    TOOL_ID = "custom.my_tool"
    
    # TODO: Map capabilities to methods
    # Keys are capability names used in API calls
    # Values are method names in this class
    CAPABILITIES = {
        "execute": "execute",  # Default capability
        # "search": "search_method",
        # "create": "create_method",
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        TODO: Initialize your tool
        
        Access config values via self.config
        These come from tools/registry.yaml or environment
        """
        super().__init__(config)
        
        # TODO: Load API keys, endpoints, etc from config or env
        # self.api_key = self.config.get("api_key") or os.getenv("MY_API_KEY")
        pass
    
    async def execute(self, param1: str, param2: int = 10, **kwargs) -> ToolResult:
        """
        TODO: Implement your main capability
        
        This is the primary method that executes the tool's function.
        
        Args:
            param1: TODO - describe this parameter
            param2: TODO - describe this parameter
            **kwargs: Catch-all for additional parameters
        
        Returns:
            ToolResult containing the execution results
            
        Raises:
            ToolError: If execution fails (use specific error codes)
        
        Example:
            async def get_weather(self, city: str, units: str = "metric", **kwargs) -> ToolResult:
                try:
                    data = await self._fetch_weather(city, units)
                    return ToolResult({
                        "city": city,
                        "temperature": data["temp"],
                        "conditions": data["description"],
                        "humidity": data["humidity"]
                    })
                except APIError as e:
                    raise ToolError("API_ERROR", f"Weather API failed: {e}")
        """
        try:
            # TODO: Implement your logic here
            result = await self._do_something(param1, param2)
            
            return ToolResult({
                "output": result,
                "status": "success"
            })
            
        except ToolError:
            # Re-raise ToolError as-is (already properly formatted)
            raise
        except Exception as e:
            # Wrap unexpected errors in ToolError
            raise ToolError("EXECUTION_ERROR", str(e))
    
    async def _do_something(self, p1: str, p2: int) -> Dict[str, Any]:
        """
        TODO: Implement internal helper methods
        
        Prefix with underscore to indicate internal use.
        These won't be exposed as capabilities.
        """
        # TODO: Your implementation
        pass


# =============================================================================
# Auto-registration
# =============================================================================
# This line registers your tool when the module is imported.
# Do not remove or modify this.
BaseTool.register(MyTool)  # TODO: Make sure class name matches above
