"use client";

import * as React from "react";
import { Sparkles, Plus, Play, ToggleLeft, ToggleRight } from "lucide-react";
import { toast } from "sonner";

interface SkillItem {
  name: string;
  version: string;
  description: string;
  skill_type: string;
  is_builtin: boolean;
  enabled: boolean;

}

export default function SkillsPage() {
  const [skills, setSkills] = React.useState<SkillItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [testSkill, setTestSkill] = React.useState<string | null>(null);
  const [testInput, setTestInput] = React.useState("");
  const [testOutput, setTestOutput] = React.useState("");
  const [running, setRunning] = React.useState(false);

  // 新建表单
  const [showCreate, setShowCreate] = React.useState(false);
  const [newSkillName, setNewSkillName] = React.useState("");
  const [newSkillDesc, setNewSkillDesc] = React.useState("");
  const [newSkillKeywords, setNewSkillKeywords] = React.useState("");
  const [newSkillPrompt, setNewSkillPrompt] = React.useState("");

  const fetchSkills = React.useCallback(async () => {
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiHost}/api/v1/skills`);
      if (res.ok) {
        const data = await res.json();
        setSkills(data);
      }
    } catch {
      // 忽略或处理异常
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  const toggleSkill = async (name: string, currentEnabled: boolean) => {
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiHost}/api/v1/skills/${name}/toggle?enabled=${!currentEnabled}`, {
        method: "POST",
      });
      if (res.ok) {
        toast.success(`技能 ${name} 已${!currentEnabled ? "启用" : "禁用"}`);
        fetchSkills();
      }
    } catch {
      toast.error("操作失败");
    }
  };

  const handleRunTest = async (name: string) => {
    if (!testInput.trim()) return;
    setRunning(true);
    setTestOutput("");
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiHost}/api/v1/skills/${name}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_text: testInput }),
      });
      if (res.ok && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          setTestOutput((prev) => prev + decoder.decode(value));
        }
      }
    } catch {
      setTestOutput("执行出错，请确认后端 API 已正常启动。");
    } finally {
      setRunning(false);
    }
  };

  const handleCreateSkill = async () => {
    if (!newSkillName || !newSkillDesc) {
      toast.error("请填写技能名称与描述");
      return;
    }
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiHost}/api/v1/skills/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newSkillName,
          description: newSkillDesc,
          keywords: newSkillKeywords.split(",").map((k) => k.trim()).filter(Boolean),
          system_prompt: newSkillPrompt || "你是一位专业助手。",
        }),
      });
      if (res.ok) {
        toast.success("技能创建成功！");
        setShowCreate(false);
        setNewSkillName("");
        setNewSkillDesc("");
        setNewSkillKeywords("");
        setNewSkillPrompt("");
        fetchSkills();
      }
    } catch {
      toast.error("创建失败");
    }
  };

  return (
    <div className="container max-w-6xl mx-auto p-6 space-y-8">
      {/* 头部标题卡片 */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-purple-500/10 via-indigo-500/10 to-blue-500/10 border border-indigo-500/20 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 font-semibold mb-1">
            <Sparkles className="size-5" />
            <span>Skill 扩展系统</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">个人技能库与能力编排</h1>
          <p className="text-sm text-muted-foreground mt-1">
            支持零代码声明式 Prompt 技能、工具封装、工作流多步编排与热重载扩展。
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 text-white font-medium text-sm hover:bg-indigo-700 transition-all shadow-md hover:shadow-indigo-500/20"
        >
          <Plus className="size-4" />
          <span>新建技能</span>
        </button>
      </div>

      {/* 快捷新建技能模态框 */}
      {showCreate && (
        <div className="p-6 rounded-2xl border bg-card/80 backdrop-blur-md space-y-4 shadow-lg animate-in fade-in zoom-in duration-200">
          <h3 className="text-lg font-bold flex items-center gap-2">
            <Sparkles className="size-5 text-indigo-500" />
            新建自定义技能
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground">技能名称 (唯一 ID)</label>
              <input
                type="text"
                placeholder="如: my_translator"
                value={newSkillName}
                onChange={(e) => setNewSkillName(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-sm rounded-lg border bg-background focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">触发关键词 (逗号分隔)</label>
              <input
                type="text"
                placeholder="如: 翻译, translate"
                value={newSkillKeywords}
                onChange={(e) => setNewSkillKeywords(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-sm rounded-lg border bg-background focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">技能描述</label>
            <input
              type="text"
              placeholder="简要描述技能的功能与用途"
              value={newSkillDesc}
              onChange={(e) => setNewSkillDesc(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm rounded-lg border bg-background focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">系统提示词 (System Prompt)</label>
            <textarea
              rows={3}
              placeholder="设定专属于该技能的 Prompt 角色约束..."
              value={newSkillPrompt}
              onChange={(e) => setNewSkillPrompt(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm rounded-lg border bg-background focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 text-sm rounded-lg border hover:bg-muted"
            >
              取消
            </button>
            <button
              onClick={handleCreateSkill}
              className="px-4 py-2 text-sm rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700"
            >
              提交保存
            </button>
          </div>
        </div>
      )}

      {/* 技能卡片列表网格 */}
      {loading ? (
        <div className="py-12 text-center text-muted-foreground">正在加载 Skill 列表...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {skills.map((skill) => (
            <div
              key={skill.name}
              className={`p-5 rounded-2xl border transition-all duration-200 hover:shadow-lg flex flex-col justify-between ${
                skill.enabled
                  ? "bg-card border-border/80"
                  : "bg-muted/40 border-border/40 opacity-70"
              }`}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-base">{skill.name}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-mono">
                      v{skill.version}
                    </span>
                  </div>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                      skill.skill_type === "workflow"
                        ? "bg-purple-500/10 text-purple-600 dark:text-purple-400"
                        : skill.skill_type === "tool"
                        ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                        : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                    }`}
                  >
                    {skill.skill_type}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-2 min-h-[32px] mb-4">
                  {skill.description}
                </p>
              </div>

              <div className="pt-4 border-t flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => toggleSkill(skill.name, skill.enabled)}
                    className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                    title={skill.enabled ? "点击禁用" : "点击启用"}
                  >
                    {skill.enabled ? (
                      <ToggleRight className="size-5 text-indigo-600" />
                    ) : (
                      <ToggleLeft className="size-5 text-muted-foreground" />
                    )}
                  </button>
                  <span className="text-xs text-muted-foreground">
                    {skill.is_builtin ? "内置" : "自定义"}
                  </span>
                </div>
                <button
                  onClick={() => {
                    setTestSkill(skill.name);
                    setTestOutput("");
                  }}
                  className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-secondary text-secondary-foreground font-medium hover:bg-secondary/80 transition-colors"
                >
                  <Play className="size-3" />
                  <span>测试技能</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 技能调试测试面板 */}
      {testSkill && (
        <div className="p-6 rounded-2xl border bg-card shadow-lg space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold flex items-center gap-2">
              <Play className="size-4 text-indigo-500" />
              正在测试技能：<span className="text-indigo-600">{testSkill}</span>
            </h3>
            <button
              onClick={() => setTestSkill(null)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              关闭测试面板
            </button>
          </div>
          <div className="space-y-2">
            <input
              type="text"
              placeholder="输入测试文本需求（例如：帮我撰写一份项目进度周报）"
              value={testInput}
              onChange={(e) => setTestInput(e.target.value)}
              className="w-full px-4 py-2.5 text-sm rounded-xl border bg-background focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              onClick={() => handleRunTest(testSkill)}
              disabled={running}
              className="px-4 py-2 text-sm font-medium rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {running ? "正在运行技能..." : "立即执行"}
            </button>
          </div>
          {testOutput && (
            <div className="p-4 rounded-xl border bg-muted/50 text-sm font-mono whitespace-pre-wrap max-h-60 overflow-y-auto">
              {testOutput}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
