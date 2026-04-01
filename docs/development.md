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
