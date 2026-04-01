# langgraph.json 配置说明

> `langgraph.json` 是 LangGraph CLI / LangGraph Studio 的项目配置文件。
> **JSON 格式本身不支持注释**，因此本文件作为独立的注释说明文档。

## 原始内容

```json
{
  "dependencies": [" ./"],
  "graphs":{
    "data_agent": "./graph.py:graph"
  },
  "env": ".env"
}
```

## 字段说明

| 字段 | 值 | 含义 |
|------|------|------|
| `dependencies` | `[" ./"]` | 项目依赖路径，`"./"` 表示将当前目录整体作为 Python 包安装，LangGraph Studio 启动时会自动 pip install 该路径下的依赖 |
| `graphs` | `{"data_agent": "./graph.py:graph"}` | 注册 Agent 图的映射表：键 `data_agent` 是图的名称（API 端点名），值 `./graph.py:graph` 表示从 `graph.py` 文件中导出名为 `graph` 的变量（即 `create_react_agent` 创建的 LangGraph 对象） |
| `env` | `".env"` | 指定环境变量文件路径，LangGraph Studio/CLI 启动时会自动加载该文件中的变量 |

## 调用方式

启动 LangGraph Studio 后，可通过如下方式调用 Agent：

```
POST /data_agent/invoke
{
  "input": {"messages": [{"role": "user", "content": "查询用户表中的数据"}]}
}
```
