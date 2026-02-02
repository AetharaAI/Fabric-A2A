# Custom Tools Directory

Place your custom tool files here. They will be auto-discovered on startup.

## Quick Start

1. Copy the template:
   ```bash
   cp ../TEMPLATE.py my_tool.py
   ```

2. Edit `my_tool.py` - follow the TODO comments

3. Restart Fabric - your tool is automatically available

## Example Tools

See `example_weather.py` for a working example.

## Best Practices

- Use descriptive `TOOL_ID`s: `stripe.create_customer`, not `tool1`
- Handle errors gracefully - raise `ToolError` with meaningful codes
- Use `**kwargs` in method signatures to accept extra params
- Keep tools focused - one tool should do one thing well
- Document parameters in docstrings
