# MCP Server Integration

Mealie includes an MCP (Model Context Protocol) server that allows AI assistants like Claude Desktop to interact with your recipes.

## Overview

The MCP server provides a standardized interface for AI assistants to:
- List and search recipes
- Get recipe details
- Create, update, and delete recipes
- Duplicate recipes

All operations use Mealie's internal authentication and services, ensuring proper permissions and data consistency.

## Prerequisites

- Mealie instance running with API access
- API token (long-lived) created in Mealie

## Creating an API Token

1. Log in to your Mealie instance
2. Navigate to `/user/profile/api-tokens` (or User Settings → API Tokens)
3. Click "Create API Token"
4. Provide a name for the token (e.g., "Claude Desktop MCP")
5. Copy the generated token (you won't be able to view it again)

**Important**: Store your API token securely. You'll need it to configure the MCP server in Claude Desktop.

## Configuring Claude Desktop

### 1. Locate Claude Desktop Configuration

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Linux**: `~/.config/Claude/claude_desktop_config.json`

### 2. Edit Configuration

Open the configuration file and add the Mealie MCP server configuration:

```json
{
  "mcpServers": {
    "mealie": {
      "url": "https://your-mealie-instance.com/api/mcp",
      "transport": {
        "type": "sse",
        "endpoint": "/sse"
      },
      "headers": {
        "Authorization": "Bearer YOUR_API_TOKEN_HERE"
      }
    }
  }
}
```

Replace:
- `https://your-mealie-instance.com` with your Mealie instance URL
- `YOUR_API_TOKEN_HERE` with the API token you created

### 3. Restart Claude Desktop

After saving the configuration, restart Claude Desktop for the changes to take effect.

## Endpoints

### Server-Sent Events (SSE)

**Endpoint**: `GET /api/mcp/sse`

Establishes a persistent SSE connection for real-time MCP communication. Used by Claude Desktop and other MCP clients for long-lived connections.

**Authentication**: Bearer token required in `Authorization` header

### HTTP POST

**Endpoint**: `POST /api/mcp`

Handles MCP protocol messages via HTTP POST. Used for stateless MCP communication.

**Authentication**: Bearer token required in `Authorization` header

## Available Tools

### mealie_list_recipes

List and search recipes with pagination and filters.

**Parameters**:
- `page` (integer, optional): Page number (default: 1)
- `per_page` (integer, optional): Items per page (default: 50)
- `search` (string, optional): Search query
- `categories` (array of strings, optional): Filter by category IDs
- `tags` (array of strings, optional): Filter by tag IDs
- `tools` (array of strings, optional): Filter by tool IDs
- `foods` (array of strings, optional): Filter by food IDs

**Returns**: Paginated list of recipe summaries

### mealie_get_recipe

Get a single recipe by slug or ID.

**Parameters**:
- `slug` (string, required): Recipe slug or ID

**Returns**: Complete recipe data

### mealie_create_recipe

Create a new recipe from JSON data.

**Parameters**:
- `recipe` (object, required): Recipe data (as Recipe JSON schema)

**Returns**: Created recipe with slug

### mealie_update_recipe

Update an existing recipe with full PUT (all fields required).

**Parameters**:
- `slug` (string, required): Recipe slug or ID
- `recipe` (object, required): Complete recipe data

**Returns**: Updated recipe

### mealie_patch_recipe

Partially update a recipe with PATCH (only specified fields).

**Parameters**:
- `slug` (string, required): Recipe slug or ID
- `recipe` (object, required): Partial recipe data (only fields to update)

**Returns**: Updated recipe

### mealie_delete_recipe

Delete a recipe by slug or ID.

**Parameters**:
- `slug` (string, required): Recipe slug or ID

**Returns**: Deleted recipe data

### mealie_duplicate_recipe

Duplicate a recipe with optional new name.

**Parameters**:
- `slug` (string, required): Recipe slug or ID to duplicate
- `name` (string, optional): Optional new name for the duplicated recipe

**Returns**: Duplicated recipe data

## Security Notes

- **API Tokens**: Treat API tokens like passwords. Never commit them to version control or share them publicly.
- **HTTPS**: Always use HTTPS in production. The MCP server endpoints are accessible over HTTP/HTTPS and should be secured appropriately.
- **Permissions**: API tokens inherit the permissions of the user who created them. Ensure users only create tokens with necessary permissions.

## Troubleshooting

### Connection Errors

**Issue**: Cannot connect to MCP server

**Solutions**:
- Verify your Mealie instance URL is correct and accessible
- Check that the API token is valid and not expired
- Ensure your Mealie instance is running and accessible
- Check network connectivity and firewall settings

### Authentication Errors

**Issue**: "401 Unauthorized" or "403 Forbidden" errors

**Solutions**:
- Verify the API token is correct in the Claude Desktop configuration
- Ensure the token hasn't been deleted or regenerated
- Check that the user who created the token still has access

### Tool Not Found Errors

**Issue**: "Unknown tool" errors when calling tools

**Solutions**:
- Ensure you're using the correct tool names (e.g., `mealie_list_recipes`)
- Check that the MCP server is properly initialized
- Verify the endpoint is `/api/mcp` (not `/mcp`)

## Testing

You can test the MCP server endpoints directly using curl:

```bash
# Test SSE endpoint (will stream events)
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
     https://your-mealie-instance.com/api/mcp/sse

# Test list tools (POST endpoint)
curl -X POST \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}' \
     https://your-mealie-instance.com/api/mcp
```

## Additional Resources

- [MCP Specification](https://modelcontextprotocol.io/)
- [Claude Desktop Documentation](https://claude.ai/docs)
- [Mealie API Documentation](/docs)
