## src/router/agents/AI 目录说明

## 概述
该目录用于组织不同 AI 模型提供方（或自建模型）的路由初始化与适配层。

## 子目录
- `Customize/`：自定义/自建模型（OpenAI 兼容接口）的路由入口。
- `Gemini/`：Google Gemini 的路由入口。
- `Qwen/`：通义千问（Qwen）的路由入口。

## 约定
每个提供方目录通常提供 `index.py`，对外暴露 `initXXX(app, prefix=...)` 形式的注册函数。
