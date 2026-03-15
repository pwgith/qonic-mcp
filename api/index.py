"""Vercel serverless function entry point."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from qonic_mcp.server import app  # noqa: E402, F401
