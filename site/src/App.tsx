import { Alert, Card, Space, Typography } from "antd";
import ReactECharts from "echarts-for-react";
import { Route, Routes } from "react-router-dom";

/**
 * W1-01 scaffold page. It only proves that the toolchain renders
 * (Ant Design with zh_TW locale, ECharts, HashRouter).
 * The design system, layout and navigation come in W1-02; data access in W1-03.
 */
export function ScaffoldPage() {
  // A fixed shape used only to prove ECharts renders. It is NOT data.
  const option = {
    animation: false,
    xAxis: { type: "category", data: ["A", "B", "C"] },
    yAxis: { type: "value", show: false },
    series: [{ type: "bar", data: [1, 2, 3] }],
  };
  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <Typography.Title level={2} style={{ margin: 0 }}>
          ExhibitIQ Dashboard
        </Typography.Title>
        <Alert
          type="info"
          showIcon
          message="前端骨架（W1-01）"
          description="這個頁面只用來確認前端工具鏈可以運作。設計系統、主選單與資料顯示會在 W1-02、W1-03 加入；頁面上沒有任何展覽資料。"
        />
        <Card title="圖表元件驗證（不是資料）" data-testid="chart-card">
          <ReactECharts option={option} style={{ height: 200 }} opts={{ renderer: "svg" }} />
        </Card>
      </Space>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<ScaffoldPage />} />
    </Routes>
  );
}
