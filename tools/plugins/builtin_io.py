"""
Built-in I/O Tools - File System Operations

Refactored to use the new BaseTool plugin architecture.
"""

import os
import re
import fnmatch
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncIterator

from tools.base import BaseTool, ToolResult, ToolError


class IOTools(BaseTool):
    """File system operation tools"""
    
    TOOL_ID = "io"  # Base ID, actual tools use io.read_file, etc.
    CAPABILITIES = {}
    
    @staticmethod
    async def read(path: str, max_lines: Optional[int] = None, encoding: str = 'utf-8', **kwargs) -> ToolResult:
        """Read file contents"""
        try:
            file_path = Path(path).resolve()
            
            # Security check
            if IOTools._is_restricted_path(file_path):
                raise ToolError("ACCESS_DENIED", f"Access to path not allowed: {path}")
            
            if not file_path.exists():
                raise ToolError("FILE_NOT_FOUND", f"File not found: {path}")
            
            with open(file_path, 'r', encoding=encoding) as f:
                if max_lines:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    content = ''.join(lines)
                    truncated = True
                    line_count = max_lines
                else:
                    content = f.read()
                    truncated = False
                    line_count = content.count('\n') + 1
            
            return ToolResult({
                "content": content,
                "line_count": line_count,
                "truncated": truncated,
                "path": str(file_path),
                "size": len(content)
            })
            
        except ToolError:
            raise
        except UnicodeDecodeError:
            raise ToolError("DECODE_ERROR", f"Could not decode file as {encoding}")
        except Exception as e:
            raise ToolError("READ_ERROR", str(e))
    
    @staticmethod
    async def write(path: str, content: str, append: bool = False, **kwargs) -> ToolResult:
        """Write content to file"""
        try:
            file_path = Path(path).resolve()
            
            if IOTools._is_restricted_path(file_path):
                raise ToolError("ACCESS_DENIED", f"Access to path not allowed: {path}")
            
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            mode = 'a' if append else 'w'
            with open(file_path, mode, encoding='utf-8') as f:
                f.write(content)
            
            bytes_written = len(content.encode('utf-8'))
            
            return ToolResult({
                "bytes_written": bytes_written,
                "path": str(file_path),
                "append": append
            })
            
        except ToolError:
            raise
        except Exception as e:
            raise ToolError("WRITE_ERROR", str(e))
    
    @staticmethod
    async def list(path: str = '.', recursive: bool = False, pattern: Optional[str] = None, **kwargs) -> ToolResult:
        """List directory contents"""
        try:
            dir_path = Path(path).resolve()
            
            if not dir_path.exists():
                raise ToolError("DIR_NOT_FOUND", f"Directory not found: {path}")
            
            entries = []
            
            if recursive:
                for item in dir_path.rglob('*'):
                    if pattern and not fnmatch.fnmatch(item.name, pattern):
                        continue
                    entries.append(IOTools._entry_to_dict(item))
            else:
                for item in dir_path.iterdir():
                    if pattern and not fnmatch.fnmatch(item.name, pattern):
                        continue
                    entries.append(IOTools._entry_to_dict(item))
            
            return ToolResult({
                "path": str(dir_path),
                "entries": sorted(entries, key=lambda x: (x['type'] == 'file', x['name'])),
                "count": len(entries)
            })
            
        except ToolError:
            raise
        except Exception as e:
            raise ToolError("LIST_ERROR", str(e))
    
    @staticmethod
    async def search(path: str, pattern: str, file_pattern: Optional[str] = None, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """Search file contents using regex"""
        try:
            dir_path = Path(path).resolve()
            
            if not dir_path.exists():
                raise ToolError("DIR_NOT_FOUND", f"Directory not found: {path}")
            
            regex = re.compile(pattern)
            match_count = 0
            files_searched = 0
            
            for file_path in dir_path.rglob('*'):
                if not file_path.is_file():
                    continue
                
                if file_pattern and not fnmatch.fnmatch(file_path.name, file_pattern):
                    continue
                
                files_searched += 1
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            matches = regex.findall(line)
                            if matches:
                                match_count += len(matches)
                                yield {
                                    "event": "match",
                                    "data": {
                                        "file": str(file_path.relative_to(dir_path)),
                                        "line": line_num,
                                        "matches": matches,
                                        "text": line.strip()[:200]
                                    }
                                }
                except Exception:
                    pass
            
            yield {
                "event": "final",
                "data": {
                    "ok": True,
                    "result": {
                        "files_searched": files_searched,
                        "total_matches": match_count
                    }
                }
            }
            
        except ToolError:
            raise
        except Exception as e:
            raise ToolError("SEARCH_ERROR", str(e))
    
    @staticmethod
    def _is_restricted_path(path: Path) -> bool:
        """Check if path is restricted for security"""
        restricted = ['/etc/shadow', '/etc/passwd', '.ssh', '.env']
        path_str = str(path)
        return any(r in path_str for r in restricted)
    
    @staticmethod
    def _entry_to_dict(path: Path) -> Dict[str, Any]:
        """Convert path entry to dictionary"""
        stat = path.stat()
        return {
            "name": path.name,
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size if path.is_file() else None,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        }


# Individual tool classes for the new registry system
class ReadFileTool(BaseTool):
    TOOL_ID = "io.read_file"
    CAPABILITIES = {"read": "read"}
    
    async def read(self, **kwargs) -> ToolResult:
        return await IOTools.read(**kwargs)


class WriteFileTool(BaseTool):
    TOOL_ID = "io.write_file"
    CAPABILITIES = {"write": "write"}
    
    async def write(self, **kwargs) -> ToolResult:
        return await IOTools.write(**kwargs)


class ListDirectoryTool(BaseTool):
    TOOL_ID = "io.list_directory"
    CAPABILITIES = {"list": "list"}
    
    async def list(self, **kwargs) -> ToolResult:
        return await IOTools.list(**kwargs)


class SearchFilesTool(BaseTool):
    TOOL_ID = "io.search_files"
    CAPABILITIES = {"search": "search"}
    
    async def search(self, **kwargs) -> ToolResult:
        # Note: This returns an async iterator, needs special handling
        return await IOTools.search(**kwargs)


# Auto-register
BaseTool.register(ReadFileTool)
BaseTool.register(WriteFileTool)
BaseTool.register(ListDirectoryTool)
BaseTool.register(SearchFilesTool)
