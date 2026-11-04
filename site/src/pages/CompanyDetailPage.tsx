import { ArrowLeftOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Descriptions, Grid, List, Space, Tag, Typography } from "antd";
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState } from "../components/states/States";
import { ClaimBadge, type ClaimKind } from "../components/status/ClaimBadge";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { SourceRef, SourceRefs, shortTime } from "../components/status/SourceRef";
import { getCompanyDetail, type CompanyDetail, type ResolvedSource } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { layout, space } from "../theme/tokens";

const c = t.companyDetail;
type Participation = CompanyDetail["participations"][number];

const Unknown = () => <Typography.Text type="secondary">{c.unknown}</Typography.Text>;
const Time = ({ iso }: { iso: string | null }) => (iso ? <span title={iso}>{shortTime(iso)}</span> : <Unknown />);

function renderValue(key: string, value: string | string[] | null) {
  if (value === null) return <Unknown />;
  if (Array.isArray(value)) return value.join("、");
  if (key === "website" && /^https?:\/\//.test(value)) return <a href={value} target="_blank" rel="noopener noreferrer">{value}</a>;
  if (key === "first_seen_at") return <Time iso={value} />;
  return value;
}

/** 企業詳情 (W2-03): every field shows its source; facts only — AI analysis is on the opportunities page (W2-04). */
export function CompanyDetailPage() {
  const { companyId = "" } = useParams();
  const d = useMemo(() => getCompanyDetail(companyId), [companyId]);
  const isMobile = !Grid.useBreakpoint()[layout.mobileBreakpoint];
  const back = <Link to="/companies"><Button icon={<ArrowLeftOutlined />}>{c.back}</Button></Link>;
  if (!d) return (<><PageHeader title={t.nav.companies} extra={back} /><EmptyState message={c.notFound(companyId)} /></>);

  // One number per distinct source on the page, in order of first citation.
  const numbering = new Map<string, number>();
  const all: ResolvedSource[] = [...d.fields.flatMap((f) => f.sources), ...d.aliases.flatMap((a) => a.sources), ...d.participations.flatMap((p) => p.sources)];
  for (const s of all) if (!numbering.has(s.sourceId)) numbering.set(s.sourceId, numbering.size + 1);
  const distinct = [...new Map(all.map((s) => [s.sourceId, s])).values()];

  return (
    <>
      <PageHeader title={d.name} extra={back} />
      <DataOriginBanner origin={d.dataOrigin} />
      <Space wrap style={{ margin: `${space.md}px 0` }} data-testid="company-meta">
        <ClaimBadge kind={d.verificationStatus as ClaimKind} />
        <Typography.Text type="secondary">{c.lastUpdated}：<Time iso={d.lastUpdated} /></Typography.Text>
        <Typography.Text type="secondary">{c.packageCreatedAt}：<Time iso={d.packageCreatedAt} />（{c.dataset} <Typography.Text code>{d.datasetId}</Typography.Text>）</Typography.Text>
      </Space>
      {d.status === "merged" && d.mergedInto && (
        <Alert type="info" showIcon style={{ marginBottom: space.md }} message={c.merged(d.mergedInto)}
          action={<Link to={`/companies/${encodeURIComponent(d.mergedInto)}`}>{c.openMerged}</Link>} />
      )}
      <Space direction="vertical" size={space.md} style={{ width: "100%" }}>
        <Card title={c.basic} data-testid="company-fields">
          <Descriptions column={1} bordered size="small" layout={isMobile ? "vertical" : "horizontal"} items={d.fields.map((f) => ({
            key: f.key, label: c.field[f.key] ?? f.key,
            children: (
              <Space direction="vertical" size={2} data-field={f.key}>
                <span>{renderValue(f.key, f.value)}</span>
                {f.value !== null && (
                  <Space size={4} wrap>
                    <SourceRefs sources={f.sources} numbering={numbering} />
                    {f.recordLevel && <Typography.Text type="secondary" style={{ fontSize: 12 }}>{c.recordLevel}</Typography.Text>}
                  </Space>
                )}
              </Space>
            ),
          }))} />
          {d.notes && <Typography.Paragraph type="secondary" style={{ marginTop: space.sm, marginBottom: 0 }}>{d.notes}</Typography.Paragraph>}
        </Card>

        <Card title={c.aliases} data-testid="company-aliases">
          {d.aliases.length === 0 ? <Typography.Text type="secondary">{c.noAliases}</Typography.Text> : (
            <List size="small" dataSource={d.aliases} renderItem={(a) => (
              <List.Item><Space wrap><span>{a.name}</span>{a.lang && <Tag>{a.lang}</Tag>}<SourceRefs sources={a.sources} numbering={numbering} /></Space></List.Item>
            )} />
          )}
        </Card>

        <Card title={c.participations} data-testid="company-participations">
          <DataTable<Participation> rowKey="key" dataSource={d.participations} pagination={false} scroll={{ x: 1100 }} columns={[
            { title: c.col.exhibition, render: (_, p) => `${p.exhibitionName}（${p.year}）` },
            { title: c.col.nameAsListed, dataIndex: "nameAsListed" },
            { title: c.col.type, render: (_, p) => c.participationType[p.participationType] ?? p.participationType },
            { title: c.col.booth, render: (_, p) => (p.booth ? [p.hall, p.booth].filter(Boolean).join(" / ") : <Typography.Text type="secondary">{t.companies.noBooth}</Typography.Text>) },
            { title: t.companies.listing, render: (_, p) => <Tag>{p.listingStatus === "listed" ? t.companies.listed : t.companies.removed}</Tag> },
            { title: c.col.categories, render: (_, p) => (p.categories.length ? p.categories.join("、") : <Unknown />) },
            { title: c.col.seen, render: (_, p) => <><Time iso={p.firstSeenAt} /> ／ <Time iso={p.lastSeenAt} /></> },
            { title: c.col.status, render: (_, p) => <ClaimBadge kind={p.verificationStatus as ClaimKind} /> },
            { title: c.col.sources, render: (_, p) => <SourceRefs sources={p.sources} numbering={numbering} /> },
          ]} />
        </Card>

        <Card title={c.sources} data-testid="company-sources">
          <List size="small" dataSource={distinct} renderItem={(s) => (
            <List.Item>
              <Space wrap>
                <SourceRef source={s} index={numbering.get(s.sourceId)} />
                {!("missing" in s) && <>
                  <span>{s.title ?? s.sourceId}</span>
                  <Typography.Text type="secondary">{t.source.retrievedAt}：<Time iso={s.retrievedAt} /></Typography.Text>
                </>}
              </Space>
            </List.Item>
          )} />
        </Card>
      </Space>
    </>
  );
}
