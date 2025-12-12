"""
Supervisor Architecture - Worker Implementations

具體的 Worker 實現，這些是 Layer 4 的專家團隊。

Worker 類型：
1. Researcher: 搜索與調研專家
2. DataAnalyst: 數據分析專家
3. Writer: 內容創作專家
4. General: 通用助手

動態模型選擇：
Workers 會根據 user_context 自動選擇對應的 AI 模型。
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

# 使用新的公共模組
from src.common.prompts import get_prompt
from src.common.function_calls import get_tools_for_langchain, get_tool_executor

# 工具導入
from src.tools import get_tavily_search, is_tavily_configured, get_datetime_tool


class BaseWorker(Worker, BaseWorkerMixin):
    """
    Worker 基類
    
    提供所有 Worker 共用的功能，減少重複代碼。
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
        """根據用戶上下文獲取對應的 LLM"""
        temp = temperature if temperature is not None else self.default_temperature
        return create_llm_from_state(state, temperature=temp)
    
    def get_query(self, state: SupervisorState) -> Optional[str]:
        """獲取用戶查詢"""
        messages = state.get("messages", [])
        return self.get_original_query(state) or self.get_last_user_query(messages)
    
    def get_task_hint(self, state: SupervisorState) -> str:
        """獲取當前任務描述的提示"""
        current_step = self.get_current_task_step(state)
        if current_step:
            description = current_step.get("description", "")
            if description:
                return f"任務要求：{description}\n\n"
        return ""
    
    def log_start(self, emoji: str = "🔧") -> None:
        """記錄任務開始日誌"""
        logger.info(f"{emoji} [{self.name}] 開始執行任務")
        self._execution_count += 1


class ResearcherWorker(BaseWorker):
    """
    研究專家 Worker
    
    負責搜索和收集信息。
    支持：Web 搜索（使用 Tavily API）、閱讀和摘要、追問搜索
    """
    
    def __init__(self, search_tool=None):
        super().__init__(
            name="Researcher",
            description="搜索專家，擅長在互聯網上查找和收集信息。可以進行多輪搜索和信息整合，回答關於事實、數據、新聞等問題。",
            priority=10,
            default_temperature=0.3,
        )
        self.search_tool = search_tool
        self._tavily_configured = is_tavily_configured()
    
    async def _web_search(self, query: str) -> str:
        """執行 Web 搜索"""
        # 1. 如果有傳入的搜索工具，使用它
        if self.search_tool:
            try:
                results = await self.search_tool.ainvoke(query)
                return str(results)
            except Exception as e:
                logger.warning(f"搜索工具調用失敗: {e}")
        
        # 2. 使用 Tavily 搜索（如果已配置）
        if self._tavily_configured:
            try:
                tavily = get_tavily_search()
                return await tavily.ainvoke(query)
            except Exception as e:
                logger.warning(f"Tavily 搜索失敗: {e}")
        
        # 3. 降級方案
        logger.warning(f"🔍 [{self.name}] Tavily 未配置，使用模擬搜索")
        return f"關於 '{query}' 的搜索結果：[Tavily 未配置，請設置 TAVILY_API_KEY 環境變量以啟用聯網搜索]"
    
    async def execute(self, state: SupervisorState) -> Dict[str, Any]:
        """執行研究任務"""
        self.log_start("🔍")
        
        query = self.get_query(state)
        if not query:
            return self._create_response("沒有收到需要研究的問題。", state)
        
        try:
            # 執行搜索
            search_results = await self._web_search(query)
            
            # 使用 LLM 分析搜索結果
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
                    content="完成搜索和分析任務",
                    worker=self.name,
                ),
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] 執行失敗: {e}", exc_info=True)
            return self.create_error_response(
                worker_name=self.name,
                error_message=f"研究任務執行失敗: {str(e)}",
                state=state,
            )


class DataAnalystWorker(BaseWorker):
    """
    數據分析專家 Worker
    
    負責數據查詢和分析。
    """
    
    def __init__(self):
        super().__init__(
            name="DataAnalyst",
            description="數據分析專家，擅長查詢業務數據庫、分析銷售/庫存/用戶等業務數據趨勢、生成數據報告。【注意】不負責回答當前日期、時間等系統信息問題，這類問題請交給 General。",
            priority=10,
            default_temperature=0.1,
        )
    
    async def execute(self, state: SupervisorState) -> Dict[str, Any]:
        """執行數據分析任務"""
        self.log_start("📊")
        
        query = self.get_query(state)
        if not query:
            return self._create_response("沒有收到需要分析的數據問題。", state)
        
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
                    content="完成數據分析任務",
                    worker=self.name,
                ),
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] 執行失敗: {e}", exc_info=True)
            return self.create_error_response(
                worker_name=self.name,
                error_message=f"數據分析任務執行失敗: {str(e)}",
                state=state,
            )


class WriterWorker(BaseWorker):
    """
    文案專家 Worker
    
    負責撰寫和總結，可以整合其他 Worker 的結果生成最終報告。
    """
    
    def __init__(self):
        super().__init__(
            name="Writer",
            description="文案專家，擅長撰寫報告、總結信息、整理文檔。可以整合多個來源的信息，根據用戶語氣偏好生成結構化的最終輸出（Markdown/表格）。",
            priority=5,
            default_temperature=0.7,
        )
    
    async def execute(self, state: SupervisorState) -> Dict[str, Any]:
        """執行文案撰寫任務"""
        self.log_start("✍️")
        
        messages = state.get("messages", [])
        worker_outputs = self.get_worker_outputs(messages)
        original_query = self.get_original_query(state)
        user_context = self.get_user_context(state)
        language = user_context.get("language", "zh-CN")
        
        if not worker_outputs and not original_query:
            return self._create_response("沒有可用的信息來撰寫內容。", state)
        
        try:
            # 準備上下文信息
            context_info = ""
            if worker_outputs:
                context_info = "\n\n".join([
                    f"### {output['name']} 的輸出：\n{output['content']}"
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
                "query": original_query or "整合現有信息",
                "task_hint": self.get_task_hint(state),
                "context": context_info or "無額外信息",
                "language": "中文" if "zh" in language else "English",
            })
            
            content = result.content if hasattr(result, 'content') else str(result)
            
            return self.create_worker_response(
                worker_name=self.name,
                content=content,
                state=state,
                thinking_step=create_thinking_step(
                    step_type="reasoning",
                    content=f"完成文案撰寫任務，整合了 {len(worker_outputs)} 個信息源",
                    worker=self.name,
                ),
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] 執行失敗: {e}", exc_info=True)
            return self.create_error_response(
                worker_name=self.name,
                error_message=f"文案撰寫任務執行失敗: {str(e)}",
                state=state,
            )


class GeneralWorker(BaseWorker):
    """
    通用 Worker
    
    處理一般性的對話和任務。
    支持 Function Calling 來獲取實時信息（如當前時間）。
    如果模型不支持 tools，會自動降級到直接注入時間的方式。
    """
    
    # 工具執行器映射
    TOOL_EXECUTORS = {
        "get_current_datetime": lambda params: get_datetime_tool().invoke(params),
    }
    
    def __init__(self):
        super().__init__(
            name="General",
            description="通用助手，可以處理各種一般性的對話和任務。【重要】負責回答關於當前日期、時間、星期幾等時間相關問題。也適合處理簡單問答、閒聊、身份介紹等場景。",
            priority=1,
            default_temperature=0.5,
        )
        self._tools_supported = True
    
    def _get_tools(self) -> List[Dict[str, Any]]:
        """獲取 LangChain 格式的工具定義"""
        try:
            return get_tools_for_langchain(["get_current_datetime"])
        except Exception as e:
            logger.warning(f"[{self.name}] 獲取工具定義失敗: {e}")
            return []
    
    def _get_current_datetime_info(self, timezone: str = "Asia/Shanghai") -> str:
        """直接獲取當前時間信息（降級方案）"""
        tool = get_datetime_tool(timezone)
        response = tool.get_datetime(timezone)
        return f"今天是 {response.date} {response.weekday}，現在時間是 {response.time}（{response.timezone}）"
    
    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """執行工具調用"""
        executor = self.TOOL_EXECUTORS.get(tool_name)
        if executor:
            logger.info(f"🔧 [{self.name}] 調用工具: {tool_name}")
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
        """使用 Function Calling 執行"""
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
        
        # 處理工具調用
        if hasattr(result, 'tool_calls') and result.tool_calls:
            logger.info(f"[{self.name}] LLM 請求調用 {len(result.tool_calls)} 個工具")
            
            tool_results = []
            for tool_call in result.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})
                tool_result = await self._execute_tool(tool_name, tool_args)
                tool_results.append({"tool": tool_name, "result": tool_result})
            
            # 構建包含工具結果的消息
            from langchain_core.messages import ToolMessage
            
            tool_messages = []
            for i, tool_call in enumerate(result.tool_calls):
                tool_messages.append(ToolMessage(
                    content=tool_results[i]["result"],
                    tool_call_id=tool_call.get("id", f"tool_{i}"),
                ))
            
            # 第二次調用
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
        """不使用 Function Calling 執行（降級方案）"""
        logger.info(f"[{self.name}] 使用降級方案（直接注入時間信息）")
        
        datetime_info = self._get_current_datetime_info(timezone)
        system_prompt = get_prompt(
            "workers.general.system_with_datetime",
            datetime_info=datetime_info,
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
        """執行通用任務"""
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
            
            # 嘗試使用 Function Calling
            if self._tools_supported:
                try:
                    system_prompt = get_prompt("workers.general.system", language="{language}")
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
                        logger.warning(f"[{self.name}] 模型不支持 tools，切換到降級方案")
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
            logger.error(f"[{self.name}] 執行失敗: {e}", exc_info=True)
            return self.create_error_response(
                worker_name=self.name,
                error_message=f"處理請求時出現問題: {str(e)}",
                state=state,
            )


# Worker 類映射
WORKER_CLASSES = {
    "Researcher": ResearcherWorker,
    "DataAnalyst": DataAnalystWorker,
    "Writer": WriterWorker,
    "General": GeneralWorker,
}


def register_default_workers() -> None:
    """註冊所有默認的 Worker"""
    from src.router.agents.supervisor.registry import register_worker, get_registry
    
    registry = get_registry()
    
    if not registry.is_empty():
        logger.info("Workers 已註冊，跳過重複註冊")
        return
    
    for worker_class in WORKER_CLASSES.values():
        register_worker(worker_class())
    
    logger.info(f"已註冊 {len(WORKER_CLASSES)} 個默認 Worker")
