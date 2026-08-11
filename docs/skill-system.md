# Skill 扩展系统开发规范与使用指南

Skill 扩展系统允许用户通过声明式 YAML 文件或自定义 Python 类快速扩展个人智能体的技能库。

---

## 1. Skill 目录与规范

技能放置于 `apps/api/sag_api/skills/builtin/`（内置）或 `apps/api/sag_api/skills/custom/`（自定义）。

每个 Skill 占据一个独立的子文件夹，核心结构如下：
```text
my_skill/
├── skill.yaml          # 技能声明元数据 (必须)
└── prompts/            # 提示词模板 (Prompt 技能专用)
    ├── system.md
    └── user.md
```

---

## 2. `skill.yaml` 配置规范

### 2.1 Prompt 技能模板
```yaml
name: "translator"
version: "1.0.0"
description: "精细多语言翻译工具"
type: "prompt"
enabled: true

triggers:
  keywords: ["翻译", "translate", "改成英文"]

prompts:
  system: "prompts/system.md"
  user: "prompts/user.md"
```

### 2.2 Workflow 技能模板
```yaml
name: "web_researcher"
version: "1.0.0"
description: "深度联网调研技能"
type: "workflow"
enabled: true

triggers:
  keywords: ["深度调研", "联网研究"]

workflow:
  - step: search_web
    tool: web_search
    input:
      query: "{{query}}"
  - step: search_kb
    tool: search_context
    input:
      query: "{{query}}"
```

---

## 3. API 交互端点

- **获取已注册 Skill**：`GET /api/v1/skills`
- **流式执行 Skill**：`POST /api/v1/skills/{name}/run`
  ```json
  {
    "input_text": "帮我翻译这段文本",
    "parameters": {}
  }
  ```
- **开启/禁用 Skill**：`POST /api/v1/skills/{name}/toggle?enabled=true`
- **动态创建 Custom Skill**：`POST /api/v1/skills/create`
