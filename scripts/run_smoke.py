"""最小烟测入口。"""

from config.settings import Settings
from agents.supervisor import create_supervisor_agent


def main() -> None:
    agent = create_supervisor_agent(Settings(), store=None)
    status = agent.get_status()
    print("Supervisor 初始化成功")
    print("中间件顺序:", status.get("middleware_order", []))


if __name__ == "__main__":
    main()
