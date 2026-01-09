import json
import base64
from urllib.parse import parse_qs, unquote


class SmitheryConfigMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            query = scope.get("query_string", b"").decode()

            if "config=" in query:
                try:
                    config_b64 = unquote(parse_qs(query)["config"][0])
                    config = json.loads(base64.b64decode(config_b64))

                    # Inject full config into request scope for per-request access
                    scope["smithery_config"] = config
                except Exception as e:
                    print(f"SmitheryConfigMiddleware: Error parsing config: {e}")
                    scope["smithery_config"] = {}
            else:
                scope["smithery_config"] = {}

        await self.app(scope, receive, send)


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        status = {"code": None}

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                status["code"] = message.get("status")
            await send(message)

        await self.app(scope, receive, send_wrapper)

        if status["code"] == 406:
            headers = {
                key.decode().lower(): value.decode()
                for key, value in scope.get("headers", [])
            }
            method = scope.get("method", "")
            path = scope.get("path", "")
            print(
                "406 Not Acceptable: "
                f"method={method} path={path} "
                f"accept={headers.get('accept')} "
                f"content-type={headers.get('content-type')} "
                f"user-agent={headers.get('user-agent')}"
            )
