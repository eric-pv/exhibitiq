import { Alert, Descriptions, List, Space, Tag, Typography } from "antd";
import type { ReactNode } from "react";
import { bundle, claimKindOf, type OpportunityView } from "../data/repository";
import type { Bundle } from "../data/types";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";
import { ScoreBar, ScoreBreakdown } from "./ScoreBreakdown";
import { ClaimBadge, type ClaimKind } from "./status/ClaimBadge";
import { CompletenessIndicator } from "./status/CompletenessIndicator";
import { SourceRefs, shortTime } from "./status/SourceRef";

const o = t.opportunities;

/**
 * The single report renderer (DEVELOPMENT_PLAN §3, W3-04). Web and PDF (print) use this component and the same
 * analysis JSON; sections and their order come from skills/exhibitiq/templates/report-templates.json, the same
 * file the Markdown report uses (A2-13), so web, PDF and Markdown cannot diverge.
 */
export function ReportViewer({ view, b = bundle }: { view: OpportunityView; b?: Bundle }) {
  const a = view.analysis, d = a.detail, tpl = b.reportTemplates;
  const type = tpl.types[a.analysisType];
  const ds = b.datasets[a.inputDatasetId];
  const ex = b.exhibitions.find((e) => e.exhibitionId === ds.exhibitionId);
  const year = ex?.editions.find((e) => e.editionId === ds.editionId)?.year;
  const num = new Map(a.evidenceSourceIds.map((id, i) => [id, i + 1]));
  const refs = (ids: string[]) => <SourceRefs sources={ids.map(view.source)} numbering={num} />;
  const order = [...type.sections];
  for (const [sec, has] of [["scores", d.scores.length > 0], ["relationships", d.relationships.length > 0]] as const)
    if (has && !order.includes(sec)) order.splice(order.indexOf("recommendations"), 0, sec);

  const body: Record<string, () => ReactNode> = {
    header: () => (
      <Descriptions size="small" column={1} items={[
        { key: "type", label: "報告類型", children: type.label },
        { key: "ex", label: "展覽／屆次", children: `${ex?.name ?? ds.exhibitionId}／${year ?? ds.editionId}` },
        { key: "ds", label: o.input, children: <Typography.Text code>{a.inputDatasetId}（{a.inputHash}）</Typography.Text> },
        { key: "sk", label: o.skill, children: `${d.skillVersion ?? "—"}｜${o.generatedAt}：${shortTime(a.generatedAt)}` },
        { key: "rv", label: o.review, children: <Tag>{t.overview.reviewed[a.reviewStatus]}</Tag> },
      ]} />
    ),
    data_status: () => (
      <Space direction="vertical">
        <Typography.Text strong>{a.dataOrigin === "synthetic" ? t.origin.synthetic : t.origin.collected}</Typography.Text>
        <CompletenessIndicator {...ds.completeness} />
        {ds.completeness.status !== "complete" && <Alert type="warning" showIcon message={o.incomplete} />}
      </Space>
    ),
    summary: () => d.summary,
    conclusions: () => d.conclusions.length > 0 && (
      <List size="small" dataSource={d.conclusions} renderItem={(c) => (
        <List.Item><Space direction="vertical" size={2}>
          <Space align="start" wrap><ClaimBadge kind={claimKindOf(c) as ClaimKind} /><span>{c.statement}</span></Space>
          {c.claimType === "inference" && <Typography.Text type="secondary">{o.confidence}：{c.confidence && o.level[c.confidence]}；{o.rationale}：{c.rationale}</Typography.Text>}
          {c.missingData && <Typography.Text type="secondary">{o.missingData}：{c.missingData}</Typography.Text>}
          {c.sourceIds.length > 0 && refs(c.sourceIds)}
        </Space></List.Item>
      )} />
    ),
    scores: () => view.ranking.length > 0 && (
      <Space direction="vertical" style={{ width: "100%" }}>
        {view.ranking.map((r) => (
          <div key={r.key} className="report-avoid-break">
            <Space wrap><Typography.Text strong>第 {r.rank ?? "—"} 名：{r.companyName}</Typography.Text><ScoreBar total={r.total} max={r.max} /><ClaimBadge kind="ai_inferred" /></Space>
            <ScoreBreakdown score={r.score} view={view} />
          </div>
        ))}
      </Space>
    ),
    relationships: () => d.relationships.length > 0 && (
      <List size="small" dataSource={d.relationships} renderItem={(r) => (
        <List.Item><Space wrap><span>{view.companyName(r.companyId)}</span><Tag>{o.relType[r.type] ?? r.type}</Tag><ClaimBadge kind="ai_inferred" />
          {r.confidence && <Typography.Text type="secondary">{o.confidence}：{o.level[r.confidence]}</Typography.Text>}
          <span>{r.rationale}</span>{refs(r.sourceIds)}</Space></List.Item>
      )} />
    ),
    recommendations: () => d.recommendations.length > 0 && (
      <List size="small" dataSource={d.recommendations} renderItem={(r) => (
        <List.Item><Space direction="vertical" size={2}>
          <Space wrap><ClaimBadge kind="ai_inferred" /><Tag>優先度：{o.level[r.priority]}</Tag><Typography.Text strong>{r.statement}</Typography.Text></Space>
          {r.rationale && <Typography.Text type="secondary">{o.rationale}：{r.rationale}</Typography.Text>}
          {r.assumptions.length > 0 && <Typography.Text type="secondary">{o.assumptions}：{r.assumptions.join("；")}</Typography.Text>}
          {r.claimIds.length > 0 && <Typography.Text type="secondary">依據結論：{r.claimIds.map((id) => view.claims.get(id)?.statement ?? id).join("；")}</Typography.Text>}
          {r.uncertaintyIds.length > 0 && <Typography.Text type="secondary">{o.uncertainties}：{r.uncertaintyIds.map((id) => view.uncertainties.get(id)?.description ?? id).join("；")}</Typography.Text>}
          {refs(r.sourceIds)}
        </Space></List.Item>
      )} />
    ),
    uncertainties: () => d.uncertainties.length > 0 && (
      <List size="small" dataSource={d.uncertainties} renderItem={(u) => <List.Item><Space wrap><Tag>{o.impact}：{o.level[u.impact]}</Tag>{u.description}</Space></List.Item>} />
    ),
    sources: () => (
      <List size="small" dataSource={a.evidenceSourceIds.map(view.source)} renderItem={(s) => (
        <List.Item><Space wrap>
          <Typography.Text>[{num.get(s.sourceId)}]</Typography.Text><Typography.Text code>{s.sourceId}</Typography.Text>
          {!("missing" in s) && <>
            <span>{t.source.type[s.sourceType] ?? s.sourceType}</span>
            {s.url && <Typography.Text>{s.url}</Typography.Text>}
            <Typography.Text type="secondary">{t.source.retrievedAt}：{shortTime(s.retrievedAt)}</Typography.Text>
            <Typography.Text code>{s.contentSha256}</Typography.Text>
          </>}
        </Space></List.Item>
      )} />
    ),
  };

  return (
    <article className="report" data-testid="report-viewer">
      <Typography.Title level={3}>{a.title}</Typography.Title>
      {order.map((sec) => (
        <section key={sec} data-section={sec} style={{ marginBottom: space.lg }}>
          <Typography.Title level={4}>{tpl.section_titles[sec]}</Typography.Title>
          {body[sec]() || <Typography.Text type="secondary">無</Typography.Text>}
        </section>
      ))}
    </article>
  );
}
