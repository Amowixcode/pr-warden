export type Section = "ingest" | "review" | "history" | "prs";

const ITEMS: { id: Section; label: string }[] = [
  { id: "ingest", label: "Ingest" },
  { id: "review", label: "Review" },
  { id: "history", label: "History" },
  { id: "prs", label: "Open PRs" },
];

export function Sidebar({
  active,
  onSelect,
}: {
  active: Section;
  onSelect: (section: Section) => void;
}) {
  return (
    <nav className="sidebar">
      <div className="sidebar-title">pr-warden</div>
      {ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`sidebar-nav-item${item.id === active ? " active" : ""}`}
          onClick={() => onSelect(item.id)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
