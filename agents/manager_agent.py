# agents/manager_agent.py
import os
import json
import time
import requests
from agents.browser_tools import navigate, click_element, type_text, get_page_summary, get_current_url
from dotenv import load_dotenv

load_dotenv()

class ManagerAgent:
    def __init__(self):
        self.api_key = os.getenv("LITELLM_API_KEY")
        self.base_url = "https://litellm.tokengate.ru/v1/chat/completions"
        self.model = "deepseek/deepseek-r1-distill-llama-70b"
        with open("prompts/manager.txt") as f:
            self.prompt_template = f.read()

    def _ask_llm(self, prompt: str) -> dict:
        print("\n💭 [LLM ДУМАЕТ...]")
        print("-" * 50)
        # print(f"Промпт:\n{prompt}\n")  # раскомментируй, если нужно видеть весь промпт
        
        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
                    timeout=300
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    print(f"🧠 Ответ LLM:\n{content}\n")
                    
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start != -1 and end > start:
                        try:
                            result = json.loads(content[start:end])
                            print(f"✅ Решение: {result}")
                            print("-" * 50)
                            return result
                        except json.JSONDecodeError as e:
                            print(f"❌ Ошибка JSON: {e}")
                else:
                    print(f"❌ API ошибка: {resp.status_code}")
            except Exception as e:
                print(f"⚠️ Исключение: {e}")
            
            if attempt < 3:
                print(f"⏳ Повтор попытки {attempt + 1}...")
                time.sleep(2)
        
        print("🛑 Не удалось получить валидное решение от LLM.")
        print("-" * 50)
        return {}

    def run(self, goal: str):
        print(f"\n🚀 НАЧИНАЮ ВЫПОЛНЕНИЕ ЗАДАЧИ: {goal}")
        print("=" * 60)
        
        history = []
        step = 0

        while True:
            step += 1
            print(f"\n🔹 ШАГ {step}")
            
            # Получаем состояние
            current_url = get_current_url()
            page_summary = get_page_summary()
            
            print(f"🌐 Текущий URL: {current_url}")
            print(f"📄 Элементы на странице: {page_summary[:150]}...")

            # Формируем промпт и получаем решение
            prompt = self.prompt_template.format(
                goal=goal,
                current_url=current_url,
                history="\n".join(history[-5:]),
                page_summary=page_summary
            )
            decision = self._ask_llm(prompt)
            
            action = decision.get("action")
            args = decision.get("args") or {}

            if action == "DONE":
                result = args.get("result", "Задача выполнена")
                print(f"\n🎉 УСПЕХ! {result}")
                break

            # Выполняем действие
            print(f"\n🛠️ ВЫПОЛНЯЮ: {action} {args}")
            
            result = "Неизвестное действие"
            if action == "NAVIGATE":
                url = args.get("url", "")
                result = navigate(url)
                history.append(f"→ перешёл на {url}")
                print(f"   → Результат: {result}")

            elif action == "CLICK":
                query = args.get("query", "")
                result = click_element(query)
                history.append(f"🖱️ кликнул по '{query}'")
                print(f"   → Результат: {result}")

            elif action == "TYPE":
                query = args.get("query", "")
                text = args.get("text", "")
                result = type_text(query, text)
                history.append(f"⌨️ ввёл '{text}' в '{query}'")
                print(f"   → Результат: {result}")

            else:
                history.append(f"❓ неизвестное действие: {action}")
                print("   → Неизвестное действие")

            # Пауза для наблюдения
            print(f"\n⏳ Жду 3 секунды, чтобы ты мог увидеть результат в браузере...")
            time.sleep(3)