export type WorkspaceSection = "search" | "answer" | "writer" | "knowledge" | "skills" | "wiki";

export interface WorkspaceSectionDefinition {
  id: WorkspaceSection;
  href: string;
  shortcut?: string;
}

/**
 * 工作台能力的单一入口配置。
 */
export const WORKSPACE_SECTIONS: readonly WorkspaceSectionDefinition[] = [
  { id: "search", href: "/search", shortcut: "⌘K" },
  { id: "answer", href: "/chat", shortcut: "⌘J" },
  { id: "writer", href: "/writer" },
  { id: "knowledge", href: "/knowledge" },
  { id: "skills", href: "/skills" },
  { id: "wiki", href: "/wiki" },
];

export function isWorkspaceSection(value: unknown): value is WorkspaceSection {
  return value === "search" || value === "answer" || value === "writer" || value === "knowledge" || value === "skills" || value === "wiki";
}

export function workspaceSectionFromPathname(pathname: string): WorkspaceSection | null {
  if (pathname === "/search" || pathname.startsWith("/search/")) return "search";
  if (pathname === "/chat" || pathname.startsWith("/chat/")) return "answer";
  if (pathname === "/writer" || pathname.startsWith("/writer/")) return "writer";
  if (pathname === "/knowledge" || pathname.startsWith("/knowledge/")) return "knowledge";
  if (pathname === "/skills" || pathname.startsWith("/skills/")) return "skills";
  if (pathname === "/wiki" || pathname.startsWith("/wiki/")) return "wiki";
  return null;
}


export function workspaceSectionDefinition(section: WorkspaceSection) {
  return WORKSPACE_SECTIONS.find((item) => item.id === section)!;
}
