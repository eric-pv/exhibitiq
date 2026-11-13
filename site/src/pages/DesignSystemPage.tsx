import { Card, Space, Typography } from "antd";
import { ClaimBadge, CLAIM_STYLE, type ClaimKind } from "../components/status/ClaimBadge";
import { CompletenessIndicator } from "../components/status/CompletenessIndicator";
import { StatusBadge, type PipelineStatus } from "../components/status/StatusBadge";
import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState, ErrorState, UnderConstruction } from "../components/states/States";
import { t } from "../i18n/zh-TW";

/** Reference page for the shared components (#/design). Not in the main menu; shows no data. */
export function DesignSystemPage() {
  return (
    <>
      <PageHeader title="設計系統元件" />
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <Card title="ClaimBadge：結論與查證狀態">
          <Space wrap>{(Object.keys(CLAIM_STYLE) as ClaimKind[]).map((k) => <ClaimBadge key={k} kind={k} />)}</Space>
        </Card>
        <Card title="StatusBadge：取得、驗證與來源評估狀態">
          <Space wrap>{(Object.keys(t.status) as PipelineStatus[]).map((s) => <StatusBadge key={s} status={s} />)}</Space>
        </Card>
        <Card title="CompletenessIndicator：完整度（示意，不是資料）">
          <Space direction="vertical">
            <CompletenessIndicator status="partial" official={null} collected={0} />
            <CompletenessIndicator status="unknown" official={null} collected={0} />
          </Space>
        </Card>
        <Card title="Loading／Empty／Error／建置中">
          <Typography.Paragraph type="secondary">頁面一律使用這幾種狀態，不各自設計。</Typography.Paragraph>
          <EmptyState />
          <ErrorState detail="（示意）" />
          <UnderConstruction workItem="W0-00" />
        </Card>
      </Space>
    </>
  );
}
