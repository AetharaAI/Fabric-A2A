"""
Fabric MCP Server - Built-in Tool Inventory
Implements common tools that execute directly within the Fabric gateway.

These tools provide universal capabilities without requiring external agents:
- File operations (io.*)
- Web requests (web.*)
- Math functions (math.*)
- Text processing (text.*)
- System commands (system.*)
- Data processing (data.*)
- Security utilities (security.*)
- Documentation (docs.*)
"""

import os
import re
import json
import aiohttp
import hashlib
import base64
import subprocess
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass
from pathlib import Path
import fnmatch


class ToolError(Exception):
    """Error raised by built-in tools"""
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ToolResult:
    """Standard result wrapper for tool execution"""
    def __init__(self, data: Dict[str, Any], success: bool = True):
        self.data = data
        self.success = success
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.success,
            "result": self.data if self.success else None,
            "error": self.data if not self.success else None
        }


# ============================================================================
# I/O Tools - File System Operations
# ============================================================================

class IOTools:
    """File system operation tools"""
    
    @staticmethod
    async def read(path: str, max_lines: Optional[int] = None, encoding: str = 'utf-8', **kwargs) -> ToolResult:
        """Read file contents"""
        try:
            file_path = Path(path).resolve()
            
            # Security check - prevent accessing sensitive files
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
            
            # Security check
            if IOTools._is_restricted_path(file_path):
                raise ToolError("ACCESS_DENIED", f"Access to path not allowed: {path}")
            
            # Create parent directories if needed
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
                    # Skip files that can't be read
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
        # Add your security restrictions here
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


# ============================================================================
# Web Tools - HTTP and URL Operations
# ============================================================================

class WebTools:
    """Web request and URL processing tools"""
    
    @staticmethod
    async def request(url: str, method: str = 'GET', headers: Optional[Dict] = None, 
                      body: Optional[str] = None, timeout: int = 30000, **kwargs) -> ToolResult:
        """Make HTTP request"""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                request_kwargs = {
                    'headers': headers or {},
                    'timeout': aiohttp.ClientTimeout(total=timeout / 1000)
                }
                if body and method.upper() in ['POST', 'PUT', 'PATCH']:
                    request_kwargs['data'] = body
                
                start_time = asyncio.get_event_loop().time()
                async with session.request(method.upper(), url, **request_kwargs) as response:
                    elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                    response_body = await response.text()
                    
                    return ToolResult({
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": response_body[:100000],  # Limit response size
                        "elapsed_ms": elapsed_ms,
                        "url": str(response.url)
                    })
                    
        except asyncio.TimeoutError:
            raise ToolError("TIMEOUT", f"Request timed out after {timeout}ms")
        except Exception as e:
            raise ToolError("REQUEST_ERROR", str(e))
    
    @staticmethod
    async def fetch(url: str, extract_text: bool = True, max_length: int = 50000, **kwargs) -> ToolResult:
        """Fetch and extract content from web page"""
        import aiohttp
        from html.parser import HTMLParser
        
        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text_parts = []
                self.in_skip_tag = 0
                self.skip_tags = {'script', 'style', 'nav', 'footer', 'header'}
                
            def handle_starttag(self, tag, attrs):
                if tag in self.skip_tags:
                    self.in_skip_tag += 1
                    
            def handle_endtag(self, tag):
                if tag in self.skip_tags:
                    self.in_skip_tag -= 1
                    
            def handle_data(self, data):
                if self.in_skip_tag == 0:
                    self.text_parts.append(data)
                    
            def get_text(self):
                text = ' '.join(self.text_parts)
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:max_length]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    html = await response.text()
                    
                    # Extract title
                    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                    title = title_match.group(1).strip() if title_match else None
                    
                    # Extract links
                    links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html)
                    
                    result = {
                        "title": title,
                        "url": str(response.url),
                        "links": list(set(links))[:50],  # Limit links
                        "metadata": {
                            "content_type": response.headers.get('Content-Type'),
                            "length": len(html)
                        }
                    }
                    
                    if extract_text:
                        extractor = TextExtractor()
                        try:
                            extractor.feed(html)
                            result["text"] = extractor.get_text()
                        except:
                            result["text"] = None
                    
                    return ToolResult(result)
                    
        except Exception as e:
            raise ToolError("FETCH_ERROR", str(e))
    
    @staticmethod
    async def parse_url(url: str, **kwargs) -> ToolResult:
        """Parse URL into components"""
        from urllib.parse import urlparse, parse_qs
        
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            # Flatten single-item lists
            query = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
            
            return ToolResult({
                "scheme": parsed.scheme,
                "netloc": parsed.netloc,
                "path": parsed.path,
                "params": parsed.params,
                "query": query,
                "fragment": parsed.fragment,
                "hostname": parsed.hostname,
                "port": parsed.port
            })
            
        except Exception as e:
            raise ToolError("PARSE_ERROR", str(e))

    

    @staticmethod
    async def brave_search(query: str, recency_days: int = 7, max_results: int = 5):
        key = os.getenv("BRAVE_API_KEY")
        if not key:
            raise RuntimeError("BRAVE_API_KEY not set")

        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": key
        }
        params = {
            "q": query,
            "recency": recency_days,
            "domains": None,
        }

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, headers=headers, params=params) as r:
                r.raise_for_status()
                data = await r.json()

        results = []
        for item in data.get("web", {}).get("results", [])[:max_results]:
            results.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("description"),
                "age_days": item.get("age"),
            })

        return ToolResult({
            "provider": "brave",
            "query": query,
            "results": results,
        })


# ============================================================================
# Math Tools - Calculations and Statistics
# ============================================================================

class MathTools:
    """Mathematical calculation tools"""
    
    @staticmethod
    async def eval(expression: str, precision: int = 10, **kwargs) -> ToolResult:
        """Safely evaluate mathematical expression"""
        import math
        
        # Whitelist of allowed names
        allowed_names = {
            'abs': abs, 'round': round, 'max': max, 'min': min,
            'sum': sum, 'pow': pow, 'len': len,
            'math': math,
            'pi': math.pi, 'e': math.e,
            'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
            'asin': math.asin, 'acos': math.acos, 'atan': math.atan,
            'sqrt': math.sqrt, 'log': math.log, 'log10': math.log10,
            'exp': math.exp, 'ceil': math.ceil, 'floor': math.floor,
            'degrees': math.degrees, 'radians': math.radians
        }
        
        try:
            # Compile and validate expression
            code = compile(expression, '<string>', 'eval')
            
            # Check for disallowed names
            for name in code.co_names:
                if name not in allowed_names:
                    raise ToolError("INVALID_EXPRESSION", f"Disallowed function: {name}")
            
            result = eval(code, {"__builtins__": {}}, allowed_names)
            
            return ToolResult({
                "result": round(result, precision) if isinstance(result, float) else result,
                "expression": expression,
                "type": type(result).__name__
            })
            
        except ToolError:
            raise
        except Exception as e:
            raise ToolError("EVAL_ERROR", f"Could not evaluate: {e}")
    
    @staticmethod
    async def analyze(data: List[float], measures: Optional[List[str]] = None, **kwargs) -> ToolResult:
        """Calculate statistical measures on dataset"""
        import statistics
        
        try:
            if not data:
                raise ToolError("EMPTY_DATA", "Data array is empty")
            
            measures = measures or ['mean', 'median', 'stddev', 'min', 'max']
            result = {"count": len(data), "sum": sum(data)}
            
            if 'mean' in measures:
                result['mean'] = statistics.mean(data)
            if 'median' in measures:
                result['median'] = statistics.median(data)
            if 'stddev' in measures and len(data) > 1:
                result['stddev'] = statistics.stdev(data)
            if 'min' in measures:
                result['min'] = min(data)
            if 'max' in measures:
                result['max'] = max(data)
            
            return ToolResult(result)
            
        except ToolError:
            raise
        except Exception as e:
            raise ToolError("STATS_ERROR", str(e))


# ============================================================================
# Text Tools - String Processing
# ============================================================================

class TextTools:
    """Text processing and transformation tools"""
    
    @staticmethod
    async def match(text: str, pattern: str, flags: Optional[List[str]] = None, **kwargs) -> ToolResult:
        """Match regex pattern in text"""
        try:
            flag_map = {'i': re.IGNORECASE, 'm': re.MULTILINE, 's': re.DOTALL, 'x': re.VERBOSE}
            re_flags = sum(flag_map.get(f, 0) for f in (flags or []))
            
            regex = re.compile(pattern, re_flags)
            matches = regex.findall(text)
            
            # Get groups if any
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
        import difflib
        
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


# ============================================================================
# System Tools - Command Execution and Environment
# ============================================================================

class SystemTools:
    """System command and environment tools"""
    
    @staticmethod
    async def exec(command: str, working_dir: Optional[str] = None, 
                   timeout: int = 30000, env: Optional[Dict[str, str]] = None, **kwargs) -> ToolResult:
        """Execute shell command safely"""
        try:
            # Security: validate command against allowed patterns
            # This is a basic implementation - enhance for production
            dangerous = ['rm -rf /', 'sudo', 'chmod 777', '> /dev']
            for d in dangerous:
                if d in command.lower():
                    raise ToolError("DANGEROUS_COMMAND", f"Command contains dangerous pattern: {d}")
            
            cwd = Path(working_dir).resolve() if working_dir else None
            
            # Create environment
            run_env = os.environ.copy()
            if env:
                run_env.update(env)
            
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=run_env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout / 1000
                )
                duration_ms = timeout  # Simplified - track actual duration
                
                return ToolResult({
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace'),
                    "exit_code": process.returncode,
                    "duration_ms": duration_ms,
                    "command": command
                })
                
            except asyncio.TimeoutError:
                process.kill()
                raise ToolError("TIMEOUT", f"Command timed out after {timeout}ms")
                
        except ToolError:
            raise
        except Exception as e:
            raise ToolError("EXEC_ERROR", str(e))
    
    @staticmethod
    async def get(name: Optional[str] = None, **kwargs) -> ToolResult:
        """Get environment variables"""
        try:
            if name:
                value = os.environ.get(name)
                return ToolResult({
                    "name": name,
                    "value": value,
                    "exists": value is not None
                })
            else:
                # Filter out sensitive variables
                sensitive = ['PASSWORD', 'SECRET', 'TOKEN', 'KEY', 'CREDENTIAL']
                env = {k: v for k, v in os.environ.items() 
                       if not any(s in k.upper() for s in sensitive)}
                return ToolResult({
                    "variables": env,
                    "count": len(env)
                })
                
        except Exception as e:
            raise ToolError("ENV_ERROR", str(e))
    
    @staticmethod
    async def now(timezone: str = 'UTC', format: str = 'iso', **kwargs) -> ToolResult:
        """Get current datetime"""
        try:
            # Parse timezone
            if timezone.upper() == 'UTC':
                tz = timezone.utc
            else:
                from datetime import timedelta
                # Simple offset parsing (e.g., "+5", "-3:30")
                tz = timezone.utc
            
            now = datetime.now(tz=tz)
            
            result = {
                "iso": now.isoformat(),
                "timestamp": now.timestamp(),
                "timezone": timezone
            }
            
            if format == 'rfc2822':
                result["formatted"] = now.strftime('%a, %d %b %Y %H:%M:%S %z')
            elif format == 'custom' and 'custom_format' in kwargs:
                result["formatted"] = now.strftime(kwargs['custom_format'])
            else:
                result["formatted"] = result["iso"]
            
            return ToolResult(result)
            
        except Exception as e:
            raise ToolError("DATETIME_ERROR", str(e))


# ============================================================================
# Data Tools - JSON, CSV, Validation
# ============================================================================

class DataTools:
    """Data processing and validation tools"""
    
    @staticmethod
    async def parse(json_str: str, query: Optional[str] = None, **kwargs) -> ToolResult:
        """Parse JSON and optionally query with JSONPath"""
        try:
            data = json.loads(json_str)
            
            if query:
                # Simple JSONPath implementation
                # For production, use jsonpath-ng library
                result = DataTools._simple_jsonpath(data, query)
            else:
                result = data
            
            return ToolResult({
                "data": result,
                "valid": True,
                "type": type(result).__name__
            })
            
        except json.JSONDecodeError as e:
            return ToolResult({
                "data": None,
                "valid": False,
                "error": str(e)
            }, success=False)
        except Exception as e:
            raise ToolError("PARSE_ERROR", str(e))
    
    @staticmethod
    def _simple_jsonpath(data: Any, query: str) -> Any:
        """Simple JSONPath implementation"""
        # Handle simple dot notation: $.key.subkey
        if query.startswith('$.'):
            parts = query[2:].split('.')
            result = data
            for part in parts:
                if isinstance(result, dict):
                    result = result.get(part)
                elif isinstance(result, list) and part.isdigit():
                    result = result[int(part)] if int(part) < len(result) else None
                else:
                    return None
                if result is None:
                    return None
            return result
        return data
    
    @staticmethod
    async def csv_parse(csv: str, delimiter: str = ',', headers: bool = True, **kwargs) -> ToolResult:
        """Parse CSV to array of objects"""
        import csv as csv_module
        import io
        
        try:
            reader = csv_module.DictReader(io.StringIO(csv), delimiter=delimiter) if headers \
                     else csv_module.reader(io.StringIO(csv), delimiter=delimiter)
            
            if headers:
                rows = list(reader)
                headers_list = reader.fieldnames or []
            else:
                all_rows = list(reader)
                rows = [{f"col_{i}": v for i, v in enumerate(row)} for row in all_rows]
                headers_list = []
            
            return ToolResult({
                "rows": rows,
                "headers": headers_list,
                "row_count": len(rows)
            })
            
        except Exception as e:
            raise ToolError("CSV_ERROR", str(e))
    
    @staticmethod
    async def validate(data: Dict, schema: Dict, **kwargs) -> ToolResult:
        """Validate data against JSON Schema"""
        try:
            from jsonschema import validate as jsonschema_validate, ValidationError
            
            jsonschema_validate(instance=data, schema=schema)
            
            return ToolResult({
                "valid": True,
                "errors": []
            })
            
        except ValidationError as e:
            return ToolResult({
                "valid": False,
                "errors": [{
                    "message": e.message,
                    "path": list(e.path),
                    "schema_path": list(e.schema_path)
                }]
            }, success=True)  # Still success, just invalid data
        except ImportError:
            # Fallback if jsonschema not installed
            return ToolResult({
                "valid": True,
                "errors": [],
                "note": "Validation skipped - jsonschema library not installed"
            })
        except Exception as e:
            raise ToolError("VALIDATION_ERROR", str(e))


# ============================================================================
# Security Tools - Hashing and Encoding
# ============================================================================

class SecurityTools:
    """Security utilities - hashing, encoding"""
    
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


# ============================================================================
# Encoding Tools - URL Encoding
# ============================================================================

class EncodeTools:
    """Encoding utilities"""
    
    @staticmethod
    async def url_encode(text: str, decode: bool = False, **kwargs) -> ToolResult:
        """URL encode/decode text"""
        from urllib.parse import quote, unquote
        
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


# ============================================================================
# Documentation Tools - Markdown Processing
# ============================================================================

class DocsTools:
    """Documentation processing tools"""
    
    @staticmethod
    async def markdown_process(markdown: str, extract_toc: bool = True, **kwargs) -> ToolResult:
        """Process markdown - convert to HTML, extract TOC"""
        try:
            # Extract headings for TOC
            heading_pattern = r'^(#{1,6})\s+(.+)$'
            headings = []
            for match in re.finditer(heading_pattern, markdown, re.MULTILINE):
                level = len(match.group(1))
                title = match.group(2)
                anchor = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '-').lower()
                headings.append({
                    "level": level,
                    "title": title,
                    "anchor": anchor
                })
            
            # Simple markdown to HTML conversion (basic)
            html = markdown
            # Headers
            for i in range(6, 0, -1):
                html = re.sub(rf'^#{i}\s+(.+)$', rf'<h{i}>\1</h{i}>', html, flags=re.MULTILINE)
            # Bold/Italic
            html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', html)
            html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
            html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', html)
            # Code
            html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
            # Links
            html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
            # Paragraphs
            html = re.sub(r'\n\n', '</p><p>', html)
            html = '<p>' + html + '</p>'
            
            result = {
                "html": html,
                "headings": headings,
                "heading_count": len(headings)
            }
            
            if extract_toc:
                result["toc"] = headings
            
            return ToolResult(result)
            
        except Exception as e:
            raise ToolError("MARKDOWN_ERROR", str(e))


# ============================================================================
# Tool Registry - Map tool IDs to implementations
# ============================================================================

# Export BUILTIN_TOOLS for server integration
__all__ = ['execute_tool', 'list_builtin_tools', 'get_tool_info', 'ToolResult', 'ToolError', 'BUILTIN_TOOLS']

BUILTIN_TOOLS = {
    # I/O Tools
    "io.read_file": (IOTools, "read"),
    "io.write_file": (IOTools, "write"),
    "io.list_directory": (IOTools, "list"),
    "io.search_files": (IOTools, "search"),
    
    # Web Tools
    "web.http_request": (WebTools, "request"),
    "web.fetch_page": (WebTools, "fetch"),
    "web.parse_url": (WebTools, "parse_url"),
    "web.brave_search": (WebTools, "brave_search"),

    
    # Math Tools
    "math.calculate": (MathTools, "eval"),
    "math.statistics": (MathTools, "analyze"),
    
    # Text Tools
    "text.regex": (TextTools, "match"),
    "text.transform": (TextTools, "transform"),
    "text.diff": (TextTools, "compare"),
    
    # System Tools
    "system.execute": (SystemTools, "exec"),
    "system.env": (SystemTools, "get"),
    "system.datetime": (SystemTools, "now"),
    
    # Data Tools
    "data.json": (DataTools, "parse"),
    "data.csv": (DataTools, "csv_parse"),
    "data.validate": (DataTools, "validate"),
    
    # Security Tools
    "security.hash": (SecurityTools, "hash"),
    "security.base64": (SecurityTools, "base64_encode"),
    
    # Encoding Tools
    "encode.url": (EncodeTools, "url_encode"),
    
    # Documentation Tools
    "docs.markdown": (DocsTools, "markdown_process"),
}


async def execute_tool(tool_id: str, capability: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a built-in tool by ID
    
    Args:
        tool_id: The tool identifier (e.g., "io.read_file")
        capability: The capability name (e.g., "read")
        arguments: The arguments to pass to the tool
    
    Returns:
        Tool execution result dictionary
    """
    full_id = f"{tool_id}.{capability}" if capability else tool_id
    
    if tool_id not in BUILTIN_TOOLS:
        raise ToolError("TOOL_NOT_FOUND", f"Built-in tool not found: {tool_id}")
    
    tool_class, method_name = BUILTIN_TOOLS[tool_id]
    method = getattr(tool_class, method_name, None)
    
    if not method:
        raise ToolError("CAPABILITY_NOT_FOUND", f"Capability '{capability}' not found on tool '{tool_id}'")
    
    try:
        result = await method(**arguments)
        return result.to_dict()
        
    except ToolError as e:
        return ToolResult({
            "code": e.code,
            "message": e.message,
            "details": e.details
        }, success=False).to_dict()
    except Exception as e:
        return ToolResult({
            "code": "EXECUTION_ERROR",
            "message": str(e)
        }, success=False).to_dict()


def get_tool_info(tool_id: str) -> Optional[Dict[str, Any]]:
    """Get information about a built-in tool"""
    if tool_id not in BUILTIN_TOOLS:
        return None
    
    tool_class, method_name = BUILTIN_TOOLS[tool_id]
    method = getattr(tool_class, method_name, None)
    
    return {
        "tool_id": tool_id,
        "class": tool_class.__name__,
        "method": method_name,
        "available": method is not None
    }


def list_builtin_tools() -> List[str]:
    """List all available built-in tool IDs"""
    return list(BUILTIN_TOOLS.keys())
