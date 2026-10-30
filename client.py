"""Custom AI chat client: Claude + the inventory MCP server over stdio.
Run: export ANTHROPIC_API_KEY=...; python client.py"""
import asyncio, os, sys
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
SYSTEM = ("You are an Inventory Management assistant. Always use the provided tools for data; never guess "
          "stock or prices. Prices are in INR (₹). Present results as concise tables or short lists, and "
          "confirm any change you make (old -> new). If a tool returns ok=false, explain the error plainly.")


async def main():
    params = StdioServerParameters(command=sys.executable,
                                   args=[os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")])
    claude = Anthropic()
    async with stdio_client(params) as (r, w), ClientSession(r, w) as session:
        await session.initialize()
        tools = [{"name": t.name, "description": t.description, "input_schema": t.inputSchema}
                 for t in (await session.list_tools()).tools]
        print(f"Connected. Tools: {', '.join(t['name'] for t in tools)}\nType 'exit' to quit.\n")
        messages = []
        while True:
            user = input("You> ").strip()
            if user.lower() in {"exit", "quit"}:
                break
            if not user:
                continue
            messages.append({"role": "user", "content": user})
            while True:  # tool-use loop
                resp = claude.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM,
                                              tools=tools, messages=messages)
                messages.append({"role": "assistant", "content": resp.content})
                if resp.stop_reason != "tool_use":
                    print("\nAssistant>", "".join(b.text for b in resp.content if b.type == "text"), "\n")
                    break
                results = []
                for b in resp.content:
                    if b.type == "tool_use":
                        print(f"  [tool] {b.name}({b.input})")
                        out = await session.call_tool(b.name, b.input)
                        results.append({"type": "tool_result", "tool_use_id": b.id,
                                        "content": "".join(c.text for c in out.content if c.type == "text")})
                messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    asyncio.run(main())
