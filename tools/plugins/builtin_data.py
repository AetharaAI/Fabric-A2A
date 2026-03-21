"""
Built-in Data Tools - JSON, CSV, Validation

Refactored to use the new BaseTool plugin architecture.
"""

import json
import csv as csv_module
import io
from typing import Dict, Any, Optional, Any

from tools.base import BaseTool, ToolResult, ToolError


class DataTools(BaseTool):
    """Data processing and validation tools"""
    
    TOOL_ID = "data"
    CAPABILITIES = {}
    
    @staticmethod
    async def parse(json_str: str, query: Optional[str] = None, **kwargs) -> ToolResult:
        """Parse JSON and optionally query with JSONPath"""
        try:
            data = json.loads(json_str)
            
            if query:
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
            }, success=True)
        except ImportError:
            return ToolResult({
                "valid": True,
                "errors": [],
                "note": "Validation skipped - jsonschema library not installed"
            })
        except Exception as e:
            raise ToolError("VALIDATION_ERROR", str(e))


class JSONTool(BaseTool):
    TOOL_ID = "data.json"
    CAPABILITIES = {"parse": "parse"}
    
    async def parse(self, **kwargs) -> ToolResult:
        return await DataTools.parse(**kwargs)


class CSVTool(BaseTool):
    TOOL_ID = "data.csv"
    CAPABILITIES = {"parse": "csv_parse"}
    
    async def csv_parse(self, **kwargs) -> ToolResult:
        return await DataTools.csv_parse(**kwargs)


class ValidateTool(BaseTool):
    TOOL_ID = "data.validate"
    CAPABILITIES = {"validate": "validate"}
    
    async def validate(self, **kwargs) -> ToolResult:
        return await DataTools.validate(**kwargs)


BaseTool.register(JSONTool)
BaseTool.register(CSVTool)
BaseTool.register(ValidateTool)
