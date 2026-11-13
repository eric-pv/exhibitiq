import { CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined, MinusCircleOutlined, QuestionCircleOutlined, SyncOutlined } from "@ant-design/icons";
import { Tag } from "antd";
import type { ReactNode } from "react";
import { t } from "../../i18n/zh-TW";
import { color } from "../../theme/tokens";

/** Acquisition, validation and source-assessment states (schemas/v1/dataset_index, crawl_run). */
export type PipelineStatus = keyof typeof t.status;

const STYLE: Record<PipelineStatus, { color: string; icon: ReactNode }> = {
  succeeded: { color: color.success, icon: <CheckCircleOutlined /> },
  passed: { color: color.success, icon: <CheckCircleOutlined /> },
  feasible: { color: color.success, icon: <CheckCircleOutlined /> },
  partial: { color: color.warning, icon: <ExclamationCircleOutlined /> },
  partially_feasible: { color: color.warning, icon: <ExclamationCircleOutlined /> },
  pending_authorization: { color: color.warning, icon: <SyncOutlined /> },
  failed: { color: color.danger, icon: <CloseCircleOutlined /> },
  not_feasible: { color: color.danger, icon: <CloseCircleOutlined /> },
  cancelled: { color: color.neutral, icon: <MinusCircleOutlined /> },
  not_run: { color: color.neutral, icon: <QuestionCircleOutlined /> },
  not_assessed: { color: color.neutral, icon: <QuestionCircleOutlined /> },
};

export function StatusBadge({ status }: { status: PipelineStatus }) {
  const s = STYLE[status];
  return (
    <Tag color={s.color} icon={s.icon} data-status={status}>
      {t.status[status]}
    </Tag>
  );
}
