import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

load_dotenv(override=True)

print('=== 硅基流动 API 测试 ===\n')

try:
    model = ChatOpenAI(
        model="deepseek-ai/DeepSeek-V3",
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        base_url="https://api.siliconflow.cn/v1",
        temperature=0.7
    )
    
    print('模型初始化成功！\n')
    print('发送测试消息...\n')
    
    # 使用标准的 LangChain 消息格式
    messages = [
        HumanMessage(content="你好，请介绍一下你自己")
    ]
    
    response = model.invoke(messages)
    
    # 处理输出编码
    try:
        print(f'模型响应：{response.content}\n')
    except:
        print(f'模型响应：{response.content.encode("gbk", errors="ignore").decode()}\n')
    print('测试成功！')
    
except Exception as e:
    print(f'测试失败：{e}\n')
    print(f'错误类型：{type(e).__name__}')
