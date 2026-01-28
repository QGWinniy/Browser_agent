import requests

def mcp_call(tool_name, args):
    try:
        resp = requests.post("http://127.0.0.1:8000/mcp", json={"tool": tool_name, "args": args}, timeout=30)
        return resp.json().get("result", "OK") if resp.status_code == 200 else f"Ошибка {resp.status_code}"
    except Exception as e:
        return f"Исключение: {str(e)}"

def navigate(url): return mcp_call("navigate", {"url": url})
def click_element(query): return mcp_call("click", {"query": query})
def type_text(query, text): return mcp_call("type", {"query": query, "text": text})
def get_page_summary(): return mcp_call("getElements", {})
def get_current_url(): return mcp_call("get_url", {})