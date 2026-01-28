from fastapi import FastAPI
from playwright.sync_api import sync_playwright
import queue
import threading
import time
import uvicorn
from typing import Optional

app = FastAPI()

browser_thread: Optional[threading.Thread] = None
playwright_instance = None
browser = None
page = None

command_queue = queue.Queue()
result_queue = queue.Queue()

def browser_worker():
    """Запускается в отдельном потоке. Управляет браузером."""
    global playwright_instance, browser, page
    
    try:
        playwright_instance = sync_playwright().start()
        user_profile = "/home/q/.mozilla/firefox/nsaalvuw.default-release"
        
        print("🚀 Запуск Firefox...")
        browser = playwright_instance.firefox.launch_persistent_context(
            user_data_dir=user_profile,
            headless=False,
            slow_mo=300
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        print(f"✅ Браузер запущен. Стартовая страница: {page.url}")
        
        while True:
            try:
                command = command_queue.get(timeout=0.5)
                tool = command.get("tool")
                args = command.get("args", {})
                
                if tool == "navigate":
                    _handle_navigate(args)
                elif tool == "wait_for_page_ready":
                    _handle_wait_for_page_ready()
                elif tool == "get_url":
                    _handle_get_url()
                elif tool == "getElements":
                    _handle_get_elements()
                elif tool == "click":
                    _handle_click(args)
                elif tool == "type":
                    _handle_type(args)
                elif tool == "quit":
                    _handle_quit()
                    break
                else:
                    result_queue.put({"error": f"Неизвестный инструмент: {tool}"})

            except queue.Empty:
                continue
            except Exception as e:
                print(f"💥 Неожиданная ошибка в основном цикле: {e}")
                result_queue.put({"error": f"Цикл сломался: {e}"})

    except Exception as e:
        print(f"❌ Ошибка в browser_worker: {e}")
        result_queue.put({"error": f"Запуск браузера сломался: {e}"})
    finally:
        try:
            if browser:
                browser.close()
            if playwright_instance:
                playwright_instance.stop()
        except:
            pass


def _handle_navigate(args):
    url = args["url"].strip()
    if not url.startswith(("http://", "https://")):
        result_queue.put({"error": "URL должен начинаться с http:// или https://"})
        return
    print(f"🌐 Переход на: {url}")
    page.goto(url, timeout=300_000)
    result_queue.put({"result": f"Перешли на {url}"})


def _handle_wait_for_page_ready():
    print("⏳ Ожидание загрузки страницы (до 300 сек)...")
    try:
        page.wait_for_load_state("networkidle", timeout=300_000)
        selectors = (
            "button, a[href], [role='button'], "
            "input:not([type='hidden']):not([type='button']):not([type='submit']), "
            "textarea, [aria-label], div[contenteditable='true'], div[contenteditable=''], "
            "div[class*='plus' i], span[class*='plus' i], "
            "div[class*='add' i], span[class*='add' i], "
            "div[class*='button' i], span[class*='button' i], "
            "div[data-testid*='button' i], div[data-testid*='plus' i], "
            "div[data-tid*='plus' i], div[data-auto*='plus' i]"
        )
        page.wait_for_selector(selectors, state="visible", timeout=150_000)
        result_queue.put({"result": "Страница готова"})
    except Exception as e:
        result_queue.put({"result": f"Частичная загрузка: {str(e)[:100]}"})


def _handle_get_url():
    current_url = page.url
    print(f"🔗 Текущий URL: {current_url}")
    result_queue.put({"result": current_url})


def _handle_get_elements():
    selectors = (
        "button, a[href], [role='button'], "
        "input:not([type='hidden']):not([type='button']):not([type='submit']), "
        "textarea, [aria-label], div[contenteditable='true'], div[contenteditable='']"
    )
    handles = page.query_selector_all(selectors)
    
    elements = []
    for el in handles:
        if not (el.is_visible() and el.is_enabled()):
            continue
            
        tag = el.evaluate("el => el.tagName.toLowerCase()")
        text = (el.text_content() or '').strip()
        placeholder = el.get_attribute("placeholder") or ""
        aria_label = el.get_attribute("aria-label") or ""
        title = el.get_attribute("title") or ""
        
        label = aria_label or text or placeholder or title or f"<{tag}>"
        label = label.replace("\n", " ").strip()[:80]
        
        is_input_tag = tag in ("input", "textarea")
        contenteditable = el.get_attribute("contenteditable")
        is_contenteditable = contenteditable is not None and contenteditable.strip().lower() in ("", "true")
        elem_type = "input" if is_input_tag or is_contenteditable else "clickable"
        
        elements.append({
            "tag": tag,
            "text": label,
            "type": elem_type
        })
    
    print(f"🔍 Найдено элементов: {len(elements)}")
    result_queue.put({"result": elements})


def _handle_click(args):
    raw_index = args.get("index")
    try:
        index = int(raw_index)
        if index < 0:
            raise ValueError("index < 0")
    except (ValueError, TypeError):
        result_queue.put({"error": f"Неверный index: {repr(raw_index)}"})
        return

    selectors = (
        "button, a[href], [role='button'], "
        "input:not([type='hidden']):not([type='button']):not([type='submit']), "
        "textarea, [aria-label], div[contenteditable='true'], div[contenteditable='']"
    )
    all_elements = page.query_selector_all(selectors)
    visible_elements = [el for el in all_elements if el.is_visible() and el.is_enabled()]
    
    if index >= len(visible_elements):
        result_queue.put({"error": f"Индекс {index} вне диапазона. Доступно: {len(visible_elements)}"})
        return
    
    target = visible_elements[index]
    tag = target.evaluate("el => el.tagName.toLowerCase()")
    is_input = tag in ("input", "textarea") or target.get_attribute("contenteditable") in ("", "true")
    
    if is_input:
        result_queue.put({"error": f"Нельзя кликнуть по полю ввода #{index}"})
        return
    
    print(f"🖱️ Клик по элементу #{index}")
    target.click(timeout=30_000)
    result_queue.put({"result": "Клик выполнен"})


def _handle_type(args):
    raw_index = args.get("index")
    text = args.get("text", "")
    try:
        index = int(raw_index)
        if index < 0:
            raise ValueError("index < 0")
    except (ValueError, TypeError):
        result_queue.put({"error": f"Неверный index: {repr(raw_index)}"})
        return

    selectors = (
        "button, a[href], [role='button'], "
        "input:not([type='hidden']):not([type='button']):not([type='submit']), "
        "textarea, [aria-label], div[contenteditable='true'], div[contenteditable='']"
    )
    all_elements = page.query_selector_all(selectors)
    visible_elements = [el for el in all_elements if el.is_visible() and el.is_enabled()]
    
    if index >= len(visible_elements):
        result_queue.put({"error": f"Индекс {index} вне диапазона. Доступно: {len(visible_elements)}"})
        return
    
    target = visible_elements[index]
    tag = target.evaluate("el => el.tagName.toLowerCase()")
    is_input = tag in ("input", "textarea") or target.get_attribute("contenteditable") in ("", "true")
    
    if not is_input:
        result_queue.put({"error": f"Элемент #{index} не является полем ввода"})
        return
    
    print(f"⌨️ Ввод в элемент #{index}: '{text}'")
    if target.get_attribute("contenteditable") in ("", "true"):
        target.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        page.keyboard.type(text, delay=50)
    else:
        target.fill("")
        target.type(text, delay=50)
    
    result_queue.put({"result": f"Введено: {text}"})


def _handle_quit():
    """Обрабатывает команду завершения — просто отправляет подтверждение."""
    print("🛑 Завершение браузера...")
    result_queue.put({"result": "Браузер завершён"})

def execute_in_browser(tool: str, args: dict = None):
    """Отправляет команду и ждёт результат (до 300 сек)."""
    if args is None:
        args = {}
    command_queue.put({"tool": tool, "args": args})
    try:
        return result_queue.get(timeout=300)
    except queue.Empty:
        return {"error": "Таймаут 300 сек"}

@app.post("/mcp")
def handle_mcp(request: dict):
    """Обрабатывает MCP-запрос. Возвращает ТОЛЬКО то, что вернул браузер."""
    tool = request.get("tool")
    args = request.get("args", {})
    print(f"📥 MCP: {tool} {args}")
    return execute_in_browser(tool, args)


if __name__ == "__main__":
    print("🖥️  Запуск MCP-сервера...")
    browser_thread = threading.Thread(target=browser_worker, daemon=True)
    browser_thread.start()
    
    for _ in range(60):
        if page is not None:
            break
        time.sleep(0.5)
    else:
        print("⚠️  Браузер не запустился за 30 сек")
    
    print("✅ MCP-сервер готов на http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")