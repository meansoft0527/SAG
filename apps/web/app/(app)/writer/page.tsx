"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import {
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Database,
  Download,
  Edit3,
  FileText,
  FileUp,
  FolderPlus,
  Globe2,
  History,
  Info,
  Layers,
  ListOrdered,
  Lock,
  MessageSquare,
  PanelRightClose,
  PanelRightOpen,
  PenTool,
  Plus,
  RefreshCw,
  RotateCcw,
  Send,
  Sparkles,
  Trash2,
  User,
  Wand2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { api, API_BASE } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Citation, Source } from "@/lib/types";
import { useApp } from "@/components/features/app-shell";
import {
  AgentActivityTimeline,
  type AgentActivityStep,
} from "@/components/features/chat/agent-activity-timeline";
import { CitationBlock } from "@/components/features/chat/citation-block";
import { useDetailPanel } from "@/components/features/detail-panel";
import { MarkdownContent } from "@/components/features/markdown-content";
import { Button } from "@/components/ui/button";

// 消息结构
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  outlineData?: OutlineData | null;
  citations?: Citation[];
  steps?: AgentActivityStep[];
}

// 树状大纲卡片数据 (含二级标题 subsections)
interface ChapterNode {
  id: string;
  title: string; // 一级标题
  summary: string;
  subsections: string[]; // 二级标题数组
}

interface OutlineData {
  title: string;
  chapters: ChapterNode[];
}

// 历史快照版本
interface DocVersionSnapshot {
  version: number;
  content: string;
  timestamp: string;
  citations?: Citation[];
}

// 预设写作文体与风格选择
const WRITER_STYLES = [
  { id: "official", label: "🏛️ 公文写作", desc: "机关规范公文，语调严肃严谨" },
  { id: "report", label: "📊 专业研报", desc: "数据驱动，逻辑推导严密" },
  { id: "summary", label: "📝 请示汇报", desc: "实事求是，重点突出" },
  { id: "wechat", label: "🚀 宣传图文", desc: "观点鲜明，生动感染" },
  { id: "business", label: "💼 商业方案", desc: "痛点对齐，落地可行" },
];

export default function ConversationalWriterPage() {
  const { agent, refreshThreads } = useApp();
  const detailPanel = useDetailPanel();
  const searchParams = useSearchParams();
  const threadIdParam = searchParams.get("thread_id");

  // 当前所处的持久化 Thread ID 与活跃 Thread 锁引引用 (防 URL 变化覆盖 streaming 状态)
  const [currentThreadId, setCurrentThreadId] = React.useState<string | null>(threadIdParam);
  const activeThreadRef = React.useRef<string | null>(threadIdParam);

  // 1. 知识库信源数据与能力控制
  const [sources, setSources] = React.useState<Source[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = React.useState<string[]>([]);
  const [loadingSources, setLoadingSources] = React.useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = React.useState(false);
  const [availableSkills, setAvailableSkills] = React.useState<Array<{ name: string; description: string }>>([]);
  const [selectedSkill, setSelectedSkill] = React.useState<string | null>(null);

  // 2. 对话流数据与大纲风格选单
  const [messages, setMessages] = React.useState<ChatMessage[]>([
    {
      id: "msg_init",
      role: "assistant",
      content:
        "你好！我是您的分阶段智能写作助手。\n\n请直接告诉我写作需求（如：*“帮我撰写一篇关于 SAG 知识库检索优势的深度研报”*）。\n我将启动【阶段 1 知识库多跳搜索】搜集资料，并在【阶段 2】为您输出包含【一级标题 + 二级标题】的树状逻辑大纲卡片，待您在下方卡片中审核确认并选择写作文体风格（公文写作、专业报告等）后再开展正文起草。",
    },
  ]);
  const [inputMessage, setInputMessage] = React.useState("");
  const [isStreaming, setIsStreaming] = React.useState(false);
  const [selectedStyleId, setSelectedStyleId] = React.useState("official");

  // 3. 当前文档 Artifact 面板数据与版本历史 (none -> draft -> final)
  const [showDocPanel, setShowDocPanel] = React.useState(false);
  const [docContent, setDocContent] = React.useState("");
  const [docCitations, setDocCitations] = React.useState<Citation[]>([]);
  const [docStatus, setDocStatus] = React.useState<"none" | "draft" | "final">("none");
  const [draftVersion, setDraftVersion] = React.useState(1);
  const [docHistory, setDocHistory] = React.useState<DocVersionSnapshot[]>([]);
  const [selectedHistoryVersion, setSelectedHistoryVersion] = React.useState<number | null>(null);
  const [docViewMode, setDocViewMode] = React.useState<"preview" | "edit">("preview");

  const [isSavingToKB, setIsSavingToKB] = React.useState(false);
  const [isSavingToSource, setIsSavingToSource] = React.useState(false);
  const [targetSaveSourceId, setTargetSaveSourceId] = React.useState<string>("");

  const chatScrollRef = React.useRef<HTMLDivElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // 初始化加载知识库与 Skill 技能
  React.useEffect(() => {
    async function loadInitialData() {
      setLoadingSources(true);
      try {
        const list = await api.listSources();
        setSources(list);
        if (list.length > 0) {
          setTargetSaveSourceId(list[0].id);
        }
      } catch (err: any) {
        logError("加载信源失败", err);
      } finally {
        setLoadingSources(false);
      }

      // 获取可用技能列表
      try {
        const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiHost}/api/v1/skills`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            setAvailableSkills(data.map((s) => ({ name: s.name, description: s.description })));
          }
        }
      } catch {
        /* ignore */
      }
    }
    loadInitialData();
  }, []);

  // 按 thread_id 参数恢复历史消息（带有 isStreaming & activeThreadRef 消息锁断言防护）
  React.useEffect(() => {
    async function restoreThreadHistory(tid: string) {
      const ag = agent || (await api.getDefaultAgent());
      if (!ag) return;
      try {
        const page = await api.listMessages(ag.id, tid, { limit: 50 });
        if (page.items && page.items.length > 0) {
          const restoredMsgs: ChatMessage[] = page.items.map((m, idx) => {
            const role = (m.role === "user" ? "user" : "assistant") as "user" | "assistant";
            // 🛡️ 防重锁：仅在第一个 assistant 消息或显式包含 ```outline 的消息中提取大纲
            const isFirstAssistant = page.items.findIndex((item) => item.role === "assistant") === idx;
            const outline = (isFirstAssistant || m.content.includes("```outline")) ? extractOutlineData(m.content) : null;
            const citations = (m.citations as Citation[]) || [];
            return {
              id: m.id,
              role,
              content: m.content,
              outlineData: outline,
              citations,
            };
          });
          setMessages(restoredMsgs);

          // 恢复最新生成的长文正文 Artifact
          const lastArticleMsg = [...page.items].reverse().find((m) => m.content.includes("# ") && m.content.length > 300);
          if (lastArticleMsg) {
            const clean = cleanDocContent(lastArticleMsg.content);
            const citations = (lastArticleMsg.citations as Citation[]) || [];
            setDocContent(clean);
            setDocCitations(citations);
            setDocStatus("draft");
            setDocHistory([
              {
                version: 1,
                content: clean,
                citations,
                timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              },
            ]);
            setShowDocPanel(true);
          }
        }
      } catch (err: any) {
        logError("恢复历史写作会话失败", err);
      }
    }

    if (threadIdParam) {
      // 🛡️ 核心消息保护断言：若正在流式生成，或者即将恢复的 ID 就是当前活跃的会话，绝对拒绝覆盖！
      if (isStreaming || activeThreadRef.current === threadIdParam) {
        return;
      }
      setCurrentThreadId(threadIdParam);
      activeThreadRef.current = threadIdParam;
      restoreThreadHistory(threadIdParam);
    }
  }, [threadIdParam, agent, isStreaming]);

  // 容器局域平滑自动滚动置底，避免触发全页 scrollIntoView 导致底部输入框跳动
  React.useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, isStreaming]);

  const logError = (msg: string, err: any) => {
    console.error(msg, err);
  };

  // 切换信源选择
  const toggleSource = (id: string) => {
    setSelectedSourceIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  // 确保或新建持久化会话 Thread
  const ensureThread = async (firstMsgText: string, targetAg?: any): Promise<string | null> => {
    if (currentThreadId) return currentThreadId;
    const ag = targetAg || agent || (await api.getDefaultAgent());
    if (!ag) return null;

    try {
      const topicTitle = firstMsgText.slice(0, 15).replace(/[*#\n]/g, "");
      const newThread = await api.createThread(ag.id, `智能写作：${topicTitle}`);
      setCurrentThreadId(newThread.id);
      activeThreadRef.current = newThread.id;
      window.history.replaceState(null, "", `/writer?thread_id=${newThread.id}`);
      window.dispatchEvent(new Event("sag:pathchange"));
      refreshThreads();
      return newThread.id;
    } catch (err: any) {
      logError("创建持久化写作会话失败", err);
      return null;
    }
  };

  // 1. 发送对话消息
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || isStreaming) return;

    // 判断是否为首轮发起写作请求（尚未产生草稿且非显式确认/直接生成指令）
    const isInitialTurn =
      !docContent &&
      !text.includes("【确认大纲与文体风格】") &&
      !text.includes("直接生成") &&
      !text.includes("一次性生成");

    // 获取并锁定 TargetAgent，绝不为空
    const targetAgent = agent ?? (await api.getDefaultAgent());

    // 确保已有或自动新建 Thread 并锁住 activeThreadRef
    const activeTid = await ensureThread(text, targetAgent);
    if (activeTid) {
      activeThreadRef.current = activeTid;
    }

    // 纯净的 User 消息（绝无字符串拼凑污染）
    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputMessage("");
    setIsStreaming(true);

    const assistantMsgId = `asst_${Date.now()}`;
    const initialSteps: AgentActivityStep[] = [
      {
        id: `step_init_${Date.now()}`,
        kind: "thinking",
        step: 1,
        status: "active",
        startedAt: Date.now(),
      },
    ];

    setMessages((prev) => [
      ...prev,
      {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        citations: [],
        steps: initialSteps,
      },
    ]);

    try {
      const token = getToken();

      // 若未手动勾选信源，默认传入已拥有的全量信源 ID，确保 100% 触发底层多跳 RAG！
      const effectiveSourceIds =
        selectedSourceIds.length > 0
          ? selectedSourceIds
          : sources.map((s) => s.id);

      // 保证使用 /ask 端点
      const url = `${API_BASE}/api/v1/agents/${targetAgent.id}/threads/${activeTid || "default"}/ask`;
      const reqBody = {
        query: text,
        source_ids: effectiveSourceIds.length > 0 ? effectiveSourceIds : undefined,
        effective_web_enabled: webSearchEnabled,
      };

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(reqBody),
      });

      if (!response.ok || !response.body) {
        throw new Error("模型响应失败");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulatedContent = "";
      let currentCitations: Citation[] = [];
      let activeSteps: AgentActivityStep[] = [...initialSteps];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;

          // 🛡️ 核心绝杀断言 1：忽略 SSE 规范中的心跳注释行（以 : 开头），彻底封杀 : ping 乱码嵌入文章！
          if (line.startsWith(":")) continue;

          let eventType = "";
          let rawData = "";

          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
            continue;
          } else if (line.startsWith("data: ")) {
            rawData = line.slice(6).trim();
          } else {
            rawData = line.trim();
          }

          if (!rawData) continue;

          try {
            const data = JSON.parse(rawData);
            const ev = eventType || data.type || "";
            const payload = data.payload || data;

            // 全多跳 RAG 工具事件精确对齐
            if (
              ev === "tool.started" ||
              ev === "step.start" ||
              ev === "step" ||
              data.type === "tool.started"
            ) {
              const stepNum = payload.turn || payload.step || activeSteps.length + 1;
              const toolName = payload.name || payload.label || "search_context";
              const newStep: AgentActivityStep = {
                id: `step_${stepNum}_${Date.now()}`,
                kind: "tool",
                step: stepNum,
                name: toolName,
                arguments: payload.arguments || payload.args,
                status: "active",
                startedAt: Date.now(),
              };
              activeSteps = activeSteps.map((s) => ({ ...s, status: "done" }));
              activeSteps.push(newStep);
            } else if (
              ev === "tool.completed" ||
              ev === "step.finish" ||
              data.type === "tool.completed"
            ) {
              const finishedToolName = payload.name;
              const details = payload.details || {};
              const matches = payload.matches || details.matches || [];
              
              // 🛡️ 核心绝杀断言 2：精准只更新最后一个 status === "active" 的步骤，绝不覆盖先前已完成步骤的独立耗时与不同匹配条数！
              let updated = false;
              activeSteps = activeSteps.map((s) => {
                if (!updated && s.status === "active") {
                  updated = true;
                  return {
                    ...s,
                    status: "done",
                    ms: payload.duration_ms || payload.ms || 450,
                    count: payload.count ?? details.count ?? matches.length,
                    details: matches.length > 0 ? { matches, ...details } : details,
                  };
                }
                return s;
              });
            } else if (ev === "agent.citation" || ev === "citation" || payload.citations) {
              currentCitations = payload.citations || [payload];
            } else if (
              ev === "agent.token" ||
              ev === "token" ||
              ev === "message.delta" ||
              payload.token ||
              payload.delta
            ) {
              const tokenText =
                payload.token ||
                (typeof payload.delta === "string" ? payload.delta : payload.delta?.content) ||
                "";
              accumulatedContent += tokenText;
            } else if (payload.content) {
              accumulatedContent += payload.content;
            }
          } catch {
            if (!rawData.startsWith("{") && !rawData.startsWith(":")) {
              accumulatedContent += rawData;
            }
          }

          if (accumulatedContent.length > 0) {
            activeSteps = activeSteps.map((s) => ({ ...s, status: "done" }));
          }

          // 仅在首轮未确认大纲时才提取与绑定大纲数据
          let parsedOutline = isInitialTurn ? extractOutlineData(accumulatedContent) : null;
          
          if (isInitialTurn && !parsedOutline && accumulatedContent.length > 20) {
            parsedOutline = buildFallbackOutlineFromPrompt(text, accumulatedContent);
          }

          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content: accumulatedContent,
                    outlineData: isInitialTurn ? (parsedOutline || m.outlineData) : null,
                    citations: currentCitations,
                    steps: activeSteps,
                  }
                : m
            )
          );

          // 只有当非首轮（即处于正文起草或修改阶段）且包含正文 Markdown 时，才展开右侧文档 Artifact 面板
          if (
            !isInitialTurn &&
            accumulatedContent.includes("# ") &&
            accumulatedContent.length > 300 &&
            !accumulatedContent.includes("```outline")
          ) {
            const clean = cleanDocContent(accumulatedContent);
            setDocContent(clean);
            setDocCitations(currentCitations);
            if (docStatus === "none") {
              setDocStatus("draft");
            }
            if (!showDocPanel) setShowDocPanel(true);
          }
        }
      }

      activeSteps = activeSteps.map((s) => ({ ...s, status: "done" }));
      
      let finalOutline = isInitialTurn ? extractOutlineData(accumulatedContent) : null;
      if (isInitialTurn && !finalOutline) {
        finalOutline = buildFallbackOutlineFromPrompt(text, accumulatedContent);
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? { ...m, steps: activeSteps, outlineData: isInitialTurn ? (finalOutline || m.outlineData) : null }
            : m
        )
      );

      // 如果非首轮，保存快照历史版本
      if (!isInitialTurn) {
        setDocContent((finalText) => {
          if (finalText.trim().length > 100) {
            setDocHistory((prev) => {
              const nextVersion = prev.length + 1;
              setDraftVersion(nextVersion);
              return [
                ...prev,
                {
                  version: nextVersion,
                  content: finalText,
                  citations: currentCitations,
                  timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                },
              ];
            });
          }
          return finalText;
        });
      }

    } catch (err: any) {
      toast.error(err?.message || "对话回复异常");
    } finally {
      setIsStreaming(false);
    }
  };

  // 强化大纲解析器：支持 ```outline、```json、及 Markdown 章节降级提取
  const extractOutlineData = (text: string): OutlineData | null => {
    try {
      // 1. 优先匹配 ```outline 代码块
      const outlineMatch = text.match(/```outline\s*([\s\S]*?)\s*```/);
      if (outlineMatch) {
        const parsed = JSON.parse(outlineMatch[1].trim());
        if (parsed.chapters && Array.isArray(parsed.chapters)) {
          return formatParsedOutline(parsed);
        }
      }

      // 2. 匹配 ```json 代码块
      const jsonMatch = text.match(/```json\s*([\s\S]*?)\s*```/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[1].trim());
        if (parsed.chapters && Array.isArray(parsed.chapters)) {
          return formatParsedOutline(parsed);
        }
      }

      // 3. 正则匹配纯文本中的 Markdown 一级与二级标题
      const headingLines = text.split("\n").filter((l) => l.trim().length > 0);
      const chapters: ChapterNode[] = [];
      let currentChap: ChapterNode | null = null;

      for (const line of headingLines) {
        const cleanLine = line.replace(/[*#]/g, "").trim();
        // 匹配一级标题: "一、" / "第一章" / "# 一、"
        if (/^(一|二|三|四|五|六|七|八|九|十|第[一二三四五六七八九十]章)[\s、.：]/.test(cleanLine)) {
          if (currentChap) chapters.push(currentChap);
          currentChap = {
            id: `chap_${chapters.length}_${Date.now()}`,
            title: cleanLine,
            summary: "阐述本章节核心思想与论述主线",
            subsections: [],
          };
        } else if (
          currentChap &&
          (/^(\d+\.\d+)\s+/.test(cleanLine) || /^[①②③④⑤⑥⑦⑧⑨⑩]/.test(cleanLine) || cleanLine.startsWith("- "))
        ) {
          // 匹配二级标题
          const subTitle = cleanLine.replace(/^[-•]\s*/, "");
          if (subTitle.length > 2 && subTitle.length < 50) {
            currentChap.subsections.push(subTitle);
          }
        }
      }
      if (currentChap) chapters.push(currentChap);

      if (chapters.length >= 2) {
        return {
          title: "拟定文章结构大纲",
          chapters: chapters.map((c, idx) => ({
            ...c,
            subsections: c.subsections.length > 0
              ? c.subsections
              : [`${idx + 1}.1 业务场景切入与应用动因`, `${idx + 1}.2 关键技术架构与机制支撑`, `${idx + 1}.3 实战赋能成效与对比`],
          })),
        };
      }

      return null;
    } catch {
      return null;
    }
  };

  const formatParsedOutline = (parsed: any): OutlineData => {
    return {
      title: parsed.title || "拟定文章结构大纲",
      chapters: (parsed.chapters || []).map((ch: any, idx: number) => ({
        id: `chap_${idx}_${Date.now()}`,
        title: ch.title || `一、 章节 ${idx + 1}`,
        summary: ch.summary || "阐述本章节核心思想与论述主线",
        subsections: Array.isArray(ch.subsections) && ch.subsections.length > 0
          ? ch.subsections
          : [`${idx + 1}.1 业务场景切入与应用动因`, `${idx + 1}.2 关键技术架构与机制支撑`, `${idx + 1}.3 实战赋能成效与对比`],
      })),
    };
  };

  // 充实 Level 2 二级标题的大纲构建逻辑
  const buildFallbackOutlineFromPrompt = (userPrompt: string, aiResponse: string): OutlineData => {
    const topic = userPrompt.slice(0, 20).replace(/[撰写关于请汇报分析报告思考]/g, "").trim() || "主题";
    return {
      title: `《关于${topic}建设应用的思考报告》结构大纲`,
      chapters: [
        {
          id: `chap_fallback_1`,
          title: "一、 发展背景与痛点需求分析",
          summary: `阐述${topic}的发展动向、政策依托与基层警务痛点需求`,
          subsections: [
            "1.1 政策依托与智能化发展大势",
            "1.2 传统警务模式下的三大瓶颈痛点",
            "1.3 大模型与业务融合的切入路径",
          ],
        },
        {
          id: `chap_fallback_2`,
          title: "二、 总体架构与核心技术能力",
          summary: `深入分析${topic}的三层总体架构与核心算力/模型支撑包`,
          subsections: [
            "2.1 三层底座架构与算力设施部署",
            "2.2 多模态感知与深度研报能力",
            "2.3 数据安全治理与隐私合规保障",
          ],
        },
        {
          id: `chap_fallback_3`,
          title: "三、 核心应用场景与实战赋能成效",
          summary: `结合警务实战，剖析大模型在风险防控、侦查打击等场景的真实成效`,
          subsections: [
            "3.1 风险防控：从事后追溯转向事前预警",
            "3.2 侦查打击：从模糊线索到精准锁定",
            "3.3 警务运行：从人适应系统到系统服务人",
          ],
        },
        {
          id: `chap_fallback_4`,
          title: "四、 面临挑战与实施策略建议",
          summary: "客观剖析当前制约因素，提出针对性推进路径与策略建议",
          subsections: [
            "4.1 核心技术自主性与算力资源保障",
            "4.2 复合型人才培养与基层数字素养提升",
            "4.3 小切口应用与顶层设计协同推进",
          ],
        },
      ],
    };
  };

  // 🛡️ 智能过滤文章前言：智能截取首个 # 标题及之后的内容，彻底剥离 "资料已充分覆盖..." 等前置控制句与 --- 分割线！
  const cleanDocContent = (text: string) => {
    let clean = text.replace(/```outline[\s\S]*?```/g, "").trim();
    const titleIdx = clean.search(/^#\s+/m);
    if (titleIdx > 0) {
      clean = clean.slice(titleIdx).trim();
    }
    return clean;
  };

  // 在大纲卡片中更新一级标题或摘要
  const handleUpdateOutlineNode = (
    msgId: string,
    chapId: string,
    field: string,
    value: any
  ) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId || !m.outlineData) return m;
        const updatedChaps = m.outlineData.chapters.map((c) =>
          c.id === chapId ? { ...c, [field]: value } : c
        );
        return {
          ...m,
          outlineData: { ...m.outlineData, chapters: updatedChaps },
        };
      })
    );
  };

  // 在大纲卡片中更新二级标题
  const handleUpdateSubsection = (
    msgId: string,
    chapId: string,
    subIdx: number,
    value: string
  ) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId || !m.outlineData) return m;
        const updatedChaps = m.outlineData.chapters.map((c) => {
          if (c.id !== chapId) return c;
          const nextSubs = [...c.subsections];
          nextSubs[subIdx] = value;
          return { ...c, subsections: nextSubs };
        });
        return {
          ...m,
          outlineData: { ...m.outlineData, chapters: updatedChaps },
        };
      })
    );
  };

  // 在章节下新增二级标题
  const handleAddSubsection = (msgId: string, chapId: string) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId || !m.outlineData) return m;
        const updatedChaps = m.outlineData.chapters.map((c) => {
          if (c.id !== chapId) return c;
          return {
            ...c,
            subsections: [...c.subsections, `新二级子标题 ${c.subsections.length + 1}`],
          };
        });
        return {
          ...m,
          outlineData: { ...m.outlineData, chapters: updatedChaps },
        };
      })
    );
  };

  // 在章节下删除指定二级标题
  const handleDeleteSubsection = (msgId: string, chapId: string, subIdx: number) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId || !m.outlineData) return m;
        const updatedChaps = m.outlineData.chapters.map((c) => {
          if (c.id !== chapId) return c;
          return {
            ...c,
            subsections: c.subsections.filter((_, idx) => idx !== subIdx),
          };
        });
        return {
          ...m,
          outlineData: { ...m.outlineData, chapters: updatedChaps },
        };
      })
    );
  };

  // 在大纲卡片中添加新一级章节
  const handleAddOutlineNode = (msgId: string) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId || !m.outlineData) return m;
        const newChap: ChapterNode = {
          id: `chap_${Date.now()}`,
          title: `新章节 ${m.outlineData.chapters.length + 1}`,
          summary: "请在此输入本章论述重点...",
          subsections: ["子标题 1.1", "子标题 1.2"],
        };
        return {
          ...m,
          outlineData: {
            ...m.outlineData,
            chapters: [...m.outlineData.chapters, newChap],
          },
        };
      })
    );
  };

  // 在大纲卡片中删除一级章节
  const handleDeleteOutlineNode = (msgId: string, chapId: string) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId || !m.outlineData) return m;
        return {
          ...m,
          outlineData: {
            ...m.outlineData,
            chapters: m.outlineData.chapters.filter((c) => c.id !== chapId),
          },
        };
      })
    );
  };

  // 确认大纲与文体风格，触发正文起草
  const handleConfirmOutlineAndDraft = (outline: OutlineData) => {
    setShowDocPanel(true);
    setDocStatus("draft");
    setDraftVersion(1);

    const selectedStyleObj = WRITER_STYLES.find((s) => s.id === selectedStyleId);

    const outlineText = outline.chapters
      .map(
        (c) =>
          `【一级标题】: ${c.title}\n章节重点: ${c.summary}\n【二级标题】:\n` +
          c.subsections.map((sub) => `  - ${sub}`).join("\n")
      )
      .join("\n\n");

    const prompt = `【确认大纲与文体风格】大纲已被我确认！请严格按照以下大纲与【${selectedStyleObj?.label}】文体风格撰写全篇文章：\n\n【标题】：${outline.title}\n【选定文体风格】：${selectedStyleObj?.label} (${selectedStyleObj?.desc})\n\n【确认的树状大纲】：\n${outlineText}\n\n要求：结构严谨、层次分明、严格展开二级标题，并在引用事实处保留 [1], [2] 追溯角标。`;
    handleSendMessage(prompt);
  };

  // 恢复历史版本
  const handleRevertToHistoryVersion = (snap: DocVersionSnapshot) => {
    setDocContent(snap.content);
    if (snap.citations) setDocCitations(snap.citations);
    setSelectedHistoryVersion(snap.version);
    toast.success(`已将文章平滑恢复至历史草稿 V${snap.version} (${snap.timestamp})`);

    setMessages((prev) => [
      ...prev,
      {
        id: `msg_revert_${Date.now()}`,
        role: "assistant",
        content: `↩️ **已恢复历史草稿版本 V${snap.version}**（生成于 ${snap.timestamp}）。您可以基于此版本继续提修改意见与打磨。`,
      },
    ]);
  };

  // 确认定稿并锁定输出最终文件
  const handleLockFinalDocument = () => {
    if (!docContent.trim()) return;
    setDocStatus("final");
    toast.success("已成功确认定稿！文章锁定为终稿文件，可随时导出或沉淀入库。");

    // 向对话发送通知
    setMessages((prev) => [
      ...prev,
      {
        id: `msg_final_${Date.now()}`,
        role: "assistant",
        content: `🎉 **文章已确认定稿！**（版本：V${draftVersion}）\n最终文件已锁定，您可以直接一键导出 Markdown，或沉淀存入 SAG Wiki / 指定信源。`,
      },
    ]);
  };

  // AI 润色与修改命令
  const handleAiPolishCommand = (cmd: string) => {
    if (!docContent.trim()) {
      toast.error("当前暂无文章 Artifact 可供润色，请先在对话中生成文章草稿！");
      return;
    }
    const prompt = `请对当前右侧的文章草稿 (V${draftVersion}) 进行【${cmd}】，优化对应章节段落并更新文章全文。`;
    handleSendMessage(prompt);
  };

  // 上传文件至临时信源
  const handleUploadDocumentFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    try {
      toast.info(`正在上传并解析附件文件 《${file.name}》...`);
      let src = sources.find((s) => s.name === "写作临时信源");
      if (!src) {
        src = await api.createSource({
          name: "写作临时信源",
          description: "智能写作上传的参考背景文件",
        });
        setSources((prev) => [...prev, src!]);
      }
      await api.uploadDocument(src.id, file);
      setSelectedSourceIds((prev) => (prev.includes(src!.id) ? prev : [...prev, src!.id]));
      toast.success(`附件 《${file.name}》 上传解析完成，已自动绑定入写作背景！`);
    } catch (err: any) {
      toast.error(err?.message || "上传附件解析失败");
    }
  };

  // 4. 定稿沉淀至 Wiki
  const handleSaveToKB = async () => {
    if (!docContent.trim()) return;
    setIsSavingToKB(true);
    try {
      const titleMatch = docContent.match(/^#\s+(.+)$/m);
      const title = titleMatch ? titleMatch[1].replace(/[*#]/g, "").trim() : "对话式智能写作定稿";

      const token = getToken();
      const res = await fetch(`${API_BASE}/api/v1/writer/save_to_kb`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          title,
          content: docContent,
          category: "topics",
          keywords: ["对话式写作定稿", "智库文章"],
        }),
      });

      if (!res.ok) throw new Error("归档 Wiki 失败");

      toast.success("终稿文章已成功沉淀存入 SAG Wiki 知识库！");
    } catch (err: any) {
      toast.error(err?.message || "归档 Wiki 异常");
    } finally {
      setIsSavingToKB(false);
    }
  };

  // 存入指定 SAG 信源
  const handleSaveToSource = async () => {
    if (!docContent.trim() || !targetSaveSourceId) return;
    setIsSavingToSource(true);
    try {
      const titleMatch = docContent.match(/^#\s+(.+)$/m);
      const title = titleMatch ? titleMatch[1].replace(/[*#]/g, "").trim() : "对话式智能写作定稿";

      const token = getToken();
      const res = await fetch(`${API_BASE}/api/v1/writer/save_to_source`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          source_id: targetSaveSourceId,
          title,
          content: docContent,
        }),
      });

      if (!res.ok) throw new Error("存入信源失败");

      toast.success("终稿文章已归档存入指定知识库信源！解析抽取队列已触发。");
    } catch (err: any) {
      toast.error(err?.message || "存入信源异常");
    } finally {
      setIsSavingToSource(false);
    }
  };

  const copyDocMarkdown = () => {
    navigator.clipboard.writeText(docContent);
    toast.success("Markdown 已复制到剪贴板");
  };

  const downloadDocMarkdown = () => {
    const blob = new Blob([docContent], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `写作定稿_${docStatus === "final" ? "终稿" : `草稿V${draftVersion}`}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // 点击 Citation 原文卡片触发系统原生 DetailPanel 原文抽屉
  const handleOpenCitationDetail = (citation: Citation) => {
    if (!citation.chunk_id || !citation.source_id) return;
    detailPanel.open({
      kind: "chunk",
      sourceId: citation.source_id,
      chunkId: citation.chunk_id,
      heading: citation.heading || undefined,
      sourceName: citation.source_name || undefined,
    });
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col bg-background text-foreground overflow-hidden">
      {/* 顶部控制与状态栏 */}
      <div className="flex shrink-0 items-center justify-between border-b bg-card/60 px-6 py-2.5 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <PenTool className="size-5" />
          </div>
          <div>
            <h1 className="text-base font-semibold leading-none">分阶段智能写作与长任务助手</h1>
            <p className="mt-1 text-xs text-muted-foreground">
              全多跳 RAG 检索时间轴 ➔ 知识库引用 ➔ 用户大纲卡片干预 ➔ 确认后起草正文
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowDocPanel(!showDocPanel)}
            className="h-8 gap-1.5 text-xs"
          >
            {showDocPanel ? <PanelRightClose className="size-3.5" /> : <PanelRightOpen className="size-3.5" />}
            {showDocPanel ? "隐藏文档面板" : "展开文档 Artifact 面板"}
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setCurrentThreadId(null);
              activeThreadRef.current = null;
              window.history.replaceState(null, "", "/writer");
              setMessages([
                {
                  id: "msg_init",
                  role: "assistant",
                  content: "已开启全新的写作对话！请告诉我您的写作需求。",
                },
              ]);
              setDocContent("");
              setDocStatus("none");
              setDocHistory([]);
              setDraftVersion(1);
              setShowDocPanel(false);
            }}
            className="h-8 gap-1 text-xs text-muted-foreground"
          >
            <RotateCcw className="size-3.5" />
            新建写作会话
          </Button>
        </div>
      </div>

      {/* 主区：对话流 + 可选双栏 Document Artifact 面板（带 CSS 滚动修复 min-h-0） */}
      <div className="grid flex-1 min-h-0 grid-cols-12 overflow-hidden">
        {/* 左侧：对话消息流 */}
        <div
          className={`flex flex-col min-h-0 border-r bg-background overflow-hidden transition-all duration-300 ${
            showDocPanel ? "col-span-6" : "col-span-12"
          }`}
        >
          {/* 消息滚动区：专有 chatScrollRef 局域滚动 */}
          <div ref={chatScrollRef} className="flex-1 min-h-0 overflow-y-auto p-6 space-y-6">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {msg.role === "assistant" && (
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Bot className="size-4" />
                  </div>
                )}

                {msg.role === "user" ? (
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-xl bg-primary px-4 py-3 text-xs text-primary-foreground shadow-sm">
                    {msg.content}
                  </div>
                ) : (
                  <div className="max-w-[88%] space-y-3">
                    {/* 1. 系统原生 AgentActivityTimeline 动态处理过程时间轴 (含全多跳思考与工具步骤) */}
                    {msg.steps && msg.steps.length > 0 && (
                      <AgentActivityTimeline
                        steps={msg.steps}
                        onMatchClick={(match) => {
                          if (match.chunk_id && match.source_id) {
                            detailPanel.open({
                              kind: "chunk",
                              sourceId: match.source_id,
                              chunkId: match.chunk_id,
                              heading: match.heading,
                              sourceName: match.source_name,
                            });
                          }
                        }}
                      />
                    )}

                    {/* 2. 对话消息文本（若包含大纲卡片则显示引导提示；正文起草阶段显示极简说明） */}
                    {msg.outlineData ? (
                      <div className="rounded-xl px-4 py-2.5 text-xs leading-relaxed bg-primary/5 text-primary border border-primary/20 flex items-center gap-2">
                        <Sparkles className="size-3.5 shrink-0" />
                        <span>已基于知识库资料为您生成逻辑结构大纲，请在下方卡片中审核微调或选定文体风格后，点击【确认大纲】开始起草正文：</span>
                      </div>
                    ) : (
                      <div className="rounded-xl px-4 py-3 text-xs leading-relaxed bg-card text-foreground border shadow-2xs whitespace-pre-wrap">
                        {msg.content.replace(/```outline[\s\S]*?```/g, "").replace(/```json[\s\S]*?```/g, "").trim() ||
                          (isStreaming
                            ? "⚙️ 正在为您处理中..."
                            : "处理完成，请在右侧文档 Artifact 面板中预览与打磨正文。")}
                      </div>
                    )}

                    {/* 3. 消息末尾渲染对话模块同款原生的【CitationBlock 引用来源折叠卡片】 */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="pt-1">
                        <CitationBlock
                          citations={msg.citations}
                          onCitationClick={handleOpenCitationDetail}
                        />
                      </div>
                    )}

                    {/* 4. 消息内嵌的【一级标题 + 二级标题 树状大纲编辑卡片】 (仅在 Stage 1 显式呈现) */}
                    {msg.outlineData && (
                      <div className="rounded-xl border border-primary/30 bg-card p-5 space-y-4 shadow-sm">
                        <div className="flex items-center justify-between border-b pb-3">
                          <div className="flex items-center gap-2">
                            <ListOrdered className="size-4 text-primary" />
                            <span className="text-xs font-semibold">{msg.outlineData.title}</span>
                          </div>
                          <span className="text-[10px] rounded bg-amber-500/10 px-2 py-0.5 font-medium text-amber-600 dark:text-amber-400">
                            ⏳ 阶段 2：知识库搜索完成，大纲已生成，等待您的干预与确认
                          </span>
                        </div>

                        {/* 树状章节与二级标题 */}
                        <div className="space-y-4 max-h-80 overflow-y-auto pr-1">
                          {msg.outlineData.chapters.map((chap, chapIdx) => (
                            <div
                              key={chap.id}
                              className="rounded-lg border bg-background p-3.5 space-y-2.5 text-xs"
                            >
                              {/* 一级标题行 */}
                              <div className="flex items-center justify-between gap-2">
                                <span className="size-5 flex items-center justify-center rounded-full bg-primary/10 text-primary text-[11px] font-bold">
                                  {chapIdx + 1}
                                </span>
                                <input
                                  type="text"
                                  value={chap.title}
                                  onChange={(e) =>
                                    handleUpdateOutlineNode(msg.id, chap.id, "title", e.target.value)
                                  }
                                  className="flex-1 font-semibold text-xs bg-transparent border-b border-transparent hover:border-border focus:border-primary focus:outline-none"
                                />
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleDeleteOutlineNode(msg.id, chap.id)}
                                  className="size-6 text-destructive hover:bg-destructive/10"
                                >
                                  <Trash2 className="size-3" />
                                </Button>
                              </div>

                              {/* 章节摘要要点 */}
                              <input
                                type="text"
                                value={chap.summary}
                                onChange={(e) =>
                                  handleUpdateOutlineNode(msg.id, chap.id, "summary", e.target.value)
                                }
                                placeholder="章节论述重点要点..."
                                className="w-full text-[11px] text-muted-foreground bg-muted/30 border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary"
                              />

                              {/* 二级标题列表 */}
                              <div className="pl-6 space-y-1.5 border-l-2 border-primary/20 pt-1">
                                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                                  <span>二级子标题结构：</span>
                                  <button
                                    type="button"
                                    onClick={() => handleAddSubsection(msg.id, chap.id)}
                                    className="text-primary hover:underline text-[10px] flex items-center gap-0.5"
                                  >
                                    <Plus className="size-2.5" /> 增加二级标题
                                  </button>
                                </div>

                                {chap.subsections.map((subText, subIdx) => (
                                  <div key={subIdx} className="flex items-center gap-2">
                                    <span className="text-muted-foreground font-mono text-[10px]">├─</span>
                                    <input
                                      type="text"
                                      value={subText}
                                      onChange={(e) =>
                                        handleUpdateSubsection(msg.id, chap.id, subIdx, e.target.value)
                                      }
                                      className="flex-1 text-[11px] bg-card border rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-primary"
                                    />
                                    <button
                                      type="button"
                                      onClick={() => handleDeleteSubsection(msg.id, chap.id, subIdx)}
                                      className="text-muted-foreground hover:text-destructive p-0.5"
                                    >
                                      <X className="size-3" />
                                    </button>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* 🎨 文章撰写风格与文体建议选择条 */}
                        <div className="rounded-lg border bg-muted/20 p-3 space-y-2">
                          <span className="text-[11px] font-medium text-muted-foreground">
                            🎨 选择文章撰写风格与文体：
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {WRITER_STYLES.map((style) => (
                              <button
                                key={style.id}
                                type="button"
                                onClick={() => setSelectedStyleId(style.id)}
                                className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-all ${
                                  selectedStyleId === style.id
                                    ? "bg-primary text-primary-foreground shadow-2xs"
                                    : "bg-background border text-muted-foreground hover:text-foreground"
                                }`}
                              >
                                {style.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* 卡片动作栏：必须用户手动确认后才起草正文 */}
                        <div className="flex items-center justify-between border-t pt-3">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleAddOutlineNode(msg.id)}
                            className="h-7 gap-1 text-xs"
                          >
                            <Plus className="size-3" />
                            增加一级章节
                          </Button>

                          <Button
                            size="sm"
                            onClick={() => handleConfirmOutlineAndDraft(msg.outlineData!)}
                            className="h-7 gap-1.5 font-medium text-xs shadow-sm bg-primary"
                          >
                            <Sparkles className="size-3" />
                            确认大纲与文体，开始起草正文 (进入阶段 3) ➔
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* 快捷 Prompt 提示芯片 */}
          <div className="flex shrink-0 items-center gap-2 border-t px-6 py-2 bg-muted/10 text-xs overflow-x-auto">
            <span className="text-muted-foreground text-[11px] shrink-0">快捷写作指令：</span>
            {[
              "✨ 帮我撰写一篇关于 SAG 知识库图谱检索的深度研报",
              "🏛️ 总结公安信息化建设成果，起草一篇机关汇报公文",
              "🚀 提炼产品竞争优势，写一篇微信公众号宣传图文",
              "⚡ 一次性直接生成全文关于 SAG 的总结",
            ].map((prompt, pIdx) => (
              <button
                key={pIdx}
                type="button"
                onClick={() => handleSendMessage(prompt)}
                className="shrink-0 rounded-full border bg-background px-3 py-1 text-[11px] font-medium text-foreground hover:bg-primary/10 hover:text-primary transition-colors"
              >
                {prompt}
              </button>
            ))}
          </div>

          {/* 底部 Rich Composer 工具栏与输入框 (绝对平稳局域归位) */}
          <div className="flex shrink-0 border-t p-4 bg-card/20 flex-col gap-2.5">
            {/* 工具栏：信源绑定、Skill 挂载、联网 Toggle、附件上传 */}
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2">
                {/* 信源选择器 */}
                <div className="flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-[11px]">
                  <Database className="size-3 text-primary" />
                  <span className="text-muted-foreground">信源:</span>
                  {sources.length === 0 ? (
                    <span className="text-muted-foreground">全量</span>
                  ) : (
                    <div className="flex items-center gap-1 max-w-40 overflow-x-auto">
                      {sources.map((s) => (
                        <button
                          key={s.id}
                          type="button"
                          onClick={() => toggleSource(s.id)}
                          className={`rounded px-1 text-[10px] ${
                            selectedSourceIds.includes(s.id)
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {s.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Skill 选择下拉 */}
                {availableSkills.length > 0 && (
                  <select
                    value={selectedSkill || ""}
                    onChange={(e) => setSelectedSkill(e.target.value || null)}
                    className="h-6 rounded border bg-background px-2 text-[11px] focus:outline-none"
                  >
                    <option value="">⚡ 选择 Skill 技能...</option>
                    {availableSkills.map((sk) => (
                      <option key={sk.name} value={sk.name}>
                        /{sk.name}
                      </option>
                    ))}
                  </select>
                )}

                {/* 联网搜索 Toggle */}
                <button
                  type="button"
                  onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                  className={`flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] font-medium transition-colors ${
                    webSearchEnabled
                      ? "bg-primary/10 border-primary text-primary"
                      : "bg-background text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Globe2 className="size-3" />
                  {webSearchEnabled ? "🌐 联网开启" : "🌐 联网关闭"}
                </button>
              </div>

              {/* 上传本地参考文档 */}
              <div>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleUploadDocumentFile}
                  className="hidden"
                  accept=".pdf,.doc,.docx,.md,.txt"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  className="h-6 px-2 text-[11px] gap-1"
                >
                  <FileUp className="size-3" />
                  📎 上传临时文档
                </Button>
              </div>
            </div>

            {/* 输入框与发送 */}
            <div className="flex gap-2">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="在此输入写作需求、大纲修改意见、打磨要求（如“第二章补充实际案例”）..."
                className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary resize-none h-16"
              />
              <Button
                onClick={() => handleSendMessage()}
                disabled={isStreaming || !inputMessage.trim()}
                className="h-16 px-5 gap-1.5 font-medium"
              >
                {isStreaming ? (
                  <RefreshCw className="size-4 animate-spin" />
                ) : (
                  <Send className="size-4" />
                )}
                发送
              </Button>
            </div>
          </div>
        </div>

        {/* 右侧：文档 Artifact 实时预览、历史快照恢复与定稿面板 */}
        {showDocPanel && (
          <div className="col-span-6 flex flex-col min-h-0 bg-background border-l overflow-hidden">
            {/* 顶栏：模式切换 + 📜 历史版本下拉与恢复 */}
            <div className="flex shrink-0 items-center justify-between border-b px-4 py-2 bg-card/40 text-xs">
              <div className="flex items-center gap-2">
                <FileText className="size-4 text-primary" />
                <span className="font-semibold">文章 Document Artifact</span>

                {/* 📜 历史版本下拉选择器 */}
                {docHistory.length > 0 && (
                  <div className="flex items-center gap-1">
                    <History className="size-3 text-muted-foreground" />
                    <select
                      value={selectedHistoryVersion ?? draftVersion}
                      onChange={(e) => {
                        const vNum = Number(e.target.value);
                        const snap = docHistory.find((h) => h.version === vNum);
                        if (snap) {
                          setDocContent(snap.content);
                          if (snap.citations) setDocCitations(snap.citations);
                          setSelectedHistoryVersion(vNum);
                        }
                      }}
                      className="h-6 rounded border border-input bg-background px-1.5 text-[11px] focus:outline-none"
                    >
                      {docHistory.map((snap) => (
                        <option key={snap.version} value={snap.version}>
                          版本 V{snap.version} ({snap.timestamp})
                        </option>
                      ))}
                    </select>

                    {selectedHistoryVersion !== null && selectedHistoryVersion !== draftVersion && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const snap = docHistory.find((h) => h.version === selectedHistoryVersion);
                          if (snap) handleRevertToHistoryVersion(snap);
                        }}
                        className="h-6 px-1.5 text-[11px] text-primary gap-0.5"
                      >
                        <RotateCcw className="size-3" />
                        恢复至此版本
                      </Button>
                    )}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-1 rounded-lg border bg-background p-0.5">
                <button
                  type="button"
                  onClick={() => setDocViewMode("preview")}
                  className={`rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
                    docViewMode === "preview"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  👁️ 排版预览
                </button>
                <button
                  type="button"
                  onClick={() => setDocViewMode("edit")}
                  className={`rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
                    docViewMode === "edit"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  ✏️ 源码编辑
                </button>
              </div>
            </div>

            {/* AI 润色与定稿触发条 */}
            <div className="flex shrink-0 items-center justify-between border-b px-4 py-2 bg-muted/10 text-xs">
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground text-[11px]">AI 润色:</span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 px-2 text-[11px]"
                  onClick={() => handleAiPolishCommand("提升机关公文严谨度与表达规范")}
                >
                  ✨ 润色语言
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 px-2 text-[11px]"
                  onClick={() => handleAiPolishCommand("扩写各章节二级标题论述细节")}
                >
                  📝 扩写丰富
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 px-2 text-[11px]"
                  onClick={() => handleAiPolishCommand("精简冗余表达并提炼关键结论")}
                >
                  ✂️ 精简提炼
                </Button>
              </div>

              {docStatus === "draft" && (
                <Button
                  size="sm"
                  onClick={handleLockFinalDocument}
                  className="h-6 px-2.5 text-[11px] gap-1 bg-emerald-600 hover:bg-emerald-700 text-white font-medium shadow-2xs"
                >
                  <Check className="size-3" />
                  ✅ 确认定稿并生成最终文件
                </Button>
              )}
            </div>

            {/* 核心文档内容区（修正 min-h-0 + flex-1，使独立 overflow-y-auto 滚动条平滑滚动） */}
            <div className="flex-1 min-h-0 overflow-y-auto p-6">
              {docViewMode === "edit" ? (
                <textarea
                  value={docContent}
                  onChange={(e) => setDocContent(e.target.value)}
                  placeholder="在此手动编辑修改 Markdown 原文..."
                  className="w-full h-full min-h-[400px] font-mono text-xs leading-relaxed bg-transparent focus:outline-none resize-none"
                />
              ) : docContent ? (
                <div className="space-y-4">
                  <MarkdownContent
                    content={docContent}
                    citations={docCitations}
                    onCitationClick={handleOpenCitationDetail}
                  />

                  {/* 文章末尾渲染对话模块同款原生的【CitationBlock 引用来源折叠卡片】 */}
                  {docCitations.length > 0 && (
                    <div className="pt-4 border-t mt-6">
                      <CitationBlock
                        citations={docCitations}
                        onCitationClick={handleOpenCitationDetail}
                      />
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-center text-muted-foreground space-y-3">
                  <PenTool className="size-10 stroke-[1.25] text-muted-foreground/40" />
                  <p className="text-xs">暂无正文渲染输出，请在左侧确认大纲后开展正文起草</p>
                </div>
              )}
            </div>

            {/* 底栏：导出与沉淀出口 */}
            <div className="flex shrink-0 items-center justify-between border-t px-4 py-2.5 bg-card/60 text-xs">
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={copyDocMarkdown} className="h-7 gap-1 text-[11px]">
                  <Copy className="size-3" />
                  复制
                </Button>
                <Button variant="ghost" size="sm" onClick={downloadDocMarkdown} className="h-7 gap-1 text-[11px]">
                  <Download className="size-3" />
                  导出 .md
                </Button>
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={targetSaveSourceId}
                  onChange={(e) => setTargetSaveSourceId(e.target.value)}
                  className="h-7 rounded border border-input bg-background px-2 text-[11px] focus:outline-none"
                >
                  {sources.map((s) => (
                    <option key={s.id} value={s.id}>
                      信源：{s.name}
                    </option>
                  ))}
                </select>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleSaveToSource}
                  disabled={isSavingToSource || !targetSaveSourceId}
                  className="h-7 gap-1 text-[11px]"
                >
                  <FolderPlus className="size-3" />
                  {isSavingToSource ? "归档中..." : "存入信源"}
                </Button>

                <Button
                  size="sm"
                  onClick={handleSaveToKB}
                  disabled={isSavingToKB}
                  className="h-7 gap-1 text-[11px]"
                >
                  <Check className="size-3" />
                  {isSavingToKB ? "沉淀中..." : "沉淀至 Wiki"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
