import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(override=True)

print('=== 测试 LangChain 消息格式 ===\n')

try:
    model = ChatOpenAI(
        model="deepseek-ai/DeepSeek-V3",
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        base_url="https://api.siliconflow.cn/v1",
        temperature=0.1,
        max_tokens=100
    )
    
    print('模型初始化成功！\n')
    
    # 测试 1: 简单消息
    print('测试 1: 简单用户消息')
    response1 = model.invoke([HumanMessage(content="你好")])
    print(f'响应类型：{type(response1)}')
    print(f'响应内容长度：{len(response1.content)}\n')
    
    # 测试 2: 带系统消息
    print('测试 2: 系统消息 + 用户消息')
    response2 = model.invoke([
        SystemMessage(content="你是一个助手"),
        HumanMessage(content="请介绍你自己")
    ])
    print(f'响应类型：{type(response2)}')
    print(f'响应内容长度：{len(response2.content)}\n')
    
    print('所有测试通过！')
    
except Exception as e:
    print(f'测试失败：{e}')
    print(f'错误类型：{type(e).__name__}')
    import traceback
    traceback.print_exc()
