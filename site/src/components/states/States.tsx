import { Empty, Result, Skeleton } from "antd";
import { ToolOutlined } from "@ant-design/icons";
import { t } from "../../i18n/zh-TW";

export const LoadingState = () => <Skeleton active aria-label={t.loading} />;
export const EmptyState = ({ message = t.empty }: { message?: string }) => <Empty description={message} />;
export const ErrorState = ({ detail }: { detail?: string }) => (
  <Result status="error" title={t.error} subTitle={detail} />
);
/** Unified placeholder for pages that are not built yet. */
export const UnderConstruction = ({ workItem }: { workItem: string }) => (
  <div data-testid="under-construction">
    <Result icon={<ToolOutlined />} title={t.underConstruction.title} subTitle={t.underConstruction.body(workItem)} />
  </div>
);
