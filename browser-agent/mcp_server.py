# mcp_server.py
from fastapi import FastAPI, BackgroundTasks
from playwright.sync_api import sync_playwright, Playwright
import asyncio
import queue
import threading
import time
import uvicorn
from typing import Optional

app = FastAPI()

# Глобальные переменные для управления браузером
browser_thread: Optional[threading.Thread] = None
playwright_instance = None
browser = None
page = None

# Очередь для коммуникации между потоками
command_queue = queue.Queue()
result_queue = queue.Queue()

def browser_worker():
    """Функция, которая запускается в отдельном потоке и управляет браузером"""
    global playwright_instance, browser, page
    
    try:
        playwright_instance = sync_playwright().start()
        user_profile = "/home/q/.mozilla/firefox/nsaalvuw.default-release"
        
        print("Запуск Firefox...")
        browser = playwright_instance.firefox.launch_persistent_context(
            user_data_dir=user_profile,
            headless=False,
            slow_mo=300
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        print(f"Браузер запущен. Текущая страница: {page.url}")
        
        # Основной цикл обработки команд
        while True:
            try:
                # Ждем команду с таймаутом, чтобы можно было проверять флаги
                command = command_queue.get(timeout=0.1)
                tool = command.get("tool")
                args = command.get("args", {})
                
                try:
                    if tool == "navigate":
                        url = args["url"].strip()
                        print(f"Переход на: {url}")
                        page.goto(url)
                        result_queue.put({"result": f"Перешли на {url}"})
                        
                    elif tool == "get_url":
                        current_url = page.url
                        print(f"Текущий URL: {current_url}")
                        result_queue.put({"result": current_url})
                        
                    elif tool == "getElements":
                        elements = []
                        handles = page.query_selector_all("button, a, input:not([type='hidden']), [role='button']")
                        
                        for i, el in enumerate(handles):
                            if el.is_visible():
                                text = (el.text_content() or '').strip()[:50]
                                # Удаляем старый атрибут, если есть
                                el.evaluate("el => el.removeAttribute('data-mcp-id')")
                                # Устанавливаем новый
                                el.evaluate(f"el => el.setAttribute('data-mcp-id', '{i}')")
                                elements.append({
                                    "id": i,
                                    "text": text,
                                    "selector": f"[data-mcp-id='{i}']"
                                })
                        
                        print(f"Найдено элементов: {len(elements)}")
                        result_queue.put({"result": elements})
                        
                    elif tool == "click":
                        selector = args["query"]
                        print(f"Клик по: {selector}")
                        page.click(selector)
                        result_queue.put({"result": "Клик выполнен"})
                        
                    elif tool == "type":
                        selector = args["query"]
                        text = args["text"]
                        print(f"Ввод '{text}' в {selector}")
                        page.fill(selector, text)
                        result_queue.put({"result": f"Введено: {text}"})
                        
                    elif tool == "screenshot":
                        screenshot = page.screenshot()
                        result_queue.put({"result": screenshot})
                        
                    elif tool == "get_html":
                        html = page.content()
                        result_queue.put({"result": html})
                        
                    elif tool == "quit":
                        print("Завершение работы браузера...")
                        result_queue.put({"result": "Браузер завершен"})
                        break
                        
                    else:
                        result_queue.put({"error": f"Неизвестный инструмент: {tool}"})
                        
                except Exception as e:
                    result_queue.put({"error": str(e)})
                    
            except queue.Empty:
                # Если нет команд, продолжаем цикл
                continue
            except KeyboardInterrupt:
                break
                
    except Exception as e:
        print(f"Ошибка в browser_worker: {e}")
        result_queue.put({"error": str(e)})
    finally:
        if browser:
            try:
                browser.close()
            except:
                pass
        if playwright_instance:
            try:
                playwright_instance.stop()
            except:
                pass

def execute_in_browser(tool: str, args: dict = None):
    """Отправляет команду в браузерный поток и ждет результат"""
    if args is None:
        args = {}
    
    # Отправляем команду
    command_queue.put({"tool": tool, "args": args})
    
    # Ждем результат с таймаутом
    try:
        result = result_queue.get(timeout=10)
        return result
    except queue.Empty:
        return {"error": "Таймаут ожидания ответа от браузера"}

@app.on_event("startup")
async def startup_event():
    """Запускаем браузер при старте сервера"""
    global browser_thread
    
    print("Запуск браузера...")
    browser_thread = threading.Thread(target=browser_worker, daemon=True)
    browser_thread.start()
    
    # Ждем инициализации браузера
    max_wait = 30
    for _ in range(max_wait * 2):  # Проверяем каждые 0.5 секунды
        try:
            # Проверяем, доступна ли страница
            if page is not None:
                print("Браузер успешно запущен!")
                return
        except:
            pass
        await asyncio.sleep(0.5)
    
    print("Предупреждение: Браузер не запустился за отведенное время")

@app.post("/mcp")
async def mcp_call(request: dict):
    """Основной обработчик MCP запросов"""
    tool = request.get("tool")
    args = request.get("args", {})
    
    print(f"Получен запрос: {tool} с аргументами: {args}")
    
    # Выполняем команду в браузерном потоке
    result = execute_in_browser(tool, args)
    
    # Добавляем информацию о текущем URL для контекста
    if "error" not in result:
        try:
            url_result = execute_in_browser("get_url", {})
            if "result" in url_result:
                result["current_url"] = url_result["result"]
        except:
            pass
    
    return result

@app.on_event("shutdown")
async def shutdown_event():
    """Корректно завершаем работу при остановке сервера"""
    print("Остановка браузера...")
    execute_in_browser("quit", {})
    if browser_thread:
        browser_thread.join(timeout=5)

if __name__ == "__main__":
    print("MCP-сервер запущен на http://127.0.0.1:8000")
    print("Используйте /mcp для доступа к браузеру")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")