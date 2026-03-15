# qonic-mcp

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for
[Qonic](https://qonic.com), written in Python and deployed on
[Vercel](https://vercel.com).

Users authenticate with their Qonic account via OAuth — no API keys needed.

## Features

The server exposes the following MCP tools:

| Tool | Description |
|------|-------------|
| `list_projects` | List all Qonic projects |
| `get_project` | Get details of a specific project |
| `create_project` | Create a new project |
| `list_designs` | List designs within a project |
| `get_design` | Get details of a specific design |
| `create_design` | Create a new design |
| `list_analyses` | List analyses for a design |
| `run_analysis` | Run an analysis on a design |
| `get_analysis_status` | Check the status/results of an analysis job |
| `get_account_info` | Get authenticated account info |
| `search` | Search across Qonic resources |

## Setup

### Prerequisites

- Python 3.11+

### Local development

```bash
# Clone the repository
git clone https://github.com/pwgith/qonic-mcp.git
cd qonic-mcp

# Install dependencies (using uv)
pip install uv
uv pip install -e .

# Run the server locally (starts on port 8000)
python -m qonic_mcp.server
```

## Deploying to Vercel

1. Push this repo to GitHub.
2. Import the repo in the [Vercel dashboard](https://vercel.com/new).
3. Set the required environment variables (see below).
4. Deploy — Vercel will use `vercel.json` and `requirements.txt` automatically.

The MCP endpoint will be available at:
`https://<your-project>.vercel.app/mcp`

OAuth metadata is served at:
`https://<your-project>.vercel.app/.well-known/oauth-authorization-server`

## Environment variables

Set these in the Vercel dashboard under **Settings → Environment Variables**.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QONIC_BASE_URL` | ❌ | `https://api.qonic.com` | Qonic API base URL |
| `QONIC_TIMEOUT` | ❌ | `30` | Request timeout in seconds |
| `QONIC_OAUTH_AUTHORIZE_URL` | ❌ | `{BASE_URL}/oauth/authorize` | Qonic OAuth authorization endpoint |
| `QONIC_OAUTH_TOKEN_URL` | ❌ | `{BASE_URL}/oauth/token` | Qonic OAuth token endpoint |
| `QONIC_OAUTH_REGISTRATION_URL` | ❌ | — | Dynamic client registration endpoint (if supported) |

## License

MIT