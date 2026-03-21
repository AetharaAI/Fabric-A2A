"""
Built-in Security Tools - Hashing and Encoding

Refactored to use the new BaseTool plugin architecture.
"""

import hashlib
import base64
from typing import Dict, Any

from tools.base import BaseTool, ToolResult, ToolError


class SecurityTools(BaseTool):
    """Security utilities - hashing, encoding"""
    
    TOOL_ID = "security"
    CAPABILITIES = {}
    
    @staticmethod
    async def hash(data: str, algorithm: str = 'sha256', **kwargs) -> ToolResult:
        """Generate cryptographic hash"""
        try:
            algorithms = {
                'md5': hashlib.md5,
                'sha1': hashlib.sha1,
                'sha256': hashlib.sha256,
                'sha512': hashlib.sha512
            }
            
            if algorithm not in algorithms:
                raise ToolError("INVALID_ALGORITHM", f"Supported: {list(algorithms.keys())}")
            
            hasher = algorithms[algorithm]()
            hasher.update(data.encode('utf-8'))
            
            return ToolResult({
                "hash": hasher.hexdigest(),
                "algorithm": algorithm,
                "bytes": hasher.digest_size
            })
            
        except ToolError:
            raise
        except Exception as e:
            raise ToolError("HASH_ERROR", str(e))
    
    @staticmethod
    async def base64_encode(data: str, decode: bool = False, **kwargs) -> ToolResult:
        """Encode/decode base64"""
        try:
            if decode:
                result = base64.b64decode(data).decode('utf-8')
            else:
                result = base64.b64encode(data.encode('utf-8')).decode('utf-8')
            
            return ToolResult({
                "result": result,
                "operation": "decode" if decode else "encode"
            })
            
        except Exception as e:
            raise ToolError("BASE64_ERROR", str(e))


class HashTool(BaseTool):
    TOOL_ID = "security.hash"
    CAPABILITIES = {"hash": "hash"}
    
    async def hash(self, **kwargs) -> ToolResult:
        return await SecurityTools.hash(**kwargs)


class Base64Tool(BaseTool):
    TOOL_ID = "security.base64"
    CAPABILITIES = {"encode": "base64_encode"}
    
    async def base64_encode(self, **kwargs) -> ToolResult:
        return await SecurityTools.base64_encode(**kwargs)


BaseTool.register(HashTool)
BaseTool.register(Base64Tool)
