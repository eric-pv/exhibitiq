import { Card, Typography } from "antd";
import { useEffect, useRef } from "react";
import { color } from "../theme/tokens";
import { EmptyState } from "./states/States";

export interface ChartDatum { name: string; value: number }

const PALETTE = [color.brand, color.info, color.success, color.warning, color.danger, color.inference, color.neutral];

/**
 * Shared bar chart panel: one colour scheme, empty state, source note, click-through.
 * Uses ECharts directly with a ResizeObserver so the chart always fits its card.
 */
export function ChartPanel(props: { title: string; note: string; data: ChartDatum[]; onSelect?: (name: string) => void; testId?: string }) {
  const el = useRef<HTMLDivElement>(null);
  const onSelect = useRef(props.onSelect);
  onSelect.current = props.onSelect;

  useEffect(() => {
    if (!el.current || props.data.length === 0) return;
    // ECharts is about half of the bundle: load it only when a chart is shown (W4-04).
    let cancelled = false;
    let cleanup = () => {};
    import("echarts").then((echarts) => {
      if (cancelled || !el.current) return;
      const chart = echarts.init(el.current, undefined, { renderer: "svg" });
    chart.setOption({
      animation: false,
      color: PALETTE,
      grid: { left: 8, right: 40, top: 16, bottom: 8, containLabel: true }, // right: room for value labels
      tooltip: { trigger: "axis" },
      xAxis: { type: "value", minInterval: 1 },
      yAxis: { type: "category", data: props.data.map((d) => d.name), inverse: true },
      series: [{ type: "bar", data: props.data.map((d) => d.value), barMaxWidth: 28, label: { show: true, position: "right" } }],
    });
      chart.on("click", (e: { name: unknown }) => onSelect.current?.(String(e.name)));
      const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => chart.resize());
      ro?.observe(el.current);
      cleanup = () => { ro?.disconnect(); chart.dispose(); };
    });
    return () => { cancelled = true; cleanup(); };
  }, [props.data]);

  return (
    <Card title={props.title} data-testid={props.testId} style={{ height: "100%" }}>
      {props.data.length === 0 ? (
        <EmptyState />
      ) : (
        <div ref={el} data-testid={props.testId ? `${props.testId}-canvas` : undefined} style={{ width: "100%", height: Math.max(160, props.data.length * 48) }} />
      )}
      <Typography.Text type="secondary">{props.note}</Typography.Text>
    </Card>
  );
}
