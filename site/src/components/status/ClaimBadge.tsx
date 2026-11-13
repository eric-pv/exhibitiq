import { CheckCircleOutlined, ClockCircleOutlined, ExperimentOutlined, QuestionCircleOutlined, UserOutlined, WarningOutlined } from "@ant-design/icons";
import { Tag, Tooltip } from "antd";
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

/** Compact list marker (Eric 2026-11-13): ✓ verified / confirmed, △ everything else; the text is in the tooltip and aria-label. */
export function ClaimIcon({ kind }: { kind: ClaimKind }) {
  const ok = kind === "verified" || kind === "human_confirmed";
  return (
    <Tooltip title={t.claim[kind]}>
      <span role="img" aria-label={t.claim[kind]} data-claim={kind} data-testid="claim-icon" style={{ color: ok ? color.success : color.warning, fontSize: "1.15em" }}>
        {ok ? <CheckCircleOutlined /> : <WarningOutlined />}
      </span>
    </Tooltip>
  );
}

/** Always colour + icon + text, so status never depends on colour alone. */
export function ClaimBadge({ kind }: { kind: ClaimKind }) {
  const s = CLAIM_STYLE[kind];
  return (
    <Tag color={s.color} icon={s.icon} data-claim={kind}>
      {t.claim[kind]}
    </Tag>
  );
}
