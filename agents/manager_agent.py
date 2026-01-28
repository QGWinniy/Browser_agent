import os, json, time, requests
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

    def _ask_llm(self, prompt):
        for _ in range(3):
            try:
                resp = requests.post(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
                    timeout=60
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start != -1 and end > start:
                        return json.loads(content[start:end])
            except: pass
            time.sleep(2)
        return {}

    def run(self, goal):
        history = []
        while True:
            current_url = get_current_url()
            page_summary = get_page_summary()
            prompt = self.prompt_template.format(
                goal=goal,
                current_url=current_url,
                history="\n".join(history[-5:]),
                page_summary=page_summary
            )
            decision = self._ask_llm(prompt)
            action = decision.get("action")
            args = decision.get("args", {})

            if action == "DONE":
                print(f"\n✅ ГОТОВО: {args.get('result', 'Задача выполнена')}")
                break

            result = "Неизвестное действие"
            if action == "NAVIGATE":
                result = navigate(args.get("url", ""))
                history.append(f"→ {args.get('url')}")
            elif action == "CLICK":
                query = args.get("query", "")
                result = click_element(query)
                history.append(f"🖱️ Клик: {query}")
            elif action == "TYPE":
                query = args.get("query", "")
                text = args.get("text", "")
                result = type_text(query, text)
                history.append(f"⌨️ Ввод: '{text}' в '{query}'")
            else:
                history.append(f"❓ Неизвестное: {action}")

            print(f"⚙️ {action} → {result}")
            time.sleep(1.5)