"""
Qonic MCP Server

A Model Context Protocol server that exposes Qonic API capabilities as MCP tools.
Designed to be hosted on Smithery.
"""

import json
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Server configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="QONIC_", env_file=".env")

    api_key: str = Field(
        default="",
        description="Qonic API key for authentication",
    )
    base_url: str = Field(
        default="https://api.qonic.com",
        description="Base URL for the Qonic API",
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
    )


settings = Settings()

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

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Return a shared HTTPX client, creating it on first use."""
    global _client
    if not settings.api_key:
        raise ValueError(
            "QONIC_API_KEY environment variable is not set. "
            "Please provide a valid Qonic API key."
        )
    if _client is None:
        _client = httpx.Client(
            base_url=settings.base_url,
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=settings.timeout,
        )
    return _client


def _api_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a request to the Qonic API and return parsed JSON."""
    response = _get_client().request(method, path, params=params, json=body)
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
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the Qonic MCP server using stdio transport (default for Smithery)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
