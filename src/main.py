import os
import json
import time
from datetime import datetime, timedelta
from typing import Any, Optional
import subprocess
from urllib.parse import urlencode, quote
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
import things
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from middleware import SmitheryConfigMiddleware, RequestLoggingMiddleware


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
_recent_commands: dict[str, float] = {}
_DEDUPE_WINDOW_SECONDS = 3.0
_TODO_DEDUPE_WINDOW_SECONDS = 120.0


def log_event(kind: str, **data: Any) -> None:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=True, default=str)
    print(f"MCP {kind}: {payload}")


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
    query = urlencode(params, doseq=True, quote_via=quote)
    if query:
        return f"things:///{command}?{query}"
    return f"things:///{command}"


def should_dedupe(command: str, token: Optional[str], arguments: dict[str, Any]) -> bool:
    payload = {"command": command, "token": token, "arguments": arguments}
    key = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    now = time.monotonic()
    last = _recent_commands.get(key)
    if last is not None and (now - last) < _DEDUPE_WINDOW_SECONDS:
        return True
    _recent_commands[key] = now
    return False


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_today() -> list[Any]:
    """Get today's todos and projects."""
    result = things.today()
    log_event("tool_result", name="get_today", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_inbox() -> list[Any]:
    """Get inbox contents."""
    result = things.inbox()
    log_event("tool_result", name="get_inbox", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_trash() -> list[Any]:
    """Get trash contents."""
    result = things.trash()
    log_event("tool_result", name="get_trash", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_logbook() -> list[Any]:
    """Get logbook contents."""
    result = things.logbook()
    log_event("tool_result", name="get_logbook", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_completed(last: str = None) -> list[Any]:
    """Get completed todos and projects.

    Args:
        last: Limit returned tasks to tasks created within the last X days, weeks, or years. For example: '3d', '5w', or '1y'.
    """
    result = things.completed(last=last)
    log_event("tool_result", name="get_completed", last=last, count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_deadlines() -> list[Any]:
    """Get deadlines."""
    result = things.deadlines()
    log_event("tool_result", name="get_deadlines", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_anytime() -> list[Any]:
    """Get anytime todos and projects."""
    result = things.anytime()
    log_event("tool_result", name="get_anytime", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_someday() -> list[Any]:
    """Get someday todos and projects."""
    result = things.someday()
    log_event("tool_result", name="get_someday", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_upcoming() -> list[Any]:
    """Get upcoming todos and projects."""
    result = things.upcoming()
    log_event("tool_result", name="get_upcoming", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_projects() -> list[Any]:
    """Get all projects."""
    result = things.projects()
    log_event("tool_result", name="get_projects", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_areas() -> list[Any]:
    """Get all areas."""
    result = things.areas()
    log_event("tool_result", name="get_areas", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_tags() -> list[Any]:
    """Get all tags."""
    result = things.tags()
    log_event("tool_result", name="get_tags", count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_project_todos(id: str) -> list[Any]:
    """Get all todos for a project."""
    result = things.todos(project=id)
    log_event("tool_result", name="get_project_todos", project=id, count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_area_todos(id: str) -> list[Any]:
    """Get all todos for an area."""
    result = things.todos(area=id)
    log_event("tool_result", name="get_area_todos", area=id, count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def search(query: str) -> list[Any]:
    """Search for todos, projects, areas, and tags.

    Args:
        query: Only pass the necessary keywords as if you were doing a Google search. If you didn't get a result, try a different query.
    """
    result = things.search(query)
    log_event("tool_result", name="search", query=query, count=len(result))
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_task(id: str) -> dict[str, Any]:
    """Get a task by ID."""
    result = things.get(id)
    log_event("tool_result", name="get_task", id=id, found=bool(result))
    return result


def run_command(command: str, **arguments: Any) -> dict[str, Any]:
    token = get_token()
    if should_dedupe(command, token, arguments):
        return {
            "ok": False,
            "deduped": True,
            "reason": "recent_command",
        }
    url = build_things_url(command=command, token=token, reveal=False, **arguments)
    subprocess.Popen(
        [
            "open",
            "-g",
            url,
        ]
    )
    return {"ok": True, "url": url}


def find_recent_duplicate_todos(title: str, list_name: Optional[str]) -> list[dict[str, Any]]:
    """Return recent duplicate todo candidates for best-effort de-dupe."""
    try:
        candidates = things.tasks(
            type="to-do",
            status="incomplete",
            last="1d",
            search_query=title,
        )
    except Exception:
        return []

    now = datetime.now()
    window_start = now - timedelta(seconds=_TODO_DEDUPE_WINDOW_SECONDS)
    matches: list[tuple[datetime, dict[str, Any]]] = []
    for task in candidates:
        uuid = task.get("uuid")
        task_title = task.get("title")
        project_title = task.get("project_title")
        area_title = task.get("area_title")
        created = task.get("created")
        if task_title != title:
            print(f"Dedup check: uuid={uuid} action=skip reason=title_mismatch")
            continue
        if list_name:
            if project_title != list_name and area_title != list_name:
                print(f"Dedup check: uuid={uuid} action=skip reason=list_mismatch")
                continue
        if not created:
            print(f"Dedup check: uuid={uuid} action=skip reason=missing_created")
            continue
        try:
            created_dt = datetime.fromisoformat(created)
        except ValueError:
            print(f"Dedup check: uuid={uuid} action=skip reason=created_parse_error")
            continue
        if window_start <= created_dt <= now:
            print(
                "Dedup check: "
                f"uuid={uuid} action=match "
                f"created={created} project={project_title} area={area_title}"
            )
            matches.append((created_dt, task))
            continue
        print(f"Dedup check: uuid={uuid} action=skip reason=outside_window")
    matches.sort(key=lambda item: item[0])
    return [task for _, task in matches]


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True, destructiveHint=False))
async def update_todo(
    id: str,
    title: str = None,
    completed: bool = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
) -> dict[str, Any]:
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

    log_event("tool_call", name="update_todo", id=id, arguments=arguments)
    result = run_command("update", id=id, **arguments)
    log_event("tool_result", name="update_todo", result=result)
    return result


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True, destructiveHint=False))
async def update_project(
    id: str,
    title: str = None,
    completed: bool = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
) -> dict[str, Any]:
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

    log_event("tool_call", name="update_project", id=id, arguments=arguments)
    result = run_command("update-project", id=id, **arguments)
    log_event("tool_result", name="update_project", result=result)
    return result


@mcp.tool(annotations=ToolAnnotations(idempotentHint=False, destructiveHint=False))
async def create_todo(
    title: str,
    list: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
) -> dict[str, Any]:
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

    log_event("tool_call", name="create_todo", title=title, list=list, arguments=arguments)
    duplicates = find_recent_duplicate_todos(title=title, list_name=list)
    if duplicates:
        keep = duplicates[0]
        completed_duplicates: list[str] = []
        for task in duplicates[1:]:
            uuid = task.get("uuid")
            if not uuid:
                continue
            completed_duplicates.append(uuid)
            run_command("update", id=uuid, completed=True)
        result = {
            "ok": True,
            "deduped": True,
            "reason": "recent_duplicate",
            "existing_uuid": keep.get("uuid"),
            "completed_duplicates": completed_duplicates,
        }
        log_event("tool_result", name="create_todo", result=result)
        return result

    result = run_command("add", **arguments)
    log_event("tool_result", name="create_todo", result=result)
    return result


@mcp.tool(annotations=ToolAnnotations(idempotentHint=False, destructiveHint=False))
async def create_project(
    title: str,
    area: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
) -> dict[str, Any]:
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

    log_event("tool_call", name="create_project", title=title, area=area, arguments=arguments)
    result = run_command("add-project", **arguments)
    log_event("tool_result", name="create_project", result=result)
    return result


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
        app = RequestLoggingMiddleware(app)
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
