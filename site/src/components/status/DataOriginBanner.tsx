import { Alert } from "antd";
import { t } from "../../i18n/zh-TW";

/** Site-wide marker: every page says whether its data is synthetic or collected (DEVELOPMENT_PLAN §3 display rules). */
export function DataOriginBanner({ origin }: { origin: "synthetic" | "collected" | "none" }) {
  if (origin === "none") return null;
  return origin === "synthetic"
    ? <Alert type="warning" showIcon banner message={t.origin.synthetic} data-testid="data-origin-banner" data-origin="synthetic" />
    : <Alert type="info" showIcon banner message={t.origin.collectedBanner} data-testid="data-origin-banner" data-origin="collected" />;
}
