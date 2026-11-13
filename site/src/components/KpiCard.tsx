import { Card, Statistic } from "antd";
import type { ReactNode } from "react";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";

/** Statistic card with an optional footer (e.g. completeness) and a click-through entry. */
export function KpiCard(props: { title: string; value: number; suffix?: string; footer?: ReactNode; onOpen?: () => void; testId?: string }) {
  return (
    <Card
      hoverable={!!props.onOpen}
      onClick={props.onOpen}
      role={props.onOpen ? "link" : undefined}
      aria-label={props.onOpen ? `${props.title} ${props.value}${props.suffix ?? ""}：${t.overview.clickHint}` : undefined}
      data-testid={props.testId}
      style={{ height: "100%" }}
    >
      <Statistic title={props.title} value={props.value} suffix={props.suffix} />
      {props.footer && <div style={{ marginTop: space.sm }}>{props.footer}</div>}
    </Card>
  );
}
