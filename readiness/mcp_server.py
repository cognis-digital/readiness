"""READINESS MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from readiness.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-readiness[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-readiness[mcp]'")
        return 1
    app = FastMCP("readiness")

    @app.tool()
    def readiness_scan(target: str) -> str:
        """Compute unit readiness (C-ratings style) from a personnel/equipment/training YAML and flag gaps.. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
