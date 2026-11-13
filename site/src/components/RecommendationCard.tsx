import { Button, Card, Space, Tag, Typography } from "antd";
import { useState } from "react";
import type { OpportunityView } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";
import { ClaimBadge } from "./status/ClaimBadge";
import { SourceRefs } from "./status/SourceRef";

const o = t.opportunities;
type Rec = OpportunityView["analysis"]["detail"]["recommendations"][number];

/** Sources collapsed to "來源（N）" on screen; always printed in full (print.css). */
export function CollapsedSources({ ids, view, numbering }: { ids: string[]; view: OpportunityView; numbering?: Map<string, number> }) {
  const [open, setOpen] = useState(false);
  if (ids.length === 0) return null;
  return (
    <div>
      <Button type="link" size="small" style={{ padding: 0 }} className="sources-toggle" onClick={() => setOpen(!open)} data-testid="sources-toggle">
        {open ? o.hideSources : o.showSources(ids.length)}
      </Button>
      <div className={open ? undefined : "sources-collapsed"} style={{ marginTop: space.xs }}><SourceRefs sources={ids.map(view.source)} numbering={numbering} /></div>
    </div>
  );
}

/** One recommendation as a readable card (shared by the opportunities page and the report): title first, then reasons, then sources. */
export function RecommendationCard({ r, view, numbering, showClaims = false }: { r: Rec; view: OpportunityView; numbering?: Map<string, number>; showClaims?: boolean }) {
  const line = (label: string, text: string) => (
    <Typography.Paragraph type="secondary" style={{ margin: 0 }}><Typography.Text strong type="secondary">{label}：</Typography.Text>{text}</Typography.Paragraph>
  );
  return (
    <Card size="small" className="report-avoid-break" data-testid="recommendation" style={{ marginBottom: space.md }}>
      <Space size={[space.xs, space.xs]} wrap style={{ marginBottom: space.sm }}>
        <ClaimBadge kind="ai_inferred" /><Tag>{o.recType[r.type] ?? r.type}</Tag><Tag>{o.priorityLabel(o.level[r.priority])}</Tag>
      </Space>
      <Typography.Paragraph strong style={{ fontSize: "1.08em", marginBottom: space.sm }}>{r.statement}</Typography.Paragraph>
      <Space direction="vertical" size={space.xs} style={{ width: "100%" }}>
        {r.rationale && line(o.rationale, r.rationale)}
        {r.assumptions.length > 0 && line(o.assumptions, r.assumptions.join("；"))}
        {showClaims && r.claimIds.length > 0 && line(o.basedOn, r.claimIds.map((id) => view.claims.get(id)?.statement ?? id).join("；"))}
        {r.uncertaintyIds.length > 0 && line(o.uncertainties, r.uncertaintyIds.map((id) => view.uncertainties.get(id)?.description ?? id).join("；"))}
        <CollapsedSources ids={r.sourceIds} view={view} numbering={numbering} />
      </Space>
    </Card>
  );
}
