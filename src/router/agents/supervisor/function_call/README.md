# Function Call 降级方案模块

当模型不支持 Function Calling 时，使用降级方案来获取实时信息并注入到系统提示词中。

## 架构设计

### 核心组件

1. **`fallback.py`**: 具体的降级方案实现
   - `get_current_datetime_fallback()`: 时间信息降级方案

2. **`fallback_manager.py`**: 降级方案管理器
   - `FallbackManager`: 统一管理所有降级方案
   - `get_fallback_manager()`: 获取管理器单例

## 使用方式

### 当前使用（时间信息降级）

在 `GeneralWorker` 中，当模型不支持 Function Calling 时：

```python
from src.router.agents.supervisor.function_call import get_fallback_manager

fallback_manager = get_fallback_manager()

# 收集需要的降级信息
fallback_info = fallback_manager.collect_fallback_info(
    ["datetime"],  # 需要的降级方案列表
    timezone="Asia/Shanghai",
)

# 构建系统提示词
system_prompt = fallback_manager.build_system_prompt_with_fallbacks(
    base_prompt_key="workers.general.system",
    fallback_names=["datetime"],
    fallback_info=fallback_info,
    language="中文",
)
```

## 扩展新的降级方案

### 示例：添加搜索能力降级方案

1. **在 `fallback.py` 中添加实现**：

```python
def get_search_capability_fallback() -> str:
    """
    搜索能力降级方案
    
    当模型不支持搜索工具时，告知模型搜索能力受限。
    """
    return "注意：当前无法使用实时搜索功能，请基于已有知识回答问题。"
```

2. **在 `fallback_manager.py` 中注册**：

```python
# 在 FallbackManager._register_default_fallbacks() 中添加：
self.register(
    name="search",
    description="搜索能力降级方案",
    get_info=lambda: get_search_capability_fallback(),
    prompt_key=None,  # 使用通用模板
)
```

3. **在 Worker 中使用**：

```python
# 在 ResearcherWorker 中，如果需要降级方案：
required_fallbacks = ["search"]

fallback_info = fallback_manager.collect_fallback_info(
    required_fallbacks,
)

system_prompt = fallback_manager.build_system_prompt_with_fallbacks(
    base_prompt_key="workers.researcher.system",
    fallback_names=required_fallbacks,
    fallback_info=fallback_info,
    language=language,
)
```

### 示例：添加数据查询降级方案

```python
# 1. 在 fallback.py 中
def get_data_query_fallback(database_status: str = "unavailable") -> str:
    """数据查询降级方案"""
    if database_status == "unavailable":
        return "注意：当前无法访问业务数据库，请基于已有信息回答问题。"
    return f"数据库状态：{database_status}"

# 2. 在 fallback_manager.py 中注册
self.register(
    name="data_query",
    description="数据查询降级方案",
    get_info=lambda database_status="unavailable": get_data_query_fallback(database_status),
)

# 3. 在 DataAnalystWorker 中使用
fallback_info = fallback_manager.collect_fallback_info(
    ["data_query"],
    data_query_database_status="unavailable",  # 传递参数
)
```

## 多降级方案组合

可以同时使用多个降级方案：

```python
# 收集多个降级信息
fallback_info = fallback_manager.collect_fallback_info(
    ["datetime", "search", "data_query"],
    timezone="Asia/Shanghai",
    data_query_database_status="unavailable",
)

# 构建包含所有降级信息的系统提示词
system_prompt = fallback_manager.build_system_prompt_with_fallbacks(
    base_prompt_key="workers.general.system",
    fallback_names=["datetime", "search", "data_query"],
    fallback_info=fallback_info,
    language="中文",
)
```

## Prompt 模板配置

### 单个降级方案

如果降级方案有专门的 prompt 模板（如 `system_with_datetime`），管理器会自动使用：

```yaml
# config/prompts/workers/general.yaml
system_with_datetime: |
  你是一个通用助手。当前时间信息：{datetime_info}
  请用{language}回答用户问题。
```

### 多个降级方案

可以创建组合模板：

```yaml
system_with_fallbacks: |
  你是一个通用助手。
  
  {datetime_info}
  {search_info}
  {data_query_info}
  
  请用{language}回答用户问题。
```

如果没有专门的组合模板，管理器会使用基础模板，降级信息会作为额外参数传递。

## 优势

1. **统一管理**：所有降级方案集中在一个地方，便于维护
2. **易于扩展**：添加新降级方案只需注册即可
3. **灵活组合**：支持多个降级方案同时使用
4. **向后兼容**：保持与现有代码的兼容性

