"""MCP Server implementation for Mealie."""

from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp.server.models import InitializationOptions
from mcp.server.session import ServerSession
from mcp.shared.message import SessionMessage
from mcp.types import ServerCapabilities, ToolsCapability

from mealie.core.settings.static import APP_VERSION


def create_mcp_server_session(
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception],
    write_stream: MemoryObjectSendStream[SessionMessage],
) -> ServerSession:
    """Create and configure an MCP server session with streams."""
    init_options = InitializationOptions(
        server_name="Mealie",
        server_version=APP_VERSION,
        protocolVersion="2024-11-05",
        capabilities=ServerCapabilities(tools=ToolsCapability(listChanged=True)),
    )

    session = ServerSession(read_stream, write_stream, init_options, stateless=False)
    return session
