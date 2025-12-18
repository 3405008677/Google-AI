# src/router/services 目录

> 与路由绑定的业务服务模块。

---

## 设计理念

每个服务模块通常包含：
- **API 端点**：一组相关的 HTTP 路由。
- **业务逻辑**：核心处理逻辑。
- **注册函数**：`register_xxx_routes(app, prefix)` 形式。

---

## 目录结构

```
services/
├── __init__.py          # 导出注册函数
└── authorization/       # JWT 授权服务
    ├── __init__.py
    └── index.py         # 路由定义与逻辑
```

---

## 当前服务

### authorization/（JWT 授权）

提供完整的 JWT 认证能力：

| 端点 | 方法 | 功能 |
|:---|:---|:---|
| `/auth/login` | POST | 登录获取 Token |
| `/auth/refresh` | POST | 刷新 Token |
| `/auth/validate` | POST | 验证 Token |
| `/auth/logout` | POST | 登出（拉黑 Token） |
| `/auth/me` | GET | 获取当前用户信息 |

详细文档：[authorization/README.md](authorization/README.md)

---

## 添加新服务

### 步骤 1：创建目录结构

```
services/
└── my_service/
    ├── __init__.py
    ├── index.py      # 路由与逻辑
    └── README.md     # 服务文档
```

### 步骤 2：实现路由

```python
# src/router/services/my_service/index.py

from fastapi import APIRouter, FastAPI

router = APIRouter()

@router.get("/items")
async def list_items():
    return {"items": [...]}

@router.post("/items")
async def create_item(item: ItemCreate):
    ...

def register_my_service_routes(app: FastAPI, prefix: str = "/my-service"):
    """注册服务路由"""
    app.include_router(router, prefix=prefix, tags=["MyService"])
```

### 步骤 3：在 index.py 中注册

```python
# src/router/index.py

from src.router.services.my_service import register_my_service_routes

def initRouter(app: FastAPI):
    ...
    register_my_service_routes(app, prefix="/my-service")
```

---

## 服务设计规范

1. **职责单一**：每个服务模块专注一个业务领域。
2. **独立可测**：服务逻辑可独立单元测试。
3. **清晰边界**：通过 `register_xxx_routes` 明确暴露。
4. **文档完整**：每个服务提供 README 说明。
