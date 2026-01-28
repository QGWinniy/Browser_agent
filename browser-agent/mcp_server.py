from fastapi import FastAPI
from playwright.sync_api import sync_playwright
import uvicorn

app = FastAPI()
page = None

def init_browser():
    global page, browser
    p = sync_playwright().start()
    # ⚠️ ЗАМЕНИ "q" НА СВОЁ ИМЯ ПОЛЬЗОВАТЕЛЯ WINDOWS!
    user_profile = "/mnt/c/Users/georg/AppData/Local/Google/Chrome/User Data"
    chrome_exe = "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
    
    browser = p.chromium.launch_persistent_context(
        user_data_dir=user_profile,
        executable_path=chrome_exe,
        headless=False,
        slow_mo=300,
        args=["--disable-web-security"]
    )
    page = browser.pages[0] if browser.pages else browser.new_page()

init_browser()

@app.post("/mcp")
async def mcp_call(request: dict):
    tool = request.get("tool")
    args = request.get("args", {})
    try:
        if tool == "navigate":
            page.goto(args["url"])
            return {"result": "OK"}
        elif tool == "get_url":
            return {"result": page.url}
        elif tool == "getElements":
            elements = []
            handles = page.query_selector_all("button, a, input:not([type='hidden'])")
            for i, el in enumerate(handles):
                if el.is_visible():
                    text = (el.text_content() or '').strip()[:50]
                    el.evaluate(f"el => el.setAttribute('data-mcp-id', '{i}')")
                    elements.append({"id": i, "text": text, "selector": f"[data-mcp-id='{i}']"})
            return {"result": elements}
        elif tool == "click":
            page.click(args["query"])
            return {"result": "OK"}
        elif tool == "type":
            page.fill(args["query"], args["text"])
            return {"result": "OK"}
        elif tool == "scroll":
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            return {"result": "OK"}
        elif tool == "pressKey":
            page.keyboard.press(args["key"])
            return {"result": "OK"}
        else:
            return {"error": f"Unknown tool: {tool}"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)