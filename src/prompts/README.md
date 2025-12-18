# src/prompts 目录

> 项目级提示词资源目录（扩展用途）。

---

## 定位

此目录作为 `src/common/prompts` 的补充，用于存放：
- 更复杂的提示词模板
- 多语言版本
- 特定场景的提示词集合
- 示例与文档

---

## 与 common/prompts 的关系

| 目录 | 职责 |
|:---|:---|
| `src/common/prompts/` | 核心提示词管理器与主配置文件 |
| `src/prompts/` | 扩展资源、多语言、高级模板 |

---

## 使用场景

### 场景 1：多语言支持

```
prompts/
├── zh/
│   └── templates.yaml
├── en/
│   └── templates.yaml
└── __init__.py
```

### 场景 2：按功能分组

```
prompts/
├── customer_service/
│   ├── greeting.txt
│   └── faq.yaml
├── data_analysis/
│   └── report.yaml
└── __init__.py
```

---

## 扩展建议

如需使用此目录，可在 `__init__.py` 中添加加载逻辑：

```python
from pathlib import Path
from src.common.prompts import get_manager

PROMPTS_DIR = Path(__file__).parent

def load_extended_prompts():
    """加载扩展提示词到主管理器"""
    manager = get_manager()
    # 实现自定义加载逻辑
    ...
```
