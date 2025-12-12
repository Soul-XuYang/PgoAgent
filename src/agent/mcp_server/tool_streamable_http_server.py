from mcp.server import FastMCP

from agent.mcp_server.tool_sse_server import server

server_streamable = FastMCP(
    name="sse-mcp",
    host = '127.0.0.1',
    port= 7080,
    log_level='DEBUG',
    mount_path="/",
    sse_path="/sse",
)
if __name__ == "__main__":
    server_streamable.run(
        transport='streamable-http',
    )

