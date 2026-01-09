import os
from typing import Any, Optional
import subprocess
from urllib.parse import urlencode
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
import things
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from middleware import SmitheryConfigMiddleware


mcp = FastMCP(
    "Things 3",
    instructions="""
When asked for todos in general, return today's todos.
""",
)


# Optional: Handle configuration for backwards compatibility with stdio mode
# This function is only needed if you want to support stdio transport alongside HTTP
def handle_config(config: dict):
    """Handle configuration from Smithery - for backwards compatibility with stdio mode."""
    global _token
    if token := config.get("token"):
        _token = token
    # You can handle other session config fields here


# Store token for stdio mode (backwards compatibility)
_token: Optional[str] = None


def get_request_config() -> dict:
    """Get full config from current request context."""
    try:
        # Access the current request context from FastMCP
        import contextvars

        # Try to get from request context if available
        request = contextvars.copy_context().get("request")
        if hasattr(request, "scope") and request.scope:
            return request.scope.get("smithery_config", {})
    except:
        pass

    # Return empty dict if no config found
    return {}


def get_config_value(key: str, default=None):
    """Get a specific config value from current request."""
    config = get_request_config()
    # Handle case where config might be None
    if config is None:
        config = {}
    return config.get(key, default)


def get_token() -> Optional[str]:
    """Resolve auth token from request config, stdio config, or env."""
    token = get_config_value("token")
    if token:
        return token
    if _token:
        return _token
    return os.getenv("THINGS_TOKEN") or os.getenv("TOKEN")


def build_things_url(command: str, token: Optional[str], reveal: bool, **arguments: Any) -> str:
    params: dict[str, Any] = {}
    if token:
        params["auth-token"] = token
    if reveal is not None:
        params["reveal"] = "true" if reveal else "false"
    for key, value in arguments.items():
        if value is None:
            continue
        if isinstance(value, bool):
            params[key] = "true" if value else "false"
        else:
            params[key] = value
    query = urlencode(params, doseq=True)
    if query:
        return f"things:///{command}?{query}"
    return f"things:///{command}"


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_today() -> list[Any]:
    """Get today's todos and projects."""
    return things.today()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_inbox() -> list[Any]:
    """Get inbox contents."""
    return things.inbox()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_trash() -> list[Any]:
    """Get trash contents."""
    return things.trash()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_logbook() -> list[Any]:
    """Get logbook contents."""
    return things.logbook()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_completed(last: str = None) -> list[Any]:
    """Get completed todos and projects.

    Args:
        last: Limit returned tasks to tasks created within the last X days, weeks, or years. For example: '3d', '5w', or '1y'.
    """
    return things.completed(last=last)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_deadlines() -> list[Any]:
    """Get deadlines."""
    return things.deadlines()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_anytime() -> list[Any]:
    """Get anytime todos and projects."""
    return things.anytime()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_someday() -> list[Any]:
    """Get someday todos and projects."""
    return things.someday()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_upcoming() -> list[Any]:
    """Get upcoming todos and projects."""
    return things.upcoming()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_projects() -> list[Any]:
    """Get all projects."""
    return things.projects()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_areas() -> list[Any]:
    """Get all areas."""
    return things.areas()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_tags() -> list[Any]:
    """Get all tags."""
    return things.tags()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_project_todos(id: str) -> list[Any]:
    """Get all todos for a project."""
    return things.todos(project=id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_area_todos(id: str) -> list[Any]:
    """Get all todos for an area."""
    return things.todos(area=id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def search(query: str) -> list[Any]:
    """Search for todos, projects, areas, and tags.

    Args:
        query: Only pass the necessary keywords as if you were doing a Google search. If you didn't get a result, try a different query.
    """
    return things.search(query)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_task(id: str) -> list[Any]:
    """Get a task by ID."""
    return things.get(id)


def run_command(command: str, **arguments: Any) -> None:
    token = get_token()
    subprocess.Popen(
        [
            "open",
            "-g",
            build_things_url(command=command, token=token, reveal=False, **arguments),
        ]
    )


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True, destructiveHint=False))
async def update_todo(
    id: str,
    title: str = None,
    completed: bool = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
) -> None:
    """Update a todo.

    Args:
        id: The ID of the todo to update.
        title: The new title of the todo.
        completed: Whether the todo is completed.
        notes: The new notes of the todo.
        when: When should the todo be completed. Can be a date following the format YYYY-MM-DD or a string like "tomorrow", "in 3 days", etc.
        deadline: The deadline of the todo. Can be a date following the format YYYY-MM-DD or a string like "tomorrow", "in 3 days", etc.
    """
    arguments = {}
    if title:
        arguments["title"] = title
    if completed is not None:
        arguments["completed"] = completed
    if notes:
        arguments["notes"] = notes
    if when:
        arguments["when"] = when
    if deadline:
        arguments["deadline"] = deadline

    run_command("update", id=id, **arguments)


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True, destructiveHint=False))
async def update_project(
    id: str,
    title: str = None,
    completed: bool = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
) -> None:
    """Update a project.

    Args:
        id: The ID of the project to update.
        title: The new title of the project.
        completed: Whether the project is completed.
        notes: The new notes of the project.
        when: When should the project be completed. Can be a date following the format YYYY-MM-DD or a string like "tomorrow", "in 3 days", etc.
        deadline: The deadline of the project. Can be a date following the format YYYY-MM-DD or a string like "tomorrow", "in 3 days", etc.
    """
    arguments = {}
    if title:
        arguments["title"] = title
    if completed is not None:
        arguments["completed"] = completed
    if notes:
        arguments["notes"] = notes
    if when:
        arguments["when"] = when
    if deadline:
        arguments["deadline"] = deadline

    run_command("update-project", id=id, **arguments)


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True, destructiveHint=False))
async def create_todo(
    title: str,
    list: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
) -> None:
    """Create a todo.

    Args:
        title: The title of the todo.
        list: The title of a project or area to add to.
        notes: The notes of the todo.
        when: When should the todo be completed. Can be a date following the format YYYY-MM-DD or a string like "tomorrow", "in 3 days", etc.
        deadline: The deadline of the todo. Can be a date following the format YYYY-MM-DD or a string like "tomorrow", "in 3 days", etc.
    """
    arguments = {}
    if list:
        arguments["list"] = list
    if title:
        arguments["title"] = title
    if notes:
        arguments["notes"] = notes
    if when:
        arguments["when"] = when
    if deadline:
        arguments["deadline"] = deadline

    run_command("add", **arguments)


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True, destructiveHint=False))
async def create_project(
    title: str,
    area: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
) -> None:
    """Create a project.

    Args:
        title: The title of the project.
        area: The title of an area to add the project to.
        notes: The notes of the project.
        when: When should the project be completed. Can be a date following the format YYYY-MM-DD or a string like "tomorrow", "in 3 days", etc.
        deadline: The deadline of the project. Can be a date following the format YYYY-MM-DD or a string like "tomorrow", "in 3 days", etc.
    """
    arguments = {}
    if area:
        arguments["area"] = area
    if title:
        arguments["title"] = title
    if notes:
        arguments["notes"] = notes
    if when:
        arguments["when"] = when
    if deadline:
        arguments["deadline"] = deadline

    run_command("add-project", **arguments)


def main():
    transport_mode = os.getenv("TRANSPORT", "stdio")

    if transport_mode == "http":
        # HTTP mode with config extraction from URL parameters
        print("Things 3 MCP Server starting in HTTP mode...")

        # Setup Starlette app with CORS for cross-origin requests
        app = mcp.streamable_http_app()

        # IMPORTANT: add CORS middleware for browser based clients
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["mcp-session-id", "mcp-protocol-version"],
            max_age=86400,
        )

        # Apply custom middleware for session config extraction
        app = SmitheryConfigMiddleware(app)

        # Use Smithery-required PORT environment variable
        port = int(os.environ.get("PORT", 8081))
        print(f"Listening on port {port}")

        uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug")

    else:
        # Optional: if you need backward compatibility, add stdio transport
        # You can publish this to uv for users to run locally
        print("Things 3 MCP Server starting in stdio mode...")

        token = os.getenv("THINGS_TOKEN") or os.getenv("TOKEN")
        # Set the server token for stdio mode
        handle_config({"token": token})

        # Run with stdio transport (default)
        mcp.run()


if __name__ == "__main__":
    main()
