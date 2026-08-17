import { BookOpen, Library, MessageCircle, PenTool, Search, Sparkles, type LucideIcon } from "lucide-react";

import type { WorkspaceSection } from "@/lib/workspace";

const ICONS = {
  search: Search,
  answer: MessageCircle,
  writer: PenTool,
  knowledge: Library,
  skills: Sparkles,
  wiki: BookOpen,
} satisfies Record<WorkspaceSection, LucideIcon>;


export function WorkspaceSectionIcon({
  section,
  className,
}: {
  section: WorkspaceSection;
  className?: string;
}) {
  const Icon = ICONS[section];
  return <Icon className={className} />;
}
