## src/router/agents/AI/Customize 目录说明

## 概述
该目录提供“自定义/自建模型（OpenAI 兼容接口）”的路由注册入口。

## 关键文件
- `index.py`：初始化并注册 Customize 模型相关的 API 路由。

## 配置提示
通常通过环境变量配置自建模型地址与模型名，例如：
- `SELF_MODEL_BASE_URL`
- `SELF_MODEL_NAME`
- `SELF_MODEL_API_KEY`（可选）
