"""LLM Skill 工具测试"""
from tools.base import ToolResult
from tools.code.llm_skill_tool import LLMSkillTool


class _DummyLLM:
    def invoke(self, _messages):
        class _Resp:
            content = "mocked llm output"

        return _Resp()


class _DummyJSONLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _messages):
        class _Resp:
            pass

        response = _Resp()
        response.content = self._content
        return response


class TestLLMSkillTool:
    """测试 LLM Skill 工具"""

    def test_execute_success(self):
        tool = LLMSkillTool()
        tool._settings.model.api_key = "test-key"
        tool._llm = _DummyLLM()

        result = tool._execute(prompt="请总结这段文本")

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "mocked llm output" in result.message

    def test_execute_without_api_key(self):
        tool = LLMSkillTool()
        tool._settings.model.api_key = ""

        result = tool._execute(prompt="hello")

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "MODEL_API_KEY" in (result.error or "")

    def test_execute_with_json_mode(self):
        tool = LLMSkillTool()
        tool._settings.model.api_key = "test-key"
        tool._llm = _DummyJSONLLM('{"label": "告警", "score": 0.9}')

        result = tool._execute(prompt="请分类", json_mode=True)

        assert result.success is True
        assert result.data["json"]["label"] == "告警"
        assert result.metadata["json_mode"] is True

    def test_execute_with_output_schema(self):
        tool = LLMSkillTool()
        tool._settings.model.api_key = "test-key"
        tool._llm = _DummyJSONLLM('{"summary": "一切正常", "category": "normal"}')

        result = tool._execute(
            prompt="请总结并分类",
            json_mode=True,
            output_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "category": {"type": "string"}
                },
                "required": ["summary", "category"]
            },
        )

        assert result.success is True
        assert result.data["json"]["summary"] == "一切正常"

    def test_execute_with_invalid_schema_output(self):
        tool = LLMSkillTool()
        tool._settings.model.api_key = "test-key"
        tool._llm = _DummyJSONLLM('{"summary": "缺字段"}')

        result = tool._execute(
            prompt="请总结并分类",
            json_mode=True,
            output_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "category": {"type": "string"}
                },
                "required": ["summary", "category"]
            },
        )

        assert result.success is False
        assert "缺少必填字段" in (result.error or "")

    def test_execute_with_type_enum_and_range_validation(self):
        tool = LLMSkillTool()
        tool._settings.model.api_key = "test-key"
        tool._llm = _DummyJSONLLM('{"label": "warning", "score": 1.2, "count": "3"}')

        result = tool._execute(
            prompt="请分类并打分",
            json_mode=True,
            output_schema={
                "type": "object",
                "properties": {
                    "label": {"type": "string", "enum": ["normal", "critical"]},
                    "score": {"type": "number", "minimum": 0, "maximum": 1},
                    "count": {"type": "integer"}
                },
                "required": ["label", "score", "count"]
            },
        )

        assert result.success is False
        assert "$" in (result.error or "")

    def test_execute_with_nested_schema_validation(self):
        tool = LLMSkillTool()
        tool._settings.model.api_key = "test-key"
        tool._llm = _DummyJSONLLM('{"items": [{"name": "a", "score": 0.8}, {"name": "bb", "score": 0.6}]}')

        result = tool._execute(
            prompt="请输出列表",
            json_mode=True,
            output_schema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "minLength": 1, "maxLength": 1},
                                "score": {"type": "number", "minimum": 0, "maximum": 1}
                            },
                            "required": ["name", "score"]
                        }
                    }
                },
                "required": ["items"]
            },
        )

        assert result.success is False
        assert "$.items[1].name" in (result.error or "")
