import { Typography } from "antd";
import type { ReactNode } from "react";
import { space } from "../../theme/tokens";

export function PageHeader({ title, extra }: { title: string; extra?: ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: space.md, marginBottom: space.lg, flexWrap: "wrap" }}>
      <Typography.Title level={2} style={{ margin: 0 }}>{title}</Typography.Title>
      {extra}
    </div>
  );
}
