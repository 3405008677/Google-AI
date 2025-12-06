# Router 模块重构说明

## 重构目标

将 Bailian、googleAI、SelfHosted 三个类似的 AI 路由模块进行优化，通过基类和公共模块实现代码复用，便于后续添加新的 AI 服务。

## 新的目录结构

```
router/
├── AI/                          # 所有 AI 服务的路由实现
│   ├── base_router.py          # 基础路由类 BaseAIChatRouter
│   ├── Bailian/                # 阿里云百炼路由
│   │   ├── api.py
│   │   ├── models/
│   │   └── services/
│   ├── googleAI/                # Google AI 路由
│   │   ├── api.py
│   │   ├── models/
│   │   └── services/
│   └── SelfHosted/             # 自建模型路由
│       ├── api.py
│       ├── models/
│       └── services/
├── modules/                     # 公共模块（无业务逻辑的复用代码）
│   ├── base_chat_service.py    # 基础聊天服务类（定义通用流程）
│   ├── logging_utils.py        # 日志工具函数
│   └── request_utils.py       # 请求处理工具函数
├── common/                      # 公共模型和工具（已存在）
│   ├── models/
│   └── utils/
└── index.py                     # 路由入口文件
```

## 核心设计

### 1. 服务类继承体系

```
BaseChatService (抽象基类)
├── MessagesBasedService (消息数组服务)
│   ├── BailianChatService
│   └── SelfHostedChatService
└── PromptBasedService (提示词字符串服务)
    └── ChatService (GoogleAI)
```

#### BaseChatService（抽象基类）
- 定义通用的聊天服务流程
- 提供 `generate_response()` 和 `stream_response()` 公共方法
- 定义三个抽象方法：
  - `_prepare_input()`: 准备输入数据
  - `_call_client_generate()`: 调用客户端生成文本
  - `_call_client_stream()`: 调用客户端流式生成文本

#### MessagesBasedService（消息数组服务）
- 继承自 `BaseChatService`
- 自动处理消息数组的转换（`_compose_messages`）
- 适用于 OpenAI 兼容的客户端（如 Bailian、SelfHosted）
- 子类只需实现客户端调用方法

#### PromptBasedService（提示词字符串服务）
- 继承自 `BaseChatService`
- 需要实现提示词组合逻辑（`_compose_prompt`）
- 适用于使用字符串提示词的客户端（如 Gemini）
- 子类需要实现提示词组合和客户端调用方法

### 2. BaseAIChatRouter（基础路由类）

位于 `AI/base_router.py`，提供：
- 标准的 `/chat` 端点（同步）
- 标准的 `/chat/stream` 端点（流式）
- 可选的 `/chat/terminate` 端点
- 可选的访问日志功能

**使用方式：**
```python
class MyAIRouter(BaseAIChatRouter):
    def __init__(self):
        super().__init__(
            service_name="MyAI",
            service_class=MyAIChatService,
            enable_terminate=True,      # 是否启用终止端点
            enable_access_log=True,     # 是否启用访问日志
            log_filename="MyAI.log",    # 日志文件名（可选）
        )
    
    def get_chat_service(self) -> MyAIChatService:
        return MyAIChatService()
```

### 3. 公共工具模块

位于 `modules/` 目录：
- `base_chat_service.py`: 服务基类（定义通用流程，无业务逻辑）
- `logging_utils.py`: 访问日志初始化、请求元数据记录（无业务逻辑）
- `request_utils.py`: 请求ID生成、SSE事件格式化、问题提取（无业务逻辑）

## 添加新的 AI 服务

### 情况 1：OpenAI 兼容的服务（使用消息数组）

1. **在 `AI/` 目录下创建新目录**，例如 `AI/NewService/`

2. **创建客户端模型**：
   ```python
   # AI/NewService/models/new_service_client.py
   class NewServiceClient:
       def generate_text(self, messages: List[Dict[str, str]]) -> str:
           # 实现同步生成
           pass
       
       def stream_text(self, messages: List[Dict[str, str]]) -> Iterable[str]:
           # 实现流式生成
           pass
   ```

3. **创建服务类**（继承 `MessagesBasedService`）：
   ```python
   # AI/NewService/services/chat_service.py
   from ....modules.base_chat_service import MessagesBasedService
   from ..models.new_service_client import get_new_service_client
   
   class NewServiceChatService(MessagesBasedService):
       def __init__(self):
           super().__init__("NewService")
           self.client = get_new_service_client()
       
       async def _call_client_generate(self, input_data: List[Dict[str, str]]) -> str:
           return self.client.generate_text(input_data)
       
       async def _call_client_stream(self, input_data: List[Dict[str, str]]):
           return self.client.stream_text(input_data)
   ```

4. **创建路由类**（继承 `BaseAIChatRouter`）：
   ```python
   # AI/NewService/api.py
   from ..base_router import BaseAIChatRouter
   from .services.chat_service import NewServiceChatService
   
   class NewServiceRouter(BaseAIChatRouter):
       def __init__(self):
           super().__init__(
               service_name="NewService",
               service_class=NewServiceChatService,
               enable_terminate=True,
               enable_access_log=True,
           )
       
       def get_chat_service(self) -> NewServiceChatService:
           return NewServiceChatService()
   
   _router = NewServiceRouter()
   
   def initNewService(app, prefix=""):
       _router.init_router(app, prefix)
   ```

5. **在 `router/index.py` 中注册**：
   ```python
   from .AI.NewService.api import initNewService
   
   def initRouter(app):
       # ...
       initNewService(app, prefix="/NewService")
   ```

### 情况 2：使用提示词字符串的服务（如 Gemini）

步骤类似，但服务类继承 `PromptBasedService`：

```python
# AI/NewService/services/chat_service.py
from ....modules.base_chat_service import PromptBasedService

class NewServiceChatService(PromptBasedService):
    def __init__(self):
        super().__init__("NewService")
        self.client = get_new_service_client()
    
    def _compose_prompt(self, request) -> str:
        """实现提示词组合逻辑"""
        # 将 ChatRequest 转换为字符串提示词
        pass
    
    async def _call_client_generate(self, input_data: str) -> str:
        return self.client.generate_text(input_data)
    
    async def _call_client_stream(self, input_data: str):
        return self.client.stream_text(input_data)
```

## 代码结构优势

### 1. 清晰的继承关系
- `BaseChatService` → 定义通用流程
- `MessagesBasedService` / `PromptBasedService` → 处理不同数据格式
- 具体服务类 → 只需实现客户端调用

### 2. 职责明确
- **modules/**: 无业务逻辑的纯工具函数和基类
- **AI/**: 具体的业务实现
- **common/**: 共享的数据模型

### 3. 易于扩展
- 添加新服务只需实现少量代码
- 公共逻辑集中在基类中
- 修改公共逻辑只需修改一处

### 4. 类型安全
- 使用类型提示和抽象基类
- 确保接口一致性

## 示例对比

### 重构前（Bailian）
```python
class BailianChatService:
    async def generate_response(self, request):
        # 准备消息
        messages = self._compose_messages(request)
        # 调用客户端
        response = self.client.generate_text(messages)
        # 格式化响应
        return ChatResponse(...)
    
    async def stream_response(self, request):
        # 准备消息
        messages = self._compose_messages(request)
        # 流式调用
        for chunk in self.client.stream_text(messages):
            yield format_sse_event(...)
```

### 重构后（Bailian）
```python
class BailianChatService(MessagesBasedService):
    def __init__(self):
        super().__init__("Bailian")
        self.client = get_bailian_client()
    
    async def _call_client_generate(self, input_data):
        return self.client.generate_text(input_data)
    
    async def _call_client_stream(self, input_data):
        return self.client.stream_text(input_data)
```

**优势**：
- 代码量减少 70%+
- 逻辑更清晰
- 公共功能自动继承
