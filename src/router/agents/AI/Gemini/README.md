## src/router/agents/AI/Gemini 目录说明

## 概述
该目录提供 Google Gemini 模型相关的路由注册入口与适配逻辑。

## 关键文件
- `index.py`：初始化并注册 Gemini 相关的 API 路由。

## 配置提示
常用环境变量：
- `GEMINI_API_KEY`
- `GEMINI_MODEL`（默认 `gemini-2.5-flash`）
- `GEMINI_TIMEOUT`、`GEMINI_MAX_RETRIES`
