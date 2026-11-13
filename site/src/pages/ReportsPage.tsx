import { PrinterOutlined } from "@ant-design/icons";
import { Button, Card, Checkbox, Select, Space } from "antd";
import { useMemo, useState } from "react";
import { loadShowCost, saveShowCost } from "../data/displayPrefs";
import { Link, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/layout/PageHeader";
import { ReportViewer } from "../components/ReportViewer";
import { EmptyState } from "../components/states/States";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { shortTime } from "../components/status/SourceRef";
import { bundle, getAnalyses, getAnalysisView } from "../data/repository";
import { t } from "../i18n/zh-TW";

/** AI 報告中心 (W3-04): pick an analysis, read the report, export PDF through the print stylesheet. */
export function ReportsPage() {
  const list = useMemo(() => getAnalyses(), []);
  const [params, setParams] = useSearchParams();
  const a = list.find((x) => x.analysisId === params.get("analysis")) ?? list[0];
  const view = useMemo(() => (a ? getAnalysisView(a) : null), [a]);
  const [showCost, setShowCost] = useState(loadShowCost);
  if (!view) return (<><PageHeader title={t.nav.reports} /><EmptyState message={t.opportunities.noAnalysis} /></>);
  return (
    <>
      <div className="no-print">
        <PageHeader title={t.nav.reports} extra={
          <Space wrap>
            <Select value={a.analysisId} style={{ width: 320, maxWidth: "100%" }} onChange={(id) => setParams({ analysis: id }, { replace: true })}
              options={list.map((x) => ({ value: x.analysisId, label: `${x.title}（${shortTime(x.generatedAt)}）` }))} data-testid="report-select" />
            <Checkbox checked={showCost} onChange={(e) => { setShowCost(e.target.checked); saveShowCost(e.target.checked); }} data-testid="show-cost">{t.appendix.showCost}</Checkbox>
            {a.detail.scores.length > 0 && <Link to={`/opportunities?analysis=${encodeURIComponent(a.analysisId)}`} data-testid="report-opportunity-link">{t.opportunities.openOpportunity}</Link>}
            <Button type="primary" icon={<PrinterOutlined />} onClick={() => window.print()} data-testid="export-pdf">匯出 PDF（列印）</Button>
          </Space>
        } />
        <DataOriginBanner origin={bundle.dataOrigin} />
      </div>
      <Card style={{ marginTop: 16 }}><ReportViewer view={view} showCost={showCost} /></Card>
    </>
  );
}
