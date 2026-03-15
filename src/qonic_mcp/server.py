"""
Qonic MCP Server

A Model Context Protocol server that exposes Qonic API capabilities as MCP tools.
Hosted on Vercel with OAuth authentication via Qonic.
"""

import contextvars
import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

# ---------------------------------------------------------------------------
# Per-request OAuth token (extracted from Authorization header)
# ---------------------------------------------------------------------------

_access_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "access_token", default=None
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("QONIC_BASE_URL", "https://api.qonic.com")
TIMEOUT = int(os.environ.get("QONIC_TIMEOUT", "30"))
OAUTH_CLIENT_ID = os.environ.get("QONIC_OAUTH_CLIENT_ID", "")

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="qonic-mcp",
    instructions=(
        "This server exposes Qonic API capabilities through the Model Context Protocol. "
        "Use the available tools to interact with Qonic resources such as projects, "
        "designs, analyses, and simulations."
    ),
)


# ---------------------------------------------------------------------------
# HTTP client helper
# ---------------------------------------------------------------------------


def _api_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a request to the Qonic API using the current user's OAuth token."""
    token = _access_token.get()
    if not token:
        raise ValueError(
            "Not authenticated. Connect through an MCP client to "
            "authenticate with your Qonic account."
        )
    with httpx.Client(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=TIMEOUT,
    ) as client:
        response = client.request(method, path, params=params, json=body)
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Tools – Projects
# ---------------------------------------------------------------------------

@mcp.tool()
def list_projects(
    page: int = Field(default=1, description="Page number (1-based)"),
    page_size: int = Field(default=20, description="Number of results per page (max 100)"),
) -> str:
    """List all Qonic projects accessible with the configured API key."""
    result = _api_request(
        "GET",
        "/v1/projects",
        params={"page": page, "page_size": min(page_size, 100)},
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def get_project(
    project_id: str = Field(description="The unique identifier of the project"),
) -> str:
    """Get details of a specific Qonic project by ID."""
    result = _api_request("GET", f"/v1/projects/{project_id}")
    return json.dumps(result, indent=2)


@mcp.tool()
def create_project(
    name: str = Field(description="Name of the new project"),
    description: str = Field(default="", description="Optional project description"),
) -> str:
    """Create a new Qonic project."""
    body: dict[str, Any] = {"name": name}
    if description:
        body["description"] = description
    result = _api_request("POST", "/v1/projects", body=body)
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tools – Designs
# ---------------------------------------------------------------------------

@mcp.tool()
def list_designs(
    project_id: str = Field(description="Project ID to list designs for"),
    page: int = Field(default=1, description="Page number (1-based)"),
    page_size: int = Field(default=20, description="Number of results per page (max 100)"),
) -> str:
    """List all designs within a specific Qonic project."""
    result = _api_request(
        "GET",
        f"/v1/projects/{project_id}/designs",
        params={"page": page, "page_size": min(page_size, 100)},
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def get_design(
    project_id: str = Field(description="Project ID that contains the design"),
    design_id: str = Field(description="The unique identifier of the design"),
) -> str:
    """Get details of a specific design within a Qonic project."""
    result = _api_request("GET", f"/v1/projects/{project_id}/designs/{design_id}")
    return json.dumps(result, indent=2)


@mcp.tool()
def create_design(
    project_id: str = Field(description="Project ID in which to create the design"),
    name: str = Field(description="Name of the new design"),
    description: str = Field(default="", description="Optional design description"),
) -> str:
    """Create a new design within a Qonic project."""
    body: dict[str, Any] = {"name": name}
    if description:
        body["description"] = description
    result = _api_request("POST", f"/v1/projects/{project_id}/designs", body=body)
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tools – Analyses / Simulations
# ---------------------------------------------------------------------------

@mcp.tool()
def list_analyses(
    project_id: str = Field(description="Project ID to list analyses for"),
    design_id: str = Field(description="Design ID to list analyses for"),
) -> str:
    """List all analyses associated with a specific design."""
    result = _api_request(
        "GET",
        f"/v1/projects/{project_id}/designs/{design_id}/analyses",
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def run_analysis(
    project_id: str = Field(description="Project ID that contains the design"),
    design_id: str = Field(description="Design ID to run analysis on"),
    analysis_type: str = Field(
        description=(
            "Type of analysis to run, e.g. 'structural', 'thermal', 'acoustic', "
            "'electromagnetic', or 'fluid'"
        )
    ),
    parameters: str = Field(
        default="{}",
        description="JSON string of analysis-specific parameters",
    ),
) -> str:
    """Run an analysis on a Qonic design and return the job details."""
    try:
        params_dict = json.loads(parameters)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Invalid JSON in parameters: {exc}"})

    body: dict[str, Any] = {
        "analysis_type": analysis_type,
        "parameters": params_dict,
    }
    result = _api_request(
        "POST",
        f"/v1/projects/{project_id}/designs/{design_id}/analyses",
        body=body,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def get_analysis_status(
    project_id: str = Field(description="Project ID that contains the design"),
    design_id: str = Field(description="Design ID the analysis belongs to"),
    analysis_id: str = Field(description="Analysis job ID to check"),
) -> str:
    """Get the current status and results of a Qonic analysis job."""
    result = _api_request(
        "GET",
        f"/v1/projects/{project_id}/designs/{design_id}/analyses/{analysis_id}",
    )
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tools – Account / Utility
# ---------------------------------------------------------------------------

@mcp.tool()
def get_account_info() -> str:
    """Retrieve information about the authenticated Qonic account."""
    result = _api_request("GET", "/v1/account")
    return json.dumps(result, indent=2)


@mcp.tool()
def search(
    query: str = Field(description="Search query string"),
    resource_type: str = Field(
        default="all",
        description=(
            "Resource type to search within: 'projects', 'designs', 'analyses', or 'all'"
        ),
    ),
    page: int = Field(default=1, description="Page number (1-based)"),
    page_size: int = Field(default=20, description="Number of results per page (max 100)"),
) -> str:
    """Search Qonic resources by keyword."""
    result = _api_request(
        "GET",
        "/v1/search",
        params={
            "q": query,
            "type": resource_type,
            "page": page,
            "page_size": min(page_size, 100),
        },
    )
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# ASGI application
# ---------------------------------------------------------------------------

# Use FastMCP's built-in Streamable HTTP app (includes lifespan management)
mcp.settings.stateless_http = True

_inner_app = mcp.streamable_http_app()


async def app(scope, receive, send):
    """ASGI wrapper that adds OAuth metadata + token extraction."""
    if scope["type"] == "http":
        request = Request(scope, receive, send)

        # Serve OAuth metadata
        if request.url.path == "/.well-known/oauth-authorization-server":
            base = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", "")
            if base and not base.startswith("http"):
                base = f"https://{base}"
            if not base:
                base = str(request.base_url).rstrip("/")

            metadata: dict[str, Any] = {
                "issuer": base,
                "authorization_endpoint": os.environ.get(
                    "QONIC_OAUTH_AUTHORIZE_URL",
                    f"{BASE_URL}/v1/auth/authorize",
                ),
                "token_endpoint": os.environ.get(
                    "QONIC_OAUTH_TOKEN_URL",
                    f"{BASE_URL}/v1/auth/token",
                ),
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["client_secret_post"],
                "scopes_supported": [
                    "projects:read", "projects:write",
                    "models:read", "models:write",
                    "issues:read",
                    "libraries:read", "libraries:write",
                ],
            }
            if OAUTH_CLIENT_ID:
                metadata["client_id"] = OAUTH_CLIENT_ID

            response = JSONResponse(metadata)
            await response(scope, receive, send)
            return

        # Extract Bearer token for API calls
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            _access_token.set(auth[7:])

        # Ensure ASGI scope has a proper server tuple for Starlette's host
        # validation (Vercel's runtime may not set this correctly)
        if not scope.get("server"):
            host = request.headers.get("host", "localhost")
            hostname = host.split(":")[0]
            port = int(host.split(":")[1]) if ":" in host else (443 if scope.get("scheme") == "https" else 80)
            scope = dict(scope, server=(hostname, port))

    # Delegate everything else to the MCP app
    await _inner_app(scope, receive, send)


# ---------------------------------------------------------------------------
# Entry point (local development)
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the Qonic MCP server locally with uvicorn."""
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
