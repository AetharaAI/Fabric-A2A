"""
Custom Tool Example: Webhook Notifications

This tool sends notifications to Slack, Discord, or generic webhooks.
It's a complete working example showing:
- How to create a custom tool
- How to use external APIs
- How to handle configuration
- How to format different message types

SETUP:
1. Copy this file to tools/plugins/custom/webhook_notifications.py (done)
2. Set environment variables in .env:
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
3. Restart Fabric
4. Tool is available as: notification.send

USAGE:
{
  "tool_id": "notification.send",
  "capability": "send",
  "parameters": {
    "channel": "slack",
    "message": "Deployment complete!",
    "level": "success"
  }
}
"""

import os
import json
from typing import Dict, Any, Optional
import aiohttp

from tools.base import BaseTool, ToolResult, ToolError


class NotificationTool(BaseTool):
    """
    Send notifications to Slack, Discord, or generic webhooks.
    
    Supports different message levels (info, success, warning, error)
    and formatted attachments for rich messages.
    
    Environment Variables:
    - SLACK_WEBHOOK_URL: Slack incoming webhook URL
    - DISCORD_WEBHOOK_URL: Discord webhook URL
    - GENERIC_WEBHOOK_URL: Fallback webhook URL
    """
    
    TOOL_ID = "notification.send"
    CAPABILITIES = {
        "send": "send",
        "slack": "send_slack",
        "discord": "send_discord",
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        # Load webhook URLs from config or environment
        self.slack_url = self._get_config("slack_webhook_url", "SLACK_WEBHOOK_URL")
        self.discord_url = self._get_config("discord_webhook_url", "DISCORD_WEBHOOK_URL")
        self.generic_url = self._get_config("generic_webhook_url", "GENERIC_WEBHOOK_URL")
    
    def _get_config(self, config_key: str, env_var: str) -> Optional[str]:
        """Get value from config dict or environment variable"""
        return self.config.get(config_key) or os.getenv(env_var)
    
    async def send(
        self,
        channel: str,
        message: str,
        level: str = "info",
        title: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ToolResult:
        """
        Send notification to specified channel
        
        Args:
            channel: 'slack', 'discord', or 'generic'
            message: Main message text
            level: 'info', 'success', 'warning', 'error'
            title: Optional title/header
            fields: Optional key-value pairs for attachments
            
        Returns:
            ToolResult with delivery status
        """
        if channel == "slack":
            return await self.send_slack(message, level, title, fields, **kwargs)
        elif channel == "discord":
            return await self.send_discord(message, level, title, fields, **kwargs)
        else:
            return await self.send_generic(channel, message, level, title, fields, **kwargs)
    
    async def send_slack(
        self,
        message: str,
        level: str = "info",
        title: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ToolResult:
        """Send Slack notification via webhook"""
        if not self.slack_url:
            raise ToolError(
                "CONFIG_ERROR",
                "Slack webhook URL not configured. Set SLACK_WEBHOOK_URL in .env"
            )
        
        # Color based on level
        colors = {
            "info": "#36a64f",
            "success": "#36a64f",
            "warning": "#ff9900",
            "error": "#ff0000"
        }
        
        # Build Slack attachment
        attachment = {
            "color": colors.get(level, "#36a64f"),
            "text": message,
            "footer": "Fabric MCP",
            "ts": int(__import__('time').time())
        }
        
        if title:
            attachment["title"] = title
        
        if fields:
            attachment["fields"] = [
                {"title": k, "value": v, "short": len(str(v)) < 50}
                for k, v in fields.items()
            ]
        
        payload = {
            "attachments": [attachment]
        }
        
        return await self._post_webhook(self.slack_url, payload, "Slack")
    
    async def send_discord(
        self,
        message: str,
        level: str = "info",
        title: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ToolResult:
        """Send Discord notification via webhook"""
        if not self.discord_url:
            raise ToolError(
                "CONFIG_ERROR",
                "Discord webhook URL not configured. Set DISCORD_WEBHOOK_URL in .env"
            )
        
        # Color based on level (Discord uses integer colors)
        colors = {
            "info": 0x36a64f,
            "success": 0x36a64f,
            "warning": 0xff9900,
            "error": 0xff0000
        }
        
        # Build Discord embed
        embed = {
            "description": message,
            "color": colors.get(level, 0x36a64f),
            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
        }
        
        if title:
            embed["title"] = title
        
        if fields:
            embed["fields"] = [
                {"name": k, "value": str(v)[:1024], "inline": len(str(v)) < 50}
                for k, v in fields.items()
            ]
        
        payload = {
            "embeds": [embed]
        }
        
        return await self._post_webhook(self.discord_url, payload, "Discord")
    
    async def send_generic(
        self,
        url: str,
        message: str,
        level: str = "info",
        title: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ToolResult:
        """Send notification to generic webhook"""
        payload = {
            "message": message,
            "level": level,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
        }
        
        if title:
            payload["title"] = title
        if fields:
            payload["fields"] = fields
        
        return await self._post_webhook(url or self.generic_url, payload, "Generic")
    
    async def _post_webhook(
        self,
        url: str,
        payload: Dict,
        provider: str
    ) -> ToolResult:
        """Internal method to POST to webhook URL"""
        if not url:
            raise ToolError("CONFIG_ERROR", f"No webhook URL configured for {provider}")
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status >= 400:
                        body = await response.text()
                        raise ToolError(
                            "WEBHOOK_ERROR",
                            f"{provider} returned {response.status}: {body[:200]}"
                        )
                    
                    return ToolResult({
                        "success": True,
                        "provider": provider,
                        "status_code": response.status,
                        "message": f"Notification sent to {provider}"
                    })
                    
        except aiohttp.ClientError as e:
            raise ToolError("CONNECTION_ERROR", f"Failed to connect to {provider}: {e}")
        except Exception as e:
            raise ToolError("SEND_ERROR", f"Failed to send {provider} notification: {e}")


# Auto-register
BaseTool.register(NotificationTool)


# =============================================================================
# USAGE EXAMPLES (for testing)
# =============================================================================
"""
# Example 1: Simple Slack notification
{
  "name": "fabric.tool.call",
  "arguments": {
    "tool_id": "notification.send",
    "capability": "send",
    "parameters": {
      "channel": "slack",
      "message": "Build completed successfully!",
      "level": "success"
    }
  }
}

# Example 2: Rich Discord notification with fields
{
  "name": "fabric.tool.call",
  "arguments": {
    "tool_id": "notification.send",
    "capability": "discord",
    "parameters": {
      "message": "New deployment detected",
      "level": "info",
      "title": "Deployment Alert",
      "fields": {
        "Version": "v2.1.0",
        "Environment": "production",
        "Duration": "45s",
        "Status": "Success"
      }
    }
  }
}

# Example 3: Error notification
{
  "name": "fabric.tool.call",
  "arguments": {
    "tool_id": "notification.send",
    "capability": "slack",
    "parameters": {
      "message": "Pipeline failed at step 3",
      "level": "error",
      "title": "CI/CD Error",
      "fields": {
        "Error": "Timeout waiting for database",
        "Job ID": "#12345",
        "Duration": "5m 23s"
      }
    }
  }
}
"""
