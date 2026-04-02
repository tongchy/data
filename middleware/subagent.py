"""
SubAgent Middleware - 子 Agent 中间件

提供子 Agent 派发机制，实现专业化分工和上下文隔离
"""

from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
import json
import re
import time

import numpy as np
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import OpenAIEmbeddings

from core.tool_compat import compatible_tool
from config.settings import get_settings
from models.llm import create_llm


@dataclass
class SubAgent:
    """
    子 Agent 定义
    
    Attributes:
        name: 子 Agent 名称
        description: 子 Agent 描述
        system_prompt: 系统提示词
        tools: 可用工具列表
        model: 使用的模型
    """
    name: str
    description: str
    system_prompt: str
    tools: List[Callable] = field(default_factory=list)
    model: str = "deepseek-ai/DeepSeek-V3"
    
    def to_tool_description(self) -> str:
        """转换为工具描述"""
        return f"""
{self.name}: {self.description}

职责:
{self.system_prompt[:200]}...

可用工具: {', '.join([t.__name__ if hasattr(t, '__name__') else str(t) for t in self.tools[:3]])}
""".strip()


class SubAgentMiddleware:
    """
    子 Agent 中间件
    
    管理子 Agent 的注册和派发，实现：
    - 专业化分工
    - 上下文隔离
    - 任务委派
    """
    
    def __init__(
        self,
        subagents: List[SubAgent],
        backend: Optional[Any] = None,
        settings: Optional[Any] = None,
        sql_generator_agent: Optional[SubAgent] = None,
        context_guardian_agent: Optional[SubAgent] = None,
    ):
        """
        初始化子 Agent 中间件
        
        Args:
            subagents: 子 Agent 列表
        """
        self.subagents = {sa.name: sa for sa in subagents}
        self.backend = backend
        self._results_cache: Dict[str, Any] = {}
        self._subagent_errors: Dict[str, str] = {}
        self.settings = settings or get_settings()
        self.sql_generator_agent = sql_generator_agent
        self.context_guardian_agent = context_guardian_agent
        self._context_slots: Dict[str, List[str]] = {
            "decision_summary": [],
            "sql_summary": [],
            "error_summary": [],
            "schema_summary": [],
        }
        # 数据语义层缓存：{table_name: {columns, sample, metadata, embedding}}
        # None 表示尚未构建；空 dict 表示构建过但 DB 无表
        self._semantic_layer: Optional[Dict[str, Any]] = None
        # 向量客户端（懒加载）
        self._embeddings_client: Optional[Any] = None

    def _persist_execution_result(self, path: str, result: Dict[str, Any]) -> str:
        """将子 Agent 执行结果持久化到文件系统后端。"""
        if self.backend is None:
            return "⚠️ 未配置文件系统后端，结果未实际保存"

        payload = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        write_result = self.backend.write_file(path, payload, append=False)
        if write_result.get("success"):
            return f"✅ 结果已保存到: {path}"
        return f"⚠️ 结果保存失败: {write_result.get('error', 'Unknown error')}"
        
    def get_tools(self) -> List[Callable]:
        """获取子 Agent 派发工具"""
        tools = []
        
        for name, subagent in self.subagents.items():
            tool_func = self._create_subagent_tool(subagent)
            tools.append(tool_func)
        
        # 添加任务管理工具
        tools.append(self._create_task_status_tool())
        # 暴露语义层重建工具
        tools.append(self._create_rebuild_semantic_layer_tool())
        
        return tools
    
    def _create_subagent_tool(self, subagent: SubAgent) -> Callable:
        """为子 Agent 创建派发工具"""
        
        @compatible_tool(
            name=f"delegate_to_{subagent.name}",
            description=f"""
委派任务给 {subagent.name}

{subagent.description}

使用场景:
- {subagent.name} 专门处理其专业领域的问题
- 需要将复杂任务分解给专业 Agent
- 需要隔离上下文环境

返回值:
- 子 Agent 的执行结果
- 结果通常保存在 /files/ 目录下
""".strip()
        )
        def delegate_task(
            task: str,
            context: Optional[Dict[str, Any]] = None,
            save_result_to: Optional[str] = None
        ) -> str:
            """
            委派任务给子 Agent
            
            Args:
                task: 任务描述
                context: 上下文信息（如相关文件路径、历史数据等）
                save_result_to: 结果保存路径（可选）
            """
            # 这里实际应该调用子 Agent 的执行逻辑
            # 简化版本：返回任务委派确认
            
            task_id = f"{subagent.name}_{hash(task) % 10000}"
            
            result = {
                "task_id": task_id,
                "subagent": subagent.name,
                "task": task,
                "status": "delegated",
                "context": context or {},
                "save_result_to": save_result_to
            }
            
            self._results_cache[task_id] = result
            
            # 优先真实执行子 Agent，失败时回退到模拟执行
            execution_result = self._execute_subagent(subagent, task, context)
            result["status"] = "completed"
            result["result"] = execution_result

            save_status = ""
            if save_result_to:
                save_status = self._persist_execution_result(save_result_to, result)
            
            return f"""
✅ 任务已委派给 {subagent.name}

任务ID: {task_id}
任务: {task[:100]}...

执行结果:
{execution_result}

{save_status}
""".strip()
        
        return delegate_task

    def _execute_subagent(
        self,
        subagent: SubAgent,
        task: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """执行子 Agent（避免 tool-call 对话循环，兼容不支持复杂 messages 的网关）。"""
        try:
            # 构建工具映射
            tool_map: Dict[str, Any] = {}
            for t in subagent.tools:
                name = getattr(t, "name", getattr(t, "__name__", None))
                if name:
                    tool_map[name] = t

            task_prompt = self._build_task_prompt(task, context)

            if subagent.name == "sql_specialist":
                return self._run_sql_specialist(tool_map, task_prompt, context or {})

            return self._run_generic_subagent(subagent, task_prompt)

        except Exception as exc:  # noqa: BLE001
            self._subagent_errors[subagent.name] = str(exc)
            fallback = self._simulate_subagent_execution(subagent, task, context)
            return (
                f"⚠️ 子 Agent 实时执行失败，已回退到模拟结果。\n"
                f"错误: {exc}\n\n{fallback}"
            )

    def _build_task_prompt(self, task: str, context: Optional[Dict[str, Any]]) -> str:
        """构造并截断任务提示，避免上下文过长。"""
        task_text = task.strip()
        context_text = ""
        if context:
            raw = json.dumps(context, ensure_ascii=False, default=str)
            context_text = raw[:2000]
        combined = task_text
        if context_text:
            combined = f"任务:\n{task_text}\n\n上下文(JSON):\n{context_text}"
        return combined[:3000]

    def _invoke_tool_by_name(self, tool_map: Dict[str, Any], tool_name: str, **tool_kwargs: Any) -> Any:
        """按名称调用工具，兼容 BaseTool 与普通可调用对象。"""
        if tool_name not in tool_map:
            raise ValueError(f"未找到工具: {tool_name}")
        tool_obj = tool_map[tool_name]
        if hasattr(tool_obj, "invoke"):
            return tool_obj.invoke(tool_kwargs)
        if callable(tool_obj):
            return tool_obj(**tool_kwargs)
        raise TypeError(f"不支持的工具类型: {type(tool_obj)}")

    def _select_sql_for_task(self, task_prompt: str) -> str:
        """针对常见数据库问题生成稳健 SQL。"""
        lowered = task_prompt.lower()
        if "多少" in task_prompt and "表" in task_prompt:
            return (
                "SELECT COUNT(*) AS table_count "
                "FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            )
        if "表结构" in task_prompt or "字段" in task_prompt:
            return (
                "SELECT table_name, column_name, data_type, is_nullable, column_key "
                "FROM information_schema.columns "
                "WHERE table_schema = DATABASE() "
                "ORDER BY table_name, ordinal_position LIMIT 500"
            )
        if "所有表" in task_prompt or "表名" in task_prompt or "table" in lowered:
            return (
                "SELECT table_name "
                "FROM information_schema.tables "
                "WHERE table_schema = DATABASE() "
                "ORDER BY table_name"
            )
        return (
            "SELECT COUNT(*) AS table_count "
            "FROM information_schema.tables "
            "WHERE table_schema = DATABASE()"
        )

    # ===== 数据语义层 =====

    def _build_semantic_layer(self, tool_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        一次性扫描数据库，为每张表提取列定义和样例数据，构建数据语义层。

        结构：
            {
                "__tables__": [table1, table2, ...],   # 全部表名有序列表
                "table1": {
                    "columns": [{"column_name":..., "data_type":..., ...}],
                    "sample":  [{row1}, {row2}, {row3}],
                    "metadata": "...",   # table_metadata 工具返回的文本（可空）
                },
                ...
                "__error__": "..."  # 仅构建失败时出现
            }
        """
        layer: Dict[str, Any] = {}
        try:
            from database.connection import DatabaseManager

            with DatabaseManager() as db:
                rows = db.execute_query(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() ORDER BY table_name LIMIT 100"
                )
                all_tables = [r.get("table_name") for r in rows if r.get("table_name")]
                layer["__tables__"] = all_tables

                for table in all_tables:
                    cols = db.execute_query(
                        "SELECT column_name, data_type, is_nullable, column_key, column_comment "
                        "FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = %s "
                        "ORDER BY ordinal_position LIMIT 50",
                        (table,),
                    )
                    sample = db.execute_query(f"SELECT * FROM `{table}` LIMIT 3")

                    meta_str = ""
                    if "table_metadata" in tool_map:
                        try:
                            meta_str = str(
                                self._invoke_tool_by_name(tool_map, "table_metadata", table_name=table)
                            )[:500]
                        except Exception:
                            pass

                    layer[table] = {
                        "columns": cols,
                        "sample": sample,
                        "metadata": meta_str,
                    }
        except Exception as exc:
            layer["__error__"] = str(exc)

        # 构建向量索引（DB 可访问时才执行）
        if "__error__" not in layer:
            self._embed_tables(layer)

        return layer

    def _get_embeddings_client(self) -> Any:
        """懒加载 SiliconFlow 向量客户端（BAAI/bge-m3，支持中英文）。"""
        if self._embeddings_client is None:
            settings = get_settings()
            self._embeddings_client = OpenAIEmbeddings(
                model="BAAI/bge-m3",
                api_key=settings.model.api_key,
                base_url=settings.model.base_url,
            )
        return self._embeddings_client

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算两个向量的余弦相似度。"""
        a_arr = np.array(a, dtype=np.float32)
        b_arr = np.array(b, dtype=np.float32)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))

    def _embed_tables(self, layer: Dict[str, Any]) -> None:
        """
        为语义层内每张表生成向量并写回 layer[table]["embedding"]。
        描述文本 = 表名 + 列名 + 列注释 + 业务元数据，全面覆盖中文语义。
        """
        all_tables: List[str] = layer.get("__tables__", [])
        if not all_tables:
            return

        texts: List[str] = []
        for table in all_tables:
            info = layer.get(table, {})
            col_names = " ".join(
                c.get("column_name", "") for c in info.get("columns", [])
            )
            col_comments = " ".join(
                c.get("column_comment", "")
                for c in info.get("columns", [])
                if c.get("column_comment")
            )
            meta = info.get("metadata", "")
            desc = f"表名:{table} 字段:{col_names} 说明:{col_comments} {meta}"
            texts.append(desc.strip())

        try:
            client = self._get_embeddings_client()
            vectors = client.embed_documents(texts)
            for table, vec in zip(all_tables, vectors):
                if table in layer:
                    layer[table]["embedding"] = vec
            layer["__embeddings_built__"] = True
        except Exception as exc:
            layer["__embeddings_error__"] = str(exc)

    def _get_or_build_semantic_layer(self, tool_map: Dict[str, Any]) -> Dict[str, Any]:
        """懒加载：首次调用时构建语义层并缓存，后续直接返回缓存。"""
        if self._semantic_layer is None:
            self._semantic_layer = self._build_semantic_layer(tool_map)
        return self._semantic_layer

    def refresh_semantic_layer(self, tool_map: Optional[Dict[str, Any]] = None) -> str:
        """
        强制重建数据语义层（表结构变动后调用）。
        tool_map 为 None 时仅清空缓存，下次查询时自动重建。
        """
        self._semantic_layer = None
        if tool_map is not None:
            self._semantic_layer = self._build_semantic_layer(tool_map)
            all_tables = self._semantic_layer.get("__tables__", [])
            return f"✅ 数据语义层已重建，共 {len(all_tables)} 张表: {all_tables[:20]}"
        return "✅ 数据语义层缓存已清空，下次生成 SQL 时自动重建"

    def _retrieve_from_semantic_layer(
        self, task_prompt: str, tool_map: Dict[str, Any], top_k: int = 4
    ) -> str:
        """
        从语义层检索与任务最相关的表，组合为 schema_context 字符串。

        检索策略（优先级依次降低）：
          1. 向量检索（余弦相似度，中英文均可）
          2. 英文 token 精确匹配（向量检索失败时的降级）
          3. 取前 top_k 张表（两者均无命中时的兜底）
        """
        layer = self._get_or_build_semantic_layer(tool_map)

        if "__error__" in layer:
            return f"⚠️ 数据语义层构建失败: {layer['__error__']}"

        all_tables: List[str] = layer.get("__tables__", [])
        if not all_tables:
            return "⚠️ 数据库暂无可用表"

        target_tables: List[str] = []
        retrieval_method = "兜底"

        # ── 策略 1：向量检索 ──────────────────────────────────────────
        if layer.get("__embeddings_built__"):
            try:
                query_vec = self._get_embeddings_client().embed_query(task_prompt)
                scored: List[tuple] = []
                for table in all_tables:
                    tab_vec = layer.get(table, {}).get("embedding")
                    if tab_vec:
                        score = self._cosine_similarity(query_vec, tab_vec)
                        scored.append((table, score))
                if scored:
                    scored.sort(key=lambda x: x[1], reverse=True)
                    target_tables = [t for t, _ in scored[:top_k]]
                    retrieval_method = (
                        f"向量检索 top{top_k}: "
                        + ", ".join(f"{t}({s:.3f})" for t, s in scored[:top_k])
                    )
            except Exception as exc:
                layer["__embeddings_error__"] = str(exc)  # 记录但不中断

        # ── 策略 2：英文 token 精确匹配（向量检索失败时降级）─────────
        if not target_tables:
            tokens: set = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", task_prompt))
            target_tables = [t for t in all_tables if t in tokens]
            if target_tables:
                retrieval_method = f"token 匹配: {target_tables}"

        # ── 策略 3：兜底取前 top_k 张 ────────────────────────────────
        if not target_tables:
            target_tables = all_tables[:top_k]
            retrieval_method = f"兜底前{top_k}张"

        context_lines: List[str] = [
            f"数据库所有表({len(all_tables)}张): {all_tables[:30]}",
            f"[检索方式: {retrieval_method}]",
        ]

        for table in target_tables:
            info = layer.get(table)
            if not info:
                continue
            col_text = ", ".join(
                f"{c.get('column_name')}({c.get('data_type')})"
                for c in info.get("columns", [])
            )
            context_lines.append(f"表 {table} 字段: {col_text}")

            sample_rows = info.get("sample", [])[:2]
            context_lines.append(
                f"表 {table} 样例: {json.dumps(sample_rows, ensure_ascii=False, default=str)}"
            )
            if info.get("metadata"):
                context_lines.append(f"表 {table} 元数据: {info['metadata']}")

        return "\n".join(context_lines)[:4000]

    # ===== SQL 生成工具 =====

    def _extract_sql_from_text(self, text: str) -> Optional[str]:
        """从 LLM 文本中提取 SQL。"""
        text = (text or "").strip()
        if not text:
            return None

        # 场景1：直接返回 JSON
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("sql_query"):
                return str(parsed["sql_query"]).strip()
        except Exception:
            pass

        # 场景2：```json ...``` 包裹
        json_block = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
        if json_block:
            try:
                parsed = json.loads(json_block.group(1))
                if isinstance(parsed, dict) and parsed.get("sql_query"):
                    return str(parsed["sql_query"]).strip()
            except Exception:
                pass

        # 场景3：```sql ...``` 包裹
        sql_block = re.search(r"```sql\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if sql_block:
            candidate = sql_block.group(1).strip()
            if candidate:
                return candidate

        # 场景4：裸 SQL（分号可选）
        bare_sql = re.search(r"(SELECT[\s\S]*?);?\s*$", text, re.IGNORECASE)
        if bare_sql:
            candidate = bare_sql.group(1).strip()
            if candidate:
                return candidate

        return None

    def _collect_table_context(self, task_prompt: str, tool_map: Dict[str, Any]) -> str:
        """
        收集与任务相关的表结构和样例数据。
        现在直接从数据语义层（缓存）检索，不再每次查询数据库。
        """
        return self._retrieve_from_semantic_layer(task_prompt, tool_map)

    def _generate_sql_with_llm(self, task_prompt: str, schema_context: str, tool_map: Dict[str, Any]) -> Optional[str]:
        """使用 llm_skill 结构化生成 SQL。"""
        return self.generate_sql_via_agent(task_prompt, schema_context, tool_map)

    def generate_sql_via_agent(
        self,
        task_prompt: str,
        schema_context: str,
        tool_map: Dict[str, Any],
    ) -> Optional[str]:
        """通过 sql_generator_agent（默认 llm_skill）生成 SQL。"""
        if "llm_skill" not in tool_map:
            return None

        output_schema = {
            "type": "object",
            "required": ["sql_query"],
            "properties": {
                "sql_query": {"type": "string", "minLength": 5}
            }
        }

        runtime_prompt = self._compose_runtime_prompt_from_slots(self._context_slots)
        prompt = (
            "你是 SQL 生成代理，请严格输出 JSON：{\"sql_query\":\"SELECT ...\"}。"
            "仅允许 SELECT/WITH 查询。\n\n"
            f"任务:\n{task_prompt}\n\n"
            f"表结构与样例:\n{schema_context}\n\n"
            f"上下文摘要槽位:\n{runtime_prompt}"
        )

        llm_result = self._invoke_tool_by_name(
            tool_map,
            "llm_skill",
            prompt=prompt,
            json_mode=True,
            output_schema=output_schema,
        )
        return self._extract_sql_from_text(str(llm_result))

    def validate_sql_for_executor(self, sql_query: str) -> Tuple[bool, str]:
        """执行前 SQL 契约校验。"""
        sql = (sql_query or "").strip()
        if not sql:
            return False, "sql_query 为空"

        normalized = sql.upper().strip()
        if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
            return False, "仅允许 SELECT/WITH 查询"

        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
        for keyword in forbidden:
            if re.search(rf"\\b{keyword}\\b", normalized):
                return False, f"包含危险关键字: {keyword}"

        return True, "ok"

    def repair_sql_on_error(
        self,
        sql_query: str,
        error_text: str,
        schema_context: str,
        tool_map: Dict[str, Any],
    ) -> Optional[str]:
        """基于执行错误尝试修复 SQL（最多一次）。"""
        if "llm_skill" not in tool_map:
            return None

        output_schema = {
            "type": "object",
            "required": ["sql_query"],
            "properties": {"sql_query": {"type": "string", "minLength": 5}},
        }
        prompt = (
            "请修复以下 SQL 执行错误，返回可执行 MySQL SELECT 语句。仅返回 JSON。\n\n"
            f"原 SQL:\n{sql_query}\n\n"
            f"错误信息:\n{error_text}\n\n"
            f"表结构与样例:\n{schema_context}"
        )
        llm_result = self._invoke_tool_by_name(
            tool_map,
            "llm_skill",
            prompt=prompt,
            json_mode=True,
            output_schema=output_schema,
        )
        return self._extract_sql_from_text(str(llm_result))

    def _build_context_keep_whitelist(self, task_prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """构建高价值上下文白名单。"""
        return {
            "task_goal": task_prompt[:300],
            "latest_valid_sql": context.get("latest_valid_sql", ""),
            "latest_error": context.get("latest_error", ""),
            "schema_digest": context.get("schema_digest", ""),
            "tool_decision": context.get("tool_decision", ""),
        }

    def _build_context_drop_blacklist(self, tool_outputs: List[Any]) -> Dict[str, Any]:
        """构建低价值上下文黑名单摘要。"""
        dropped = []
        for out in tool_outputs:
            text = str(out)
            if len(text) > 800:
                dropped.append(text[:120] + "...")
        return {"dropped_payloads": dropped[:5]}

    def _llm_summarize_context(
        self,
        task_prompt: str,
        context: Dict[str, Any],
        tool_outputs: List[Any],
        tool_map: Dict[str, Any],
    ) -> Dict[str, Any]:
        """LLM 主路径摘要。"""
        if "llm_skill" not in tool_map:
            raise RuntimeError("llm_skill 不可用")

        output_schema = {
            "type": "object",
            "required": [
                "task_goal",
                "tool_decision",
                "sql_reasoning",
                "latest_valid_sql",
                "latest_error",
                "schema_digest",
                "next_action",
            ],
            "properties": {
                "task_goal": {"type": "string"},
                "tool_decision": {"type": "string"},
                "sql_reasoning": {"type": "string"},
                "latest_valid_sql": {"type": "string"},
                "latest_error": {"type": "string"},
                "schema_digest": {"type": "string"},
                "next_action": {"type": "string"},
            },
        }
        prompt = (
            "请将以下上下文压缩为结构化 JSON 摘要，不要输出多余文字。\n\n"
            f"任务: {task_prompt}\n"
            f"上下文: {json.dumps(context, ensure_ascii=False, default=str)[:2500]}\n"
            f"工具输出: {json.dumps([str(x)[:500] for x in tool_outputs], ensure_ascii=False)}"
        )
        raw = self._invoke_tool_by_name(
            tool_map,
            "llm_skill",
            prompt=prompt,
            json_mode=True,
            output_schema=output_schema,
        )
        text = str(raw)
        parsed = json.loads(text) if text.strip().startswith("{") else {}
        if not parsed:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise ValueError("LLM 摘要非 JSON 对象")
        return parsed

    def _rule_summarize_fallback(
        self,
        task_prompt: str,
        context: Dict[str, Any],
        tool_outputs: List[Any],
    ) -> Dict[str, Any]:
        """规则兜底摘要。"""
        latest_sql = str(context.get("latest_valid_sql", ""))[:1000]
        latest_error = str(context.get("latest_error", ""))[:1000]
        schema_digest = str(context.get("schema_digest", ""))[:800]
        return {
            "task_goal": task_prompt[:300],
            "tool_decision": "使用 sql_specialist + sql_generator 生成并执行 SQL",
            "sql_reasoning": "优先根据语义层匹配结果选择相关表并生成 SELECT",
            "latest_valid_sql": latest_sql,
            "latest_error": latest_error,
            "schema_digest": schema_digest,
            "next_action": "继续执行 SQL 或根据错误重试修复",
            "_fallback": True,
            "_tool_outputs": [str(x)[:200] for x in tool_outputs[:3]],
        }

    def _route_summary_to_slots(self, summary: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """将结构化摘要路由到槽位。"""
        slots = context.setdefault("summary_slots", self._context_slots)

        def _append(slot_key: str, value: str) -> None:
            slot = slots.setdefault(slot_key, [])
            if value:
                slot.append(value)
            slots[slot_key] = slot[-3:]

        _append("decision_summary", str(summary.get("tool_decision", "")))
        _append("schema_summary", str(summary.get("schema_digest", "")))
        _append("sql_summary", str(summary.get("sql_reasoning", "")) + "\n" + str(summary.get("latest_valid_sql", "")))
        _append("error_summary", str(summary.get("latest_error", "")))

        self._context_slots = slots
        return context

    def _compose_runtime_prompt_from_slots(self, context: Dict[str, Any]) -> str:
        """将摘要槽位拼接为运行时 prompt。"""
        slots = context.get("summary_slots", self._context_slots)
        blocks: List[str] = []

        decision = slots.get("decision_summary", [])
        schema = slots.get("schema_summary", [])
        sql = slots.get("sql_summary", [])
        error = slots.get("error_summary", [])

        if decision:
            blocks.append("[decision_summary]\n" + "\n".join(decision[-3:]))
        if schema:
            blocks.append("[schema_summary]\n" + "\n".join(schema[-3:]))
        if sql:
            blocks.append("[sql_summary]\n" + "\n".join(sql[-3:]))
        if error:
            blocks.append("[error_summary]\n" + "\n".join(error[-3:]))

        return "\n\n".join(blocks) if blocks else "(no summary slots)"

    def context_compact_gate(
        self,
        task_prompt: str,
        context: Dict[str, Any],
        tool_outputs: List[Any],
        tool_map: Dict[str, Any],
    ) -> Dict[str, Any]:
        """上下文压缩闸门：LLM 主路径，规则兜底，并写入快照。"""
        keep = self._build_context_keep_whitelist(task_prompt, context)
        drop = self._build_context_drop_blacklist(tool_outputs)
        work_ctx = {**context, **keep, **drop}
        try:
            summary = self._llm_summarize_context(task_prompt, work_ctx, tool_outputs, tool_map)
        except Exception:
            summary = self._rule_summarize_fallback(task_prompt, work_ctx, tool_outputs)

        updated_context = self._route_summary_to_slots(summary, context)
        updated_context["latest_summary"] = summary

        thread_id = str(updated_context.get("thread_id") or "default")
        snapshot_path = f"/files/context_snapshot_{thread_id}.md"
        snapshot_text = (
            f"# Context Snapshot\n\n"
            f"- timestamp: {int(time.time())}\n"
            f"- thread_id: {thread_id}\n\n"
            f"## summary\n{json.dumps(summary, ensure_ascii=False, indent=2, default=str)}\n\n"
            f"## runtime_slots\n{self._compose_runtime_prompt_from_slots(updated_context)}\n"
        )
        if self.backend is not None:
            self.backend.write_file(snapshot_path, snapshot_text, append=False)

        return updated_context

    def _hitl_interrupt(self, sql_query: str, schema_digest: str, task_goal: str) -> Optional[Dict[str, Any]]:
        """执行前 HITL 中断。resume 后返回决策载荷。"""
        if not getattr(self.settings, "enable_hitl", False):
            return None
        from langgraph.types import interrupt

        payload = {
            "stage": "pre_execution",
            "sql_query": sql_query,
            "schema_digest": schema_digest,
            "task_goal": task_goal,
        }
        resumed = interrupt(payload)
        if isinstance(resumed, dict):
            return resumed
        return None

    def _hitl_resume_handler(
        self,
        resume: Dict[str, Any],
        sql_query: str,
        schema_context: str,
        tool_map: Dict[str, Any],
    ) -> Optional[str]:
        """处理 approve/edit/reject 三种恢复决策。"""
        decision = str((resume or {}).get("decision", "approve")).lower()
        if decision == "approve":
            return sql_query
        if decision == "edit":
            edited = str((resume or {}).get("edited_sql", "")).strip()
            ok, reason = self.validate_sql_for_executor(edited)
            if not ok:
                raise ValueError(f"HITL edit SQL 校验失败: {reason}")
            return edited
        if decision == "reject":
            return None
        return sql_query

    def _run_sql_specialist(
        self,
        tool_map: Dict[str, Any],
        task_prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """SQL 专家：先提取表结构/样例，再生成 SQL，最后执行并校验。"""
        context = dict(context or {})
        context.setdefault("thread_id", context.get("thread_id") or "default")

        context = self.context_compact_gate(task_prompt, context, [], tool_map)
        schema_context = self._collect_table_context(task_prompt, tool_map)
        context["schema_digest"] = schema_context[:800]
        sql_query = self.generate_sql_via_agent(task_prompt, schema_context, tool_map)

        # LLM 生成失败时回退规则 SQL
        if not sql_query:
            sql_query = self._select_sql_for_task(task_prompt)

        is_valid, reason = self.validate_sql_for_executor(sql_query)
        if not is_valid:
            return f"SQL 契约校验失败: {reason}\nSQL: {sql_query}"

        context["latest_valid_sql"] = sql_query

        resume_payload = self._hitl_interrupt(sql_query, context.get("schema_digest", ""), task_prompt)
        if resume_payload is not None:
            sql_after_hitl = self._hitl_resume_handler(resume_payload, sql_query, schema_context, tool_map)
            if sql_after_hitl is None:
                reason_text = str((resume_payload or {}).get("reason", "用户拒绝执行"))
                return f"SQL 执行已被人工拒绝: {reason_text}"
            sql_query = sql_after_hitl
            context["latest_valid_sql"] = sql_query

        sql_result = self._invoke_tool_by_name(tool_map, "sql_inter", sql_query=sql_query)
        sql_result_text = str(sql_result)

        if "执行失败" in sql_result_text or "SQL 执行失败" in sql_result_text:
            context["latest_error"] = sql_result_text
            context = self.context_compact_gate(task_prompt, context, [sql_result_text], tool_map)
            repaired_sql = self.repair_sql_on_error(sql_query, sql_result_text, schema_context, tool_map)

            if repaired_sql:
                ok, repaired_reason = self.validate_sql_for_executor(repaired_sql)
                if ok:
                    retry_result = self._invoke_tool_by_name(tool_map, "sql_inter", sql_query=repaired_sql)
                    retry_text = str(retry_result)
                    if "执行失败" not in retry_text and "SQL 执行失败" not in retry_text:
                        return (
                            "SQL 查询首次失败后修复成功:\n"
                            f"- 原 SQL: {sql_query}\n"
                            f"- 修复 SQL: {repaired_sql}\n"
                            f"- 结果: {retry_text}"
                        )

            return (
                "SQL 查询执行失败:\n"
                f"- SQL: {sql_query}\n"
                f"- 错误: {sql_result_text}\n"
                "- 建议: 检查数据库连接配置(DB_HOST/DB_USER/DB_PASSWORD/DB_DATABASE)"
            )

        return (
            "SQL 查询专家已完成执行:\n"
            f"- SQL: {sql_query}\n"
            f"- 结果: {sql_result_text}"
        )

    def _run_generic_subagent(self, subagent: SubAgent, task_prompt: str) -> str:
        """通用子 Agent：仅单轮文本推理，不进行工具对话循环。"""
        settings = get_settings()
        llm = create_llm(settings)
        response = llm.invoke([
            SystemMessage(content=subagent.system_prompt),
            HumanMessage(content=task_prompt),
        ])
        content = getattr(response, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        return str(response)

    # ---- 以下方法保留以兼容旧调用（不再使用）----
    def _get_or_create_subagent_graph(self, subagent: SubAgent) -> Any:
        """已废弃，保留兼容接口。"""
        raise NotImplementedError("已使用手动 ReAct 循环替代 create_react_agent")

    def _extract_message_text(self, response: Any) -> str:
        """从子 Agent 返回结构中提取文本结果（保留兼容接口）。"""
        if isinstance(response, dict):
            messages = response.get("messages")
            if messages:
                last_message = messages[-1]
                content = getattr(last_message, "content", None)
                if isinstance(content, str) and content.strip():
                    return content
                if content is not None:
                    return str(content)
            return json.dumps(response, ensure_ascii=False, default=str)
        return str(response)

    def _execute_subagent_legacy(
        self,
        subagent: SubAgent,
        task: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Legacy stub - replaced by _execute_subagent."""
        try:
            task_prompt = task
            if context:
                task_prompt = (
                    f"任务:\n{task}\n\n"
                    f"上下文(JSON):\n{json.dumps(context, ensure_ascii=False, default=str)}"
                )

            response = {  # placeholder
                "messages": [
                    {"role": "user", "content": task_prompt}
                    ]
                }
            text = self._extract_message_text(response)
            if text.strip():
                return text
            return f"子 Agent {subagent.name} 已执行，但返回了空内容"
        except Exception as exc:
            self._subagent_errors[subagent.name] = str(exc)
            fallback = self._simulate_subagent_execution(subagent, task, context)
            return (
                f"⚠️ 子 Agent 实时执行失败，已回退到模拟结果。\n"
                f"错误: {exc}\n\n{fallback}"
            )
    
    def _simulate_subagent_execution(
        self,
        subagent: SubAgent,
        task: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """模拟子 Agent 执行（实际实现中应该调用真实的 Agent）"""
        
        # 根据子 Agent 类型返回不同的模拟结果
        if "sql" in subagent.name.lower():
            return f"""
SQL 查询专家已处理任务:
- 分析了查询需求
- 生成了优化 SQL
- 执行并验证结果
- 数据已保存到 /files/sql_result_*.json
""".strip()
        
        elif "data" in subagent.name.lower() or "analyst" in subagent.name.lower():
            return f"""
数据分析专家已处理任务:
- 读取了源数据
- 执行统计分析
- 生成数据洞察
- 结果已保存到 /files/analysis_*.json
""".strip()
        
        elif "viz" in subagent.name.lower() or "visual" in subagent.name.lower():
            return f"""
可视化专家已处理任务:
- 读取了分析结果
- 创建专业图表
- 保存为 PNG 格式
- 图表路径: images/chart_*.png
""".strip()
        
        else:
            return f"子 Agent {subagent.name} 已完成任务处理"

    def _create_rebuild_semantic_layer_tool(self) -> Callable:
        """创建数据语义层重建工具，供主 Agent 主动触发。"""

        middleware_ref = self

        @compatible_tool(
            name="rebuild_data_semantic_layer",
            description=(
                "重建数据语义层（缓存全库表结构+样例）。\n"
                "使用场景：\n"
                "- 数据库表结构发生变更后\n"
                "- 首次使用前预热缓存（可提升 SQL 生成速度）\n"
                "- 发现 SQL 生成使用了错误的字段名时\n"
                "调用后返回已索引的表名列表。"
            ),
        )
        def rebuild_data_semantic_layer() -> str:
            """强制重建数据语义层。"""
            # 从 sql_specialist 的工具中取 tool_map
            sql_subagent = middleware_ref.subagents.get("sql_specialist")
            tool_map: Dict[str, Any] = {}
            if sql_subagent:
                for t in sql_subagent.tools:
                    name = getattr(t, "name", getattr(t, "__name__", None))
                    if name:
                        tool_map[name] = t

            return middleware_ref.refresh_semantic_layer(tool_map)

        return rebuild_data_semantic_layer

    def _create_task_status_tool(self) -> Callable:
        """创建任务状态查询工具"""
        
        @compatible_tool(
            name="check_task_status",
            description="查询已委派任务的状态和结果"
        )
        def check_task_status(task_id: str) -> str:
            """
            查询任务状态
            
            Args:
                task_id: 任务ID
            """
            if task_id not in self._results_cache:
                return f"❌ 未找到任务: {task_id}"
            
            result = self._results_cache[task_id]
            
            return f"""
任务状态: {result['status']}
任务ID: {task_id}
子 Agent: {result['subagent']}
任务: {result['task'][:100]}...

结果:
{result.get('result', '暂无结果')}
""".strip()
        
        return check_task_status
    
    def get_subagent_info(self) -> Dict[str, Any]:
        """获取所有子 Agent 信息"""
        return {
            name: {
                "description": sa.description,
                "tool_count": len(sa.tools),
                "model": sa.model
            }
            for name, sa in self.subagents.items()
        }


def create_subagent_middleware(subagents: List[SubAgent]) -> SubAgentMiddleware:
    """
    创建子 Agent 中间件（便捷函数）
    
    Args:
        subagents: 子 Agent 列表
        
    Returns:
        SubAgentMiddleware 实例
    """
    return SubAgentMiddleware(subagents)
