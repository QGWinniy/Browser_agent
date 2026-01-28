import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

class ExecutorAgent:
    def __init__(self):
        self.api_key = os.getenv("LITELLM_API_KEY")
        self.base_url = os.getenv("LITELLM_BASE_URL")
        self.model = os.getenv("EXECUTOR_MODEL", "qwen/qwen3-coder")
        
        if not self.api_key or not self.base_url:
            raise ValueError("❌ Отсутствуют LITELLM_API_KEY или LITELLM_BASE_URL в .env")
        
        with open("prompts/executor.txt", encoding="utf-8") as f:
            self.prompt_template = f.read()

    def choose_best_action(self, options: list, goal: str, current_url: str, page_summary: str) -> int:
        """
        Выбирает индекс лучшего действия из списка.
        Возвращает int или None при ошибке.
        """
        if len(options) == 1:
            return 0

        options_text = "\n".join(
            f"{i}. [{opt.get('action', 'UNKNOWN')}] {self._describe_option(opt)}"
            for i, opt in enumerate(options)
        )

        prompt = self.prompt_template.format(
            goal=goal,
            current_url=current_url,
            page_summary=page_summary[:300],
            options=options_text
        )

        for attempt in range(1, 3):
            try:
                resp = requests.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0
                    },
                    timeout=300
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start != -1 and end > start:
                        try:
                            data = json.loads(content[start:end])
                            idx = data.get("chosen_index")
                            if isinstance(idx, int) and 0 <= idx < len(options):
                                reason = data.get("reason", "")
                                print(f"✅ Исполнитель выбрал вариант {idx}: {reason}")
                                return idx
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                print(f"⚠️ Ошибка при выборе действия (попытка {attempt}): {e}")
            if attempt < 2:
                continue

        print("⚠️ Не удалось выбрать действие — использую первый вариант")
        return 0

    def _describe_option(self, opt: dict) -> str:
        action = opt.get("action", "")
        args = opt.get("args", {})
        if action == "TYPE":
            return f"Ввести текст '{args.get('text', '')}' в элемент с селектором '{args.get('query', '')}'"
        elif action == "CLICK":
            return f"Кликнуть по элементу с селектором '{args.get('query', '')}'"
        elif action == "NAVIGATE":
            return f"Перейти по URL: {args.get('url', '')}"
        else:
            return f"Выполнить действие {action} с аргументами: {args}"