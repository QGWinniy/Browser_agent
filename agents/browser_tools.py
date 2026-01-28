import requests

MCP_SERVER_URL = "http://127.0.0.1:8000/mcp" 

def mcp_call(tool_name: str, args: dict):
    try:
        resp = requests.post(
            MCP_SERVER_URL,
            json={"tool": tool_name, "args": args},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            if "error" in data:
                return f"Ошибка: {data['error']}"
            return data.get("result", "OK")
        else:
            return f"Ошибка HTTP {resp.status_code}"
    except Exception as e:
        return f"Исключение: {str(e)}"

def summarize_elements(elements):
    if not elements:
        return "Нет элементов."
    parts = []
    for i, el in enumerate(elements):
        typ = "поле" if el.get("type") == "input" else "кнопка"
        text = el.get("text", "").replace("\n", " ").strip()
        parts.append(f"{i}: {typ} '{text}'")
    return "; ".join(parts)


def wait_for_page_ready(timeout=15):
    """
    Ждёт, пока страница не станет "интерактивной":
    - исчезнет индикатор загрузки,
    - появится хотя бы один интерактивный элемент.
    """
    try:
        resp = requests.post("http://127.0.0.1:8000/mcp", json={
            "tool": "wait_for_page_ready",
            "args": {"timeout": timeout * 1000}
        }, timeout=timeout + 2)
        return resp.json().get("result", "OK")
    except Exception as e:
        return f"Таймаут ожидания страницы: {e}"

# --- Публичные функции для агента ---
def navigate(url: str) -> str:
    return mcp_call("navigate", {"url": url})

def click_element(index: int) -> str:
    return mcp_call("click", {"index": index})

def type_text(index: int, text: str) -> str:
    return mcp_call("type", {"index": index, "text": text})

def get_page_summary() -> list:
    result = mcp_call("getElements", {})
    print("result: ", len(result), type(result))
    print("result: ", result)
    return result if isinstance(result, list) else []

def get_current_url() -> str:
    return mcp_call("get_url", {})