import { Alert, Card, Select, Space, Table, Typography } from "antd";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { ChartPanel } from "../components/ChartPanel";
import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState } from "../components/states/States";
import { ClaimBadge } from "../components/status/ClaimBadge";
import { CompletenessIndicator } from "../components/status/CompletenessIndicator";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { SourceRefs, shortTime } from "../components/status/SourceRef";
import { StatusBadge } from "../components/status/StatusBadge";
import { bundle, getComparison, getHistory, type ComparisonColumn, type HistoryStep } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";

const c = t.compare;
type Row = { key: string; label: React.ReactNode; cell: (col: ComparisonColumn) => React.ReactNode };
const Insufficient = () => <Typography.Text type="secondary">{c.insufficient}</Typography.Text>;

/** 展覽情報與比較 (W3-01): any two or more registered editions side by side; selection lives in the URL. */
export function ComparePage() {
  const [params, setParams] = useSearchParams();
  const all = useMemo(() => getComparison([], null).editions, []);
  const selected = params.get("e")?.split(",").filter(Boolean) ?? all.filter((e) => e.latest).slice(0, 4).map((e) => e.editionId).concat(all.filter((e) => !e.latest).slice(0, 1).map((e) => e.editionId));
  const profileId = params.get("profile") ?? bundle.settings.profiles[0]?.profile.profile_id ?? null;
  const v = useMemo(() => getComparison(selected, profileId), [selected.join(","), profileId]);
  const set = (k: string, val: string) => { const n = new URLSearchParams(params); n.set(k, val); setParams(n, { replace: true }); };
  const src = (col: ComparisonColumn, ids: string[]) => col.dataset ? <SourceRefs sources={ids.map((id) => col.dataset!.sources[id] ?? { sourceId: id, missing: true as const })} /> : null;

  const rows: Row[] = [
    { key: "origin", label: c.origin, cell: (col) => (col.dataset ? (col.dataset.dataOrigin === "synthetic" ? c.synthetic : c.collected) : <Insufficient />) },
    { key: "acq", label: c.lastAcquisition, cell: (col) => (col.lastAcquisition ? <Space direction="vertical" size={0}><StatusBadge status={col.lastAcquisition.status} /><Typography.Text type="secondary">{shortTime(col.lastAcquisition.finishedAt)}</Typography.Text></Space> : <Typography.Text type="secondary">{t.overview.notAcquired}</Typography.Text>) },
    { key: "comp", label: c.completeness, cell: (col) => (col.dataset ? <CompletenessIndicator {...col.dataset.completeness} /> : <Insufficient />) },
    { key: "companies", label: c.companies, cell: (col) => col.companyCount ?? <Insufficient /> },
    { key: "listed", label: c.listed, cell: (col) => col.listedParticipations ?? <Insufficient /> },
    { key: "countries", label: c.countries, cell: (col) => (col.dataset ? col.topCountries.map((x) => `${x.name} ${x.value}`).join("、") || "—" : <Insufficient />) },
    { key: "analyses", label: c.analyses, cell: (col) => (col.dataset ? col.analysisCount : <Insufficient />) },
    ...v.keywords.map((k) => ({
      key: k.term_id, label: <Space size={4}><ClaimBadge kind="ai_inferred" />{k.label}</Space>,
      cell: (col: ComparisonColumn) => {
        if (!col.dataset) return <Insufficient />;
        const x = col.keywords[k.term_id];
        return <Space direction="vertical" size={0}><span>{c.hits(x.count)}{x.share !== null ? `（${Math.round(x.share * 100)}%）` : ""}</span>{x.count > 0 && src(col, x.sourceIds)}</Space>;
      },
    })),
  ];

  return (
    <>
      <PageHeader title={t.nav.exhibitionIntel} />
      <DataOriginBanner origin={bundle.dataOrigin} />
      <Space wrap style={{ margin: `${space.md}px 0` }}>
        <Select mode="multiple" style={{ minWidth: 320 }} value={selected} placeholder={c.pick} data-testid="compare-select"
          options={all.map((e) => ({ value: e.editionId, label: `${e.exhibitionName}（${e.year}）${e.latest ? "" : `｜${c.noPackage}`}` }))}
          onChange={(vals: string[]) => set("e", vals.join(","))} />
        <Select style={{ minWidth: 220 }} value={profileId ?? undefined} placeholder={c.profile} data-testid="compare-profile"
          options={bundle.settings.profiles.map((p) => ({ value: p.profile.profile_id, label: `${p.profile.name}（v${p.profile.version}）` }))}
          onChange={(val: string) => set("profile", val)} />
      </Space>
      <Alert type="info" showIcon style={{ marginBottom: space.md }} message={c.note} />
      {v.columns.length < 2 ? <EmptyState message={c.needTwo} /> : (
        <Space direction="vertical" size={space.md} style={{ width: "100%" }}>
          <Card data-testid="compare-table">
            <Table<Row> size="small" pagination={false} rowKey="key" dataSource={rows} scroll={{ x: 240 + v.columns.length * 220 }}
              columns={[{ title: c.metric, dataIndex: "label", fixed: "left", width: 200 },
                ...v.columns.map((col) => ({ title: col.label, key: col.editionId, width: 220, render: (_: unknown, r: Row) => r.cell(col) }))]} />
          </Card>
          <ChartPanel testId="compare-chart" title={c.chart} note={c.chartNote}
            data={v.columns.filter((col) => col.companyCount !== null).map((col) => ({ name: col.label, value: col.companyCount! }))} />
        </Space>
      )}
      <HistorySection profileId={profileId} exhibitionId={params.get("h")} onPick={(id) => set("h", id)} />
    </>
  );
}

/** 歷史趨勢 (W3-02): one exhibition across years; fewer than two years with a package -> 資料不足. */
function HistorySection(props: { profileId: string | null; exhibitionId: string | null; onPick: (id: string) => void }) {
  const h = t.history;
  const exhibitions = bundle.exhibitions;
  const id = props.exhibitionId ?? exhibitions[0]?.exhibitionId ?? null;
  const v = useMemo(() => (id ? getHistory(id, props.profileId) : null), [id, props.profileId]);
  const unknown = (n: number | null) => (n === null ? <Typography.Text type="secondary">{h.unknown}</Typography.Text> : n);
  return (
    <Card title={h.title} data-testid="history" style={{ marginTop: space.md }}>
      <Space direction="vertical" size={space.md} style={{ width: "100%" }}>
        <Select style={{ minWidth: 260 }} value={id ?? undefined} placeholder={h.exhibition} data-testid="history-select"
          options={exhibitions.map((e) => ({ value: e.exhibitionId, label: e.name }))} onChange={props.onPick} />
        {!v || v.status === "insufficient" ? <EmptyState message={h.insufficient} /> : (
          <>
            <Alert type="info" showIcon message={h.note} />
            <Table size="small" pagination={false} rowKey="year" data-testid="history-years" scroll={{ x: 480 }} dataSource={v.years}
              columns={[{ title: h.year, dataIndex: "year" },
                { title: c.completeness, key: "comp", render: (_: unknown, y: (typeof v.years)[number]) => <CompletenessIndicator {...y.completeness} /> },
                ...v.keywords.map((k) => ({ title: <Space size={4}><ClaimBadge kind="ai_inferred" />{k.label}</Space>, key: k.term_id,
                  render: (_: unknown, y: (typeof v.years)[number]) => `${c.hits(y.keywords[k.term_id].count)}${y.keywords[k.term_id].share !== null ? `（${Math.round(y.keywords[k.term_id].share! * 100)}%）` : ""}` }))]} />
            <Table<HistoryStep> size="small" pagination={false} rowKey={(s) => `${s.fromYear}-${s.toYear}`} data-testid="history-steps" dataSource={v.steps}
              columns={[{ title: h.period, key: "p", render: (_, s) => `${s.fromYear} → ${s.toYear}` },
                { title: h.returning, dataIndex: "returning" },
                { title: h.newCount, key: "n", render: (_, s) => unknown(s.newCount) },
                { title: h.notSeenAgain, key: "g", render: (_, s) => unknown(s.notSeenAgain) }]} />
            <ChartPanel testId="history-chart" title={h.chart} note={h.chartNote} data={v.years.map((y) => ({ name: String(y.year), value: y.companyCount }))} />
          </>
        )}
      </Space>
    </Card>
  );
}
