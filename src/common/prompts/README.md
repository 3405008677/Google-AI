## src/common/prompts 目录说明

## 概述
该目录用于集中管理提示词（Prompt）配置，支持：
- YAML 配置文件加载
- 线程安全的单例访问
- 热重载
- 模板变量替换（`{var}`）

## 关键文件
- `config.yaml`：提示词配置（分层结构，支持点号路径读取）。
- `manager.py`：`PromptManager` 与便捷函数（`get_prompt`、`reload_prompts` 等）。

## 常用用法
- 获取提示词：`get_prompt("workers.researcher.system")`
- 热重载：`reload_prompts()`
- 列出可用键：`list_prompts(prefix="workers")`
