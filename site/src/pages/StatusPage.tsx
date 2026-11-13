import { Alert, Card, Col, List, Row, Space, Tag, Typography } from "antd";
import { useMemo } from "react";
import { DataTable } from "../components/DataTable";
import { KpiCard } from "../components/KpiCard";
import { PageHeader } from "../components/layout/PageHeader";
import { CompletenessIndicator } from "../components/status/CompletenessIndicator";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { shortTime } from "../components/status/SourceRef";
import { StatusBadge } from "../components/status/StatusBadge";
import { bundle, getSystemStatus, type EditionRow } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";

const s = t.systemStatus;
type DatasetRow = ReturnType<typeof getSystemStatus>["datasets"][number];
const method = (m: string) => t.exhibitions.methodLabel[m] ?? m;
const LEVEL = { error: "error", warning: "warning", info: "info" } as const;

/** 資料及系統狀態 (W2-05). Every number comes from the dataset index; failures and missing data are shown, not hidden. */
export function StatusPage() {
  const v = useMemo(() => getSystemStatus(), []);
  const failed = (v.acquisition.failed ?? 0) + (v.acquisition.none ?? 0);
  return (
    <>
      <PageHeader title={t.nav.status} />
      <DataOriginBanner origin={bundle.dataOrigin} />
      <Space direction="vertical" size={space.md} style={{ width: "100%", marginTop: space.md }}>
        <Row gutter={[space.md, space.md]}>
          <Col xs={24} sm={12} xl={6}><KpiCard testId="kpi-editions" title={s.editions} value={v.editions.length} suffix={s.unit} /></Col>
          <Col xs={24} sm={12} xl={6}><KpiCard testId="kpi-acq-ok" title={s.acqOk} value={(v.acquisition.succeeded ?? 0) + (v.acquisition.partial ?? 0)} suffix={s.unit} /></Col>
          <Col xs={24} sm={12} xl={6}><KpiCard testId="kpi-acq-failed" title={s.acqFailed} value={failed} suffix={s.unit} /></Col>
          <Col xs={24} sm={12} xl={6}><KpiCard testId="kpi-validation" title={s.validated} value={v.validation.passed ?? 0} suffix={`／ ${v.datasets.length}`} /></Col>
        </Row>
        {failed > 0 && <Alert type="warning" showIcon message={s.failedNote(failed)} data-testid="failed-note" />}

        <Card title={s.acquisitionTitle} data-testid="status-acquisition">
          <DataTable<EditionRow> rowKey="editionId" dataSource={v.editions} pagination={false} scroll={{ x: 960 }} columns={[
            { title: s.edition, render: (_, e) => `${e.exhibitionName}（${e.year}）` },
            { title: s.assessment, render: (_, e) => <Space direction="vertical" size={0}><StatusBadge status={e.assessment.status} /><Typography.Text type="secondary">{method(e.assessment.method)}</Typography.Text></Space> },
            { title: s.lastRun, render: (_, e) => (e.lastAcquisition ? <Space direction="vertical" size={0}><StatusBadge status={e.lastAcquisition.status} /><Typography.Text type="secondary">{shortTime(e.lastAcquisition.finishedAt)}</Typography.Text></Space> : <Typography.Text type="secondary">{t.overview.notAcquired}</Typography.Text>) },
            { title: s.records, render: (_, e) => e.lastAcquisition?.recordsExtracted ?? "—" },
            { title: s.errors, render: (_, e) => (e.lastAcquisition?.errorCount ? <Tag color="red">{e.lastAcquisition.errorCount}</Tag> : e.lastAcquisition ? 0 : "—") },
            { title: s.completeness, render: (_, e) => (e.latest ? <CompletenessIndicator {...e.latest.completeness} /> : <Typography.Text type="secondary">{t.overview.noPackage}</Typography.Text>) },
            { title: s.notes, render: (_, e) => e.lastAcquisition?.notes ?? e.assessment.notes ?? "—" },
          ]} />
        </Card>

        <Card title={s.validationTitle} data-testid="status-validation">
          <DataTable<DatasetRow> rowKey="datasetId" dataSource={v.datasets} pagination={false} scroll={{ x: 960 }} columns={[
            { title: s.dataset, render: (_, d) => <Space direction="vertical" size={0}><Typography.Text code>{d.datasetId}</Typography.Text>{d.isLatest && <Tag color="blue">{s.latest}</Tag>}</Space> },
            { title: s.edition, render: (_, d) => `${d.exhibitionName}（${d.year}）` },
            { title: s.origin, render: (_, d) => (d.dataOrigin === "synthetic" ? t.compare.synthetic : t.compare.collected) },
            { title: s.validation, render: (_, d) => <StatusBadge status={d.validation} /> },
            { title: s.validatedAt, render: (_, d) => (d.validatedAt ? shortTime(d.validatedAt) : "—") },
            { title: s.validator, render: (_, d) => d.validator ?? "—" },
            { title: s.errors, render: (_, d) => d.validationErrors ?? "—" },
            { title: s.completeness, render: (_, d) => <CompletenessIndicator {...d.completeness} /> },
            { title: "Schema", render: (_, d) => d.schemaVersion },
          ]} />
        </Card>

        <Card title={s.noticesTitle(v.notices.length)} data-testid="status-notices">
          {v.notices.length === 0 ? <Typography.Text type="secondary">{s.noNotices}</Typography.Text> : (
            <List size="small" dataSource={v.notices} renderItem={(n) => (
              <List.Item><Alert type={LEVEL[n.level]} showIcon style={{ width: "100%" }} message={n.message} description={shortTime(n.occurredAt)} /></List.Item>
            )} />
          )}
        </Card>
        <Typography.Text type="secondary" data-testid="status-source">{t.overview.source(v.source.index, v.source.schemaVersion, shortTime(v.source.indexGeneratedAt))}</Typography.Text>
      </Space>
    </>
  );
}
