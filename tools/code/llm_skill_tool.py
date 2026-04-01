"""LLM Skill 工具

将 LLM 调用能力封装为标准工具，供 Agent 在运行时按需调用。
"""
import json
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field, PrivateAttr
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import Settings, get_settings
from models.llm import create_llm
from tools.base import BaseCustomTool, ToolResult
from tools.registry import registry


class LLMSkillInput(BaseModel):
    """LLM Skill 输入参数"""

    prompt: str = Field(..., description="需要模型完成的任务或问题")
    system_prompt: Optional[str] = Field(default=None, description="可选系统提示词")
    json_mode: bool = Field(default=False, description="是否要求模型返回 JSON 对象")
    output_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="可选 JSON Schema 风格结构定义，用于约束返回字段"
    )


class LLMSkillTool(BaseCustomTool):
    """LLM 调用工具

    适用场景：
    - 需要进行纯文本推理、总结、改写
    - 不需要访问数据库或执行 Python 代码时
    """

    name: str = "llm_skill"
    description: str = """
    调用当前配置的 LLM 完成文本类任务。

    使用场景：
    - 总结、改写、提取、分类
    - 生成解释性文本

    参数：
    - prompt: 用户任务描述
    - system_prompt: 可选系统指令
    """
    category: str = "model"
    args_schema: Type[BaseModel] = LLMSkillInput
    _settings: Settings = PrivateAttr()
    _llm: object = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._settings = get_settings()
        self._llm = create_llm(self._settings)

    def _normalize_text_content(self, content: Any) -> str:
        """将 LLM 返回内容统一转换为文本。"""
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    parts.append(str(part.get("text") or part))
                else:
                    parts.append(str(part))
            return "\n".join(parts)
        return str(content) if content is not None else ""

    def _build_json_instruction(
        self,
        prompt: str,
        json_mode: bool,
        output_schema: Optional[Dict[str, Any]],
    ) -> str:
        """为 JSON/Schema 输出构造显式指令。"""
        instructions = [prompt.strip()]
        if json_mode or output_schema:
            instructions.append("请仅返回一个合法 JSON 对象，不要输出额外说明、Markdown 或代码块。")
        if output_schema:
            schema_text = json.dumps(output_schema, ensure_ascii=False)
            instructions.append(f"输出必须满足以下结构定义：{schema_text}")
        return "\n\n".join(part for part in instructions if part)

    def _parse_json_output(self, text: str, output_schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """解析并做结构校验。"""
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"模型未返回合法 JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("模型返回的 JSON 不是对象")

        if output_schema:
            self._validate_schema(parsed, output_schema, path="$")

        return parsed

    def _validate_schema(self, value: Any, schema: Dict[str, Any], path: str) -> None:
        """按简化 JSON Schema 校验值。"""
        expected_type = schema.get("type")
        if expected_type:
            self._validate_type(value, expected_type, path)

        enum_values = schema.get("enum")
        if enum_values is not None and value not in enum_values:
            raise ValueError(f"{path} 的值 {value!r} 不在允许枚举中: {enum_values}")

        if isinstance(value, dict):
            required = schema.get("required", [])
            missing = [key for key in required if key not in value]
            if missing:
                raise ValueError(f"{path} 缺少必填字段: {', '.join(missing)}")

            properties = schema.get("properties", {})
            allowed_keys = set(properties.keys())
            if allowed_keys:
                extra_keys = [key for key in value if key not in allowed_keys]
                if extra_keys:
                    raise ValueError(f"{path} 包含未声明字段: {', '.join(extra_keys)}")

            for key, item_schema in properties.items():
                if key in value:
                    self._validate_schema(value[key], item_schema, f"{path}.{key}")

        if isinstance(value, list):
            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")
            if min_items is not None and len(value) < min_items:
                raise ValueError(f"{path} 列表长度 {len(value)} 小于最小值 {min_items}")
            if max_items is not None and len(value) > max_items:
                raise ValueError(f"{path} 列表长度 {len(value)} 大于最大值 {max_items}")

            item_schema = schema.get("items")
            if item_schema:
                for index, item in enumerate(value):
                    self._validate_schema(item, item_schema, f"{path}[{index}]")

        if isinstance(value, str):
            min_length = schema.get("minLength")
            max_length = schema.get("maxLength")
            if min_length is not None and len(value) < min_length:
                raise ValueError(f"{path} 字符串长度 {len(value)} 小于最小值 {min_length}")
            if max_length is not None and len(value) > max_length:
                raise ValueError(f"{path} 字符串长度 {len(value)} 大于最大值 {max_length}")

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = schema.get("minimum")
            maximum = schema.get("maximum")
            if minimum is not None and value < minimum:
                raise ValueError(f"{path} 数值 {value} 小于最小值 {minimum}")
            if maximum is not None and value > maximum:
                raise ValueError(f"{path} 数值 {value} 大于最大值 {maximum}")

    def _validate_type(self, value: Any, expected_type: str, path: str) -> None:
        """校验 JSON Schema 基础类型。"""
        type_validators = {
            "object": lambda item: isinstance(item, dict),
            "array": lambda item: isinstance(item, list),
            "string": lambda item: isinstance(item, str),
            "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
            "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
            "boolean": lambda item: isinstance(item, bool),
            "null": lambda item: item is None,
        }
        validator = type_validators.get(expected_type)
        if validator is None:
            raise ValueError(f"不支持的 schema 类型: {expected_type}")
        if not validator(value):
            raise ValueError(f"{path} 类型不匹配，期望 {expected_type}，实际为 {type(value).__name__}")

    def _execute(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        if not self._settings.model.api_key:
            return ToolResult(
                success=False,
                error="MODEL_API_KEY 未配置，且未检测到可兼容映射的 API Key",
                message="LLM 调用失败：请设置 MODEL_API_KEY 或 SILICONFLOW_API_KEY"
            )

        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(
                HumanMessage(
                    content=self._build_json_instruction(prompt, json_mode, output_schema)
                )
            )

            response = self._llm.invoke(messages)
            content = getattr(response, "content", "")
            text = self._normalize_text_content(content)

            if not text.strip():
                text = "LLM 调用成功，但返回了空内容。"

            data: Dict[str, Any] = {"text": text}
            if json_mode or output_schema:
                parsed = self._parse_json_output(text, output_schema)
                data = {
                    "text": text,
                    "json": parsed,
                }

            return ToolResult(
                success=True,
                data=data,
                message=text,
                metadata={
                    "provider": self._settings.model.provider,
                    "model_name": self._settings.model.model_name,
                    "json_mode": json_mode,
                    "structured": bool(output_schema),
                },
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"LLM 调用异常: {exc}",
                message=f"LLM 调用失败：{exc}",
            )


# 全局工具实例（兼容旧版导入）
llm_skill = LLMSkillTool()
registry.register(llm_skill)
