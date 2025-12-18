# src/common/prompts 目录

> 提示词（Prompt）集中管理，支持 YAML 配置、模板变量、多文件结构、热重载。

---

## 核心能力

| 特性 | 说明 |
|:---|:---|
| **多文件结构** | 按功能模块拆分到不同文件夹和文件 |
| **YAML 配置** | 支持分层结构，易于阅读和编辑 |
| **点号路径** | 使用 `workers.general.system` 形式访问嵌套配置 |
| **模板变量** | 支持 `{variable}` 占位符，运行时替换 |
| **热重载** | 调用 `reload_prompts()` 无需重启服务 |
| **线程安全** | `PromptManager` 为单例模式，内置锁保护 |
| **向后兼容** | 支持旧版 `config.yaml` 单文件模式 |

---

## 文件结构

```
prompts/
├── __init__.py              # 导出便捷函数
├── manager.py               # PromptManager 实现
├── README.md                # 本文档
│
├── config.yaml              # 索引文件 + 向后兼容
├── common.yaml              # 通用组件（角色定义、输出约束等）
├── languages.yaml           # 语言设定
├── search.yaml              # 搜索相关配置
│
├── supervisor/              # Supervisor 提示词
│   ├── planning.yaml        # 任务规划
│   └── routing.yaml         # 路由决策
│
├── workers/                 # Worker 专家提示词
│   ├── researcher.yaml      # 研究专家
│   ├── data_analyst.yaml    # 资料分析专家
│   ├── writer.yaml          # 写作专家
│   └── general.yaml         # 通用助手
│
└── system/                  # 系统消息
    ├── error_messages.yaml  # 错误消息
    ├── thinking.yaml        # 思考步骤
    └── status_messages.yaml # 状态消息
```

---

## 路径映射规则

### 文件夹内文件
```
文件夹/文件名.yaml → 前缀.文件名.配置项

例如:
supervisor/planning.yaml 中的 system → supervisor.planning.system
workers/researcher.yaml 中的 human → workers.researcher.human
system/error_messages.yaml 中的 input.no_query → system.error_messages.input.no_query
```

### 独立文件
```
文件名.yaml → 前缀.配置项

例如:
common.yaml 中的 roles.supervisor → common.roles.supervisor
languages.yaml 中的 supported.zh-CN → languages.supported.zh-CN
```

---

## 常用路径速查

| 功能 | 路径 |
|:---|:---|
| Supervisor 规划 | `supervisor.planning.system` |
| Supervisor 路由 | `supervisor.routing.system` |
| 研究专家 system | `workers.researcher.system` |
| 研究专家 human | `workers.researcher.human` |
| 资料分析专家 system | `workers.data_analyst.system` |
| 写作专家 system | `workers.writer.system` |
| 通用助手 system | `workers.general.system` |
| 通用助手（含时间）| `workers.general.system_with_datetime` |
| 预设问候语 | `workers.general.default_greeting` |
| 输入错误 | `system.error_messages.input.no_query` |
| 执行错误 | `system.error_messages.execution.task_failed` |
| 规划完成 | `system.thinking.planning.complete` |
| 路由决策 | `system.thinking.routing.decision` |
| 处理中状态 | `system.status_messages.task.processing` |
| 角色定义 | `common.roles.supervisor` |
| 语言设定 | `languages.supported.zh-CN` |
| 搜索提示 | `search.result_hints.no_config` |

---

## API 参考

```python
from src.common.prompts import (
    get_prompt,      # 获取单个提示词
    list_prompts,    # 列出所有/前缀匹配的键
    reload_prompts,  # 热重载配置
    has_prompt,      # 检查提示词是否存在
    get_prompt_manager,  # 获取 PromptManager 实例
)

# 基本用法
prompt = get_prompt("workers.general.system")

# 带变量替换
prompt = get_prompt("supervisor.planning.system", 
                    worker_list="Researcher, Writer", 
                    max_steps=8)

# 列出 workers 下所有提示词
keys = list_prompts(prefix="workers")

# 检查提示词是否存在
if has_prompt("workers.researcher.system"):
    print("存在")

# 热重载（修改配置后立即生效）
reload_prompts()
```

---

## 配置文件示例

### workers/general.yaml

```yaml
# 完整系统提示词
system: |
  你是友好、专业的 AI 助手，名称是「GG后台系统」。
  
  身分规则：
  - 若使用者问「你是谁」→ 回答：「我是 GG后台系统」
  
  语言：{language}

# 细分组件（可单独引用）
components:
  role: |
    你是友好、专业的 AI 助手，名称是「GG后台系统」。

identity:
  self_intro: |
    若使用者问「你是谁」→ 回答：「我是 GG后台系统」

# 预设问候语
default_greeting: |
  你好！我是 GG后台系统，想先从哪个问题开始？
```

---

## 最佳实践

1. **按功能模块组织**：相关提示词放在同一文件夹/文件中
2. **提供完整版和细分版**：`system` 为完整提示词，`components` 为可组合的细分组件
3. **变量命名清晰**：使用有意义的变量名，如 `{worker_list}` 而非 `{w}`
4. **保持向后兼容**：新增路径时保留旧路径的别名
5. **版本控制**：所有 YAML 文件纳入 Git，便于追溯变更历史
6. **热重载测试**：修改配置后使用 `reload_prompts()` 验证

