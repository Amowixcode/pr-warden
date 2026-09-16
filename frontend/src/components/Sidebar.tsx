import {
  Database,
  GitPullRequest,
  History as HistoryIcon,
  Home,
  List,
  Moon,
  Sun,
} from "lucide-react";
import type { Theme } from "../hooks/useTheme";
import { StackedLogo } from "./StackedLogo";

export type Section = "home" | "review" | "history" | "prs" | "ingest";

const ITEMS: { id: Section; label: string; icon: typeof Home }[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "ingest", label: "Ingest a repo", icon: Database },
  { id: "review", label: "Review a PR", icon: GitPullRequest },
  { id: "prs", label: "Open PRs", icon: List },
  { id: "history", label: "History", icon: HistoryIcon },
];

export function Sidebar({
  active,
  onSelect,
  theme,
  onToggleTheme,
}: {
  active: Section | null;
  onSelect: (section: Section) => void;
  theme: Theme | null;
  onToggleTheme: () => void;
}) {
  return (
    <nav className="sidebar">
      <div className="workspace">
        <StackedLogo />
        <span>pr-warden</span>
      </div>

      <div className="nav">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-item${item.id === active ? " active" : ""}`}
              onClick={() => onSelect(item.id)}
            >
              <Icon size={16} />
              {item.label}
            </button>
          );
        })}
      </div>

      <div className="sidebar-footer">
        <button type="button" className="theme-btn" onClick={onToggleTheme}>
          {theme === "dark" ? <Moon size={14} /> : <Sun size={14} />}
          Theme
        </button>
      </div>
    </nav>
  );
}
