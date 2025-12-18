# src/router/agents/AI 目录

> 模型适配层：统一接入 Gemini、Qwen 和自定义模型。

---

## 设计目标

- **统一接口**：不同模型提供统一的调用方式。
- **灵活切换**：通过配置/参数切换模型，无需改代码。
- **优雅降级**：某模型不可用时自动切换备选。

---

## 目录结构

```
AI/
├── __init__.py       # 导出
├── Gemini/           # Google Gemini 适配
│   └── index.py
├── Qwen/             # 通义千问适配
│   └── index.py
└── Customize/        # 自定义模型（OpenAI 兼容）
    └── index.py
```

---

## 模型优先级

`llm_factory.py` 按以下顺序尝试创建 LLM：

```
1. Customize（自定义模型）  ← 最高优先级
2. Qwen（通义千问）
3. Gemini（Google）        ← 最低优先级
```

如果高优先级模型未配置，自动尝试下一个。

---

## 模型配置

### Gemini

```ini
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-1.5-flash     # 或 gemini-pro, gemini-1.5-pro
GEMINI_TIMEOUT=60
GEMINI_MAX_RETRIES=3
```

### Qwen

```ini
QWEN_API_KEY=your_dashscope_api_key
QWEN_MODEL=qwen-plus              # 或 qwen-turbo, qwen-max
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_TIMEOUT=60
QWEN_MAX_RETRIES=3
```

### Customize（自定义模型）

兼容 OpenAI API 格式的任意模型：

```ini
SELF_MODEL_BASE_URL=http://localhost:8000/v1
SELF_MODEL_NAME=my-local-model
SELF_MODEL_API_KEY=optional_key   # 可选
```

---

## 使用方式

### 通过 LLM Factory

```python
from src.router.agents.supervisor.llm_factory import create_llm_from_context

# 自动选择可用模型
llm = create_llm_from_context(user_context=None, temperature=0.7)

# 指定模型
llm = create_llm_from_context(
    user_context={"model": "qwen"},
    temperature=0.7,
)
```

### 在 Worker 中使用

```python
class MyWorker(BaseWorker):
    async def run(self, state: SupervisorState) -> dict:
        # 从 user_context 获取模型偏好
        user_context = state.get("user_context", {})
        
        # 创建 LLM
        llm = create_llm_from_context(user_context, temperature=0.7)
        
        # 调用
        response = await llm.ainvoke([HumanMessage(content="...")])
        ...
```

---

## 适配器实现

每个模型目录的 `index.py` 提供：

### 1. 初始化函数

```python
def initGemini(app: FastAPI, prefix: str = "/gemini"):
    """注册 Gemini 相关路由"""
    router = APIRouter()
    
    @router.post("/chat")
    async def chat(...):
        ...
    
    app.include_router(router, prefix=prefix)
```

### 2. LLM 创建函数

```python
def create_gemini_llm(temperature: float = 0.7) -> BaseChatModel:
    """创建 Gemini LLM 实例"""
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
    )
```

---

## 子目录文档

| 目录 | 说明 |
|:---|:---|
| [Gemini/](Gemini/README.md) | Google Gemini 配置 |
| [Qwen/](Qwen/README.md) | 通义千问配置 |
| [Customize/](Customize/README.md) | 自定义模型配置 |
