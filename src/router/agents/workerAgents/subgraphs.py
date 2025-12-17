"""
Supervisor Architecture - Subgraph Workers

数据分析团队子图实现。

这是一个嵌套的子图，内部包含：
- SQL Generator (编写员)：读取数据库 Schema，生成 SQL
- SQL Executor (执行员)：执行 SQL，如果报错返回给编写员
- Data Analyst (分析员)：拿到数据结果，生成人类可读的结论

自愈机制：生成 -> 执行 -> 报错 -> 反思 -> 重写 -> 执行

注意：子图目前使用环境变量配置的模型，因为子图状态不包含 user_context。
未来可考虑在子图状态中传递模型配置。
"""

from typing import TypedDict, List, Annotated, Optional, Dict, Any
import operator
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, END

from src.router.agents.supervisor.registry import SubgraphWorker
from src.router.agents.supervisor.llm_factory import create_llm_from_context
from src.server.logging_setup import logger


def _get_default_llm(temperature: float = 0.0) -> BaseChatModel:
    """
    获取预设的 LLM 实例（用于子图）
    
    子图目前不直接访问 user_context，所以使用预设配置。
    LLM Factory 会按优先顺序尝试：Customize > Qwen
    """
    return create_llm_from_context(user_context=None, temperature=temperature)


# --- 1. 定义子图状态 (DataState) ---
class DataState(TypedDict):
    """数据分析子图的状态"""
    messages: Annotated[List[BaseMessage], operator.add]
    question: str        # 原始问题
    sql_query: str       # 生成的 SQL
    query_result: str    # SQL 执行结果
    error: Optional[str] # 报错信息 (如果有)
    trials: int          # 重试次数 (防止无限循环)
    schema: str          # 数据库 Schema


# --- 2. 数据库连接工具（可替换为真实实现） ---
class MockDatabase:
    """
    模拟数据库连接
    
    在实际项目中，请替换为真实的数据库连接。
    支持：SQLite、PostgreSQL、MySQL 等。
    """
    
    def __init__(self):
        self._schema = """
-- 示例 Schema (请替换为真实的数据库 Schema)
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(200),
    created_at TIMESTAMP
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    product_name VARCHAR(200),
    amount DECIMAL(10,2),
    status VARCHAR(50),
    created_at TIMESTAMP
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200),
    price DECIMAL(10,2),
    stock INTEGER,
    category VARCHAR(100)
);
"""
    
    def get_table_info(self) -> str:
        """获取数据库 Schema 信息"""
        return self._schema
    
    def run(self, query: str) -> str:
        """
        执行 SQL 查询
        
        在实际项目中，这里应该连接真实数据库执行查询。
        """
        # 模拟执行结果
        logger.info(f"📊 [MockDB] 执行 SQL: {query[:100]}...")
        
        # 简单的模拟：根据 SQL 类型返回不同结果
        query_lower = query.lower().strip()
        
        if "select" in query_lower:
            if "count" in query_lower:
                return "查询结果: count = 1250"
            elif "sum" in query_lower:
                return "查询结果: sum = 125000.00"
            else:
                return """查询结果:
| id | name | value |
|----|------|-------|
| 1  | A    | 100   |
| 2  | B    | 200   |
| 3  | C    | 150   |
(示例数据，请接入真实数据库)"""
        
        return "查询执行成功（无返回数据）"


# 全局数据库实例（可替换为真实连接）
_db_instance = None

def get_db():
    """获取数据库实例"""
    global _db_instance
    if _db_instance is None:
        # TODO: 在实际项目中，替换为真实的数据库连接
        # 例如：
        # from langchain_community.utilities import SQLDatabase
        # _db_instance = SQLDatabase.from_uri(os.getenv("DATABASE_URL"))
        _db_instance = MockDatabase()
    return _db_instance


# --- 3. 节点逻辑 ---

def generate_sql_node(state: DataState) -> Dict[str, Any]:
    """
    节点 A: SQL 编写员 (Generator)
    
    读取数据库 Schema，生成 SQL 查询。
    如果上一次执行有错误，会根据错误信息修正 SQL。
    """
    question = state["question"]
    error = state.get("error")
    schema = state.get("schema", "")
    
    # 如果没有 Schema，获取它
    if not schema:
        db = get_db()
        schema = db.get_table_info()
    
    # 使用 LLM Factory 获取模型（按优先顺序：Customize > Qwen）
    llm = _get_default_llm(temperature=0)
    
    # 动态 Prompt：如果有错，要把错误信息加进去
    system_msg = f"""你是一个 SQL 专家。请根据以下表结构编写 SQL 查询。

Schema:
{schema}

注意：
1. 只返回 SQL 语句，不要 Markdown 格式，不要 ```sql ... ```
2. 使用标准 SQL 语法
3. 确保 SQL 语句可以直接执行
"""
    
    if error:
        system_msg += f"\n\n⚠️ 上一次执行报错: {error}\n请根据错误信息修正你的 SQL。"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("human", "{question}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"question": question})
    
    # 清洗 SQL (去掉可能的 markdown 符号)
    sql = response.content.replace("```sql", "").replace("```", "").strip()
    
    logger.info(f"📝 [SQL Generator] 生成 SQL: {sql[:100]}...")
    
    return {
        "sql_query": sql,
        "trials": state.get("trials", 0) + 1,
        "error": None,  # 重置错误
        "schema": schema,
    }


def execute_sql_node(state: DataState) -> Dict[str, Any]:
    """
    节点 B: SQL 执行员 (Executor)
    
    执行 SQL 查询。如果报错，将错误信息返回给编写员。
    """
    db = get_db()
    query = state["sql_query"]
    
    logger.info(f"⚡ [SQL Executor] 执行 SQL...")
    
    try:
        # 执行 SQL
        result = db.run(query)
        return {"query_result": result, "error": None}
    except Exception as e:
        # 捕获错误，不抛出异常，而是存入 State 供下一步反思
        logger.warning(f"[SQL Executor] 执行失败: {e}")
        return {"query_result": "", "error": str(e)}


def analyze_result_node(state: DataState) -> Dict[str, Any]:
    """
    节点 C: 数据分析师 (Analyst)
    
    分析查询结果，生成人类可读的结论。
    """
    result = state["query_result"]
    question = state["question"]
    
    # 使用 LLM Factory 获取模型
    llm = _get_default_llm(temperature=0.3)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个专业的数据分析师。
请根据数据库查询结果，用清晰、专业的语言回答用户问题。

输出格式：
## 数据结果
简要说明查询结果

## 分析结论
基于数据的分析结论

## 建议
如果适用，提供基于数据的建议"""),
        ("human", "用户问题: {question}\n\n数据库查询结果:\n{result}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"question": question, "result": result})
    
    logger.info(f"📊 [Data Analyst] 分析完成")
    
    # 将最终结果包装成 AIMessage 返回给父图 (Supervisor)
    return {"messages": [AIMessage(content=response.content, name="DataTeam")]}


def give_up_node(state: DataState) -> Dict[str, Any]:
    """
    放弃节点
    
    当多次重试都失败时，返回错误信息。
    """
    error = state.get("error", "未知错误")
    trials = state.get("trials", 0)
    
    content = f"""## 数据查询失败

很抱歉，经过 {trials} 次尝试，我无法成功执行数据库查询。

### 错误信息
{error}

### 可能的原因
1. 查询条件不满足数据库约束
2. 相关数据表或字段不存在
3. 数据库连接问题

### 建议
请检查您的问题描述，或联系数据库管理员确认表结构。"""
    
    logger.warning(f"[DataTeam] 放弃查询，错误: {error}")
    
    return {"messages": [AIMessage(content=content, name="DataTeam")]}


# --- 4. 路由逻辑 (Check SQL Execution) ---

def check_execution(state: DataState) -> str:
    """
    决定下一步去哪
    
    - 如果有错且未超过重试次数 -> 重写 SQL
    - 如果有错且超过重试次数 -> 放弃
    - 如果没错 -> 分析结果
    """
    max_trials = 3
    
    if state.get("error"):
        if state.get("trials", 0) >= max_trials:
            return "give_up"  # 尝试多次还不行，放弃
        return "retry"  # 有错，且没超次 -> 重写
    return "success"  # 没错 -> 分析


# --- 5. 构建子图 ---

def build_data_subgraph():
    """
    构建数据分析子图
    
    工作流程：
    1. generate_sql: 生成 SQL
    2. execute_sql: 执行 SQL
    3. 检查执行结果：
       - 成功 -> analyze_data
       - 失败 -> retry (回到 generate_sql) 或 give_up
    4. analyze_data: 分析结果
    """
    workflow = StateGraph(DataState)
    
    # 添加节点
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("analyze_data", analyze_result_node)
    workflow.add_node("give_up", give_up_node)
    
    # 设置入口点
    workflow.set_entry_point("generate_sql")
    
    # 添加边
    workflow.add_edge("generate_sql", "execute_sql")
    
    # 条件边：执行完 SQL 后，看是否有错
    workflow.add_conditional_edges(
        "execute_sql",
        check_execution,
        {
            "retry": "generate_sql",   # 回退重写
            "success": "analyze_data", # 继续分析
            "give_up": "give_up"       # 放弃
        }
    )
    
    # 终止边
    workflow.add_edge("analyze_data", END)
    workflow.add_edge("give_up", END)
    
    return workflow.compile()


# --- 6. DataTeam Worker 实现 ---

class DataTeamWorker(SubgraphWorker):
    """
    数据分析团队 Worker
    
    这是一个子图 Worker，内部包含：
    - SQL Generator: 生成 SQL
    - SQL Executor: 执行 SQL
    - Data Analyst: 分析结果
    
    支持自愈机制：生成 -> 执行 -> 报错 -> 反思 -> 重写 -> 执行
    """
    
    def __init__(self):
        super().__init__(
            name="DataTeam",
            description="数据分析团队，专门用于查询业务数据库（如销售、订单、库存、用户数据），执行SQL并分析结果。【注意】不负责回答当前日期、时间、天气等系统信息问题，这类问题请交给General。",
            priority=15,  # 较高优先级
        )
    
    def build_subgraph(self):
        """构建数据分析子图"""
        return build_data_subgraph()
    
    def prepare_subgraph_input(self, state) -> Dict[str, Any]:
        """
        准备子图输入
        
        从父状态中提取问题信息。
        """
        from src.router.agents.supervisor.registry import BaseWorkerMixin
        
        messages = state.get("messages", [])
        
        # 优先使用原始查询
        question = state.get("original_query", "")
        
        # 如果没有原始查询，从消息中提取
        if not question:
            question = BaseWorkerMixin.get_last_user_query(messages) or ""
        
        # 获取当前任务步骤的描述
        current_step = BaseWorkerMixin.get_current_task_step(state)
        if current_step:
            task_description = current_step.get("description", "")
            if task_description:
                question = f"{question}\n\n具体任务：{task_description}"
        
        logger.info(f"[DataTeam] 准备子图输入，问题: {question[:100]}...")
        
        return {
            "messages": [],
            "question": question,
            "sql_query": "",
            "query_result": "",
            "error": None,
            "trials": 0,
            "schema": "",
        }
    
    def process_subgraph_output(
        self, 
        result: Dict[str, Any], 
        parent_state
    ) -> Dict[str, Any]:
        """
        处理子图输出
        
        将子图的输出转换为父图格式，并更新任务进度。
        """
        from src.router.agents.supervisor.state import TaskStatus
        
        # 获取子图的消息输出
        messages = result.get("messages", [])
        if not messages:
            messages = [AIMessage(
                content="数据分析完成，但没有生成报告。",
                name=self.name
            )]
        
        output = {
            "messages": messages,
            "current_worker": self.name,
        }
        
        # 更新任务步骤状态
        task_plan = parent_state.get("task_plan", [])
        current_index = parent_state.get("current_step_index", 0)
        if 0 <= current_index < len(task_plan):
            # 检查是否有错误
            if result.get("error"):
                task_plan[current_index]["status"] = TaskStatus.FAILED
                task_plan[current_index]["error"] = result.get("error")
            else:
                task_plan[current_index]["status"] = TaskStatus.COMPLETED
                # 保存结果摘要
                if messages:
                    content = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
                    task_plan[current_index]["result"] = content[:200] + "..." if len(content) > 200 else content
            
            output["task_plan"] = task_plan
            output["current_step_index"] = current_index + 1
        
        return output


# 导出
__all__ = [
    "DataTeamWorker",
    "build_data_subgraph",
    "get_db",
    "MockDatabase",
]
