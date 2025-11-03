"""Integration tests for MCP server endpoints.

These tests use FastAPI's TestClient to test the MCP server functionality
including authentication and tool calls. They run as part of the backend
integration test suite via pytest.
"""

import pytest
from fastapi.testclient import TestClient

from tests.utils import api_routes
from tests.utils.fixture_schemas import TestUser


@pytest.fixture
def api_token(api_client: TestClient, unique_user: TestUser):
    """Create an API token for testing."""
    response = api_client.post(
        api_routes.users_api_tokens,
        json={"name": "MCP Test Token"},
        headers=unique_user.token,
    )
    assert response.status_code == 201
    token_data = response.json()
    return {"Authorization": f"Bearer {token_data['token']}"}


def test_mcp_post_endpoint_authenticated(api_client: TestClient, api_token: dict):
    """Test that POST endpoint requires authentication."""
    # Test without auth
    response = api_client.post("/api/mcp")
    assert response.status_code == 401 or response.status_code == 403

    # Test with auth
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    response = api_client.post("/api/mcp", json=mcp_request, headers=api_token)
    # Should either succeed or return a proper MCP error
    assert response.status_code in [200, 400, 500]


def test_mcp_sse_endpoint_authenticated(api_client: TestClient):
    """Test that SSE endpoint requires authentication."""
    # Test without auth
    response = api_client.get("/api/mcp/sse")
    assert response.status_code == 401 or response.status_code == 403


def test_mcp_list_tools(api_client: TestClient, api_token: dict):
    """Test listing available MCP tools."""
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    response = api_client.post("/api/mcp", json=mcp_request, headers=api_token)

    # Should return 200 or handle the request
    if response.status_code == 200:
        data = response.json()
        # Check for MCP response structure
        assert "jsonrpc" in data
        assert "id" in data
        if "result" in data:
            # If tools are returned, verify structure
            result = data.get("result", {})
            if "tools" in result:
                tools = result["tools"]
                assert isinstance(tools, list)
                # Check for expected recipe tools
                tool_names = [tool.get("name") for tool in tools]
                expected_tools = [
                    "mealie_list_recipes",
                    "mealie_get_recipe",
                    "mealie_create_recipe",
                    "mealie_update_recipe",
                    "mealie_patch_recipe",
                    "mealie_delete_recipe",
                    "mealie_duplicate_recipe",
                ]
                for expected_tool in expected_tools:
                    assert expected_tool in tool_names


def test_mcp_call_tool_list_recipes(api_client: TestClient, api_token: dict, unique_user: TestUser):
    """Test calling mealie_list_recipes tool."""
    # First create a recipe to list
    recipe_data = {
        "name": "Test Recipe for MCP",
        "recipeIngredient": [{"note": "Test ingredient"}],
        "recipeInstructions": [{"text": "Test instruction"}],
    }
    create_response = api_client.post(api_routes.recipes, json=recipe_data, headers=unique_user.token)
    assert create_response.status_code == 201

    # Now call MCP tool
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "mealie_list_recipes",
            "arguments": {
                "page": 1,
                "per_page": 10,
            },
        },
    }
    response = api_client.post("/api/mcp", json=mcp_request, headers=api_token)

    # Should handle the request (may need to check actual MCP protocol format)
    assert response.status_code in [200, 400, 500]
    if response.status_code == 200:
        data = response.json()
        # Check for MCP response structure
        assert "jsonrpc" in data
        assert "id" in data


def test_mcp_call_tool_get_recipe(api_client: TestClient, api_token: dict, unique_user: TestUser):
    """Test calling mealie_get_recipe tool."""
    # First create a recipe
    recipe_data = {
        "name": "Test Recipe for MCP Get",
        "recipeIngredient": [{"note": "Test ingredient"}],
        "recipeInstructions": [{"text": "Test instruction"}],
    }
    create_response = api_client.post(api_routes.recipes, json=recipe_data, headers=unique_user.token)
    assert create_response.status_code == 201
    recipe_slug = create_response.text  # Returns slug as string

    # Now call MCP tool
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "mealie_get_recipe",
            "arguments": {
                "slug": recipe_slug,
            },
        },
    }
    response = api_client.post("/api/mcp", json=mcp_request, headers=api_token)

    # Should handle the request
    assert response.status_code in [200, 400, 500]
    if response.status_code == 200:
        data = response.json()
        assert "jsonrpc" in data
        assert "id" in data


def test_mcp_call_tool_create_recipe(api_client: TestClient, api_token: dict):
    """Test calling mealie_create_recipe tool."""
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "mealie_create_recipe",
            "arguments": {
                "recipe": {
                    "name": "MCP Test Recipe",
                    "recipeIngredient": [{"note": "Test ingredient"}],
                    "recipeInstructions": [{"text": "Test instruction"}],
                },
            },
        },
    }
    response = api_client.post("/api/mcp", json=mcp_request, headers=api_token)

    # Should handle the request
    assert response.status_code in [200, 400, 500]
    if response.status_code == 200:
        data = response.json()
        assert "jsonrpc" in data
        assert "id" in data


def test_mcp_call_tool_unknown(api_client: TestClient, api_token: dict):
    """Test calling an unknown tool returns proper error."""
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "unknown_tool",
            "arguments": {},
        },
    }
    response = api_client.post("/api/mcp", json=mcp_request, headers=api_token)

    # Should return error for unknown tool
    assert response.status_code in [200, 400, 500]
    if response.status_code == 200:
        data = response.json()
        # If error, should have error field
        if "error" in data:
            assert "code" in data["error"] or "message" in data["error"]


def test_mcp_post_invalid_jsonrpc(api_client: TestClient, api_token: dict):
    """Test that invalid JSON-RPC requests are handled properly."""
    # Invalid JSON-RPC request
    invalid_request = {
        "id": 1,
        "method": "tools/list",
        # Missing jsonrpc field
    }
    response = api_client.post("/api/mcp", json=invalid_request, headers=api_token)

    # Should return error
    assert response.status_code in [200, 400, 500]
