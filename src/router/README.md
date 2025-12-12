## src/router 目录说明

## 概述
该目录负责 API 路由体系：
- 路由注册与统一入口
- 路由级中间件（认证/限流/追踪）
- 健康检查端点
- Agent API（Supervisor/Worker）
- 授权服务（JWT 登录/刷新/验证等）

## 关键入口
- `index.py`：路由系统初始化入口（`initRouter`），负责注册中间件、健康检查、AI 路由与 Agent 路由。
- `health.py`：健康检查与指标端点（`/health`、`/ready`、`/status`、`/metrics`）。

## 子目录
- `agents/`：Agent/Supervisor 架构与相关 API。
- `utils/`：路由层通用异常与中间件实现。
- `services/`：与路由绑定的业务服务（如授权）。
