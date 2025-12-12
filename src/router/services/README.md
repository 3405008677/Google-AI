## src/router/services 目录说明

## 概述
该目录存放与路由绑定的“服务模块”，通常提供：
- 一组 API 端点（路由）
- 相关的业务逻辑/认证逻辑
- 对外的注册函数（`register_xxx_routes`）

## 当前包含
- `authorization/`：JWT 登录、刷新、验证、登出等授权相关端点。
