## src/router/services/authorization 目录说明

## 概述
JWT 授权服务模块，提供前端/客户端认证所需的 API：
- 登录获取 Access/Refresh Token
- 刷新 Access Token
- 验证 Token
- 登出（Token 拉黑）
- 获取当前用户信息

## 关键文件
- `index.py`：JWT 生成/校验逻辑、FastAPI 路由定义与注册函数。

## 配置提示
环境变量（生产环境务必配置）：
- `JWT_SECRET_KEY`：签名密钥（建议足够随机且长度足够）
- `JWT_ALGORITHM`（默认 HS256）
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`、`JWT_REFRESH_TOKEN_EXPIRE_DAYS`
- `AUTH_ADMIN_USERNAME`、`AUTH_ADMIN_PASSWORD`（示例实现，生产环境建议接数据库）

## 安全备注
当前 Token 黑名单为内存集合，生产环境建议使用 Redis 等持久化存储。
