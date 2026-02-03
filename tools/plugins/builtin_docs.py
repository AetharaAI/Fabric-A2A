"""
Built-in Documentation Tools - Markdown Processing

Refactored to use the new BaseTool plugin architecture.
"""

import re
from typing import Dict, Any

from tools.base import BaseTool, ToolResult, ToolError


class DocsTools(BaseTool):
    """Documentation processing tools"""
    
    TOOL_ID = "docs"
    CAPABILITIES = {}
    
    @staticmethod
    async def markdown_process(markdown: str, extract_toc: bool = True, **kwargs) -> ToolResult:
        """Process markdown - convert to HTML, extract TOC"""
        try:
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
            
            html = markdown
            for i in range(6, 0, -1):
                html = re.sub(rf'^#{i}\s+(.+)$', rf'<h{i}>\1</h{i}>', html, flags=re.MULTILINE)
            html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', html)
            html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
            html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', html)
            html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
            html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
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


class MarkdownTool(BaseTool):
    TOOL_ID = "docs.markdown"
    CAPABILITIES = {"process": "markdown_process"}
    
    async def markdown_process(self, **kwargs) -> ToolResult:
        return await DocsTools.markdown_process(**kwargs)


BaseTool.register(MarkdownTool)
