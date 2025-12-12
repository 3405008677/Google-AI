"""
JWT 授权服务模块

提供前端认证授权相关的 API 端点：
1. 登录获取 JWT Token
2. Token 刷新
3. Token 验证
4. 登出

Token 格式说明：
- 使用 JWT (JSON Web Token) 标准格式
- Access Token: 短期有效（默认 30 分钟）
- Refresh Token: 长期有效（默认 7 天）
- 支持 HS256 算法签名
"""

import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Set
from functools import lru_cache
from enum import Enum

import jwt
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from src.server.logging_setup import logger


# === JWT 配置 ===

class TokenType(str, Enum):
    """Token 类型"""
    ACCESS = "access"
    REFRESH = "refresh"


@lru_cache(maxsize=1)
def get_jwt_config() -> Dict[str, Any]:
    """
    获取 JWT 相关配置
    
    环境变量：
    - JWT_SECRET_KEY: JWT 签名密钥（必须设置，建议 64 位以上随机字符串）
    - JWT_ALGORITHM: 签名算法（默认 HS256）
    - JWT_ACCESS_TOKEN_EXPIRE_MINUTES: Access Token 有效期（分钟，默认 30）
    - JWT_REFRESH_TOKEN_EXPIRE_DAYS: Refresh Token 有效期（天，默认 7）
    - JWT_ISSUER: Token 发行者（可选）
    - AUTH_ADMIN_USERNAME: 管理员账号（默认 admin）
    - AUTH_ADMIN_PASSWORD: 管理员密码（默认 123456）
    """
    secret_key = os.getenv("JWT_SECRET_KEY")
    if not secret_key:
        # 开发环境使用默认密钥，生产环境必须设置
        secret_key = "dev-secret-key-please-change-in-production"
        logger.warning("⚠️ JWT_SECRET_KEY 未设置，使用默认密钥（仅供开发使用）")
    
    return {
        "secret_key": secret_key,
        "algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
        "access_token_expire_minutes": int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        "refresh_token_expire_days": int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
        "issuer": os.getenv("JWT_ISSUER", "google-ai-service"),
        "admin_username": os.getenv("AUTH_ADMIN_USERNAME", "admin"),
        "admin_password": os.getenv("AUTH_ADMIN_PASSWORD", "123456"),
    }


# === Token 黑名单（登出后的 Token 失效处理）===
# 生产环境建议使用 Redis 存储
_token_blacklist: Set[str] = set()


def _add_to_blacklist(jti: str) -> None:
    """将 Token ID 加入黑名单"""
    _token_blacklist.add(jti)


def _is_blacklisted(jti: str) -> bool:
    """检查 Token ID 是否在黑名单中"""
    return jti in _token_blacklist


# === JWT Token 操作 ===

def create_jwt_token(
    subject: str,
    token_type: TokenType,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> tuple[str, str, datetime]:
    """
    创建 JWT Token
    
    Args:
        subject: Token 主题（通常是 user_id）
        token_type: Token 类型（access 或 refresh）
        additional_claims: 额外的 claims
    
    Returns:
        (token, jti, expires_at) - Token 字符串、Token ID、过期时间
    """
    config = get_jwt_config()
    now = datetime.now(timezone.utc)
    
    # 根据类型设置过期时间
    if token_type == TokenType.ACCESS:
        expires_delta = timedelta(minutes=config["access_token_expire_minutes"])
    else:
        expires_delta = timedelta(days=config["refresh_token_expire_days"])
    
    expires_at = now + expires_delta
    
    # 生成唯一的 Token ID (jti)
    jti = hashlib.sha256(f"{subject}{now.timestamp()}{token_type}".encode()).hexdigest()[:16]
    
    # 构建 JWT payload
    payload = {
        "sub": subject,  # Subject（主题，通常是 user_id）
        "type": token_type.value,  # Token 类型
        "iat": now,  # Issued At（发行时间）
        "exp": expires_at,  # Expiration Time（过期时间）
        "jti": jti,  # JWT ID（唯一识别码）
        "iss": config["issuer"],  # Issuer（发行者）
    }
    
    # 添加额外的 claims
    if additional_claims:
        payload.update(additional_claims)
    
    # 签名并生成 Token
    token = jwt.encode(
        payload,
        config["secret_key"],
        algorithm=config["algorithm"],
    )
    
    return token, jti, expires_at


def decode_jwt_token(token: str, verify_type: Optional[TokenType] = None) -> Dict[str, Any]:
    """
    解码并验证 JWT Token
    
    Args:
        token: JWT Token 字符串
        verify_type: 验证 Token 类型（可选）
    
    Returns:
        解码后的 payload
    
    Raises:
        HTTPException: Token 无效、过期或类型不符
    """
    config = get_jwt_config()
    
    try:
        payload = jwt.decode(
            token,
            config["secret_key"],
            algorithms=[config["algorithm"]],
            options={
                "require": ["sub", "type", "iat", "exp", "jti"],
            },
        )
        
        # 检查 Token 是否在黑名单中
        if _is_blacklisted(payload.get("jti", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 已被撤销",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 验证 Token 类型
        if verify_type and payload.get("type") != verify_type.value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token 类型错误，预期 {verify_type.value}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token 无效: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# === 密码处理 ===

def hash_password(password: str) -> str:
    """
    密码哈希
    
    注意：这是简易实现，生产环境建议使用 bcrypt：
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    """
    config = get_jwt_config()
    return hashlib.sha256(f"{password}{config['secret_key']}".encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    注意：这是简易实现，生产环境建议使用 bcrypt：
    import bcrypt
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    """
    return hash_password(plain_password) == hashed_password


# === 使用者验证（简易实现，生产环境应查询数据库）===

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    验证用户账号密码
    
    Args:
        username: 用户名
        password: 密码
    
    Returns:
        用户信息，验证失败返回 None
    
    注意：这是简易实现，生产环境应该：
    1. 从数据库查询用户
    2. 使用 bcrypt 验证密码
    3. 检查用户状态（是否停用等）
    """
    config = get_jwt_config()
    
    # 简易验证（仅匹配管理员账号）
    if username == config["admin_username"] and password == config["admin_password"]:
        return {
            "user_id": f"user_{hashlib.md5(username.encode()).hexdigest()[:8]}",
            "username": username,
            "role": "admin",
        }
    
    return None


# === 请求/响应模型 ===

class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名", min_length=1, max_length=50)
    password: str = Field(..., description="密码", min_length=1, max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin",
                "password": "admin123"
            }
        }


class TokenResponse(BaseModel):
    """JWT Token 响应"""
    access_token: str = Field(..., description="JWT Access Token")
    refresh_token: str = Field(..., description="JWT Refresh Token")
    token_type: str = Field(default="Bearer", description="Token 类型")
    expires_in: int = Field(..., description="Access Token 有效期（秒）")
    expires_at: str = Field(..., description="Access Token 过期时间 (ISO 8601)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 1800,
                "expires_at": "2024-01-15T10:30:00+00:00"
            }
        }


class RefreshRequest(BaseModel):
    """Token 刷新请求"""
    refresh_token: str = Field(..., description="JWT Refresh Token")
    
    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class TokenValidationResponse(BaseModel):
    """Token 验证响应"""
    valid: bool = Field(..., description="Token 是否有效")
    user_id: Optional[str] = Field(None, description="用户 ID")
    username: Optional[str] = Field(None, description="用户名")
    role: Optional[str] = Field(None, description="用户角色")
    expires_at: Optional[str] = Field(None, description="过期时间")
    message: str = Field(..., description="验证消息")


class MessageResponse(BaseModel):
    """通用消息响应"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="消息")


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    user_id: str = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    role: str = Field(..., description="用户角色")
    token_expires_at: str = Field(..., description="Token 过期时间")


# === 依赖注入 ===

security = HTTPBearer(auto_error=False)


async def get_current_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """从请求中获取当前 Token"""
    if credentials:
        return credentials.credentials
    return None


async def get_current_user(
    token: Optional[str] = Depends(get_current_token)
) -> Dict[str, Any]:
    """
    获取当前登录用户（从 JWT 中解析）
    
    Raises:
        HTTPException: 未认证或 Token 无效
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证 Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 解码并验证 Token（必须是 access token）
    payload = decode_jwt_token(token, verify_type=TokenType.ACCESS)
    
    return {
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
        "role": payload.get("role"),
        "jti": payload.get("jti"),
        "exp": payload.get("exp"),
    }


async def get_optional_user(
    token: Optional[str] = Depends(get_current_token)
) -> Optional[Dict[str, Any]]:
    """
    获取当前用户（可选，不强制要求登录）
    """
    if not token:
        return None
    
    try:
        payload = decode_jwt_token(token, verify_type=TokenType.ACCESS)
        return {
            "user_id": payload.get("sub"),
            "username": payload.get("username"),
            "role": payload.get("role"),
        }
    except HTTPException:
        return None


# === 路由定义 ===

router = APIRouter(tags=["Authorization"])


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(request: LoginRequest, http_request: Request):
    """
    用户登录，获取 JWT Access Token 和 Refresh Token
    
    - **username**: 用户名
    - **password**: 密码
    
    成功后返回：
    - access_token: JWT 格式，用于 API 请求认证（短期有效）
    - refresh_token: JWT 格式，用于刷新 Access Token（长期有效）
    
    JWT Payload 包含：
    - sub: 用户 ID
    - username: 用户名
    - role: 用户角色
    - type: Token 类型 (access/refresh)
    - iat: 发行时间
    - exp: 过期时间
    - jti: Token 唯一识别码
    """
    # 验证用户
    user = authenticate_user(request.username, request.password)
    
    if not user:
        logger.warning(
            "登录失败 | 用户: %s | IP: %s",
            request.username,
            http_request.client.host if http_request.client else "unknown"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    
    # 创建 JWT Token
    additional_claims = {
        "username": user["username"],
        "role": user["role"],
    }
    
    access_token, _, access_expires = create_jwt_token(
        subject=user["user_id"],
        token_type=TokenType.ACCESS,
        additional_claims=additional_claims,
    )
    
    refresh_token, _, _ = create_jwt_token(
        subject=user["user_id"],
        token_type=TokenType.REFRESH,
        additional_claims={"username": user["username"]},
    )
    
    # 计算有效期（秒）
    expires_in = int((access_expires - datetime.now(timezone.utc)).total_seconds())
    
    logger.info(
        "登录成功 | 用户: %s | ID: %s | IP: %s",
        user["username"],
        user["user_id"],
        http_request.client.host if http_request.client else "unknown"
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=expires_in,
        expires_at=access_expires.isoformat(),
    )


@router.post("/refresh", response_model=TokenResponse, summary="刷新 Token")
async def refresh_token(request: RefreshRequest, http_request: Request):
    """
    使用 Refresh Token 获取新的 Access Token
    
    当 Access Token 过期时，使用此端点获取新的 Token，无需重新登录。
    Refresh Token 本身不会更新，直到过期后需要重新登录。
    """
    # 解码并验证 Refresh Token
    payload = decode_jwt_token(request.refresh_token, verify_type=TokenType.REFRESH)
    
    user_id = payload.get("sub")
    username = payload.get("username")
    
    # 创建新的 Access Token
    # 注意：这里应该从数据库重新获取用户角色，以防角色变更
    additional_claims = {
        "username": username,
        "role": "admin",  # 生产环境应从数据库获取
    }
    
    access_token, _, access_expires = create_jwt_token(
        subject=user_id,
        token_type=TokenType.ACCESS,
        additional_claims=additional_claims,
    )
    
    expires_in = int((access_expires - datetime.now(timezone.utc)).total_seconds())
    
    logger.info(
        "Token 刷新成功 | 用户: %s | IP: %s",
        username,
        http_request.client.host if http_request.client else "unknown"
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,  # Refresh Token 不变
        token_type="Bearer",
        expires_in=expires_in,
        expires_at=access_expires.isoformat(),
    )


@router.post("/validate", response_model=TokenValidationResponse, summary="验证 Token")
async def validate_token(token: Optional[str] = Depends(get_current_token)):
    """
    验证 JWT Access Token 是否有效
    
    在 Authorization Header 中提供 Bearer Token 进行验证。
    返回 Token 的有效性和包含的用户信息。
    """
    if not token:
        return TokenValidationResponse(
            valid=False,
            message="未提供 Token",
        )
    
    try:
        payload = decode_jwt_token(token, verify_type=TokenType.ACCESS)
        
        # 转换过期时间
        exp_timestamp = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc).isoformat() if exp_timestamp else None
        
        return TokenValidationResponse(
            valid=True,
            user_id=payload.get("sub"),
            username=payload.get("username"),
            role=payload.get("role"),
            expires_at=expires_at,
            message="Token 有效",
        )
    except HTTPException as e:
        return TokenValidationResponse(
            valid=False,
            message=e.detail,
        )


@router.post("/logout", response_model=MessageResponse, summary="用户登出")
async def logout(
    http_request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    用户登出，撤销当前 JWT Token
    
    将 Token 的 jti（JWT ID）加入黑名单，使其无法再次使用。
    注意：由于 JWT 是无状态的，黑名单需要持久化（建议使用 Redis）。
    """
    jti = user.get("jti")
    if jti:
        _add_to_blacklist(jti)
    
    logger.info(
        "登出成功 | 用户: %s | IP: %s",
        user.get("username"),
        http_request.client.host if http_request.client else "unknown"
    )
    
    return MessageResponse(success=True, message="登出成功，Token 已撤销")


@router.get("/me", response_model=UserInfoResponse, summary="获取当前用户信息")
async def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """
    获取当前登录用户的信息
    
    从 JWT Token 中解析用户信息，需要有效的 Bearer Token。
    """
    exp_timestamp = user.get("exp")
    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc).isoformat() if exp_timestamp else ""
    
    return UserInfoResponse(
        user_id=user["user_id"],
        username=user["username"],
        role=user.get("role", "user"),
        token_expires_at=expires_at,
    )


# === 工具函数（供其他模块使用）===

def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """
    从 Token 中获取用户信息（同步版本，供中间件使用）
    
    Args:
        token: JWT Token
    
    Returns:
        用户信息，无效返回 None
    """
    try:
        payload = decode_jwt_token(token, verify_type=TokenType.ACCESS)
        return {
            "user_id": payload.get("sub"),
            "username": payload.get("username"),
            "role": payload.get("role"),
        }
    except HTTPException:
        return None


# === 路由注册函数 ===

def register_authorization_routes(app, prefix: str = "/auth"):
    """
    注册授权路由到 FastAPI 应用
    
    Args:
        app: FastAPI 应用实例
        prefix: 路由前缀（默认 "/auth"）
    
    使用方式：
        from src.router.services.authorization.index import register_authorization_routes
        register_authorization_routes(app, prefix="/v1/auth")
    
    注册后的端点：
        - POST {prefix}/login - 登录获取 JWT
        - POST {prefix}/refresh - 刷新 Access Token
        - POST {prefix}/validate - 验证 Token
        - POST {prefix}/logout - 登出（撤销 Token）
        - GET {prefix}/me - 获取当前用户
    """
    from fastapi import APIRouter as FastAPIRouter
    
    if prefix:
        prefixed_router = FastAPIRouter(prefix=prefix)
        prefixed_router.include_router(router)
        app.include_router(prefixed_router)
    else:
        app.include_router(router)
    
    logger.info(f"✓ 已注册 JWT 授权路由，前缀: {prefix or '/'}")


# === 导出 ===

__all__ = [
    # 路由
    "router",
    "register_authorization_routes",
    # 依赖注入
    "get_current_user",
    "get_current_token",
    "get_optional_user",
    # Token 操作
    "create_jwt_token",
    "decode_jwt_token",
    "get_user_from_token",
    "TokenType",
    # 请求/响应模型
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "TokenValidationResponse",
    "UserInfoResponse",
]
