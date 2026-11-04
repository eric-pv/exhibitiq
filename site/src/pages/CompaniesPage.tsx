import { Input, Select, Space, Tag, Typography } from "antd";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/layout/PageHeader";
import { ClaimBadge, type ClaimKind } from "../components/status/ClaimBadge";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { bundle, getCompanyRows, matchesQuery, toCsv, type CompanyRow } from "../data/repository";
import { t } from "../i18n/zh-TW";

/** 參展商與企業情報 — list (W2-02). Filters live in the URL so a view can be shared or returned to. */
export function CompaniesPage() {
  const rows = useMemo(() => getCompanyRows(), []);
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "", country = params.get("country"), ex = params.get("exhibition"), vs = params.get("status");
  const set = (k: string, v: string | null) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const filtered = rows.filter((r) => matchesQuery(r, q) && (!country || (r.country ?? "未知") === country) && (!ex || r.exhibitionId === ex) && (!vs || r.verificationStatus === vs));
  const opts = (vals: (string | null)[]) => [...new Set(vals.map((v) => v ?? "未知"))].sort().map((v) => ({ value: v, label: v }));
  const c = t.companies;
  return (
    <>
      <PageHeader title={t.nav.companies} />
      <DataOriginBanner origin={bundle.dataOrigin} />
      <Space wrap style={{ margin: "16px 0" }}>
        <Input.Search allowClear placeholder={c.search} defaultValue={q} onSearch={(v) => set("q", v)} style={{ width: 260 }} data-testid="company-search" />
        <Select allowClear placeholder={c.country} value={country} onChange={(v) => set("country", v ?? null)} options={opts(rows.map((r) => r.country))} style={{ width: 140 }} />
        <Select allowClear placeholder={c.exhibition} value={ex} onChange={(v) => set("exhibition", v ?? null)}
          options={[...new Map(rows.map((r) => [r.exhibitionId, r.exhibitionName]))].map(([value, label]) => ({ value, label }))} style={{ width: 220 }} />
        <Select allowClear placeholder={c.status} value={vs} onChange={(v) => set("status", v ?? null)}
          options={opts(rows.map((r) => r.verificationStatus)).map((o) => ({ ...o, label: t.claim[o.value as ClaimKind] ?? o.value }))} style={{ width: 140 }} />
        <Typography.Text type="secondary" data-testid="company-count">{c.count(filtered.length, rows.length)}</Typography.Text>
      </Space>
      <DataTable<CompanyRow>
        rowKey="key" dataSource={filtered} data-testid="company-table"
        csv={() => toCsv(c.csvHeaders, filtered.map((r) => [r.companyId, r.name, r.aliases.join("; "), r.country, r.exhibitionName, r.year, r.listed ? "listed" : "removed", r.booths.join("; "), r.verificationStatus, r.dataOrigin]))}
        csvName="companies.csv"
        columns={[
          { title: c.name, dataIndex: "name", sorter: (a, b) => a.name.localeCompare(b.name),
            render: (_, r) => <Space direction="vertical" size={0}><Link to={`/companies/${encodeURIComponent(r.companyId)}`} data-testid="company-link">{r.name}</Link>{r.aliases.length > 0 && <Typography.Text type="secondary">{r.aliases.join("、")}</Typography.Text>}</Space> },
          { title: c.country, dataIndex: "country", render: (v) => v ?? "未知", sorter: (a, b) => (a.country ?? "").localeCompare(b.country ?? "") },
          { title: c.exhibition, render: (_, r) => `${r.exhibitionName}（${r.year}）` },
          { title: c.booth, render: (_, r) => (r.booths.length ? r.booths.join("、") : <Typography.Text type="secondary">{c.noBooth}</Typography.Text>) },
          { title: c.listing, render: (_, r) => (r.listed ? <Tag>{c.listed}</Tag> : <Tag color="default">{c.removed}</Tag>) },
          { title: c.status, render: (_, r) => <ClaimBadge kind={r.verificationStatus as ClaimKind} /> },
        ]}
      />
    </>
  );
}
