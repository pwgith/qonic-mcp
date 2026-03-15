FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install project dependencies
RUN uv pip install --system --no-cache .

# Run the MCP server
CMD ["python", "-m", "qonic_mcp.server"]
