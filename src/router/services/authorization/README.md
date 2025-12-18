# src/router/services/authorization 目录

> JWT 授权服务：登录、刷新、验证、登出。

---

## 功能概览

```
┌─────────────────────────────────────────────────────────────┐
│                      Authorization Flow                      │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────────┐
                    │   /login     │
                    │  用户名+密码  │
                    └──────┬───────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  验证凭证 → 生成 Token  │
              │  Access + Refresh      │
              └────────────┬───────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ /refresh │    │ /validate│    │ /logout  │
    │ 刷新Token │    │ 验证Token │    │ 拉黑Token │
    └──────────┘    └──────────┘    └──────────┘
```

---

## API 端点

### POST /auth/login

登录获取 Token。

**请求体**：
```json
{
  "username": "admin",
  "password": "password"
}
```

**响应**：
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### POST /auth/refresh

刷新 Access Token。

**请求体**：
```json
{
  "refresh_token": "eyJ..."
}
```

**响应**：
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### POST /auth/validate

验证 Token 有效性。

**请求体**：
```json
{
  "token": "eyJ..."
}
```

**响应**：
```json
{
  "valid": true,
  "payload": {
    "sub": "admin",
    "exp": 1705312800,
    "type": "access"
  }
}
```

### POST /auth/logout

登出（将 Token 加入黑名单）。

**请求头**：
```
Authorization: Bearer eyJ...
```

**响应**：
```json
{
  "message": "登出成功"
}
```

### GET /auth/me

获取当前登录用户信息。

**请求头**：
```
Authorization: Bearer eyJ...
```

**响应**：
```json
{
  "username": "admin",
  "roles": ["admin"]
}
```

---

## Token 设计

### 双 Token 机制

| Token 类型 | 有效期 | 用途 |
|:---|:---|:---|
| Access Token | 30 分钟 | API 访问认证 |
| Refresh Token | 7 天 | 刷新 Access Token |

### Token Payload

```json
{
  "sub": "admin",           // 用户标识
  "type": "access",         // Token 类型
  "exp": 1705312800,        // 过期时间
  "iat": 1705311000,        // 签发时间
  "jti": "uuid..."          // Token ID（用于黑名单）
}
```

---

## 配置项

| 环境变量 | 说明 | 默认值 |
|:---|:---|:---|
| `JWT_SECRET_KEY` | 签名密钥 | `secret`（生产必改） |
| `JWT_ALGORITHM` | 签名算法 | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 有效期（分钟） | `30` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token 有效期（天） | `7` |
| `AUTH_ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `AUTH_ADMIN_PASSWORD` | 管理员密码 | `admin`（生产必改） |

---

## 安全注意事项

### 1. 密钥管理

```bash
# 生成安全的随机密钥
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Token 黑名单

当前实现使用内存集合存储黑名单：

```python
# 当前：内存存储（单实例有效）
_token_blacklist: Set[str] = set()

# 生产建议：使用 Redis
# redis.sadd("token_blacklist", jti)
# redis.expire("token_blacklist", TOKEN_EXPIRE_SECONDS)
```

### 3. 密码存储

当前为示例实现（明文比对），生产环境应使用 bcrypt：

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"])

# 存储
hashed = pwd_context.hash(password)

# 验证
pwd_context.verify(password, hashed)
```

---

## 使用示例

### 前端集成

```javascript
// 登录
const response = await fetch('/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'password' })
});
const { access_token, refresh_token } = await response.json();

// 存储 Token
localStorage.setItem('access_token', access_token);
localStorage.setItem('refresh_token', refresh_token);

// API 请求
const apiResponse = await fetch('/agents/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${access_token}`
  },
  body: JSON.stringify({ message: 'Hello' })
});
```
