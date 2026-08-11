# LLM Wiki 三层架构与自生长引擎指南

SAG 扩展的 LLM Wiki 提供了兼顾原始凭据留存与结构化概念演进的知识库管理能力。

---

## 1. 三层架构说明

| 层次 | 路径 | 说明 | 读写约束 |
|---|---|---|---|
| **Raw 原始层** | `data/knowledge_wiki/raw/` | 保存文章、图书、会议纪要与对话原始文件 | **只读**，严禁篡改 |
| **Wiki 沉淀层** | `data/knowledge_wiki/wiki/` | 保存 Agent 抽取的结构化概念与主题概念页 | 允许 Agent 自动合并与人手修改 |
| **Schema 规范** | `data/knowledge_wiki/AGENTS.md` | 指导 AI 进行知识沉淀、去重与冲入处理的操作准则 | 全局规范指引 |

---

## 2. 自生长引擎工作原理

`AutoGrowEngine` 在助手与用户完成问答交互后自动触发：
1. 分析问答提取核心概念实体。
2. 检索 `wiki/concepts/` 中是否已有同名概念。
3. 若存在，则增量追加最新的洞察与对话纪录；若不存在，则创建新的 Wiki 概念页。

---

## 3. Wiki API 端点

- **获取 Wiki 页面列表**：`GET /api/v1/wiki/pages?category=concepts`
- **读取 Wiki 页面**：`GET /api/v1/wiki/pages/{category}/{page_name}`
- **修改保存 Wiki 页面**：`POST /api/v1/wiki/pages/{category}/{page_name}`
- **触发自生长**：`POST /api/v1/wiki/auto-grow`
