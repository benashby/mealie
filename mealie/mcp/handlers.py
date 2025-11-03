"""MCP message handlers for routing tool calls."""

import json
from typing import Any

from mcp.server.session import ServerSession
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    TextContent,
)

from mealie.mcp.tools.recipes import handle_tool_call


async def process_mcp_messages(mcp_session: ServerSession) -> None:
    """Process incoming messages from MCP client and route tool calls."""
    try:
        async for message_wrapper in mcp_session.incoming_messages():
            if isinstance(message_wrapper, Exception):
                # Handle errors
                continue

            # Check if this is a request with a responder
            if hasattr(message_wrapper, "message") and hasattr(message_wrapper, "responder"):
                request = message_wrapper.message

                # Handle different message types
                if isinstance(request, CallToolRequest):
                    await _handle_call_tool_request(mcp_session, message_wrapper)
                elif isinstance(request, ListToolsRequest):
                    await _handle_list_tools_request(mcp_session, message_wrapper)
    except Exception:
        # Log error but don't crash
        pass


async def _handle_call_tool_request(
    mcp_session: ServerSession,
    request_message: Any,
) -> None:
    """Handle a tool call request."""
    request = request_message.message
    tool_name = request.params.name
    arguments = request.params.arguments or {}

    try:
        # Route to appropriate handler
        result_data = await handle_tool_call(mcp_session, tool_name, arguments)

        # Serialize result data to JSON string
        # Handle dict, list, and other types properly
        if isinstance(result_data, dict):
            result_text = json.dumps(result_data, default=str)
        elif isinstance(result_data, list):
            result_text = json.dumps(result_data, default=str)
        else:
            result_text = json.dumps({"result": result_data}, default=str)

        # Create success response with proper content blocks
        result = CallToolResult(
            content=[TextContent(type="text", text=result_text)],
            isError=False,
        )
    except ValueError as e:
        # Unknown tool error
        error_text = json.dumps({"error": str(e), "code": "UNKNOWN_TOOL"}, default=str)
        result = CallToolResult(
            content=[TextContent(type="text", text=error_text)],
            isError=True,
        )
    except Exception as e:
        # Generic error response
        error_text = json.dumps({"error": str(e), "code": "INTERNAL_ERROR"}, default=str)
        result = CallToolResult(
            content=[TextContent(type="text", text=error_text)],
            isError=True,
        )

    # Send response
    await request_message.responder.send_response(result)


async def _handle_list_tools_request(
    mcp_session: ServerSession,
    request_message: Any,
) -> None:
    """Handle a list tools request."""
    # Get registered tools from session
    tools = getattr(mcp_session, "_mcp_tools", {})
    tools_list = list(tools.values()) if tools else []

    result = ListToolsResult(tools=tools_list)
    await request_message.responder.send_response(result)


# Create a handler mapping for tool calls
async def get_tool_handler(mcp_session: ServerSession, tool_name: str):
    """Get the handler function for a tool."""
    # Check if tool is registered
    tools = getattr(mcp_session, "_mcp_tools", {})
    if tool_name not in tools:
        raise ValueError(f"Unknown tool: {tool_name}")

    # Route to the handle_tool_call function which routes to specific handlers
    from mealie.mcp.tools.recipes import handle_tool_call

    return handle_tool_call
