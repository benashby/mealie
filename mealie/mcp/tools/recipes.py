"""MCP Tools for Recipe operations."""

from typing import Any

from mcp.server.session import ServerSession
from mcp.types import Tool
from sqlalchemy.orm.session import Session

from mealie.core.exceptions import NoEntryFound, PermissionDenied, SlugError
from mealie.lang.providers import local_provider
from mealie.repos.all_repositories import get_repositories
from mealie.schema.recipe.recipe import Recipe
from mealie.schema.recipe.request_helpers import RecipeDuplicate
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.user.user import PrivateUser
from mealie.services.recipe.recipe_service import RecipeService


def register_recipe_tools(
    mcp_session: ServerSession,
    user: PrivateUser,
    session: Session,
) -> None:
    """Register all recipe tools with the MCP server session."""
    # Store user and session in session context for tools to access
    mcp_session._mealie_user = user  # type: ignore
    mcp_session._mealie_session = session  # type: ignore
    mcp_session._mealie_repos = get_repositories(session, group_id=user.group_id, household_id=user.household_id)  # type: ignore
    mcp_session._mealie_service = RecipeService(
        mcp_session._mealie_repos,
        user,
        mcp_session._mealie_repos.households.get_one(user.household_id),
        translator=local_provider(),
    )  # type: ignore

    # Define tools
    tools = [
        _create_list_recipes_tool(),
        _create_get_recipe_tool(),
        _create_create_recipe_tool(),
        _create_update_recipe_tool(),
        _create_patch_recipe_tool(),
        _create_delete_recipe_tool(),
        _create_duplicate_recipe_tool(),
    ]

    # Store tools in session
    mcp_session._mcp_tools = {tool.name: tool for tool in tools}  # type: ignore


def _create_list_recipes_tool() -> Tool:
    """Create tool for listing recipes."""
    return Tool(
        name="mealie_list_recipes",
        title="List Recipes",
        description="List and search recipes with pagination and filters",
        inputSchema={
            "type": "object",
            "properties": {
                "page": {"type": "integer", "default": 1, "description": "Page number"},
                "per_page": {"type": "integer", "default": 50, "description": "Items per page"},
                "search": {"type": "string", "description": "Search query"},
                "categories": {"type": "array", "items": {"type": "string"}, "description": "Filter by category IDs"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tag IDs"},
                "tools": {"type": "array", "items": {"type": "string"}, "description": "Filter by tool IDs"},
                "foods": {"type": "array", "items": {"type": "string"}, "description": "Filter by food IDs"},
            },
        },
    )


def _create_get_recipe_tool() -> Tool:
    """Create tool for getting a single recipe."""
    return Tool(
        name="mealie_get_recipe",
        title="Get Recipe",
        description="Get a single recipe by slug or ID",
        inputSchema={
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Recipe slug or ID"},
            },
            "required": ["slug"],
        },
    )


def _create_create_recipe_tool() -> Tool:
    """Create tool for creating a recipe."""
    return Tool(
        name="mealie_create_recipe",
        title="Create Recipe",
        description="Create a new recipe from JSON data",
        inputSchema={
            "type": "object",
            "properties": {
                "recipe": {"type": "object", "description": "Recipe data (as Recipe JSON schema)"},
            },
            "required": ["recipe"],
        },
    )


def _create_update_recipe_tool() -> Tool:
    """Create tool for updating a recipe (full PUT)."""
    return Tool(
        name="mealie_update_recipe",
        title="Update Recipe",
        description="Update an existing recipe with full PUT (all fields required)",
        inputSchema={
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Recipe slug or ID"},
                "recipe": {"type": "object", "description": "Complete recipe data"},
            },
            "required": ["slug", "recipe"],
        },
    )


def _create_patch_recipe_tool() -> Tool:
    """Create tool for partially updating a recipe (PATCH)."""
    return Tool(
        name="mealie_patch_recipe",
        title="Patch Recipe",
        description="Partially update a recipe with PATCH (only specified fields)",
        inputSchema={
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Recipe slug or ID"},
                "recipe": {"type": "object", "description": "Partial recipe data (only fields to update)"},
            },
            "required": ["slug", "recipe"],
        },
    )


def _create_delete_recipe_tool() -> Tool:
    """Create tool for deleting a recipe."""
    return Tool(
        name="mealie_delete_recipe",
        title="Delete Recipe",
        description="Delete a recipe by slug or ID",
        inputSchema={
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Recipe slug or ID"},
            },
            "required": ["slug"],
        },
    )


def _create_duplicate_recipe_tool() -> Tool:
    """Create tool for duplicating a recipe."""
    return Tool(
        name="mealie_duplicate_recipe",
        title="Duplicate Recipe",
        description="Duplicate a recipe with optional new name",
        inputSchema={
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Recipe slug or ID to duplicate"},
                "name": {"type": "string", "description": "Optional new name for the duplicated recipe"},
            },
            "required": ["slug"],
        },
    )


async def handle_tool_call(mcp_session: ServerSession, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle tool calls and route to appropriate handlers."""
    if tool_name == "mealie_list_recipes":
        return await _handle_list_recipes(mcp_session, arguments)
    elif tool_name == "mealie_get_recipe":
        return await _handle_get_recipe(mcp_session, arguments)
    elif tool_name == "mealie_create_recipe":
        return await _handle_create_recipe(mcp_session, arguments)
    elif tool_name == "mealie_update_recipe":
        return await _handle_update_recipe(mcp_session, arguments)
    elif tool_name == "mealie_patch_recipe":
        return await _handle_patch_recipe(mcp_session, arguments)
    elif tool_name == "mealie_delete_recipe":
        return await _handle_delete_recipe(mcp_session, arguments)
    elif tool_name == "mealie_duplicate_recipe":
        return await _handle_duplicate_recipe(mcp_session, arguments)
    else:
        raise ValueError(f"Unknown tool: {tool_name}")


async def _handle_list_recipes(mcp_session: ServerSession, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle list recipes tool call."""
    user: PrivateUser = mcp_session._mealie_user  # type: ignore

    pagination = PaginationQuery(
        page=arguments.get("page", 1),
        per_page=arguments.get("per_page", 50),
        search=arguments.get("search"),
    )

    # Get recipes using group recipes (no household filter)
    group_recipes = get_repositories(mcp_session._mealie_session, group_id=user.group_id, household_id=None).recipes  # type: ignore
    pagination_response = group_recipes.by_user(user.id).page_all(
        pagination=pagination,
        categories=arguments.get("categories"),
        tags=arguments.get("tags"),
        tools=arguments.get("tools"),
        foods=arguments.get("foods"),
        require_all_categories=False,
        require_all_tags=False,
        require_all_tools=False,
        require_all_foods=False,
        search=arguments.get("search"),
    )

    return {
        "items": [item.model_dump(by_alias=True) for item in pagination_response.items],
        "page": pagination_response.page,
        "per_page": pagination_response.per_page,
        "total": pagination_response.total,
        "total_pages": pagination_response.total_pages,
    }


async def _handle_get_recipe(mcp_session: ServerSession, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle get recipe tool call."""
    service: RecipeService = mcp_session._mealie_service  # type: ignore
    slug = arguments["slug"]

    try:
        recipe = service.get_one(slug)
        return recipe.model_dump(by_alias=True)
    except NoEntryFound:
        return {"error": "Recipe not found"}
    except Exception as e:
        return {"error": str(e)}


async def _handle_create_recipe(mcp_session: ServerSession, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle create recipe tool call."""
    service: RecipeService = mcp_session._mealie_service  # type: ignore
    recipe_data = arguments["recipe"]

    try:
        recipe = Recipe(**recipe_data)
        new_recipe = service.create_one(recipe)
        return {"slug": new_recipe.slug, "recipe": new_recipe.model_dump(by_alias=True)}
    except SlugError:
        return {"error": "Unable to generate recipe slug"}
    except Exception as e:
        return {"error": str(e)}


async def _handle_update_recipe(mcp_session: ServerSession, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle update recipe tool call."""
    service: RecipeService = mcp_session._mealie_service  # type: ignore
    slug = arguments["slug"]
    recipe_data = arguments["recipe"]

    try:
        # Fetch existing recipe to get system fields (id, group_id, household_id, user_id, created_at)
        existing_recipe = service.get_one(slug)

        # Merge user-provided data with existing recipe data
        # Preserve system fields that shouldn't change
        existing_dict = existing_recipe.model_dump()
        existing_dict.update(recipe_data)

        # Ensure system fields are preserved
        existing_dict["id"] = existing_recipe.id
        existing_dict["groupId"] = existing_recipe.group_id
        existing_dict["householdId"] = existing_recipe.household_id
        existing_dict["userId"] = existing_recipe.user_id
        existing_dict["createdAt"] = existing_recipe.created_at

        # Create Recipe object with complete data including id
        recipe = Recipe(**existing_dict)
        updated_recipe = service.update_one(slug, recipe)
        return {"recipe": updated_recipe.model_dump(by_alias=True)}
    except NoEntryFound:
        return {"error": "Recipe not found"}
    except PermissionDenied:
        return {"error": "Permission denied"}
    except Exception as e:
        return {"error": str(e)}


async def _handle_patch_recipe(mcp_session: ServerSession, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle patch recipe tool call."""
    service: RecipeService = mcp_session._mealie_service  # type: ignore
    slug = arguments["slug"]
    recipe_data = arguments["recipe"]

    try:
        # For PATCH, we need to create a Recipe object with only the patch fields "set"
        # The service.patch_one() uses exclude_unset=True, so only fields that are
        # explicitly provided in recipe_data should be set in the Recipe object.
        #
        # Using Recipe(**recipe_data) will properly track which fields are set in Pydantic v2
        recipe = Recipe(**recipe_data)

        updated_recipe = service.patch_one(slug, recipe)
        return {"recipe": updated_recipe.model_dump(by_alias=True)}
    except NoEntryFound:
        return {"error": "Recipe not found"}
    except PermissionDenied:
        return {"error": "Permission denied"}
    except Exception as e:
        return {"error": str(e)}


async def _handle_delete_recipe(mcp_session: ServerSession, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle delete recipe tool call."""
    service: RecipeService = mcp_session._mealie_service  # type: ignore
    slug = arguments["slug"]

    try:
        recipe = service.delete_one(slug)
        return {"success": True, "recipe": recipe.model_dump(by_alias=True)}
    except NoEntryFound:
        return {"error": "Recipe not found"}
    except PermissionDenied:
        return {"error": "Permission denied"}
    except Exception as e:
        return {"error": str(e)}


async def _handle_duplicate_recipe(mcp_session: ServerSession, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle duplicate recipe tool call."""
    service: RecipeService = mcp_session._mealie_service  # type: ignore
    slug = arguments["slug"]
    name = arguments.get("name")

    try:
        duplicate_req = RecipeDuplicate(name=name) if name else RecipeDuplicate()
        new_recipe = service.duplicate_one(slug, duplicate_req)
        return {"recipe": new_recipe.model_dump(by_alias=True)}
    except NoEntryFound:
        return {"error": "Recipe not found"}
    except Exception as e:
        return {"error": str(e)}
