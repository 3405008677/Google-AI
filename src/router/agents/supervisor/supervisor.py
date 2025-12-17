"""
Supervisor Architecture - Supervisor Node

Supervisor 节点负责：
1. 任务规划：分析复杂指令，分解为多个步骤
2. 决策路由：决定下一步应该由哪个 Worker 执行
3. 进度追踪：监控任务执行进度，决定是否结束

动态模型选择：
Supervisor 会根据 user_context 自动选择对应的 AI 模型：
- Customize 路由 → 使用 SELF_MODEL_* 配置
- Qwen 路由 → 使用 QWEN_* 配置
- 预设 → 按顺序尝试可用的模型
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field
from src.router.agents.supervisor.state import (
    SupervisorState, 
    MAX_ITERATIONS,
    MAX_TASK_STEPS,
    TaskStep,
    TaskStatus,
    ThinkingStep,
    create_thinking_step,
    create_task_step,
)
from src.router.agents.supervisor.registry import get_registry
from src.router.agents.supervisor.llm_factory import create_llm_from_state
from src.server.logging_setup import logger
from src.common.prompts import get_prompt


class TaskPlan(BaseModel):
    """
    任务规划结果
    
    Supervisor 分析用户请求后，生成的任务规划。
    """
    steps: List[Dict[str, str]] = Field(
        default_factory=list,
        description="任务步骤列表，每个步骤包含 worker（执行者）和 description（描述）"
    )
    reasoning: str = Field(
        default="",
        description="规划理由"
    )


class RouteDecision(BaseModel):
    """
    Supervisor 的路由决策结果
    
    使用 Pydantic 模型确保 LLM 只能返回预定义的路由选项。
    """
    next: str = Field(
        ...,
        description="下一个要执行的角色名称，如果任务完成则选择 FINISH"
    )
    reasoning: str = Field(
        default="",
        description="决策理由（用于调试和流式输出）"
    )
    should_replan: bool = Field(
        default=False,
        description="是否需要重新规划任务（当当前计划不足以完成任务时）"
    )


@dataclass
class SupervisorConfig:
    """
    Supervisor 配置类
    
    注意：模型选择已改为动态方式，从 user_context 中读取。
    这里只保留 Supervisor 行为相关的配置。
    """
    temperature: float = 0.0  # Supervisor 使用低温度以确保决策稳定
    max_iterations: int = MAX_ITERATIONS
    max_task_steps: int = MAX_TASK_STEPS
    enable_planning: bool = True  # 是否启用任务规划
    
    def validate(self) -> None:
        """验证配置（模型配置已移至 llm_factory）"""
        pass


# 提示词现在从配置文件读取：src/common/prompts/config.yaml
# 使用 get_prompt("supervisor.planning") 和 get_prompt("supervisor.routing") 获取


def _build_planning_prompt(worker_list: str, max_steps: int) -> ChatPromptTemplate:
    """构建任务规划 Prompt（从配置文件读取）"""
    # 从配置文件获取提示词，支持模板变量
    system_prompt = get_prompt(
        "supervisor.planning",
        worker_list=worker_list,
        max_steps=max_steps,
    )
    
    # 获取规划完成提示词
    planning_complete = get_prompt(
        "supervisor.planning_complete",
        default='请分析用户的请求，制定一个执行计划。返回 JSON 格式：{{"steps": [{{"worker": "专家名称", "description": "任务描述"}}], "reasoning": "规划理由"}}'
    )
    
    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        ("system", planning_complete),
    ])


def _build_routing_prompt(
    worker_list: str, 
    worker_names: list,
    task_plan: str,
    completed_steps: int,
    total_steps: int,
) -> ChatPromptTemplate:
    """构建路由决策 Prompt（从配置文件读取）"""
    # 从配置文件获取提示词，支持模板变量
    system_prompt = get_prompt(
        "supervisor.routing",
        worker_list=worker_list,
        worker_options=', '.join(worker_names),
        task_plan=task_plan,
        completed_steps=completed_steps,
        total_steps=total_steps,
    )
    
    # 获取路由决策提示词
    routing_decision = get_prompt(
        "supervisor.routing_decision",
        default="根据以上对话历史和任务进度，请做出你的决策：下一步交给哪个专家？或者任务是否已经完成？"
    )
    
    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        ("system", routing_decision),
    ])


def _get_llm_from_state(state: SupervisorState, temperature: float = 0.0) -> BaseChatModel:
    """
    从状态中获取 LLM 实例
    
    根据 user_context 动态选择对应的模型。
    Supervisor 使用较低温度以确保决策稳定。
    """
    import os
    # 清理与 httpx SSL 验证冲突的环境变量
    for _var in ("SSL_CERT_FILE", "SSL_KEY_FILE"):
        if _var in os.environ:
            del os.environ[_var]
    
    return create_llm_from_state(state, temperature=temperature)


def _format_task_plan(task_plan: List[TaskStep]) -> str:
    """格式化任务计划为字符串"""
    if not task_plan:
        return "无任务计划"
    
    lines = []
    for i, step in enumerate(task_plan):
        status_emoji = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.SKIPPED: "⏭️",
        }.get(step.get("status", TaskStatus.PENDING), "⏳")
        
        lines.append(f"{i+1}. [{status_emoji}] {step.get('worker', 'Unknown')}: {step.get('description', 'No description')}")
    
    return "\n".join(lines)


def create_supervisor_node(
    config: Optional[SupervisorConfig] = None,
    llm: Optional[BaseChatModel] = None,
) -> Callable[[SupervisorState], Dict[str, Any]]:
    """
    创建 Supervisor 节点
    
    Supervisor 使用 LLM 来分析当前状态，决定下一步应该：
    1. 制定任务规划（如果还没有规划）
    2. 交给哪个 Worker 处理
    3. 或者结束任务（FINISH）
    
    动态模型选择：
    LLM 会根据 state["user_context"] 动态选择对应的模型。
    这允许不同路由（Customize、Qwen、Gemini）使用各自配置的模型。
    
    Args:
        config: Supervisor 配置，如果为 None 则使用默认配置
        llm: 可选的 LLM 实例，用于测试时注入 mock（覆盖动态选择）
    
    Returns:
        一个异步函数，接受 SupervisorState 并返回更新后的状态
    """
    if config is None:
        config = SupervisorConfig()
    config.validate()
    
    # 如果提供了 llm（用于测试），则使用它；否则会在每次请求时根据 state 动态创建
    _fixed_llm = llm
    
    async def _plan_task(state: SupervisorState, registry) -> Dict[str, Any]:
        """
        任务规划阶段
        
        分析用户请求，分解为多个执行步骤。
        """
        logger.info("📋 [Supervisor] 开始任务规划...")
        
        # 根据用户上下文动态获取 LLM
        llm = _fixed_llm or _get_llm_from_state(state, temperature=config.temperature)
        
        worker_list = registry.get_formatted_descriptions()
        prompt = _build_planning_prompt(worker_list, config.max_task_steps)
        
        try:
            planning_chain = prompt | llm.with_structured_output(TaskPlan)
            result = await planning_chain.ainvoke({"messages": state.get("messages", [])})
            
            if isinstance(result, TaskPlan):
                # 转换为 TaskStep 列表
                task_plan = []
                for i, step in enumerate(result.steps):
                    # 清理 Worker 名称，移除可能的类型标记（如 "Researcher [llm_powered]" -> "Researcher"）
                    worker_name = step.get("worker", "General")
                    if "[" in worker_name:
                        worker_name = worker_name.split("[")[0].strip()
                    
                    task_step = create_task_step(
                        step_id=f"step_{i+1}",
                        worker=worker_name,
                        description=step.get("description", ""),
                    )
                    task_plan.append(task_step)
                
                # 记录思考步骤
                thinking_step = create_thinking_step(
                    step_type="planning",
                    content=f"任务规划完成：{result.reasoning}\n计划步骤：{len(task_plan)} 个",
                )
                
                logger.info(f"📋 [Supervisor] 任务规划完成，共 {len(task_plan)} 个步骤")
                
                return {
                    "task_plan": task_plan,
                    "current_step_index": 0,
                    "original_query": state.get("messages", [{}])[0].content if state.get("messages") else "",
                    "thinking_steps": state.get("thinking_steps", []) + [thinking_step],
                }
            
        except Exception as e:
            logger.warning(f"任务规划失败，使用默认单步计划: {e}")
        
        # 降级：创建单步计划
        default_step = create_task_step(
            step_id="step_1",
            worker="General",
            description="处理用户请求",
        )
        return {
            "task_plan": [default_step],
            "current_step_index": 0,
        }
    
    async def _route_decision(state: SupervisorState, registry) -> Dict[str, Any]:
        """
        路由决策阶段
        
        根据任务计划和当前进度，决定下一步动作。
        
        优化策略：
        1. 快速路径：单步任务完成后直接结束，不调用 LLM
        2. 进度检查：所有步骤完成后直接结束
        3. 顺序执行：按计划顺序执行，减少 LLM 调用
        """
        task_plan = state.get("task_plan", [])
        current_step_index = state.get("current_step_index", 0)
        
        # 计算完成进度
        completed_steps = sum(
            1 for step in task_plan 
            if step.get("status") in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]
        )
        total_steps = len(task_plan)
        
        # ===== 快速路径 1：所有步骤都已完成 =====
        if completed_steps >= total_steps and total_steps > 0:
            logger.info("🎯 [Supervisor] 所有任务步骤已完成，决策: FINISH")
            thinking_step = create_thinking_step(
                step_type="decision",
                content="所有任务步骤已完成，准备结束流程",
            )
            return {
                "next": "FINISH",
                "thinking_steps": state.get("thinking_steps", []) + [thinking_step],
            }
        
        # ===== 快速路径 2：单步简单任务，Worker 已回复，直接结束 =====
        # 检查是否有 Worker 已经给出了回复
        messages = state.get("messages", [])
        has_ai_response = any(
            hasattr(msg, 'name') and msg.name in registry.get_names()
            for msg in messages
            if hasattr(msg, 'content') and msg.content
        )
        
        if total_steps == 1 and completed_steps == 0 and has_ai_response:
            # 单步任务，且有 Worker 回复，直接结束
            logger.info("🎯 [Supervisor] 单步任务已有回复，决策: FINISH")
            thinking_step = create_thinking_step(
                step_type="decision",
                content="单步任务已完成，准备结束流程",
            )
            return {
                "next": "FINISH",
                "thinking_steps": state.get("thinking_steps", []) + [thinking_step],
            }
        
        # ===== 快速路径 3：按任务计划顺序执行（不调用 LLM）=====
        worker_names = registry.get_names()
        worker_names_lower = {name.lower(): name for name in worker_names}
        
        # 找到下一个未完成的步骤
        for i, step in enumerate(task_plan):
            step_status = step.get("status")
            # 处理 status 可能是字符串或枚举的情况
            if isinstance(step_status, str):
                is_completed = step_status in ["completed", "skipped", "failed"]
            else:
                is_completed = step_status in [TaskStatus.COMPLETED, TaskStatus.SKIPPED, TaskStatus.FAILED]
            
            if not is_completed:
                next_worker = step.get("worker", "General")
                # 处理 LLM 可能返回带有类型标记的 Worker 名称，如 "Researcher [llm_powered]"
                if "[" in next_worker:
                    next_worker = next_worker.split("[")[0].strip()
                # 尝试精确匹配
                if next_worker in worker_names:
                    logger.info(f"🎯 [Supervisor] 按计划执行步骤 {i+1}: {next_worker}")
                    thinking_step = create_thinking_step(
                        step_type="decision",
                        content=f"按计划执行: {step.get('description', '处理任务')}",
                    )
                    return {
                        "next": next_worker,
                        "thinking_steps": state.get("thinking_steps", []) + [thinking_step],
                    }
                # 尝试不区分大小写匹配
                elif next_worker.lower() in worker_names_lower:
                    actual_worker = worker_names_lower[next_worker.lower()]
                    logger.info(f"🎯 [Supervisor] 按计划执行步骤 {i+1}: {actual_worker} (原名: {next_worker})")
                    thinking_step = create_thinking_step(
                        step_type="decision",
                        content=f"按计划执行: {step.get('description', '处理任务')}",
                    )
                    return {
                        "next": actual_worker,
                        "thinking_steps": state.get("thinking_steps", []) + [thinking_step],
                    }
                else:
                    # Worker 名称无效，使用 General 作为备选
                    logger.warning(f"计划中的 Worker '{next_worker}' 不存在，使用 General 代替")
                    if "General" in worker_names:
                        thinking_step = create_thinking_step(
                            step_type="decision",
                            content=f"按计划执行: {step.get('description', '处理任务')}（使用 General 代替）",
                        )
                        return {
                            "next": "General",
                            "thinking_steps": state.get("thinking_steps", []) + [thinking_step],
                        }
        
        # ===== 如果上述快速路径都不满足，才调用 LLM 决策 =====
        # （这种情况应该很少发生，主要用于复杂的多步骤任务）
        worker_list = registry.get_formatted_descriptions()
        
        task_plan_str = _format_task_plan(task_plan)
        prompt = _build_routing_prompt(
            worker_list=worker_list,
            worker_names=worker_names,
            task_plan=task_plan_str,
            completed_steps=completed_steps,
            total_steps=total_steps,
        )
        
        try:
            llm = _fixed_llm or _get_llm_from_state(state, temperature=config.temperature)
            routing_chain = prompt | llm.with_structured_output(RouteDecision)
            result = await routing_chain.ainvoke({"messages": state.get("messages", [])})
            
            if isinstance(result, RouteDecision):
                next_action = result.next
                reasoning = result.reasoning
                
                valid_options = ["FINISH"] + worker_names
                if next_action not in valid_options:
                    logger.warning(f"Supervisor 返回了无效的路由选项: {next_action}")
                    
                    # 尝试从 reasoning 中智能提取正确的 Worker 名称
                    fallback_worker = None
                    reasoning_lower = reasoning.lower() if reasoning else ""
                    for worker_name in worker_names:
                        if worker_name.lower() in reasoning_lower:
                            fallback_worker = worker_name
                            break
                    
                    if fallback_worker:
                        logger.info(f"从 reasoning 中推断出目标 Worker: {fallback_worker}")
                        next_action = fallback_worker
                    else:
                        # 如果还有未完成的任务步骤，使用计划中的 Worker
                        for step in task_plan:
                            if step.get("status") not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED, TaskStatus.FAILED]:
                                planned_worker = step.get("worker", "General")
                                # 处理带有类型标记的 Worker 名称
                                if "[" in planned_worker:
                                    planned_worker = planned_worker.split("[")[0].strip()
                                if planned_worker in worker_names:
                                    logger.info(f"使用任务计划中的 Worker: {planned_worker}")
                                    next_action = planned_worker
                                    break
                        else:
                            # 最终回退到 FINISH
                            logger.warning(f"无法推断有效的 Worker，使用 FINISH")
                            next_action = "FINISH"
                
                # 关键检查：如果 LLM 返回 FINISH 但还有未完成的任务，强制使用计划中的 Worker
                if next_action == "FINISH" and completed_steps < total_steps:
                    logger.warning(f"LLM 返回 FINISH 但还有未完成任务 ({completed_steps}/{total_steps})，尝试使用计划中的 Worker")
                    for step in task_plan:
                        step_status = step.get("status")
                        if isinstance(step_status, str):
                            is_completed = step_status in ["completed", "skipped", "failed"]
                        else:
                            is_completed = step_status in [TaskStatus.COMPLETED, TaskStatus.SKIPPED, TaskStatus.FAILED]
                        
                        if not is_completed:
                            planned_worker = step.get("worker", "General")
                            # 处理带有类型标记的 Worker 名称
                            if "[" in planned_worker:
                                planned_worker = planned_worker.split("[")[0].strip()
                            # 尝试找到匹配的 Worker
                            if planned_worker in worker_names:
                                next_action = planned_worker
                                logger.info(f"强制使用计划中的 Worker: {next_action}")
                                break
                            elif planned_worker.lower() in {n.lower() for n in worker_names}:
                                for wn in worker_names:
                                    if wn.lower() == planned_worker.lower():
                                        next_action = wn
                                        logger.info(f"强制使用计划中的 Worker: {next_action}")
                                        break
                                break
                    else:
                        # 如果找不到匹配的 Worker，使用 General
                        if "General" in worker_names:
                            next_action = "General"
                            logger.info(f"使用 General 作为备选")
                
                thinking_step = create_thinking_step(
                    step_type="decision",
                    content=reasoning or f"决定交给 {next_action} 处理",
                )
                
                logger.info(f"🎯 [Supervisor] 决策: {next_action}" + (f" (理由: {reasoning})" if reasoning else ""))
                
                if result.should_replan:
                    logger.info("🔄 [Supervisor] 请求重新规划任务")
                    return {
                        "task_plan": [],
                        "thinking_steps": state.get("thinking_steps", []) + [thinking_step],
                    }
                
                return {
                    "next": next_action,
                    "thinking_steps": state.get("thinking_steps", []) + [thinking_step],
                }
                
        except Exception as e:
            logger.error(f"路由决策时出错: {e}")
        
        # 最终降级：直接结束
        return {"next": "FINISH"}
    
    async def supervisor_node(state: SupervisorState) -> Dict[str, Any]:
        """
        Supervisor 节点函数
        
        动态获取 Worker 列表，支持运行时注册新的 Worker。
        """
        try:
            # 检查迭代次数，防止无限循环
            iteration_count = state.get("iteration_count", 0)
            if iteration_count >= config.max_iterations:
                logger.warning(f"达到最大迭代次数 {config.max_iterations}，强制结束")
                return {
                    "next": "FINISH",
                    "iteration_count": iteration_count,
                    "metadata": {
                        **state.get("metadata", {}),
                        "terminated_reason": "max_iterations_reached"
                    }
                }
            
            logger.info(f"🎯 [Supervisor] 开始决策... (迭代 {iteration_count + 1})")
            
            # 动态获取当前注册的 Worker
            registry = get_registry()
            if registry.is_empty():
                logger.warning("没有注册任何 Worker，默认返回 FINISH")
                return {"next": "FINISH", "iteration_count": iteration_count + 1}
            
            # 阶段 1：任务规划（如果启用且还没有规划）
            planning_result: Dict[str, Any] = {}
            if config.enable_planning and not state.get("task_plan"):
                planning_result = await _plan_task(state, registry)
                # 合并规划结果并继续决策（注意：需要把规划结果写回状态，否则下一轮会重复规划）
                state = {**state, **planning_result}
            
            # 阶段 2：路由决策
            routing_result = await _route_decision(state, registry)
            
            return {
                # 先写入 planning_result，让 task_plan/current_step_index 等字段进入图状态；
                # routing_result 允许覆盖（例如 should_replan 时返回 task_plan: []）
                **planning_result,
                **routing_result,
                "iteration_count": iteration_count + 1,
            }
            
        except Exception as e:
            logger.error(f"Supervisor 决策时出错: {e}")
            return {
                "next": "FINISH",
                "iteration_count": state.get("iteration_count", 0) + 1,
                "metadata": {
                    **state.get("metadata", {}),
                    "error": str(e),
                    "error_type": "supervisor_decision_error"
                }
            }
    
    return supervisor_node
