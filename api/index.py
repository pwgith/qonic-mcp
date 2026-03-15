"""
Qonic MCP Server – Vercel serverless function entry point.

A Model Context Protocol server that exposes Qonic API capabilities as MCP tools.
Hosted on Vercel with OAuth authentication via Qonic.
"""

import base64
import contextvars
import json
import os
from typing import Any
from urllib.parse import urlencode, parse_qs, urlparse, urlunparse

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

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
OAUTH_CLIENT_SECRET = os.environ.get("QONIC_OAUTH_CLIENT_SECRET", "")

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="qonic-mcp",
    instructions=(
        "This server exposes Qonic API capabilities through the Model Context Protocol. "
        "Use the available tools to interact with Qonic resources such as projects, "
        "models, products (building elements), spatial locations, materials, types, "
        "codifications, and custom properties.\n\n"
        "Workflow for modifying a model:\n"
        "1. Call start_modification_session before making changes\n"
        "2. Use modify_products / delete_product to make changes\n"
        "3. Call publish_changes to save, or discard_changes to revert\n"
        "4. Call end_modification_session when done"
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
    body: Any | None = None,
    allow_empty: bool = False,
) -> Any:
    """Make a request to the Qonic API using the current user's OAuth token."""
    token = _access_token.get()
    if not token:
        raise ValueError(
            "Not authenticated. Connect through an MCP client to "
            "authenticate with your Qonic account."
        )
    with httpx.Client(
        base_url=BASE_URL + "/v1",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=TIMEOUT,
    ) as client:
        response = client.request(method, path, params=params, json=body)
        response.raise_for_status()
        if allow_empty and not response.content:
            return {"status": "ok"}
        return response.json()


# ---------------------------------------------------------------------------
# Tools – Projects & Models
# ---------------------------------------------------------------------------


@mcp.tool()
def list_projects() -> str:
    """List all Qonic projects accessible to the authenticated user."""
    result = _api_request("GET", "/projects")
    return json.dumps(result, indent=2)


@mcp.tool()
def list_models(
    project_id: str = Field(description="Project ID to list models for"),
) -> str:
    """List all models within a Qonic project. Returns model IDs, names, and edit permissions."""
    result = _api_request("GET", f"/projects/{project_id}/models")
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tools – Products (building elements in a model)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_available_product_fields(
    project_id: str = Field(description="Project ID"),
    model_id: str = Field(description="Model ID"),
) -> str:
    """Get the list of available property fields for products in a model (e.g. Name, Class, FireRating, Width)."""
    result = _api_request(
        "GET", f"/projects/{project_id}/models/{model_id}/products/properties/available-data"
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def query_products(
    project_id: str = Field(description="Project ID"),
    model_id: str = Field(description="Model ID"),
    fields: str = Field(
        description='JSON array of field names to return, e.g. ["Name", "Class", "Guid"]'
    ),
    filters: str = Field(
        default="[]",
        description=(
            'JSON array of filter objects, e.g. [{"property": "Class", "value": "Wall", "operator": "equals"}]. '
            "Use an empty array [] for no filtering."
        ),
    ),
) -> str:
    """Query products (building elements) in a model. Returns requested fields for all products matching the filters."""
    fields_list = json.loads(fields)
    filters_list = json.loads(filters)
    result = _api_request(
        "POST",
        f"/projects/{project_id}/models/{model_id}/products/properties/query",
        body={"fields": fields_list, "filters": filters_list},
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def start_modification_session(
    project_id: str = Field(description="Project ID"),
    model_id: str = Field(description="Model ID to start a modification session on"),
) -> str:
    """Start a modification session on a model. Required before modifying or deleting products."""
    result = _api_request(
        "POST",
        f"/projects/{project_id}/models/{model_id}/start-session",
        allow_empty=True,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def end_modification_session(
    project_id: str = Field(description="Project ID"),
    model_id: str = Field(description="Model ID to end the modification session on"),
) -> str:
    """End the current modification session on a model."""
    result = _api_request(
        "POST",
        f"/projects/{project_id}/models/{model_id}/end-session",
        allow_empty=True,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def modify_products(
    project_id: str = Field(description="Project ID"),
    model_id: str = Field(description="Model ID"),
    changes: str = Field(
        description=(
            "JSON object describing product property changes. Supports 'add', 'update', and 'delete' keys. "
            'Example: {"update": {"FireRating": {"<product_guid>": {"PropertySet": "Pset_WallCommon", "Value": "60"}}}}'
        ),
    ),
) -> str:
    """Modify product properties in a model. Must call start_modification_session first."""
    changes_dict = json.loads(changes)
    result = _api_request(
        "POST",
        f"/projects/{project_id}/models/{model_id}/products",
        body=changes_dict,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def delete_product(
    project_id: str = Field(description="Project ID"),
    model_id: str = Field(description="Model ID"),
    product_guid: str = Field(description="GUID of the product to delete"),
) -> str:
    """Permanently delete a product (building element) from a model. Must call start_modification_session first."""
    result = _api_request(
        "DELETE",
        f"/projects/{project_id}/models/{model_id}/products/{product_guid}",
        allow_empty=True,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def publish_changes(
    project_id: str = Field(description="Project ID"),
    model_id: str = Field(description="Model ID"),
    title: str = Field(default="", description="Title for the published version"),
    description: str = Field(default="", description="Description of the changes"),
) -> str:
    """Publish pending changes in a modification session, creating a new model version."""
    body: dict[str, Any] = {"title": title, "description": description}
    result = _api_request(
        "POST",
        f"/projects/{project_id}/models/{model_id}/publish",
        body=body,
        allow_empty=True,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def discard_changes(
    project_id: str = Field(description="Project ID"),
    model_id: str = Field(description="Model ID"),
) -> str:
    """Discard all pending changes in the current modification session."""
    result = _api_request(
        "POST",
        f"/projects/{project_id}/models/{model_id}/discard",
        allow_empty=True,
    )
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tools – Spatial Locations
# ---------------------------------------------------------------------------


@mcp.tool()
def list_locations(
    project_id: str = Field(description="Project ID"),
) -> str:
    """List all spatial locations (Sites, Buildings, Floors, Spaces) in a project."""
    result = _api_request("GET", f"/projects/{project_id}/locations")
    return json.dumps(result, indent=2)


@mcp.tool()
def create_location(
    project_id: str = Field(description="Project ID"),
    name: str = Field(description="Name of the location"),
    location_type: str = Field(
        description=(
            "Type of location: Site, Building, Floor, Space, Bridge, MarineFacility, "
            "Railway, Road, Facility, or ExternalSpatialElement"
        ),
    ),
    parent_guid: str = Field(default="", description="GUID of the parent location (empty for top-level)"),
) -> str:
    """Create a new spatial location in a project's location hierarchy."""
    body: dict[str, Any] = {"name": name, "type": location_type}
    if parent_guid:
        body["parentGuid"] = parent_guid
    result = _api_request("POST", f"/projects/{project_id}/locations", body=body)
    return json.dumps(result, indent=2)


@mcp.tool()
def update_location(
    project_id: str = Field(description="Project ID"),
    location_guid: str = Field(description="GUID of the location to update"),
    name: str = Field(default="", description="New name (leave empty to keep current)"),
    location_type: str = Field(default="", description="New type (leave empty to keep current)"),
    parent_guid: str = Field(default="", description="New parent GUID (leave empty to keep current)"),
) -> str:
    """Update a spatial location's properties."""
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if location_type:
        body["type"] = location_type
    if parent_guid:
        body["parentGuid"] = parent_guid
    result = _api_request("PUT", f"/projects/{project_id}/locations/{location_guid}", body=body)
    return json.dumps(result, indent=2)


@mcp.tool()
def delete_location(
    project_id: str = Field(description="Project ID"),
    location_guid: str = Field(description="GUID of the location to delete"),
) -> str:
    """Permanently delete a spatial location from a project."""
    result = _api_request(
        "DELETE", f"/projects/{project_id}/locations/{location_guid}", allow_empty=True
    )
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tools – Material Libraries
# ---------------------------------------------------------------------------


@mcp.tool()
def list_material_libraries(
    project_id: str = Field(description="Project ID"),
) -> str:
    """List all material libraries in a project, including their materials."""
    result = _api_request("GET", f"/projects/{project_id}/material-libraries")
    return json.dumps(result, indent=2)


@mcp.tool()
def get_material_library(
    project_id: str = Field(description="Project ID"),
    library_guid: str = Field(description="GUID of the material library"),
) -> str:
    """Get details of a specific material library."""
    result = _api_request("GET", f"/projects/{project_id}/material-libraries/{library_guid}")
    return json.dumps(result, indent=2)


@mcp.tool()
def create_material_library(
    project_id: str = Field(description="Project ID"),
    name: str = Field(description="Name of the new material library"),
    library_type: str = Field(default="project", description="'project' or 'model'"),
    description: str = Field(default="", description="Optional description"),
) -> str:
    """Create a new material library in a project."""
    body: dict[str, Any] = {"name": name, "type": library_type}
    if description:
        body["description"] = description
    result = _api_request("POST", f"/projects/{project_id}/material-libraries", body=body)
    return json.dumps(result, indent=2)


@mcp.tool()
def create_material(
    project_id: str = Field(description="Project ID"),
    library_guid: str = Field(description="GUID of the material library"),
    name: str = Field(description="Name of the material"),
    color: str = Field(default="", description="Color value for the material"),
    category: str = Field(default="", description="Material category"),
    description: str = Field(default="", description="Optional description"),
) -> str:
    """Create a new material in a material library."""
    body: dict[str, Any] = {"name": name}
    if color:
        body["color"] = color
    if category:
        body["category"] = category
    if description:
        body["description"] = description
    result = _api_request(
        "POST", f"/projects/{project_id}/material-libraries/{library_guid}/materials", body=body
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def update_material(
    project_id: str = Field(description="Project ID"),
    library_guid: str = Field(description="GUID of the material library"),
    material_guid: str = Field(description="GUID of the material to update"),
    name: str = Field(default="", description="New name"),
    color: str = Field(default="", description="New color"),
    category: str = Field(default="", description="New category"),
    description: str = Field(default="", description="New description"),
) -> str:
    """Update a material's properties."""
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if color:
        body["color"] = color
    if category:
        body["category"] = category
    if description:
        body["description"] = description
    result = _api_request(
        "PUT",
        f"/projects/{project_id}/material-libraries/{library_guid}/materials/{material_guid}",
        body=body,
        allow_empty=True,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def delete_material(
    project_id: str = Field(description="Project ID"),
    library_guid: str = Field(description="GUID of the material library"),
    material_guid: str = Field(description="GUID of the material to delete"),
) -> str:
    """Permanently delete a material from a material library."""
    result = _api_request(
        "DELETE",
        f"/projects/{project_id}/material-libraries/{library_guid}/materials/{material_guid}",
        allow_empty=True,
    )
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tools – Types
# ---------------------------------------------------------------------------


@mcp.tool()
def list_types(
    project_id: str = Field(description="Project ID"),
) -> str:
    """List all types (reusable element definitions like wall types, door types) in a project."""
    result = _api_request("GET", f"/projects/{project_id}/types")
    return json.dumps(result, indent=2)


@mcp.tool()
def create_type(
    project_id: str = Field(description="Project ID"),
    library_guid: str = Field(description="GUID of the type library to add the type to"),
    name: str = Field(description="Name of the new type"),
    type_class: str = Field(description="Class of the type (e.g. Wall, Door, Window, Slab)"),
    subtype: str = Field(default="", description="Subtype of the type"),
) -> str:
    """Create a new type definition in a type library."""
    body: dict[str, Any] = {"name": name, "class": type_class}
    if subtype:
        body["subtype"] = subtype
    result = _api_request("POST", f"/projects/{project_id}/types/{library_guid}", body=body)
    return json.dumps(result, indent=2)


@mcp.tool()
def update_type(
    project_id: str = Field(description="Project ID"),
    library_guid: str = Field(description="GUID of the type library"),
    type_guid: str = Field(description="GUID of the type to update"),
    name: str = Field(default="", description="New name"),
    type_class: str = Field(default="", description="New class"),
    subtype: str = Field(default="", description="New subtype"),
) -> str:
    """Update a type definition's properties."""
    body: dict[str, Any] = {}
    if name:
        body["name"] = name
    if type_class:
        body["class"] = type_class
    if subtype:
        body["subtype"] = subtype
    result = _api_request(
        "PUT",
        f"/projects/{project_id}/types/{library_guid}/types/{type_guid}",
        body=body,
        allow_empty=True,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def delete_type(
    project_id: str = Field(description="Project ID"),
    library_guid: str = Field(description="GUID of the type library"),
    type_guid: str = Field(description="GUID of the type to delete"),
) -> str:
    """Permanently delete a type definition from a type library."""
    result = _api_request(
        "DELETE",
        f"/projects/{project_id}/types/{library_guid}/types/{type_guid}",
        allow_empty=True,
    )
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tools – Codification Libraries
# ---------------------------------------------------------------------------


@mcp.tool()
def list_codifications(
    project_id: str = Field(description="Project ID"),
) -> str:
    """List all codification (classification) libraries in a project."""
    result = _api_request("GET", f"/projects/{project_id}/codifications")
    return json.dumps(result, indent=2)


@mcp.tool()
def create_codification_library(
    project_id: str = Field(description="Project ID"),
    name: str = Field(description="Name of the new codification library"),
    library_type: str = Field(default="project", description="'project' or 'model'"),
    description: str = Field(default="", description="Optional description"),
) -> str:
    """Create a new codification (classification) library in a project."""
    body: dict[str, Any] = {"name": name, "type": library_type}
    if description:
        body["description"] = description
    result = _api_request("POST", f"/projects/{project_id}/codifications", body=body)
    return json.dumps(result, indent=2)


@mcp.tool()
def create_classification_code(
    project_id: str = Field(description="Project ID"),
    library_guid: str = Field(description="GUID of the codification library"),
    name: str = Field(description="Name of the code"),
    identification: str = Field(description="Identification string for the code"),
    parent_id: str = Field(default="", description="Parent code ID (empty for top-level)"),
    description: str = Field(default="", description="Optional description"),
) -> str:
    """Create a new classification code in a codification library."""
    body: dict[str, Any] = {"name": name, "identification": identification}
    if parent_id:
        body["parentId"] = parent_id
    if description:
        body["description"] = description
    result = _api_request(
        "POST", f"/projects/{project_id}/codifications/{library_guid}/codification", body=body
    )
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tools – Custom Properties
# ---------------------------------------------------------------------------


@mcp.tool()
def list_custom_properties(
    project_id: str = Field(description="Project ID"),
) -> str:
    """List all custom property sets and their definitions in a project."""
    result = _api_request("GET", f"/projects/{project_id}/customProperties")
    return json.dumps(result, indent=2)


@mcp.tool()
def create_property_set(
    project_id: str = Field(description="Project ID"),
    name: str = Field(description="Name of the new property set"),
    entity_types: str = Field(
        default="[]",
        description=(
            'JSON array of entity type objects, e.g. '
            '[{"displayName": "Wall", "value": "IfcWall", "predefinedTypes": []}]'
        ),
    ),
) -> str:
    """Create a new custom property set in a project."""
    body: dict[str, Any] = {"name": name}
    et = json.loads(entity_types)
    if et:
        body["entityTypes"] = et
    result = _api_request(
        "POST", f"/projects/{project_id}/customProperties/property-sets", body=body
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def add_property_definition(
    project_id: str = Field(description="Project ID"),
    property_set_id: str = Field(description="ID of the property set to add the property to"),
    name: str = Field(description="Name of the property"),
    data_type: str = Field(description="Data type (e.g. 'string', 'integer', 'boolean', 'real')"),
    measure_type: str = Field(default="", description="Measure type"),
    unit: str = Field(default="", description="Unit name"),
) -> str:
    """Add a new property definition to a custom property set."""
    body: dict[str, Any] = {"name": name, "dataType": data_type}
    if measure_type:
        body["measureType"] = measure_type
    if unit:
        body["unit"] = unit
    result = _api_request(
        "POST",
        f"/projects/{project_id}/customProperties/property-sets/{property_set_id}/property",
        body=body,
    )
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# ASGI application
# ---------------------------------------------------------------------------

# Use FastMCP's built-in Streamable HTTP app (includes lifespan management)
mcp.settings.stateless_http = True
mcp.settings.streamable_http_path = "/mcp"

# Vercel handles host validation at its edge; disable MCP's DNS rebinding
# protection which only allows localhost by default.
mcp.settings.transport_security.enable_dns_rebinding_protection = False

_inner_app = mcp.streamable_http_app()


async def app(scope, receive, send):
    """ASGI wrapper that adds OAuth proxy endpoints + token extraction."""
    if scope["type"] == "http":
        request = Request(scope, receive, send)
        path = request.url.path

        # --- OAuth metadata discovery ---
        if path == "/.well-known/oauth-authorization-server":
            base = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", "")
            if base and not base.startswith("http"):
                base = f"https://{base}"
            if not base:
                base = str(request.base_url).rstrip("/")

            metadata: dict[str, Any] = {
                "issuer": base,
                "authorization_endpoint": f"{base}/oauth/authorize",
                "token_endpoint": f"{base}/oauth/token",
                "registration_endpoint": f"{base}/oauth/register",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
                "scopes_supported": [
                    "projects:read", "projects:write",
                    "models:read", "models:write",
                    "issues:read",
                    "libraries:read", "libraries:write",
                ],
            }

            response = JSONResponse(metadata)
            await response(scope, receive, send)
            return

        # --- OAuth authorize proxy (redirect to Qonic) ---
        if path == "/oauth/authorize":
            base = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", "")
            if base and not base.startswith("http"):
                base = f"https://{base}"
            if not base:
                base = str(request.base_url).rstrip("/")

            params = dict(request.query_params)
            params["client_id"] = OAUTH_CLIENT_ID

            # Wrap the original state + redirect_uri so we can relay
            # the auth code back to mcp-remote's localhost callback.
            original_redirect = params.pop("redirect_uri", "")
            original_state = params.pop("state", "")
            wrapped = json.dumps({"s": original_state, "r": original_redirect})
            params["state"] = base64.urlsafe_b64encode(wrapped.encode()).decode()
            params["redirect_uri"] = f"{base}/oauth/callback"

            authorize_url = f"{BASE_URL}/v1/auth/authorize?{urlencode(params)}"
            response = RedirectResponse(authorize_url, status_code=302)
            await response(scope, receive, send)
            return

        # --- OAuth callback relay (Qonic -> our server -> mcp-remote localhost) ---
        if path == "/oauth/callback":
            params = dict(request.query_params)
            wrapped_state = params.get("state", "")
            try:
                inner = json.loads(base64.urlsafe_b64decode(wrapped_state).decode())
                original_redirect = inner["r"]
                original_state = inner["s"]
            except Exception:
                response = Response("Invalid OAuth state", status_code=400)
                await response(scope, receive, send)
                return

            # Build the redirect to mcp-remote's localhost callback
            relay_params = {}
            if "code" in params:
                relay_params["code"] = params["code"]
            if "error" in params:
                relay_params["error"] = params["error"]
            if original_state:
                relay_params["state"] = original_state
            relay_url = f"{original_redirect}?{urlencode(relay_params)}"
            response = RedirectResponse(relay_url, status_code=302)
            await response(scope, receive, send)
            return

        # --- OAuth token proxy (inject client_secret) ---
        if path == "/oauth/token" and request.method == "POST":
            body = await request.body()
            form_data = parse_qs(body.decode())
            # Flatten single-value lists
            token_params = {k: v[0] if len(v) == 1 else v for k, v in form_data.items()}
            # Inject our client credentials
            token_params["client_id"] = OAUTH_CLIENT_ID
            token_params["client_secret"] = OAUTH_CLIENT_SECRET

            # Replace mcp-remote's localhost redirect_uri with our Vercel
            # callback URL — must match what was used in the authorize step.
            base = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", "")
            if base and not base.startswith("http"):
                base = f"https://{base}"
            if not base:
                base = str(request.base_url).rstrip("/")
            token_params["redirect_uri"] = f"{base}/oauth/callback"

            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                token_resp = await client.post(
                    f"{BASE_URL}/v1/auth/token",
                    data=token_params,
                )

            response = Response(
                content=token_resp.content,
                status_code=token_resp.status_code,
                headers={"Content-Type": token_resp.headers.get("content-type", "application/json")},
            )
            await response(scope, receive, send)
            return

        # --- Dynamic client registration (return our pre-registered client) ---
        if path == "/oauth/register" and request.method == "POST":
            try:
                body = await request.json()
            except Exception:
                body = {}

            # Echo back the client's requested redirect_uris so mcp-remote
            # can find its localhost callback URI in the cached registration.
            client_redirect_uris = body.get("redirect_uris", [])

            response = JSONResponse({
                "client_id": OAUTH_CLIENT_ID,
                "client_name": "qonic-mcp",
                "redirect_uris": client_redirect_uris,
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            })
            await response(scope, receive, send)
            return

        # Extract Bearer token, or require auth on MCP endpoint
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            _access_token.set(auth[7:])
        elif path == "/mcp":
            # Return 401 to trigger OAuth flow in MCP clients
            response = Response(
                content="Unauthorized",
                status_code=401,
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )
            await response(scope, receive, send)
            return

    # Delegate everything else to the MCP app
    await _inner_app(scope, receive, send)
