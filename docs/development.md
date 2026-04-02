# 开发指南

## 环境搭建

### 1. 克隆仓库

```bash
git clone <repository-url>
cd data-analysis-agent
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
pip install -e ".[dev]"  # 安装开发依赖
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

关键配置项：

```bash
# 模型（SiliconFlow）
MODEL_API_KEY=your_siliconflow_api_key
MODEL_BASE_URL=https://api.siliconflow.cn/v1
MODEL_MODEL_NAME=deepseek-ai/DeepSeek-V3

# 数据库
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_DATABASE=alarm
```

## 代码规范

### 代码风格

使用 Black 格式化代码：

```bash
black .
```

### 类型检查

使用 mypy 进行类型检查：

```bash
mypy .
```

### 代码检查

使用 flake8 检查代码：

```bash
flake8 .
```

## 测试

## 启动开发服务

### 首选方式：LangGraph Dev

```bash
# 启动 LangGraph 调试服务器（推荐，提供 Web Studio）
langgraph dev
# 访问 http://localhost:2024
```

### 其他方式

```bash
# FastAPI REST 服务
python scripts/run_api.py
# 或
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 数据语义层预热（可选）

首次发送 SQL 任务时系统会自动构建向量语义层（需访问数据库 + SiliconFlow Embedding API）。
如需提前预热，可在启动后发送：
```
"请重建数据语义层"
→ Supervisor 调用 rebuild_data_semantic_layer()
```

### 运行所有测试

```bash
pytest
```

### 运行特定测试

```bash
pytest tests/unit/test_tools/
```

### 生成覆盖率报告

```bash
pytest --cov=. --cov-report=html
```

## 调试

### 启用调试日志

在 `.env` 中设置：

```env
LOG_LEVEL=DEBUG
```

### 使用 LangSmith 追踪

在 `.env` 中配置：

```env
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=data-agent-dev
```

## 提交规范

使用 Conventional Commits：

```
feat: 添加新功能
fix: 修复 bug
docs: 更新文档
style: 代码格式调整
refactor: 重构代码
test: 添加测试
chore: 构建过程或辅助工具的变动
```

## 发布流程

1. 更新版本号（`pyproject.toml`）
2. 更新 CHANGELOG
3. 创建 Git 标签
4. 构建 Docker 镜像
5. 部署到生产环境
