"""Vercel serverless function entry point."""

import os
import sys

# Add src/ to the Python path so qonic_mcp is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from qonic_mcp.server import app  # noqa: E402 – path must be set first
