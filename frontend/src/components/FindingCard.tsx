import type { AgentKey, AttributedFinding } from "../lib/attributeFindings";
import { parseFinding } from "../lib/parseFinding";
import { StatusTag } from "./StatusTag";

const RAIL_CLASS: Record<AgentKey, string> = {
  security: "rail-sec",
  quality: "rail-qua",
  test: "rail-tst",
};

const AGENT_DOT: Record<AgentKey, "sec" | "qua" | "tst"> = {
  security: "sec",
  quality: "qua",
  test: "tst",
};

const AGENT_LABEL: Record<AgentKey, string> = {
  security: "security",
  quality: "quality",
  test: "test coverage",
};

export function FindingCard({ text, agent }: AttributedFinding) {
  const { location, body } = parseFinding(text);
  return (
    <li className="finding">
      <span className={agent ? RAIL_CLASS[agent] : ""} />
      <span className="finding-body">
        {location && <span className="loc">{location}</span>}
        <span className="what">{body}</span>
        {agent && <StatusTag color={AGENT_DOT[agent]} label={AGENT_LABEL[agent]} />}
      </span>
    </li>
  );
}
