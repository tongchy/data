import sys

packages = {
    'langgraph': 'langgraph',
    'langchain-core': 'langchain_core',
    'langchain-deepseek': 'langchain_deepseek',
    'python-dotenv': 'dotenv',
    'langsmith': 'langsmith',
    'pydantic': 'pydantic',
    'matplotlib': 'matplotlib',
    'seaborn': 'seaborn',
    'pandas': 'pandas',
    'IPython': 'IPython',
    'langchain_mcp_adapters': 'langchain_mcp_adapters',
    'uv': 'uv',
    'pymysql': 'pymysql'
}

print('=== 环境检查结果 ===\n')
all_installed = True

for package_name, import_name in packages.items():
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', '已安装')
        print(f'[OK] {package_name}: {version}')
    except ImportError as e:
        print(f'[FAIL] {package_name}: 未安装或导入失败')
        all_installed = False

print()
if all_installed:
    print('所有依赖包已成功安装！')
else:
    print('部分依赖包未正确安装')
