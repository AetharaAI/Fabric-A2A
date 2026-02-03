"""
Built-in Text Tools - String Processing

Refactored to use the new BaseTool plugin architecture.
"""

import re
import difflib
from typing import Dict, Any, List, Optional

from tools.base import BaseTool, ToolResult, ToolError


class TextTools(BaseTool):
    """Text processing and transformation tools"""
    
    TOOL_ID = "text"
    CAPABILITIES = {}
    
    @staticmethod
    async def match(text: str, pattern: str, flags: Optional[List[str]] = None, **kwargs) -> ToolResult:
        """Match regex pattern in text"""
        try:
            flag_map = {'i': re.IGNORECASE, 'm': re.MULTILINE, 's': re.DOTALL, 'x': re.VERBOSE}
            re_flags = sum(flag_map.get(f, 0) for f in (flags or []))
            
            regex = re.compile(pattern, re_flags)
            matches = regex.findall(text)
            
            groups = []
            for match in regex.finditer(text):
                if match.groups():
                    groups.append(match.groups())
            
            return ToolResult({
                "matches": matches,
                "groups": groups,
                "count": len(matches),
                "pattern": pattern
            })
            
        except re.error as e:
            raise ToolError("INVALID_REGEX", str(e))
        except Exception as e:
            raise ToolError("MATCH_ERROR", str(e))
    
    @staticmethod
    async def transform(text: str, operations: List[Dict[str, Any]], **kwargs) -> ToolResult:
        """Apply text transformations"""
        try:
            result = text
            applied = 0
            
            for op in operations:
                op_type = op.get('type')
                
                if op_type == 'uppercase':
                    result = result.upper()
                elif op_type == 'lowercase':
                    result = result.lower()
                elif op_type == 'trim':
                    result = result.strip()
                elif op_type == 'truncate':
                    length = op.get('length', 100)
                    result = result[:length] + ('...' if len(result) > length else '')
                elif op_type == 'replace':
                    old = op.get('old', '')
                    new = op.get('new', '')
                    count = op.get('count', -1)
                    if count >= 0:
                        result = result.replace(old, new, count)
                    else:
                        result = result.replace(old, new)
                elif op_type == 'split':
                    sep = op.get('separator', '\n')
                    return ToolResult({
                        "result": result.split(sep),
                        "operations_applied": applied + 1,
                        "count": len(result.split(sep))
                    })
                elif op_type == 'join':
                    sep = op.get('separator', '')
                    if isinstance(result, list):
                        result = sep.join(str(x) for x in result)
                
                applied += 1
            
            return ToolResult({
                "result": result,
                "operations_applied": applied
            })
            
        except Exception as e:
            raise ToolError("TRANSFORM_ERROR", str(e))
    
    @staticmethod
    async def compare(original: str, modified: str, context_lines: int = 3, **kwargs) -> ToolResult:
        """Compare two texts and show diff"""
        try:
            original_lines = original.splitlines(keepends=True)
            modified_lines = modified.splitlines(keepends=True)
            
            diff = list(difflib.unified_diff(
                original_lines, 
                modified_lines,
                lineterm='',
                n=context_lines
            ))
            
            added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
            removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
            
            return ToolResult({
                "diff": '\n'.join(diff),
                "added": added,
                "removed": removed,
                "unchanged": len(original_lines) - removed,
                "total_changes": added + removed
            })
            
        except Exception as e:
            raise ToolError("DIFF_ERROR", str(e))


class RegexTool(BaseTool):
    TOOL_ID = "text.regex"
    CAPABILITIES = {"match": "match"}
    
    async def match(self, **kwargs) -> ToolResult:
        return await TextTools.match(**kwargs)


class TransformTool(BaseTool):
    TOOL_ID = "text.transform"
    CAPABILITIES = {"transform": "transform"}
    
    async def transform(self, **kwargs) -> ToolResult:
        return await TextTools.transform(**kwargs)


class DiffTool(BaseTool):
    TOOL_ID = "text.diff"
    CAPABILITIES = {"compare": "compare"}
    
    async def compare(self, **kwargs) -> ToolResult:
        return await TextTools.compare(**kwargs)


BaseTool.register(RegexTool)
BaseTool.register(TransformTool)
BaseTool.register(DiffTool)
