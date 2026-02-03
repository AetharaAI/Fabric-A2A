"""
Built-in Math Tools - Calculations and Statistics

Refactored to use the new BaseTool plugin architecture.
"""

import math
import statistics
from typing import Dict, Any, List, Optional

from tools.base import BaseTool, ToolResult, ToolError


class MathTools(BaseTool):
    """Mathematical calculation tools"""
    
    TOOL_ID = "math"
    CAPABILITIES = {}
    
    @staticmethod
    async def eval(expression: str, precision: int = 10, **kwargs) -> ToolResult:
        """Safely evaluate mathematical expression"""
        
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
            code = compile(expression, '<string>', 'eval')
            
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


class CalculateTool(BaseTool):
    TOOL_ID = "math.calculate"
    CAPABILITIES = {"eval": "eval"}
    
    async def eval(self, **kwargs) -> ToolResult:
        return await MathTools.eval(**kwargs)


class StatisticsTool(BaseTool):
    TOOL_ID = "math.statistics"
    CAPABILITIES = {"analyze": "analyze"}
    
    async def analyze(self, **kwargs) -> ToolResult:
        return await MathTools.analyze(**kwargs)


BaseTool.register(CalculateTool)
BaseTool.register(StatisticsTool)
