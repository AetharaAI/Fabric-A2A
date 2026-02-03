"""
Built-in Encoding Tools - URL Encoding

Refactored to use the new BaseTool plugin architecture.
"""

from urllib.parse import quote, unquote
from typing import Dict, Any

from tools.base import BaseTool, ToolResult, ToolError


class EncodeTools(BaseTool):
    """Encoding utilities"""
    
    TOOL_ID = "encode"
    CAPABILITIES = {}
    
    @staticmethod
    async def url_encode(text: str, decode: bool = False, **kwargs) -> ToolResult:
        """URL encode/decode text"""
        try:
            if decode:
                result = unquote(text)
            else:
                result = quote(text, safe='')
            
            return ToolResult({
                "result": result,
                "operation": "decode" if decode else "encode",
                "original_length": len(text),
                "result_length": len(result)
            })
            
        except Exception as e:
            raise ToolError("URL_ENCODE_ERROR", str(e))


class URLEncodeTool(BaseTool):
    TOOL_ID = "encode.url"
    CAPABILITIES = {"encode": "url_encode"}
    
    async def url_encode(self, **kwargs) -> ToolResult:
        return await EncodeTools.url_encode(**kwargs)


BaseTool.register(URLEncodeTool)
