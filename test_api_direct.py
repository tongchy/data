import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
from dotenv import load_dotenv

load_dotenv(override=True)

print('=== 硅基流动 API 直接测试 ===\n', flush=True)

api_key = os.getenv("SILICONFLOW_API_KEY")
print(f'API Key: {api_key[:20]}...\n', flush=True)

try:
    from openai import OpenAI
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.siliconflow.cn/v1"
    )
    
    print('客户端初始化成功！\n', flush=True)
    print('发送请求...\n', flush=True)
    
    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3",
        messages=[
            {"role": "user", "content": "你好"}
        ],
        max_tokens=50
    )
    
    print(f'响应成功！\n', flush=True)
    print(f'内容：{response.choices[0].message.content}\n', flush=True)
    
except Exception as e:
    print(f'错误：{e}\n', flush=True)
    print(f'错误类型：{type(e).__name__}\n', flush=True)
