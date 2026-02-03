"""
Built-in System Tools - Command Execution and Environment

Refactored to use the new BaseTool plugin architecture.
"""

import os
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from tools.base import BaseTool, ToolResult, ToolError


class SystemTools(BaseTool):
    """System command and environment tools"""
    
    TOOL_ID = "system"
    CAPABILITIES = {}
    
    @staticmethod
    async def exec(command: str, working_dir: Optional[str] = None, 
                   timeout: int = 30000, env: Optional[Dict[str, str]] = None, **kwargs) -> ToolResult:
        """Execute shell command safely"""
        try:
            dangerous = ['rm -rf /', 'sudo', 'chmod 777', '> /dev']
            for d in dangerous:
                if d in command.lower():
                    raise ToolError("DANGEROUS_COMMAND", f"Command contains dangerous pattern: {d}")
            
            cwd = Path(working_dir).resolve() if working_dir else None
            
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
                
                return ToolResult({
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace'),
                    "exit_code": process.returncode,
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
    async def now(timezone_str: str = 'UTC', format: str = 'iso', **kwargs) -> ToolResult:
        """Get current datetime"""
        try:
            if timezone_str.upper() == 'UTC':
                tz = timezone.utc
            else:
                tz = timezone.utc
            
            now = datetime.now(tz=tz)
            
            result = {
                "iso": now.isoformat(),
                "timestamp": now.timestamp(),
                "timezone": timezone_str
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


class ExecuteTool(BaseTool):
    TOOL_ID = "system.execute"
    CAPABILITIES = {"exec": "exec"}
    trust_tier = "local"
    
    async def exec(self, **kwargs) -> ToolResult:
        return await SystemTools.exec(**kwargs)


class EnvTool(BaseTool):
    TOOL_ID = "system.env"
    CAPABILITIES = {"get": "get"}
    
    async def get(self, **kwargs) -> ToolResult:
        return await SystemTools.get(**kwargs)


class DateTimeTool(BaseTool):
    TOOL_ID = "system.datetime"
    CAPABILITIES = {"now": "now"}
    
    async def now(self, **kwargs) -> ToolResult:
        return await SystemTools.now(**kwargs)


BaseTool.register(ExecuteTool)
BaseTool.register(EnvTool)
BaseTool.register(DateTimeTool)
