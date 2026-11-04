import { Alert } from "antd";
import { t } from "../../i18n/zh-TW";

/** Site-wide marker: synthetic data must always be labelled (spec §8.1). */
export function DataOriginBanner({ origin }: { origin: "synthetic" | "collected" | "none" }) {
  if (origin !== "synthetic") return null;
  return <Alert type="warning" showIcon banner message={t.origin.synthetic} data-testid="data-origin-banner" />;
}
