"""
Supervisor Architecture - Worker Implementations

具体的 Worker 实现，这些是 Layer 4 的专家团队。

Worker 类型：
1. Researcher: 搜索与调研专家
2. DataAnalyst: 数据分析专家
3. Writer: 内容创作专家
4. General: 通用助手

动态模型选择：
Workers 会根据 user_context 自动选择对应的 AI 模型。
"""

from typing import Dict, Any, List, Optional
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseChatModel

from src.router.agents.supervisor.registry import (
    Worker, 
    WorkerType, 
    BaseWorkerMixin,
)
from src.router.agents.supervisor.state import SupervisorState, create_thinking_step
from src.router.agents.supervisor.llm_factory import create_llm_from_state
from src.server.logging_setup import logger

# 使用新的公共模组
from src.common.prompts import get_prompt
from src.common.function_calls import get_tools_for_langchain, get_tool_executor

# 工具导入
from src.tools import get_tavily_search, is_tavily_configured, get_datetime_tool

# Function Call 降级方案
from src.router.agents.supervisor.function_call import get_fallback_manager


class BaseWorker(Worker, BaseWorkerMixin):
    """
    Worker 基类
    
    提供所有 Worker 共用的功能，减少重复代码。
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        priority: int = 0,
        worker_type: WorkerType = WorkerType.LLM_POWERED,
        default_temperature: float = 0.5,
    ):
        super().__init__(
            name=name,
            description=description,
            priority=priority,
            worker_type=worker_type,
        )
        self.default_temperature = default_temperature
    
    def get_llm(self, state: SupervisorState, temperature: Optional[float] = None) -> BaseChatModel:
        """根据用户上下文获取对应的 LLM"""
        temp = temperature if temperature is not None else self.default_temperature
        return create_llm_from_state(state, temperature=temp)
    
    def get_query(self, state: SupervisorState) -> Optional[str]:
        """获取用户查询"""
        messages = state.get("messages", [])
        return self.get_original_query(state) or self.get_last_user_query(messages)
    
    def get_task_hint(self, state: SupervisorState) -> str:
        """获取当前任务描述的提示"""
        current_step = self.get_current_task_step(state)
        if current_step:
            description = current_step.get("description", "")
            if description:
                return f"任务要求：{description}\n\n"
        return ""
    
    def log_start(self, emoji: str = "🔧") -> None:
        """记录任务开始日志"""
        logger.info(f"{emoji} [{self.name}] 开始执行任务")
        self._execution_count += 1


class ResearcherWorker(BaseWorker):
    """
    研究专家 Worker
    
    负责搜索和收集信息。
    支持：Web 搜索（使用 Tavily API）、阅读和摘要、追问搜索
    """
    
    def __init__(self, search_tool=None):
        super().__init__(
            name="Researcher",
            description="搜索专家，擅长在互联网上查找和收集信息。可以进行多轮搜索和信息整合，回答关于事实、数据、新闻等问题。",
            priority=10,
            default_temperature=0.3,
        )
        self.search_tool = search_tool
        self._tavily_configured = is_tavily_configured()
    
    async def _web_search(self, query: str) -> str:
        """执行 Web 搜索"""
        # 1. 如果有传入的搜索工具，使用它
        if self.search_tool:
            try:
                results = await self.search_tool.ainvoke(query)
                return str(results)
            except Exception as e:
                logger.warning(f"搜索工具调用失败: {e}")
        
        # 2. 使用 Tavily 搜索（如果已配置）
        if self._tavily_configured:
            try:
                tavily = get_tavily_search()
                return await tavily.ainvoke(query)
            except Exception as e:
                logger.warning(f"Tavily 搜索失败: {e}")
        
        # 3. 降级方案
        logger.warning(f"🔍 [{self.name}] Tavily 未配置，使用模拟搜索")
        return f"关于 '{query}' 的搜索结果：[Tavily 未配置，请设置 TAVILY_API_KEY 环境变量以启用联网搜索]"
    
    async def execute(self, state: SupervisorState) -> Dict[str, Any]:
        """执行研究任务"""
        self.log_start("🔍")
        
        query = self.get_query(state)
        if not query:
            return self._create_response("没有收到需要研究的问题。", state)
        
        try:
            # 执行搜索
            search_results = await self._web_search(query)
            
            # 使用 LLM 分析搜索结果
            system_prompt = get_prompt("workers.researcher.system")
            human_prompt = get_prompt("workers.researcher.human")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", human_prompt),
            ])
            
            llm = self.get_llm(state)
            chain = prompt | llm
            result = await chain.ainvoke({
                "query": query,
                "task_hint": self.get_task_hint(state),
                "search_results": search_results,
            })
            
            content = result.content if hasattr(result, 'content') else str(result)
            
            return self.create_worker_response(
                worker_name=self.name,
                content=content,
                state=state,
                thinking_step=create_thinking_step(
                    step_type="reasoning",
                    content="完成搜索和分析任务",
                    worker=self.name,
                ),
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] 执行失败: {e}", exc_info=True)
            return self.create_error_response(
                worker_name=self.name,
                error_message=f"研究任务执行失败: {str(e)}",
                state=state,
            )


class DataAnalystWorker(BaseWorker):
    """
    数据分析专家 Worker
    
    负责数据查询和分析。
    """
    
    def __init__(self):
        super().__init__(
            name="DataAnalyst",
            description="数据分析专家，擅长查询业务数据库、分析销售/库存/用户等业务数据趋势、生成数据报告。【注意】不负责回答当前日期、时间等系统信息问题，这类问题请交给 General。",
            priority=10,
            default_temperature=0.1,
        )
    
    async def execute(self, state: SupervisorState) -> Dict[str, Any]:
        """执行数据分析任务"""
        self.log_start("📊")
        
        query = self.get_query(state)
        if not query:
            return self._create_response("没有收到需要分析的数据问题。", state)
        
        try:
            system_prompt = get_prompt("workers.data_analyst.system")
            human_prompt = get_prompt("workers.data_analyst.human")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", human_prompt),
            ])
            
            llm = self.get_llm(state)
            chain = prompt | llm
            result = await chain.ainvoke({
                "query": query,
                "task_hint": self.get_task_hint(state),
            })
            
            content = result.content if hasattr(result, 'content') else str(result)
            
            return self.create_worker_response(
                worker_name=self.name,
                content=content,
                state=state,
                thinking_step=create_thinking_step(
                    step_type="reasoning",
                    content="完成数据分析任务",
                    worker=self.name,
                ),
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] 执行失败: {e}", exc_info=True)
            return self.create_error_response(
                worker_name=self.name,
                error_message=f"数据分析任务执行失败: {str(e)}",
                state=state,
            )


class WriterWorker(BaseWorker):
    """
    文案专家 Worker
    
    负责撰写和总结，可以整合其他 Worker 的结果生成最终报告。
    """
    
    def __init__(self):
        super().__init__(
            name="Writer",
            description="文案专家，擅长撰写报告、总结信息、整理文档。可以整合多个来源的信息，根据用户语气偏好生成结构化的最终输出（Markdown/表格）。",
            priority=5,
            default_temperature=0.7,
        )
    
    async def execute(self, state: SupervisorState) -> Dict[str, Any]:
        """执行文案撰写任务"""
        self.log_start("✍️")
        
        messages = state.get("messages", [])
        worker_outputs = self.get_worker_outputs(messages)
        original_query = self.get_original_query(state)
        user_context = self.get_user_context(state)
        language = user_context.get("language", "zh-CN")
        
        if not worker_outputs and not original_query:
            return self._create_response("没有可用的信息来撰写内容。", state)
        
        try:
            # 准备上下文信息
            context_info = ""
            if worker_outputs:
                context_info = "\n\n".join([
                    f"### {output['name']} 的输出：\n{output['content']}"
                    for output in worker_outputs
                ])
            
            system_prompt = get_prompt("workers.writer.system", language="{language}")
            human_prompt = get_prompt("workers.writer.human")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", human_prompt),
            ])
            
            llm = self.get_llm(state)
            chain = prompt | llm
            result = await chain.ainvoke({
                "query": original_query or "整合现有信息",
                "task_hint": self.get_task_hint(state),
                "context": context_info or "无额外信息",
                "language": "中文" if "zh" in language else "English",
            })
            
            content = result.content if hasattr(result, 'content') else str(result)
            
            return self.create_worker_response(
                worker_name=self.name,
                content=content,
                state=state,
                thinking_step=create_thinking_step(
                    step_type="reasoning",
                    content=f"完成文案撰写任务，整合了 {len(worker_outputs)} 个信息源",
                    worker=self.name,
                ),
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] 执行失败: {e}", exc_info=True)
            return self.create_error_response(
                worker_name=self.name,
                error_message=f"文案撰写任务执行失败: {str(e)}",
                state=state,
            )


class GeneralWorker(BaseWorker):
    """
    通用 Worker
    
    处理一般性的对话和任务。
    支持 Function Calling 来获取实时信息（如当前时间）。
    如果模型不支持 tools，会自动降级到直接注入时间的方式。
    """
    
    # 工具执行器映射
    TOOL_EXECUTORS = {
        "get_current_datetime": lambda params: get_datetime_tool().invoke(params),
    }
    
    def __init__(self):
        super().__init__(
            name="General",
            description="通用助手，可以处理各种一般性的对话和任务。【重要】负责回答关于当前日期、时间、星期几等时间相关问题。也适合处理简单问答、闲聊、身份介绍等场景。",
            priority=1,
            default_temperature=0.5,
        )
        self._tools_supported = True
    
    def _get_tools(self) -> List[Dict[str, Any]]:
        """获取 LangChain 格式的工具定义"""
        try:
            return get_tools_for_langchain(["get_current_datetime"])
        except Exception as e:
            logger.warning(f"[{self.name}] 获取工具定义失败: {e}")
            return []
    
    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """执行工具调用"""
        executor = self.TOOL_EXECUTORS.get(tool_name)
        if executor:
            logger.info(f"🔧 [{self.name}] 调用工具: {tool_name}")
            return executor(tool_args)
        return f"未知工具: {tool_name}"
    
    async def _execute_with_tools(
        self, 
        llm: BaseChatModel, 
        prompt: ChatPromptTemplate,
        query: str,
        history_messages: List,
        language: str,
        system_prompt: str,
    ) -> str:
        """使用 Function Calling 执行"""
        tools = self._get_tools()
        if not tools:
            raise ValueError("No tools available")
        
        llm_with_tools = llm.bind_tools(tools)
        chain = prompt | llm_with_tools
        
        result = await chain.ainvoke({
            "query": query,
            "history": history_messages,
            "language": language,
        })
        
        # 处理工具调用
        if hasattr(result, 'tool_calls') and result.tool_calls:
            logger.info(f"[{self.name}] LLM 请求调用 {len(result.tool_calls)} 个工具")
            
            tool_results = []
            for tool_call in result.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_result = await self._execute_tool(tool_name, tool_args)
                tool_results.append({"tool": tool_name, "result": tool_result})
            
            # 构建包含工具结果的消息
            from langchain_core.messages import ToolMessage
            
            tool_messages = []
            for i, tool_call in enumerate(result.tool_calls):
                tool_messages.append(ToolMessage(
                    content=tool_results[i]["result"],
                    tool_call_id=tool_call.get("id", f"tool_{i}"),
                ))
            
            # 第二次调用
            final_prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{query}"),
                result,
                *tool_messages,
            ])
            
            final_chain = final_prompt | llm
            final_result = await final_chain.ainvoke({
                "query": query,
                "history": history_messages,
                "language": language,
            })
            
            return final_result.content if hasattr(final_result, 'content') else str(final_result)
        
        return result.content if hasattr(result, 'content') else str(result)
    
    async def _execute_without_tools(
        self,
        llm: BaseChatModel,
        query: str,
        history_messages: List,
        language: str,
        timezone: str,
    ) -> str:
        """
        不使用 Function Calling 执行（降级方案）
        
        根据需要的工具类型，收集相应的降级信息并注入到系统提示词中。
        当前支持：datetime（时间信息）
        未来可扩展：search（搜索能力）、data_query（数据查询）等
        """
        logger.info(f"[{self.name}] 使用降级方案（直接注入实时信息）")
        
        # 获取降级方案管理器
        fallback_manager = get_fallback_manager()
        
        # 确定需要的降级方案（根据工具列表）
        # 当前 General Worker 只需要时间信息
        required_fallbacks = ["datetime"]
        
        # 收集降级信息
        fallback_info = fallback_manager.collect_fallback_info(
            required_fallbacks,
            timezone=timezone,
        )
        
        # 构建系统提示词
        system_prompt = fallback_manager.build_system_prompt_with_fallbacks(
            base_prompt_key="workers.general.system",
            fallback_names=required_fallbacks,
            fallback_info=fallback_info,
            language=language,
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{query}"),
        ])
        
        chain = prompt | llm
        result = await chain.ainvoke({
            "query": query,
            "history": history_messages,
            "language": language,
        })
        
        return result.content if hasattr(result, 'content') else str(result)
    
    async def execute(self, state: SupervisorState) -> Dict[str, Any]:
        """执行通用任务"""
        self.log_start("💬")
        
        query = self.get_query(state)
        user_context = self.get_user_context(state)
        
        if not query:
            default_greeting = get_prompt("workers.general.default_greeting")
            return self._create_response(default_greeting, state)
        
        try:
            language = user_context.get("language", "zh-CN")
            timezone = user_context.get("timezone", "Asia/Shanghai")
            language_text = "中文" if "zh" in language else "English"
            
            messages = state.get("messages", [])
            history_messages = [
                msg for msg in messages[:-1]
                if isinstance(msg, (HumanMessage, AIMessage))
            ][-6:]
            
            llm = self.get_llm(state)
            
            # 尝试使用 Function Calling
            if self._tools_supported:
                try:
                    # 注意：这里必须传入实际的 language 值，否则 config.yaml 中的 {language}
                    # 会保留为占位符，影响模型遵循语言/风格约束。
                    system_prompt = get_prompt("workers.general.system", language=language_text)
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", system_prompt),
                        MessagesPlaceholder(variable_name="history"),
                        ("human", "{query}"),
                    ])
                    
                    content = await self._execute_with_tools(
                        llm=llm,
                        prompt=prompt,
                        query=query,
                        history_messages=history_messages,
                        language=language_text,
                        system_prompt=system_prompt,
                    )
                except Exception as e:
                    error_msg = str(e).lower()
                    if "does not support tools" in error_msg or ("tool" in error_msg and "support" in error_msg):
                        logger.warning(f"[{self.name}] 模型不支持 tools，切换到降级方案")
                        self._tools_supported = False
                        content = await self._execute_without_tools(
                            llm=llm,
                            query=query,
                            history_messages=history_messages,
                            language=language_text,
                            timezone=timezone,
                        )
                    else:
                        raise
            else:
                content = await self._execute_without_tools(
                    llm=llm,
                    query=query,
                    history_messages=history_messages,
                    language=language_text,
                    timezone=timezone,
                )
            
            return self.create_worker_response(
                worker_name=self.name,
                content=content,
                state=state,
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] 执行失败: {e}", exc_info=True)
            return self.create_error_response(
                worker_name=self.name,
                error_message=f"处理请求时出现问题: {str(e)}",
                state=state,
            )


# Worker 类映射
WORKER_CLASSES = {
    "Researcher": ResearcherWorker,
    "DataAnalyst": DataAnalystWorker,
    "Writer": WriterWorker,
    "General": GeneralWorker,
}


def register_default_workers() -> None:
    """注册所有默认的 Worker"""
    from src.router.agents.supervisor.registry import register_worker, get_registry
    
    registry = get_registry()
    
    if not registry.is_empty():
        logger.info("Workers 已注册，跳过重复注册")
        return
    
    for worker_class in WORKER_CLASSES.values():
        register_worker(worker_class())
    
    logger.info(f"已注册 {len(WORKER_CLASSES)} 个默认 Worker")
