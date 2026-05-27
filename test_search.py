import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(timeout=30.0)

print("Testing web search tool...")
try:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": "Search the web for Notion the company and tell me one recent fact."}],
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 1, "allowed_callers": ["direct"]}],
    )
    print("SUCCESS")
    for block in response.content:
        if hasattr(block, "text"):
            print(block.text)
except anthropic.APITimeoutError:
    print("TIMEOUT — web search tool is not available or too slow in your region.")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
