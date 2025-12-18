# src/common/prompts 目录

> 提示词（Prompt）集中管理，支持 YAML 配置、模板变量、热重载。

---

## 核心能力

| 特性 | 说明 |
|:---|:---|
| **YAML 配置** | 提示词定义在 `config.yaml`，支持分层结构 |
| **点号路径** | 使用 `workers.general.system` 形式访问嵌套配置 |
| **模板变量** | 支持 `{variable}` 占位符，运行时替换 |
| **热重载** | 调用 `reload_prompts()` 无需重启服务 |
| **线程安全** | `PromptManager` 为单例模式，内置锁保护 |

---

## 文件结构

```
prompts/
├── __init__.py      # 导出便捷函数
├── config.yaml      # 提示词配置文件
└── manager.py       # PromptManager 实现
```

---

## 配置示例 (config.yaml)

```yaml
# 分层结构
workers:
  general:
    system: |
      你是一个通用助手，负责回答用户的日常问题。
      当前时间：{current_time}
    
  researcher:
    system: |
      你是一个研究助手，擅长信息检索与分析。

# 顶层提示词
greeting: "你好，{name}！有什么可以帮助你的？"
```

---

## API 参考

```python
from src.common.prompts import (
    get_prompt,      # 获取单个提示词
    list_prompts,    # 列出所有/前缀匹配的键
    reload_prompts,  # 热重载配置
    get_manager,     # 获取 PromptManager 实例
)

# 基本用法
prompt = get_prompt("workers.general.system")

# 带变量替换
prompt = get_prompt("greeting", name="Alice")

# 列出 workers 下所有提示词
keys = list_prompts(prefix="workers")

# 热重载
reload_prompts()
```

---

## 最佳实践

1. **分层组织**：按 Worker/模块分组，便于查找与维护。
2. **变量命名**：使用有意义的变量名，如 `{user_query}` 而非 `{q}`。
3. **版本控制**：`config.yaml` 纳入 Git，便于追溯 Prompt 变更历史。
