"""
测试 LangGraph 服务
"""
import asyncio
import httpx


async def test_service():
    """测试服务是否正常运行"""
    base_url = "http://127.0.0.1:2024"
    
    async with httpx.AsyncClient() as client:
        # 测试健康检查
        print("1. 测试健康检查...")
        try:
            response = await client.get(f"{base_url}/ok")
            print(f"   [OK] 服务正常: {response.text}")
        except Exception as e:
            print(f"   [FAIL] 健康检查失败: {e}")
            return
        
        # 获取 assistants
        print("\n2. 获取 assistants...")
        try:
            response = await client.get(f"{base_url}/assistants")
            assistants = response.json()
            print(f"   [OK] 找到 {len(assistants)} 个 assistant")
            for a in assistants:
                print(f"     - {a.get('graph_id', 'unknown')}")
        except Exception as e:
            print(f"   [FAIL] 获取 assistants 失败: {e}")
        
        # 尝试运行一个 stateless run
        print("\n3. 测试运行 agent...")
        try:
            response = await client.post(
                f"{base_url}/runs",
                json={
                    "assistant_id": "data_agent",
                    "input": {
                        "messages": [
                            {"role": "user", "content": "你好"}
                        ]
                    }
                },
                timeout=30.0
            )
            result = response.json()
            print(f"   [OK] 运行成功")
            print(f"     响应: {result}")
        except Exception as e:
            print(f"   [FAIL] 运行失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_service())
