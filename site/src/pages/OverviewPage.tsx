import { Alert, Card, Col, List, Row, Space, Typography } from "antd";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ChartPanel } from "../components/ChartPanel";
import { KpiCard } from "../components/KpiCard";
import { PageHeader } from "../components/layout/PageHeader";
import { CompletenessIndicator } from "../components/status/CompletenessIndicator";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { StatusBadge, type PipelineStatus } from "../components/status/StatusBadge";
import { EmptyState } from "../components/states/States";
import { getOverview } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";

const statusLabel = (s: string) => (s === "none" ? t.overview.notAcquired : t.status[s as PipelineStatus] ?? s);

/** 系統總覽 (W1-03). Every number comes from the bundle built from schema-validated files. */
export function OverviewPage() {
  const o = useMemo(() => getOverview(), []);
  const acquisitionData = useMemo(() => o.acquisitionDistribution.map((d) => ({ name: statusLabel(d.status), value: d.value })), [o]);
  const go = useNavigate();
  return (
    <>
      <PageHeader title={t.nav.overview} />
      <DataOriginBanner origin={o.dataOrigin} />
      <Space direction="vertical" size="large" style={{ width: "100%", marginTop: space.md }}>
        <Row gutter={[space.md, space.md]}>
          <Col xs={24} sm={12} xl={6}>
            <KpiCard testId="kpi-exhibitions" title={t.overview.exhibitions} value={o.exhibitionCount} suffix={t.overview.unitExhibition} onOpen={() => go("/exhibitions")} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <KpiCard
              testId="kpi-companies" title={t.overview.companies} value={o.companyCount} suffix={t.overview.unitCompany} onOpen={() => go("/companies")}
              footer={o.companyCompleteness && <CompletenessIndicator {...o.companyCompleteness} />}
            />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <KpiCard testId="kpi-analyzed" title={t.overview.analyzedCompanies} value={o.analyzedCompanyCount} suffix={t.overview.unitCompany} onOpen={() => go("/opportunities")} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <KpiCard testId="kpi-priority" title={t.overview.highPriority} value={o.highPriorityCount} suffix={t.overview.unitItem} onOpen={() => go("/opportunities")} />
          </Col>
        </Row>

        <Row gutter={[space.md, space.md]}>
          <Col xs={24} lg={12}>
            <ChartPanel testId="chart-country" title={t.overview.countryChart} note={t.overview.countryChartNote} data={o.countryDistribution} onSelect={(name) => go(`/companies?country=${encodeURIComponent(name)}`)} />
          </Col>
          <Col xs={24} lg={12}>
            <ChartPanel
              testId="chart-acquisition" title={t.overview.acquisitionChart} note={t.overview.acquisitionChartNote}
              data={acquisitionData} onSelect={() => go("/status")}
            />
          </Col>
        </Row>

        <Row gutter={[space.md, space.md]}>
          <Col xs={24} lg={16}>
            <Card title={t.overview.dataStatus} data-testid="data-status">
              {o.editions.length === 0 ? <EmptyState /> : (
                <List
                  dataSource={o.editions}
                  renderItem={(r) => (
                    <List.Item key={r.editionId}>
                      <Space direction="vertical" size={space.xs} style={{ width: "100%" }}>
                        <Typography.Text strong>{r.exhibitionName}（{r.year}）</Typography.Text>
                        <Space wrap>
                          <Typography.Text type="secondary">{t.overview.assessment}</Typography.Text>
                          <StatusBadge status={r.assessment.status} />
                          <Typography.Text type="secondary">{t.overview.lastAcquisition}</Typography.Text>
                          {r.lastAcquisition ? <StatusBadge status={r.lastAcquisition.status} /> : <Typography.Text>{t.overview.notAcquired}</Typography.Text>}
                          {r.latest && (<><Typography.Text type="secondary">{t.overview.validation}</Typography.Text><StatusBadge status={r.latest.validation} /></>)}
                        </Space>
                        {r.latest ? <CompletenessIndicator {...r.latest.completeness} /> : <Typography.Text type="warning">{t.overview.noPackage}</Typography.Text>}
                        {r.lastAcquisition?.notes && <Typography.Text type="secondary">{r.lastAcquisition.notes}</Typography.Text>}
                      </Space>
                    </List.Item>
                  )}
                />
              )}
            </Card>
          </Col>
          <Col xs={24} lg={8}>
            <Space direction="vertical" size="middle" style={{ width: "100%" }}>
              <Card title={t.overview.latestAnalysis} data-testid="latest-analysis">
                {o.latestAnalysis ? (
                  <Space direction="vertical" size={space.xs}>
                    <Typography.Text strong>{o.latestAnalysis.title}</Typography.Text>
                    <Typography.Text type="secondary">{o.latestAnalysis.generatedAt}</Typography.Text>
                    <Typography.Text type={o.latestAnalysis.reviewStatus === "draft" ? "warning" : undefined}>
                      {t.overview.reviewed[o.latestAnalysis.reviewStatus]}
                    </Typography.Text>
                  </Space>
                ) : <EmptyState message={t.overview.noAnalysis} />}
              </Card>
              <Card title={t.overview.notices}>
                {o.notices.length === 0 ? <EmptyState /> : o.notices.map((n, i) => (
                  <Alert key={i} type={n.level} showIcon message={n.message} style={{ marginBottom: space.sm }} />
                ))}
              </Card>
            </Space>
          </Col>
        </Row>
        <Typography.Text type="secondary" data-testid="data-source">
          {t.overview.source(o.source.index, o.source.schemaVersion, o.source.indexGeneratedAt)}
        </Typography.Text>
      </Space>
    </>
  );
}
