# qonic-mcp

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for
[Qonic](https://qonic.com), written in Python and deployable on
[Smithery](https://smithery.ai).

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
- A Qonic API key

### Local development

```bash
# Clone the repository
git clone https://github.com/pwgith/qonic-mcp.git
cd qonic-mcp

# Install dependencies (using uv)
pip install uv
uv pip install -e .

# Configure your API key
cp .env.example .env
# Edit .env and set QONIC_API_KEY

# Run the server
python -m qonic_mcp.server
```

### Running with Docker

```bash
docker build -t qonic-mcp .
docker run -e QONIC_API_KEY=your-key qonic-mcp
```

## Deploying to Smithery

This server is configured for deployment on [Smithery](https://smithery.ai) via
`smithery.yaml`. When deploying, provide the following configuration:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `apiKey` | ✅ | Your Qonic API key |
| `baseUrl` | ❌ | Qonic API base URL (default: `https://api.qonic.com`) |

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QONIC_API_KEY` | ✅ | — | Qonic API key |
| `QONIC_BASE_URL` | ❌ | `https://api.qonic.com` | Qonic API base URL |
| `QONIC_TIMEOUT` | ❌ | `30` | Request timeout in seconds |

## License

MIT