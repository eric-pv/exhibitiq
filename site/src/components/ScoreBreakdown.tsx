import { Progress, Space, Table, Tag, Typography } from "antd";
import type { OpportunityView } from "../data/repository";
import { claimKindOf } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { color } from "../theme/tokens";
import { ClaimBadge, type ClaimKind } from "./status/ClaimBadge";
import { SourceRefs } from "./status/SourceRef";

const o = t.opportunities;
type Score = OpportunityView["ranking"][number]["score"];
type Factor = Score["factors"][number];

/** Total as a bar; never shown as a percentage of an unknown maximum. */
export function ScoreBar({ total, max }: { total: number; max: number }) {
  return (
    <Space size={8} style={{ minWidth: 160 }}>
      <Progress percent={max ? Math.round((total / max) * 100) : 0} showInfo={false} size="small" strokeColor={color.inference} style={{ width: 90, margin: 0 }} />
      <Typography.Text strong>{total}</Typography.Text><Typography.Text type="secondary">／ {max}</Typography.Text>
    </Space>
  );
}

/**
 * The single score breakdown (DEVELOPMENT_PLAN §3): every factor with its points, rationale, sources and the
 * conclusions it relies on. Factors without evidence show 「資料不足，不計分」 (contract: no evidence → no points).
 */
export function ScoreBreakdown({ score, view }: { score: Score; view: OpportunityView }) {
  return (
    <Table<Factor>
      size="small" rowKey="factorId" pagination={false} dataSource={score.factors} scroll={{ x: 900 }} data-testid="score-breakdown"
      columns={[
        { title: o.factor, dataIndex: "label", width: 140 },
        { title: o.points, width: 150, render: (_, f) => (f.status === "scored"
          ? <Typography.Text data-factor-status="scored">{f.points} ／ {f.max}</Typography.Text>
          : <Tag color={color.warning} data-factor-status="insufficient_data">{o.notScored}（0 ／ {f.max}）</Tag>) },
        { title: o.rationale, dataIndex: "rationale", render: (v) => v ?? "—" },
        { title: o.basis, width: 320, render: (_, f) => (
          <Space direction="vertical" size={4}>
            {f.claimIds.map((id) => { const c = view.claims.get(id); return c && (
              <Space key={id} size={4} align="start"><ClaimBadge kind={claimKindOf(c) as ClaimKind} /><Typography.Text style={{ fontSize: 12 }}>{c.statement}</Typography.Text></Space>
            ); })}
            <SourceRefs sources={f.sourceIds.map(view.source)} />
          </Space>
        ) },
      ]}
    />
  );
}
