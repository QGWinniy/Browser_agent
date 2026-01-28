from agents.manager_agent import ManagerAgent

if __name__ == "__main__":
    goal = input("🎯 Задача: ")
    agent = ManagerAgent()
    agent.run(goal)