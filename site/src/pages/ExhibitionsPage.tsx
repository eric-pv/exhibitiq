import { ArrowLeftOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Descriptions, Input, Select, Space, Typography } from "antd";
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState } from "../components/states/States";
import { CompletenessIndicator } from "../components/status/CompletenessIndicator";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { shortTime } from "../components/status/SourceRef";
import { StatusBadge } from "../components/status/StatusBadge";
import { bundle, getExhibitionRows, matchesExhibition, toCsv, type EditionRow, type ExhibitionRow } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";

const e = t.exhibitions;
const method = (m: string) => e.methodLabel[m] ?? m;
const Completeness = ({ r }: { r: ExhibitionRow }) =>
  r.latestCompleteness ? <CompletenessIndicator {...r.latestCompleteness} /> : <Typography.Text type="secondary">{e.noPackage}</Typography.Text>;

/** 展覽搜尋與新增 — list (W2-01). Exhibitions always come from the dataset index; filters live in the URL. */
export function ExhibitionsPage() {
  const rows = useMemo(() => getExhibitionRows(), []);
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "", country = params.get("country"), year = params.get("year"), st = params.get("status");
  const set = (k: string, v: string | null) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const filtered = rows.filter((r) => matchesExhibition(r, q) && (!country || (r.country ?? "未知") === country) && (!year || r.years.includes(Number(year))) && (!st || r.acquisition.status === st));
  const uniq = (v: string[]) => [...new Set(v)].sort().map((x) => ({ value: x, label: x }));
  return (
    <>
      <PageHeader title={t.nav.exhibitionSearch} />
      <DataOriginBanner origin={bundle.dataOrigin} />
      <Alert type="info" showIcon message={e.addHint} style={{ margin: `${space.md}px 0` }} />
      <Space wrap style={{ marginBottom: space.md }}>
        <Input.Search allowClear placeholder={e.search} defaultValue={q} onSearch={(v) => set("q", v)} style={{ width: 260 }} data-testid="exhibition-search" />
        <Select allowClear placeholder={e.country} value={country} onChange={(v) => set("country", v ?? null)} options={uniq(rows.map((r) => r.country ?? "未知"))} style={{ width: 140 }} />
        <Select allowClear placeholder={e.year} value={year} onChange={(v) => set("year", v ?? null)} options={uniq(rows.flatMap((r) => r.years.map(String)))} style={{ width: 120 }} />
        <Select allowClear placeholder={e.acquisitionStatus} value={st} onChange={(v) => set("status", v ?? null)}
          options={[...new Set(rows.map((r) => r.acquisition.status))].map((s) => ({ value: s, label: t.status[s] ?? s }))} style={{ width: 160 }} />
        <Typography.Text type="secondary" data-testid="exhibition-count">{e.count(filtered.length, rows.length)}</Typography.Text>
      </Space>
      <DataTable<ExhibitionRow>
        rowKey="exhibitionId" dataSource={filtered} data-testid="exhibition-table" scroll={{ x: 900 }} csvName="exhibitions.csv"
        csv={() => toCsv(e.csvHeaders, filtered.map((r) => [r.exhibitionId, r.name, r.country, r.years.join("; "), r.acquisition.method, r.acquisition.status,
          r.latestCompleteness?.status ?? null, r.latestCompleteness?.collected ?? null, r.latestCompleteness?.official ?? null]))}
        columns={[
          { title: e.name, sorter: (a, b) => a.name.localeCompare(b.name), render: (_, r) => <Link to={`/exhibitions/${encodeURIComponent(r.exhibitionId)}`} data-testid="exhibition-link">{r.name}</Link> },
          { title: e.country, render: (_, r) => r.country ?? "未知" },
          { title: e.years, render: (_, r) => r.years.join("、") || "—" },
          { title: e.method, render: (_, r) => method(r.acquisition.method) },
          { title: e.acquisitionStatus, render: (_, r) => <StatusBadge status={r.acquisition.status} /> },
          { title: e.completeness, render: (_, r) => <Completeness r={r} /> },
        ]}
      />
    </>
  );
}

/** 展覽詳情 (W2-01): acquisition method, assessment, each edition's last acquisition, validation and completeness. */
export function ExhibitionDetailPage() {
  const { exhibitionId = "" } = useParams();
  const r = useMemo(() => getExhibitionRows().find((x) => x.exhibitionId === exhibitionId) ?? null, [exhibitionId]);
  const back = <Space wrap><Link to={`/intel?h=${encodeURIComponent(exhibitionId)}`} data-testid="exhibition-intel-link"><Button>{e.viewIntel}</Button></Link><Link to="/exhibitions"><Button icon={<ArrowLeftOutlined />}>{e.back}</Button></Link></Space>;
  if (!r) return (<><PageHeader title={t.nav.exhibitionSearch} extra={back} /><EmptyState message={e.notFound(exhibitionId)} /></>);
  return (
    <>
      <PageHeader title={r.name} extra={back} />
      <DataOriginBanner origin={bundle.dataOrigin} />
      <Space direction="vertical" size={space.md} style={{ width: "100%", marginTop: space.md }}>
        <Card title={e.assessment} data-testid="exhibition-assessment">
          <Descriptions size="small" column={{ xs: 1, md: 2 }} items={[
            { key: "c", label: e.country, children: r.country ?? "未知" },
            { key: "w", label: e.website, children: r.website ? <a href={r.website} target="_blank" rel="noopener noreferrer">{r.website}</a> : "未知" },
            { key: "m", label: e.method, children: method(r.acquisition.method) },
            { key: "s", label: e.acquisitionStatus, children: <StatusBadge status={r.acquisition.status} /> },
            { key: "a", label: e.assessedAt, children: r.acquisition.assessedAt ? shortTime(r.acquisition.assessedAt) : "未知" },
            ...(r.acquisition.reportPath ? [{ key: "r", label: e.report, children: <Typography.Text code>{r.acquisition.reportPath}</Typography.Text> }] : []),
            ...(r.acquisition.notes ? [{ key: "n", label: e.notes, children: r.acquisition.notes }] : []),
          ]} />
        </Card>
        <Card title={e.editions} data-testid="exhibition-editions">
          <DataTable<EditionRow> rowKey="editionId" dataSource={r.editions} pagination={false} scroll={{ x: 900 }} columns={[
            { title: e.edition, render: (_, d) => d.year },
            { title: e.lastAcquisition, render: (_, d) => (d.lastAcquisition
              ? <Space direction="vertical" size={0}><Space><StatusBadge status={d.lastAcquisition.status} />{method(d.lastAcquisition.method)}</Space>
                  <Typography.Text type="secondary">{e.finishedAt}：{shortTime(d.lastAcquisition.finishedAt)}</Typography.Text>
                  {d.lastAcquisition.notes && <Typography.Text type="secondary">{d.lastAcquisition.notes}</Typography.Text>}</Space>
              : <Typography.Text type="secondary">{t.overview.notAcquired}</Typography.Text>) },
            { title: e.validation, render: (_, d) => (d.latest ? <StatusBadge status={d.latest.validation} /> : "—") },
            { title: e.completeness, render: (_, d) => (d.latest ? <CompletenessIndicator {...d.latest.completeness} /> : <Typography.Text type="secondary">{e.noPackage}</Typography.Text>) },
            { title: e.dataset, render: (_, d) => (d.latest
              ? <Space direction="vertical" size={0}><Typography.Text code>{d.latest.datasetId}</Typography.Text>
                  <Link to={`/companies?exhibition=${encodeURIComponent(r.exhibitionId)}`}>{e.viewCompanies}</Link></Space>
              : "—") },
          ]} />
        </Card>
      </Space>
    </>
  );
}
