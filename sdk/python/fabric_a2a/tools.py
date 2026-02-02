"""
Fabric A2A SDK - Tool Client
Convenient interface for calling built-in tools.
"""

from typing import TYPE_CHECKING, Optional, Dict, Any, List

if TYPE_CHECKING:
    from fabric_a2a.client import FabricClient

from fabric_a2a.models import FileContent, HTTPResponse, CalculationResult, HashResult


class ToolClient:
    """
    Client for Fabric built-in tools.
    
    Access via:
        >>> client = FabricClient(...)
        >>> client.tools.math.calculate("2 + 2")
        >>> client.tools.io.read_file("./README.md")
    """
    
    def __init__(self, client: "FabricClient"):
        self._client = client
        
        # Sub-clients for categories
        self.io = IOTools(client)
        self.web = WebTools(client)
        self.math = MathTools(client)
        self.text = TextTools(client)
        self.system = SystemTools(client)
        self.data = DataTools(client)
        self.security = SecurityTools(client)
        self.encode = EncodingTools(client)
        self.docs = DocsTools(client)
    
    def list(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available tools.
        
        Args:
            category: Optional category filter (io, web, math, etc.)
        
        Returns:
            List of tool information dictionaries
        """
        args = {}
        if category:
            args["category"] = category
        
        result = self._client.call("fabric.tool.list", args)
        return result.result.get("tools", [])
    
    def call(self, tool_id: str, capability: str = None, **kwargs) -> Any:
        """
        Call a tool directly.
        
        Args:
            tool_id: Tool ID (e.g., "io.read_file")
            capability: Capability name (optional)
            **kwargs: Arguments for the tool
        
        Returns:
            Tool-specific result
        """
        tool_name = f"fabric.tool.{tool_id}"
        result = self._client.call(tool_name, kwargs)
        return result.result


class IOTools:
    """File system operations"""
    
    def __init__(self, client: "FabricClient"):
        self._client = client
    
    def read_file(
        self,
        path: str,
        max_lines: Optional[int] = None,
        encoding: str = "utf-8"
    ) -> FileContent:
        """
        Read a file's contents.
        
        Args:
            path: File path
            max_lines: Maximum lines to read (optional)
            encoding: File encoding (default: utf-8)
        
        Returns:
            FileContent object
        """
        args = {"path": path, "encoding": encoding}
        if max_lines:
            args["max_lines"] = max_lines
        
        result = self._client.call("fabric.tool.io.read_file", args)
        return FileContent(**result.result)
    
    def write_file(
        self,
        path: str,
        content: str,
        append: bool = False
    ) -> Dict[str, Any]:
        """
        Write content to a file.
        
        Args:
            path: File path
            content: Content to write
            append: If True, append to file instead of overwriting
        
        Returns:
            Write result with bytes_written and path
        """
        result = self._client.call("fabric.tool.io.write_file", {
            "path": path,
            "content": content,
            "append": append
        })
        return result.result
    
    def list_directory(
        self,
        path: str = ".",
        recursive: bool = False,
        pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List directory contents.
        
        Args:
            path: Directory path
            recursive: List recursively
            pattern: Glob pattern filter (e.g., "*.py")
        
        Returns:
            Directory listing with entries
        """
        args = {"path": path, "recursive": recursive}
        if pattern:
            args["pattern"] = pattern
        
        result = self._client.call("fabric.tool.io.list_directory", args)
        return result.result
    
    def search_files(
        self,
        path: str,
        pattern: str,
        file_pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search file contents using regex.
        
        Args:
            path: Directory to search
            pattern: Regex pattern
            file_pattern: Optional file glob filter
        
        Returns:
            List of matches with file, line number, and text
        """
        args = {"path": path, "pattern": pattern}
        if file_pattern:
            args["file_pattern"] = file_pattern
        
        result = self._client.call("fabric.tool.io.search_files", args)
        return result.result.get("matches", [])


class WebTools:
    """Web and HTTP operations"""
    
    def __init__(self, client: "FabricClient"):
        self._client = client
    
    def http_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        timeout: int = 30000
    ) -> HTTPResponse:
        """
        Make HTTP request.
        
        Args:
            url: Request URL
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            headers: Request headers
            body: Request body
            timeout: Timeout in milliseconds
        
        Returns:
            HTTPResponse object
        """
        args = {
            "url": url,
            "method": method,
            "timeout": timeout
        }
        if headers:
            args["headers"] = headers
        if body:
            args["body"] = body
        
        result = self._client.call("fabric.tool.web.http_request", args)
        return HTTPResponse(**result.result)
    
    def get(self, url: str, **kwargs) -> HTTPResponse:
        """Convenience method for GET requests"""
        return self.http_request(url, method="GET", **kwargs)
    
    def post(self, url: str, **kwargs) -> HTTPResponse:
        """Convenience method for POST requests"""
        return self.http_request(url, method="POST", **kwargs)
    
    def fetch_page(
        self,
        url: str,
        extract_text: bool = True,
        max_length: int = 50000
    ) -> Dict[str, Any]:
        """
        Fetch and extract readable content from web page.
        
        Args:
            url: Page URL
            extract_text: Extract article text
            max_length: Maximum characters to return
        
        Returns:
            Page content with title, text, links, metadata
        """
        result = self._client.call("fabric.tool.web.fetch_page", {
            "url": url,
            "extract_text": extract_text,
            "max_length": max_length
        })
        return result.result
    
    def parse_url(self, url: str) -> Dict[str, Any]:
        """
        Parse URL into components.
        
        Args:
            url: URL to parse
        
        Returns:
            URL components (scheme, host, path, query, etc.)
        """
        result = self._client.call("fabric.tool.web.parse_url", {"url": url})
        return result.result


class MathTools:
    """Mathematical operations"""
    
    def __init__(self, client: "FabricClient"):
        self._client = client
    
    def calculate(self, expression: str, precision: int = 10) -> float:
        """
        Evaluate mathematical expression safely.
        
        Args:
            expression: Math expression (e.g., "sqrt(144) * 2")
            precision: Decimal precision
        
        Returns:
            Calculated result
        """
        result = self._client.call("fabric.tool.math.calculate", {
            "expression": expression,
            "precision": precision
        })
        return result.result.get("result")
    
    def statistics(
        self,
        data: List[float],
        measures: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Calculate statistical measures.
        
        Args:
            data: List of numbers
            measures: Measures to calculate (mean, median, stddev, min, max, count, sum)
        
        Returns:
            Dictionary of calculated statistics
        """
        args = {"data": data}
        if measures:
            args["measures"] = measures
        
        result = self._client.call("fabric.tool.math.statistics", args)
        return result.result


class TextTools:
    """Text processing operations"""
    
    def __init__(self, client: "FabricClient"):
        self._client = client
    
    def regex_match(
        self,
        text: str,
        pattern: str,
        flags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Match regex pattern in text.
        
        Args:
            text: Text to search
            pattern: Regex pattern
            flags: Optional flags (i=ignore case, m=multiline, s=dotall)
        
        Returns:
            Matches, groups, and count
        """
        args = {"text": text, "pattern": pattern}
        if flags:
            args["flags"] = flags
        
        result = self._client.call("fabric.tool.text.regex", args)
        return result.result
    
    def transform(
        self,
        text: str,
        operations: List[Dict[str, Any]]
    ) -> str:
        """
        Apply text transformations.
        
        Args:
            text: Input text
            operations: List of operations (uppercase, lowercase, trim, replace, etc.)
        
        Returns:
            Transformed text
        """
        result = self._client.call("fabric.tool.text.transform", {
            "text": text,
            "operations": operations
        })
        return result.result.get("result")
    
    def diff(
        self,
        original: str,
        modified: str,
        context_lines: int = 3
    ) -> Dict[str, Any]:
        """
        Compare two texts and show differences.
        
        Args:
            original: Original text
            modified: Modified text
            context_lines: Number of context lines
        
        Returns:
            Diff output with added/removed counts
        """
        result = self._client.call("fabric.tool.text.diff", {
            "original": original,
            "modified": modified,
            "context_lines": context_lines
        })
        return result.result


class SystemTools:
    """System operations"""
    
    def __init__(self, client: "FabricClient"):
        self._client = client
    
    def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: int = 30000,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute shell command (sandboxed).
        
        Args:
            command: Shell command
            working_dir: Working directory
            timeout: Timeout in milliseconds
            env: Environment variables
        
        Returns:
            stdout, stderr, exit_code, duration
        """
        args = {"command": command, "timeout": timeout}
        if working_dir:
            args["working_dir"] = working_dir
        if env:
            args["env"] = env
        
        result = self._client.call("fabric.tool.system.execute", args)
        return result.result
    
    def env(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get environment variables.
        
        Args:
            name: Specific variable name (optional)
        
        Returns:
            Environment variable(s)
        """
        args = {}
        if name:
            args["name"] = name
        
        result = self._client.call("fabric.tool.system.env", args)
        return result.result
    
    def datetime(self, timezone: str = "UTC") -> Dict[str, Any]:
        """
        Get current datetime.
        
        Args:
            timezone: Timezone name
        
        Returns:
            ISO timestamp, Unix timestamp, formatted string
        """
        result = self._client.call("fabric.tool.system.datetime", {
            "timezone": timezone
        })
        return result.result


class DataTools:
    """Data processing operations"""
    
    def __init__(self, client: "FabricClient"):
        self._client = client
    
    def parse_json(
        self,
        json_str: str,
        query: Optional[str] = None
    ) -> Any:
        """
        Parse JSON string and optionally query with JSONPath.
        
        Args:
            json_str: JSON string to parse
            query: Optional JSONPath query
        
        Returns:
            Parsed data
        """
        args = {"json": json_str}
        if query:
            args["query"] = query
        
        result = self._client.call("fabric.tool.data.json", args)
        return result.result.get("data")
    
    def parse_csv(
        self,
        csv: str,
        delimiter: str = ",",
        headers: bool = True
    ) -> Dict[str, Any]:
        """
        Parse CSV to array of objects.
        
        Args:
            csv: CSV string
            delimiter: Field delimiter
            headers: First row is headers
        
        Returns:
            Rows and headers
        """
        result = self._client.call("fabric.tool.data.csv", {
            "csv": csv,
            "delimiter": delimiter,
            "headers": headers
        })
        return result.result
    
    def validate_schema(
        self,
        data: Dict,
        schema: Dict
    ) -> Dict[str, Any]:
        """
        Validate data against JSON Schema.
        
        Args:
            data: Data to validate
            schema: JSON Schema
        
        Returns:
            Validation result with errors if any
        """
        result = self._client.call("fabric.tool.data.validate", {
            "data": data,
            "schema": schema
        })
        return result.result


class SecurityTools:
    """Security operations"""
    
    def __init__(self, client: "FabricClient"):
        self._client = client
    
    def hash(
        self,
        data: str,
        algorithm: str = "sha256"
    ) -> HashResult:
        """
        Generate cryptographic hash.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm (md5, sha1, sha256, sha512)
        
        Returns:
            Hash result with hex digest
        """
        result = self._client.call("fabric.tool.security.hash", {
            "data": data,
            "algorithm": algorithm
        })
        return HashResult(**result.result)
    
    def base64_encode(self, data: str) -> str:
        """
        Base64 encode string.
        
        Args:
            data: String to encode
        
        Returns:
            Base64 encoded string
        """
        result = self._client.call("fabric.tool.security.base64", {
            "data": data,
            "decode": False
        })
        return result.result.get("result")
    
    def base64_decode(self, data: str) -> str:
        """
        Base64 decode string.
        
        Args:
            data: Base64 string to decode
        
        Returns:
            Decoded string
        """
        result = self._client.call("fabric.tool.security.base64", {
            "data": data,
            "decode": True
        })
        return result.result.get("result")


class EncodingTools:
    """Encoding operations"""
    
    def __init__(self, client: "FabricClient"):
        self._client = client
    
    def url_encode(self, text: str) -> str:
        """URL encode string"""
        result = self._client.call("fabric.tool.encode.url", {
            "text": text,
            "decode": False
        })
        return result.result.get("result")
    
    def url_decode(self, text: str) -> str:
        """URL decode string"""
        result = self._client.call("fabric.tool.encode.url", {
            "text": text,
            "decode": True
        })
        return result.result.get("result")


class DocsTools:
    """Documentation operations"""
    
    def __init__(self, client: "FabricClient"):
        self._client = client
    
    def process_markdown(
        self,
        markdown: str,
        extract_toc: bool = True
    ) -> Dict[str, Any]:
        """
        Process markdown to HTML and extract structure.
        
        Args:
            markdown: Markdown text
            extract_toc: Extract table of contents
        
        Returns:
            HTML, headings, TOC
        """
        result = self._client.call("fabric.tool.docs.markdown", {
            "markdown": markdown,
            "extract_toc": extract_toc
        })
        return result.result