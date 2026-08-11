# 个人智能助手系统 — 部署启动与功能测试操作手册

本手册指导使用者快速完成**个人智能助手（Personal Agent Assistant）**系统的本地环境配置、服务启动以及全套功能的手动测试与验证。

---

## 目录
1. [环境准备与配置](#一环境准备与配置)
2. [后端 API 服务启动](#二后端-api-服务启动)
3. [前端 Web 界面启动](#三前端-web-界面启动)
4. [核心功能手动测试指南](#四核心功能手动测试指南)
   - [4.1 智能 Agent 对话与技能自动路由测试](#41-智能-agent-对话与技能自动路由测试)
   - [4.2 Skill 扩展技能库测试](#42-skill-扩展技能库测试)
   - [4.3 LLM Wiki 自生长与结构化沉淀测试](#43-llm-wiki-自生长与结构化沉淀测试)
   - [4.4 数据源接入测试（网页/RSS/MCP）](#44-数据源接入测试网页rssmcp)
5. [自动化单元测试跑通指南](#五自动化单元测试跑通指南)
6. [常见问题与故障排查](#六常见问题与故障排查)

---

## 一、环境准备与配置

### 1. 软件依赖要求
- **Python**: `3.11+` (推荐 Python 3.11 或 3.12)
- **Node.js**: `≥ 20.19`
- **数据库**: 零配置（内置 SQLite + 本地 LanceDB 存储于 `./.data/` 目录）

### 2. 环境变量配置
在项目根目录 `/Users/meansoft/Documents/MyAgent` 下确认或新建 `.env` 文件：
```env
# 基础服务配置
SAG_ENVIRONMENT=dev
SAG_SECRET_KEY=dev-secret-change-me-0123456789abcdef

# LLM 与模型配置 (支持 OpenAI 兼容 API / 302.AI / 私有部署 Ollama/vLLM)
SAG_LLM_PROVIDER=openai
SAG_LLM_BASE_URL=https://api.302ai.cn/v1
SAG_LLM_API_KEY=sk-your-actual-api-key-here
SAG_LLM_MODEL=qwen3.6-flash

# Embedding 模型配置
SAG_EMBEDDING_MODEL=bge-large-en-v1.5
```

> 💡 **提示**：如果使用本地私有化的 **Ollama**：
> `SAG_LLM_BASE_URL=http://localhost:11434/v1`，`SAG_LLM_MODEL=qwen2.5:7b`，`SAG_LLM_API_KEY=ollama` 即可。

---

## 二、后端 API 服务启动

进入 API 目录并启动 FastAPI 后端：

```bash
cd /Users/meansoft/Documents/MyAgent/apps/api

# 1. 激活 Virtualenv 环境（如未激活）
source .venv/bin/activate

# 2. 启动服务（默认监听端口 8000）
PYTHONPATH=. uvicorn sag_api.main:app --reload --port 8000
```

启动成功的标志日志：
```text
INFO:     sag-api 已启动 · env=dev · llm_configured=True
INFO:     Skill 注册表加载完毕，共注册 6 个技能
INFO:     Wiki 三层架构初始化完毕
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

验证后端 Swagger 文档：浏览器访问 [http://localhost:8000/docs](http://localhost:8000/docs)。

---

## 三、前端 Web 界面启动

在新的 Terminal 窗口中启动前端应用：

```bash
cd /Users/meansoft/Documents/MyAgent/apps/web

# 1. 启动 Web 开发服务器
npm run dev
```

打开浏览器，访问 [http://localhost:3000](http://localhost:3000)。

---

## 四、核心功能手动测试指南

### 4.1 智能 Agent 对话与技能自动路由测试
1. 浏览器打开 [http://localhost:3000/chat](http://localhost:3000/chat)。
2. **场景 A（技能匹配测试）**：
   - 输入：`帮我撰写一份本周的项目进度总结与下周计划`
   - **预期现象**：触发内置 `writer` 技能，流式输出条理清晰的周报文本。
3. **场景 B（时间与工具计算测试）**：
   - 输入：`现在的具体时间是几点？并算一下: 128 * 4 + 50`
   - **预期现象**：助手调用内置 `get_time` 获取当前时间与 UTC 偏移，并调用 `execute_code` 输出计算结果 `562`。

---

### 4.2 Skill 扩展技能库测试
1. 访问 [http://localhost:3000/skills](http://localhost:3000/skills) 进入技能扩展管理面板。
2. **卡片管理与状态切换**：
   - 看到 6 个内置技能（`writer`, `translator`, `summarizer`, `web_researcher`, `data_analyst`, `code_runner`）。
   - 点击开关可启用/禁用技能。
3. **在线测试技能**：
   - 点击 `code_runner` 的【测试技能】按钮。
   - 输入测试代码参数或指令，点击【立即执行】，下方控制台实时呈现执行结果。
4. **新建自定义技能测试**：
   - 点击右上角【+ 新建技能】。
   - 填入名称 `my_explainer`、触发词 `解释一下`、描述 `概念解释助手`。
   - 点击【提交保存】，列表中即刻自动刷新出现新建技能！

---

### 4.3 LLM Wiki 自生长与结构化沉淀测试
1. 访问 [http://localhost:3000/wiki](http://localhost:3000/wiki) 进入 Wiki 自生长管理界面。
2. **页面分类与浏览**：
   - 在左侧切换 `CONCEPTS` / `ENTITIES` / `TOPICS` / `SOURCES` 分类。
3. **沉淀与更新测试**：
   - 点击列表中任一概念页面，右侧面板预览 Markdown 渲染文本。
   - 点击【编辑 Markdown】，修改文本后点击【保存修改】，系统提示“Wiki 页面已保存”。
4. **触发知识自生长测试**：
   - 在 `/chat` 对话框中询问：`什么是超边检索技术？`
   - 对话完成后，前往 `/wiki` 页面刷新，可以看到系统已在 `CONCEPTS` 中**自动生成** `超边检索技术.md` 概念归纳页！

---

### 4.4 数据源接入测试（网页/RSS/MCP）
可以通过 REST API 控制台直接进行手动调用测试：

1. **测试网页抓取**：
   ```bash
   curl -X POST http://localhost:8000/api/v1/connectors-ext/crawl-url \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}'
   ```
   **预期结果**：返回结构化的页面标题与提取好的 Markdown 正文。

2. **测试 RSS 订阅解析**：
   ```bash
   curl -X POST http://localhost:8000/api/v1/connectors-ext/rss-fetch \
     -H "Content-Type: application/json" \
     -d '{"feed_url": "https://news.ycombinator.com/rss", "limit": 3}'
   ```
   **预期结果**：返回格式化的文章标题、链接与摘要列表。

---

## 五、自动化单元测试跑通指南

若需一次性校验整个系统底层核心逻辑，可运行全套自动化测试套件：

```bash
cd /Users/meansoft/Documents/MyAgent

PYTHONPATH=apps/api python3 -m pytest \
  apps/api/tests/test_extensions.py \
  apps/api/tests/test_agent_orchestrator.py \
  apps/api/tests/test_skills_system.py \
  apps/api/tests/test_wiki_growth.py \
  apps/api/tests/test_connectors_ext.py
```

执行完毕后应输出：
`============================== 14 passed in 0.66s ==============================`

---

## 六、常见问题与故障排查

| 现象 | 可能原因 | 解决办法 |
|---|---|---|
| 对话提示“未配置模型” | `.env` 未填写 `SAG_LLM_API_KEY` | 在 `.env` 或前端 `/settings` 界面中填入有效的 API Key |
| 前端提示“无法连接 API” | 后端 8000 端口服务未启动 | 检查后端 Terminal 运行日志，确保 uvicorn 处于 running 状态 |
| 新建 Skill 未生效 | 技能名称冲突或 YAML 语法有误 | 检查 `sag_api/skills/custom/` 目录下生成的 `skill.yaml` |
| 网页抓取提示超时 | 目标网址存在防火墙或网络超时 | 确认目标 URL 能够公开 HTTP 访问，或增加超时配置 |
