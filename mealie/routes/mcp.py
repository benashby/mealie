"""MCP Server HTTP/SSE router for Mealie."""

from anyio import create_memory_object_stream
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from mcp.server.sse import SseServerTransport
from mcp.shared.message import SessionMessage
from starlette.responses import StreamingResponse

from mealie.core.dependencies.dependencies import generate_session, get_current_user
from mealie.db.db_setup import Session
from mealie.mcp.handlers import process_mcp_messages
from mealie.mcp.server import create_mcp_server_session
from mealie.mcp.tools.recipes import register_recipe_tools
from mealie.schema.user.user import PrivateUser

router = APIRouter(prefix="/mcp", tags=["MCP"])


async def handle_mcp_sse(
    request: Request,
    background_tasks: BackgroundTasks,
    user: PrivateUser = Depends(get_current_user),
    session: Session = Depends(generate_session),
):
    """Handle Server-Sent Events (SSE) for MCP client connections."""
    # Create memory streams for MCP session
    # Returns (send_stream, receive_stream), where send_stream is for writing
    # and receive_stream is for reading
    write_stream, read_stream = create_memory_object_stream[SessionMessage | Exception]()

    # Create MCP server session with user context
    mcp_session = create_mcp_server_session(read_stream, write_stream)

    # Store user and session in session context for tools to access
    mcp_session._mealie_user = user  # type: ignore
    mcp_session._mealie_session = session  # type: ignore

    # Register all recipe tools
    register_recipe_tools(mcp_session, user, session)

    # Create SSE transport
    transport = SseServerTransport(endpoint="/mcp")

    # Start background task to process incoming messages
    background_tasks.add_task(process_mcp_messages, mcp_session)

    # Handle SSE connection
    async def send_sse():
        async for message in transport.connect_sse(request.scope, request.receive, write_stream.send):
            yield message

    return StreamingResponse(send_sse(), media_type="text/event-stream")


async def handle_mcp_post(
    request: Request,
    background_tasks: BackgroundTasks,
    user: PrivateUser = Depends(get_current_user),
    session: Session = Depends(generate_session),
):
    """Handle POST requests for MCP messages."""
    import json

    from fastapi.responses import JSONResponse

    # Read request body
    body = await request.body()
    try:
        request_data = json.loads(body)
    except json.JSONDecodeError:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON", "code": "INVALID_JSON"},
        )

    # Create memory streams for MCP session
    # Returns (send_stream, receive_stream), where send_stream is for writing
    # and receive_stream is for reading
    write_stream, read_stream = create_memory_object_stream[SessionMessage | Exception]()

    # Create MCP server session
    mcp_session = create_mcp_server_session(read_stream, write_stream)

    # Store user and session in session context
    mcp_session._mealie_user = user  # type: ignore
    mcp_session._mealie_session = session  # type: ignore

    # Register all recipe tools
    register_recipe_tools(mcp_session, user, session)

    # Process the MCP request manually
    method = request_data.get("method", "")
    params = request_data.get("params", {})
    request_id = request_data.get("id")

    from mealie.mcp.tools.recipes import handle_tool_call

    try:
        if method == "tools/list":
            # List tools
            tools = getattr(mcp_session, "_mcp_tools", {})
            tools_list = list(tools.values()) if tools else []
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": [tool.model_dump() for tool in tools_list]},
                }
            )
        elif method == "tools/call":
            # Call tool
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if not tool_name:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32602, "message": "Missing tool name"},
                    },
                )

            try:
                result_data = await handle_tool_call(mcp_session, tool_name, arguments)
                result_text = json.dumps(result_data, default=str) if not isinstance(result_data, str) else result_data
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": result_text}],
                            "isError": False,
                        },
                    }
                )
            except ValueError as e:
                error_text = json.dumps({"error": str(e), "code": "UNKNOWN_TOOL"}, default=str)
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": error_text}],
                            "isError": True,
                        },
                    }
                )
            except Exception as e:
                error_text = json.dumps({"error": str(e), "code": "INTERNAL_ERROR"}, default=str)
                return JSONResponse(
                    status_code=500,
                    content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": error_text}],
                            "isError": True,
                        },
                    },
                )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                },
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)},
            },
        )


router.get("/sse")(handle_mcp_sse)
router.post("")(handle_mcp_post)
