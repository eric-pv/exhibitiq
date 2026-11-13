import { Alert, Card, Descriptions, List, Select, Space, Tag, Typography } from "antd";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { RecommendationCard } from "../components/RecommendationCard";
import { PageHeader } from "../components/layout/PageHeader";
import { ScoreBar, ScoreBreakdown } from "../components/ScoreBreakdown";
import { EmptyState } from "../components/states/States";
import { ClaimBadge, type ClaimKind } from "../components/status/ClaimBadge";
import { CompletenessIndicator } from "../components/status/CompletenessIndicator";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { SourceRefs, shortTime } from "../components/status/SourceRef";
import { claimKindOf, getOpportunityView, getScoredAnalyses, toCsv, type RankingRow } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";

const o = t.opportunities;
const companyLink = (id: string, name: string) => <Link to={`/companies/${encodeURIComponent(id)}`}>{name}</Link>;

/** 商機分析與評分 (W2-04). All content is AI analysis output and is labelled as such; facts keep their verification status. */
export function OpportunitiesPage() {
  const [params, setParams] = useSearchParams();
  const analyses = useMemo(() => getScoredAnalyses(), []);
  const v = useMemo(() => getOpportunityView(params.get("analysis")), [params]);
  if (!v) return (<><PageHeader title={t.nav.opportunities} /><EmptyState message={o.noAnalysis} /></>);
  const a = v.analysis, d = a.detail;
  const subjectName = (e: { entity_type: string; entity_id: string }) => (e.entity_type === "company" ? companyLink(e.entity_id, v.companyName(e.entity_id)) : e.entity_id);

  return (
    <>
      <PageHeader title={t.nav.opportunities} extra={analyses.length > 1 && (
        <Select value={a.analysisId} style={{ minWidth: 260 }} onChange={(id) => setParams({ analysis: id }, { replace: true })}
          options={analyses.map((x) => ({ value: x.analysisId, label: `${x.title}（${shortTime(x.generatedAt)}）` }))} />
      )} />
      <DataOriginBanner origin={v.dataOrigin} />
      <Space direction="vertical" size={space.md} style={{ width: "100%", marginTop: space.md }}>
        <Alert type="info" showIcon icon={<span />} message={<Space wrap><ClaimBadge kind="ai_inferred" />{o.aiNotice}</Space>} data-testid="ai-notice" />
        <Card title={a.title} data-testid="analysis-meta">
          {d.summary && <Typography.Paragraph>{d.summary}</Typography.Paragraph>}
          <Space wrap style={{ marginBottom: space.sm }}>
            <Link to={`/reports?analysis=${encodeURIComponent(a.analysisId)}`} data-testid="opportunity-report-link">{o.openReport}</Link>
            {v.exhibitionId && <Link to={`/exhibitions/${encodeURIComponent(v.exhibitionId)}`} data-testid="opportunity-exhibition-link">{o.openExhibition}</Link>}
          </Space>
          <Descriptions size="small" column={{ xs: 1, md: 2 }} items={[
            { key: "review", label: o.review, children: <Tag>{t.overview.reviewed[a.reviewStatus]}</Tag> },
            { key: "at", label: o.generatedAt, children: shortTime(a.generatedAt) },
            { key: "model", label: o.model, children: [...new Set(d.scores.map((s) => s.modelId))].join("、") },
            { key: "input", label: o.input, children: <Space wrap><Typography.Text code>{a.inputDatasetId}</Typography.Text><CompletenessIndicator {...v.completeness} /></Space> },
            ...(d.skillVersion ? [{ key: "skill", label: o.skill, children: d.skillVersion }] : []),
            { key: "cfg", label: t.analysisConfig.profile, children: a.config ? `${t.settings.modes[a.config.mode].short}｜${a.config.profileId} v${a.config.profileVersion}` : t.analysisConfig.legacy },
          ]} />
          {v.completeness.status !== "complete" && <Alert type="warning" showIcon message={o.incomplete} style={{ marginTop: space.sm }} />}
          {(a.config?.bxrProductsStatus === "draft" || a.config?.bxrProductsStatus === "mixed") && <Alert type="warning" showIcon message={t.analysisConfig.productsUnapproved} style={{ marginTop: space.sm }} />}
        </Card>

        <Card title={o.ranking} data-testid="ranking">
          <DataTable<RankingRow>
            rowKey="key" dataSource={v.ranking} data-testid="ranking-table" scroll={{ x: 760 }}
            csv={() => toCsv(o.csvHeaders, v.ranking.map((r) => [r.rank, r.companyId, r.companyName, r.total, r.max, r.scoredFactors, r.relationship?.type ?? null, r.relationship?.confidence ?? null, a.analysisId, a.reviewStatus, a.dataOrigin]))}
            csvName="opportunity-ranking.csv"
            expandable={{ expandedRowRender: (r) => <ScoreBreakdown score={r.score} view={v} />, defaultExpandedRowKeys: v.ranking.slice(0, 1).map((r) => r.key) }}
            columns={[
              { title: o.rank, dataIndex: "rank", width: 70, render: (x) => x ?? "—" },
              { title: o.company, render: (_, r) => companyLink(r.companyId, r.companyName) },
              { title: o.score, sorter: (x, y) => x.total - y.total, render: (_, r) => <ScoreBar total={r.total} max={r.max} /> },
              { title: o.factors, render: (_, r) => o.factorsOf(r.scoredFactors, r.factorCount) },
              { title: o.relationship, render: (_, r) => (r.relationship
                ? <Space size={4} wrap><Tag>{o.relType[r.relationship.type] ?? r.relationship.type}</Tag>{r.relationship.confidence && <Typography.Text type="secondary">{o.confidence}：{o.level[r.relationship.confidence]}</Typography.Text>}</Space>
                : <Typography.Text type="secondary">{o.relType.unknown}</Typography.Text>) },
            ]}
          />
        </Card>

        {d.recommendations.length > 0 && (
          <Card title={o.recommendations} data-testid="recommendations">
            {d.recommendations.map((r) => <RecommendationCard key={r.recommendationId} r={r} view={v} />)}
          </Card>
        )}

        <Card title={o.conclusions} data-testid="conclusions">
          <List dataSource={d.conclusions} renderItem={(c) => (
            <List.Item>
              <Space direction="vertical" size={4} style={{ width: "100%" }}>
                <Space wrap align="start"><ClaimBadge kind={claimKindOf(c) as ClaimKind} /><span>{c.statement}</span></Space>
                <Space wrap size={4}>
                  {c.subjects.map((s) => <Tag key={s.entity_id}>{subjectName(s)}</Tag>)}
                  {c.confidence && <Typography.Text type="secondary">{o.confidence}：{o.level[c.confidence]}</Typography.Text>}
                </Space>
                {c.rationale && <Typography.Text type="secondary">{o.rationale}：{c.rationale}</Typography.Text>}
                {c.missingData && <Typography.Text type="secondary">{o.missingData}：{c.missingData}</Typography.Text>}
                {c.sourceIds.length > 0 && <SourceRefs sources={c.sourceIds.map(v.source)} />}
              </Space>
            </List.Item>
          )} />
        </Card>

        {d.uncertainties.length > 0 && (
          <Card title={o.uncertainties} data-testid="uncertainties">
            <List size="small" dataSource={d.uncertainties} renderItem={(u) => (
              <List.Item><Space wrap><Tag>{o.impact}：{o.level[u.impact]}</Tag>{u.description}</Space></List.Item>
            )} />
          </Card>
        )}
      </Space>
    </>
  );
}
