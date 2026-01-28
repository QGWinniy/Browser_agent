# agents/manager_agent.py
import os
import json
import time
import requests
from agents.browser_tools import navigate, click_element, type_text, get_page_summary, get_current_url, summarize_elements
from dotenv import load_dotenv

load_dotenv()

class ManagerAgent:
    def __init__(self):
        self.api_key = os.getenv("LITELLM_API_KEY")
        self.base_url = os.getenv("LITELLM_BASE_URL")
        self.model = os.getenv("MANAGER_MODEL", "deepseek/deepseek-r1-distill-llama-70b")
        
        if not self.api_key:
            raise ValueError("❌ LITELLM_API_KEY не задан в .env")
        if not self.base_url:
            raise ValueError("❌ LITELLM_BASE_URL не задан в .env")

        self.base_url = self.base_url.strip()
        
        with open("prompts/manager.txt", encoding="utf-8") as f:
            self.prompt_template = f.read()

    def _ask_llm(self, prompt: str) -> dict:
        print("\n💭 [LLM ДУМАЕТ...]")
        print("-" * 50)
        
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

    def _ask_manager(self, goal: str, current_url: str, page_summary: str, history: list) -> dict:
        """
        Запрашивает у LLM план: несколько вариантов действий или сигнал завершения.
        Возвращает словарь с ключами: thought, options (list), is_done (bool)
        """
        prompt = self.prompt_template.format(
            goal=goal,
            current_url=current_url,
            history="\n".join(history[-5:]),
            page_summary=page_summary
        )

        print("\n🧠 [МЕНЕДЖЕР ДУМАЕТ...]")
        print("-" * 50)

        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    self.base_url.strip(),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3
                    },
                    timeout=300
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    print(f"🧠 Ответ менеджера:\n{content}\n")

                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start != -1 and end > start:
                        try:
                            result = json.loads(content[start:end])
                            result.setdefault("options", [])
                            result.setdefault("is_done", False)
                            print(f"✅ План получен: {len(result['options'])} вариантов, завершено: {result['is_done']}")
                            print("-" * 50)
                            return result
                        except json.JSONDecodeError as e:
                            print(f"❌ Ошибка парсинга JSON: {e}")
                else:
                    print(f"❌ API ошибка: {resp.status_code} — {resp.text[:200]}")
            except Exception as e:
                print(f"⚠️ Исключение при запросе к менеджеру: {e}")

            if attempt < 3:
                print(f"⏳ Повтор попытки {attempt + 1}...")
                time.sleep(2)

        print("🛑 Не удалось получить валидный план от менеджера.")
        print("-" * 50)
        return {}

    def run(self, goal: str):
        from agents.executor_agent import ExecutorAgent

        print(f"\n🚀 НАЧИНАЮ ВЫПОЛНЕНИЕ ЗАДАЧИ: {goal}")
        print("=" * 60)

        executor = ExecutorAgent()
        history = []
        step = 0

        while True:
            step += 1
            print(f"\n🔹 ШАГ {step}")

            # === 1. Получаем состояние страницы ===
            current_url, page_summary = self._get_page_state()
            
            # === 2. Планируем шаг ===
            plan = self._ask_manager(goal, current_url, page_summary, history)
            if not plan or plan.get("is_done"):
                self._handle_completion(plan)
                break

            options = plan.get("options", [])
            if not options:
                print("❌ Менеджер не предложил ни одного действия. Остановка.")
                break

            # === 3. Выполняем действие ===
            result, should_continue = self._execute_step(
                executor, options, goal, current_url, page_summary, history
            )
            if not should_continue:
                break

            print(f"   → Результат: {result}")
            print(f"\n⏳ Жду 2 секунды...")
            time.sleep(2)


    def _get_page_state(self):
        """Получает текущий URL и форматированный список элементов."""
        current_url = get_current_url()
        raw_elements = get_page_summary()
        page_summary = self._summarize_elements(raw_elements)
        
        print(f"🌐 Текущий URL: {current_url}")
        print(f"📄 Элементы на странице: {page_summary[:150]}...")
        return current_url, page_summary


    def _summarize_elements(self, elements):
        """Преобразует сырые элементы в человекочитаемую строку."""
        if not elements:
            return "Нет интерактивных элементов."
        parts = []
        for i, el in enumerate(elements):
            typ = "поле" if el.get("type") == "input" else "кнопка"
            text = str(el.get("text", "")).replace("\n", " ").strip()
            parts.append(f"{i}: {typ} '{text}'")
        return "; ".join(parts)


    def _handle_completion(self, plan):
        """Обрабатывает завершение задачи."""
        if not plan:
            print("🛑 Менеджер не вернул план. Остановка.")
        else:
            final_result = plan.get("final_result", "Задача успешно завершена")
            print(f"\n🎉 УСПЕХ! {final_result}")


    def _execute_step(self, executor, options, goal, current_url, page_summary, history):
        """Выбирает и выполняет одно действие, возвращает результат и флаг продолжения."""
        print(f"🧠 Менеджер предложил {len(options)} вариантов:")
        for i, opt in enumerate(options):
            action = opt.get("action", "???")
            args = opt.get("args", {})
            desc = f"{action} {args}"
            print(f"  {i}: {desc}")

        chosen_index = executor.choose_best_action(
            options=options,
            goal=goal,
            current_url=current_url,
            page_summary=page_summary
        )

        if chosen_index is None or chosen_index < 0 or chosen_index >= len(options):
            print("⚠️ Исполнитель не выбрал корректный вариант. Пропуск шага.")
            time.sleep(2)
            return "Пропущено", True

        chosen_action = options[chosen_index]
        action = chosen_action["action"]
        args = chosen_action.get("args", {})

        print(f"\n🛠️ ИСПОЛНИТЕЛЬ ВЫБРАЛ: {action} {args}")

        result = "Неизвестное действие"
        if action == "NAVIGATE":
            url = args.get("url", "").strip()
            result = navigate(url)
            history.append(f"→ перешёл на {url}")

        elif action == "CLICK":
            index = args.get("index")
            result = click_element(index)
            history.append(f"🖱️ кликнул по элементу #{index}")
            print("⏳ Ждём загрузку после клика (4 сек)...")
            time.sleep(4)

        elif action == "TYPE":
            index = args.get("index")
            text = args.get("text", "")
            result = type_text(index, text)
            history.append(f"⌨️ ввёл '{text}' в поле #{index}")

        else:
            result = f"Неизвестное действие: {action}"
            history.append(f"❓ {result}")

        return result, True