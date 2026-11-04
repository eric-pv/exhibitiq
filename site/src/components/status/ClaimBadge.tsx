import { CheckCircleOutlined, ClockCircleOutlined, ExperimentOutlined, QuestionCircleOutlined, UserOutlined, WarningOutlined } from "@ant-design/icons";
import { Tag } from "antd";
import type { ReactNode } from "react";
import { t } from "../../i18n/zh-TW";
import { color } from "../../theme/tokens";

/** Fact verification statuses (schemas common.fact_verification_status) + AI inference + unknown. */
export type ClaimKind = "verified" | "unverified" | "human_confirmed" | "insufficient_data" | "ai_inferred" | "unknown";

export const CLAIM_STYLE: Record<ClaimKind, { color: string; icon: ReactNode }> = {
  verified: { color: color.success, icon: <CheckCircleOutlined /> },
  human_confirmed: { color: color.success, icon: <UserOutlined /> },
  unverified: { color: color.neutral, icon: <ClockCircleOutlined /> },
  insufficient_data: { color: color.warning, icon: <WarningOutlined /> },
  ai_inferred: { color: color.inference, icon: <ExperimentOutlined /> },
  unknown: { color: color.warning, icon: <QuestionCircleOutlined /> },
};

/** Always colour + icon + text, so status never depends on colour alone. */
export function ClaimBadge({ kind }: { kind: ClaimKind }) {
  const s = CLAIM_STYLE[kind];
  return (
    <Tag color={s.color} icon={s.icon} data-claim={kind}>
      {t.claim[kind]}
    </Tag>
  );
}
