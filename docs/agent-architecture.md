# 个人智能体（Personal Agent Assistant）架构与扩展指南

本文档全面记录了基于 **SAG（SQL-driven Event Graph RAG）** 架构演进构建的个人智能助手系统的技术设计、模块划分与 API 说明。

---

## 1. 系统架构全景

本系统在 SAG 高效知识检索（数据源分块、事件/实体抽离、超边检索）的基础上，二次扩展了 **Agent 编排**、**Skill 扩展系统**、**LLM Wiki 自生长架构** 以及 **多源连接器** 4 大核心扩展模块。

```mermaid
graph TD
    Client[用户端 Next.js Web / 桌面客户端] --> Router[FastAPI 路由入口 /api/v1]
    
    subgraph Core Engine [核心引擎层]
        Router --> Orchestrator[Agent 编排器 orchestrator.py]
        Orchestrator --> SkillReg[Skill 注册表 SkillRegistry]
        Orchestrator --> TaskPlan[任务规划器 TaskPlanner]
        Orchestrator --> ToolReg[工具注册表 ToolRegistry]
        
        ToolReg --> BuiltinTools[内置工具: search_context / web_search / execute_code / get_time]
    end

    subgraph Knowledge & Growth [知识与自生长层]
        Orchestrator --> AutoGrow[Wiki 自生长引擎 AutoGrowEngine]
        AutoGrow --> WikiMgr[Wiki 管理器 WikiManager]
        WikiMgr --> RawData[Raw/ 原始资料 (只读)]
        WikiMgr --> WikiData[Wiki/ 沉淀数据 (Concepts/Entities/Topics)]
        WikiMgr --> AgentsSchema[AGENTS.md Schema 约束]
    end

    subgraph Connectors & Plugins [连接与扩展层]
        SkillReg --> CustomSkills[Skill 技能包 (custom/ & builtin/)]
        ToolReg --> MCPClient[MCP 客户端适配器]
        Connectors[数据源连接器] --> WebCrawler[网页与 Sitemap 抓取器]
        Connectors --> RSSFeed[RSS / Atom 订阅轮询器]
    end
```

---

## 2. 核心四大扩展模块说明

### 2.1 Agent 编排与多步规划器 (`sag_api/agent/`)
- **`AgentOrchestrator`**：智能体交互主入口，支持 **Skill 优先匹配**，当未匹配到专有 Skill 时，自动调用 `TaskPlanner` 将复杂复合用户需求拆解为子任务步骤，并依次调度底层工具完成解答与交付。
- **`TaskPlanner`**：任务拆解器，将包含多重指令的复合需求分解为 `TaskPlan` 与 `TaskStep`。

### 2.2 Skill 声明式扩展系统 (`sag_api/skills/`)
- **四种 Skill 形态**：
  - `prompt`：零代码编写，仅需 `skill.yaml` + `prompts/` 声明提示词与触发词。
  - `tool`：直接包装底层可执行 Tool 能力。
  - `workflow`：编排多个步骤串联执行的复合工作流技能。
  - `composite`：混合型技能。
- **内置 Skill**：`writer`（写作）、`translator`（翻译）、`summarizer`（摘要）、`web_researcher`（联网研究）、`data_analyst`（数据分析）、`code_runner`（代码计算）。
- **动态热加载与管理 API**：
  - `GET /api/v1/skills`：列表查询
  - `POST /api/v1/skills/{name}/run`：流式运行
  - `POST /api/v1/skills/{name}/toggle`：开启/禁用
  - `POST /api/v1/skills/create`：动态创建
  - `DELETE /api/v1/skills/{name}`：删除技能

### 2.3 LLM Wiki 三层自生长架构 (`sag_api/wiki/`)
- **三层形态划分**：
  - `raw/`：保存原始导入文章、图书、会议纪要与对话，只读不可篡改。
  - `wiki/`：保存 Agent 抽取的结构化沉淀与概念关联（`concepts/`, `entities/`, `topics/`, `sources/`）。
  - `AGENTS.md`：全局 Markdown 操作与 Schema 规范，指导 AI 助手在沉淀知识时的增量更新与矛盾冲突处理。
- **自生长引擎 `AutoGrowEngine`**：
  - 自动分析助手与用户的对话交互，提取核心概念。
  - 自动查重并进行增量融合合并，使个人知识库随日常使用自发生长。

### 2.4 多源数据接入扩展 (`sag_api/connectors_ext/`)
- **Web 抓取器 (`WebCrawler`)**：支持公开网页转 Markdown 提炼与 Sitemap 链接提取。
- **RSS 订阅器 (`RSSFeedManager`)**：支持 RSS 2.0 / Atom 订阅链接解析。
- **MCP Client 客户端 (`MCPClientManager`)**：支持外部 MCP 服务连接与工具代理。

---

## 3. 验证与单元测试

全套扩展功能内置于 `apps/api/tests/` 目录中：
- `test_extensions.py`：扩展 ORM 模型与基础加载
- `test_agent_orchestrator.py`：Agent 编排与工具调度
- `test_skills_system.py`：Skill 四种形态与内置技能
- `test_wiki_growth.py`：Wiki 三层架构与自生长引擎
- `test_connectors_ext.py`：数据源抓取与 MCP Client

使用以下命令运行完整测试套件：
```bash
PYTHONPATH=apps/api python3 -m pytest \
  apps/api/tests/test_extensions.py \
  apps/api/tests/test_agent_orchestrator.py \
  apps/api/tests/test_skills_system.py \
  apps/api/tests/test_wiki_growth.py \
  apps/api/tests/test_connectors_ext.py
```
