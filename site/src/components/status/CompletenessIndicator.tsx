import { CheckCircleOutlined, ExclamationCircleOutlined, QuestionCircleOutlined } from "@ant-design/icons";
import { Space, Tag, Typography } from "antd";
import type { ReactNode } from "react";
import { t } from "../../i18n/zh-TW";
import { color } from "../../theme/tokens";

export type CompletenessStatus = "complete" | "partial" | "unknown";

const STYLE: Record<CompletenessStatus, { color: string; icon: ReactNode }> = {
  complete: { color: color.success, icon: <CheckCircleOutlined /> },
  partial: { color: color.warning, icon: <ExclamationCircleOutlined /> },
  unknown: { color: color.neutral, icon: <QuestionCircleOutlined /> },
};

/**
 * Shows completeness next to any count (DEVELOPMENT_PLAN.md §3).
 * A missing official count is shown as 「未知」 — never estimated.
 */
export function CompletenessIndicator(props: { status: CompletenessStatus; official: number | null; collected: number }) {
  const s = STYLE[props.status];
  return (
    <Space size="small" wrap data-completeness={props.status}>
      <Tag color={s.color} icon={s.icon}>{t.completeness[props.status]}</Tag>
      <Typography.Text type="secondary">
        {t.completeness.collected} {props.collected} ／ {t.completeness.official}{" "}
        {props.official === null ? t.completeness.notAvailable : props.official}
      </Typography.Text>
    </Space>
  );
}
