## src/router/agents/AI/Qwen 目录说明

## 概述
该目录提供通义千问（Qwen / DashScope 兼容接口）相关的路由注册入口与适配逻辑。

## 关键文件
- `index.py`：初始化并注册 Qwen 相关的 API 路由。

## 配置提示
常用环境变量：
- `QWEN_API_KEY`
- `QWEN_MODEL`（默认 `qwen-plus`）
- `QWEN_BASE_URL`（默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`）
- `QWEN_TIMEOUT`、`QWEN_MAX_RETRIES`
