"use client";

import * as React from "react";
import { BookOpen, RefreshCw, FileText, Sparkles, Folder, Trash2 } from "lucide-react";
import { toast } from "sonner";

interface WikiItem {
  name: string;
  path: string;
}

export default function WikiPage() {
  const [category, setCategory] = React.useState("concepts");
  const [pages, setPages] = React.useState<WikiItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [selectedPage, setSelectedPage] = React.useState<string | null>(null);
  const [pageContent, setPageContent] = React.useState<string>("");
  const [editContent, setEditContent] = React.useState<string>("");
  const [isEditing, setIsEditing] = React.useState(false);

  const fetchPages = React.useCallback(async (cat: string) => {
    setLoading(true);
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiHost}/api/v1/wiki/pages?category=${cat}`);
      if (res.ok) {
        const data = await res.json();
        setPages(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchPages(category);
  }, [category, fetchPages]);

  const loadPageContent = async (cat: string, name: string) => {
    setSelectedPage(name);
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiHost}/api/v1/wiki/pages/${cat}/${name}`);
      if (res.ok) {
        const data = await res.json();
        setPageContent(data.content || "");
        setEditContent(data.content || "");
      }
    } catch (e) {
      toast.error("加载页面失败");
    }
  };

  const savePage = async () => {
    if (!selectedPage) return;
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiHost}/api/v1/wiki/pages/${category}/${selectedPage}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editContent }),
      });
      if (res.ok) {
        toast.success("Wiki 页面已保存");
        setPageContent(editContent);
        setIsEditing(false);
      }
    } catch (e) {
      toast.error("保存失败");
    }
  };

  const deletePage = async (name: string) => {
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiHost}/api/v1/wiki/pages/${category}/${name}`, {
        method: "DELETE",
      });
      if (res.ok) {
        toast.success("页面已删除");
        if (selectedPage === name) {
          setSelectedPage(null);
          setPageContent("");
        }
        fetchPages(category);
      }
    } catch (e) {
      toast.error("删除失败");
    }
  };

  const [rebuilding, setRebuilding] = React.useState(false);

  const rebuildWiki = async () => {
    setRebuilding(true);
    try {
      const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiHost}/api/v1/wiki/rebuild`, { method: "POST" });
      if (res.ok) {
        toast.success("已完成全量知识库扫描，成功自动沉淀 Wiki 概念与实体页面！");
        fetchPages(category);
      }
    } catch (e) {
      toast.error("刷新重建失败");
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <div className="container max-w-6xl mx-auto p-6 space-y-8">
      {/* 头部标题卡片 */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-emerald-500/10 via-teal-500/10 to-cyan-500/10 border border-emerald-500/20 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-semibold mb-1">
            <BookOpen className="size-5" />
            <span>LLM Wiki 自生长架构</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">个人结构化知识图谱与概念沉淀</h1>
          <p className="text-sm text-muted-foreground mt-1">
             Raw 只读原文 / Wiki 概念与实体沉淀 / AGENTS.md Schema 三层规范守护。
          </p>
        </div>
        <button
          onClick={rebuildWiki}
          disabled={rebuilding}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border bg-background hover:bg-muted text-sm font-medium transition-all disabled:opacity-50"
        >
          <RefreshCw className={`size-4 ${rebuilding ? "animate-spin" : ""}`} />
          <span>{rebuilding ? "正在扫描沉淀..." : "刷新索引"}</span>
        </button>
      </div>


      {/* 选项卡与主内容分栏 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* 左侧分类与页面列表 */}
        <div className="space-y-4 md:col-span-1">
          <div className="flex rounded-xl p-1 bg-muted/60 text-xs font-medium">
            {["concepts", "entities", "topics", "sources"].map((cat) => (
              <button
                key={cat}
                onClick={() => {
                  setCategory(cat);
                  setSelectedPage(null);
                }}
                className={`flex-1 py-1.5 rounded-lg capitalize transition-all ${
                  category === cat
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="p-4 rounded-2xl border bg-card space-y-2 min-h-[300px]">
            <div className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5 pb-2 border-b">
              <Folder className="size-3.5" />
              <span>{category.toUpperCase()} 目录</span>
            </div>
            {loading ? (
              <p className="text-xs text-muted-foreground py-4 text-center">加载中...</p>
            ) : pages.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">暂无沉淀页面</p>
            ) : (
              pages.map((p) => (
                <div
                  key={p.name}
                  onClick={() => loadPageContent(category, p.name)}
                  className={`flex items-center justify-between p-2 rounded-xl text-xs cursor-pointer transition-colors ${
                    selectedPage === p.name
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold"
                      : "hover:bg-muted text-foreground"
                  }`}
                >
                  <span className="truncate flex-1">{p.name}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deletePage(p.name);
                    }}
                    className="p-1 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 右侧页面详情与编辑 */}
        <div className="md:col-span-3">
          <div className="p-6 rounded-2xl border bg-card min-h-[400px] space-y-4">
            {selectedPage ? (
              <div>
                <div className="flex items-center justify-between pb-4 border-b">
                  <h3 className="text-lg font-bold flex items-center gap-2">
                    <FileText className="size-5 text-emerald-500" />
                    <span>{selectedPage}</span>
                  </h3>
                  <div className="flex gap-2">
                    {isEditing ? (
                      <>
                        <button
                          onClick={() => setIsEditing(false)}
                          className="px-3 py-1.5 text-xs rounded-lg border"
                        >
                          取消
                        </button>
                        <button
                          onClick={savePage}
                          className="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700"
                        >
                          保存修改
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setIsEditing(true)}
                        className="px-3 py-1.5 text-xs rounded-lg border hover:bg-muted"
                      >
                        编辑 Markdown
                      </button>
                    )}
                  </div>
                </div>

                {isEditing ? (
                  <textarea
                    rows={15}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="w-full mt-4 p-4 text-sm font-mono rounded-xl border bg-background focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                ) : (
                  <div className="prose dark:prose-invert max-w-none pt-4 whitespace-pre-wrap font-mono text-sm">
                    {pageContent}
                  </div>
                )}
              </div>
            ) : (
              <div className="py-24 text-center text-muted-foreground space-y-2">
                <Sparkles className="size-8 mx-auto text-emerald-500/50" />
                <p className="text-sm font-medium">请从左侧选择一个 Wiki 概念页面进行预览或修改</p>
                <p className="text-xs">随着你与智能体的日常问答，这里会自动沉淀新的概念与主题关联。</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
