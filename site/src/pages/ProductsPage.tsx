import { Alert, Card, Col, Empty, List, Row, Space, Tag, Typography } from "antd";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState } from "../components/states/States";
import { ClaimBadge } from "../components/status/ClaimBadge";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { bundle, getProducts } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";

const p = t.products;

/** BXR 產品推薦 (W3-03): only approved product cards; recommendations are AI inference and link to their analysis. */
export function ProductsPage() {
  const products = useMemo(() => getProducts(), []);
  return (
    <>
      <PageHeader title={t.nav.products} />
      <DataOriginBanner origin={bundle.dataOrigin} />
      <Alert type="info" showIcon style={{ margin: `${space.md}px 0` }} message={p.note} data-testid="products-note" />
      {products.length === 0 ? <EmptyState message={p.none} /> : (
        <Row gutter={[space.md, space.md]} data-testid="product-grid">
          {products.map((x) => (
            <Col key={x.productId} xs={24} md={12} xl={8}>
              <Card style={{ height: "100%" }} data-testid="product-card" title={<Space direction="vertical" size={0}><span>{x.name}</span>{x.nameEn && x.nameEn !== x.name && <Typography.Text type="secondary" style={{ fontSize: 12 }}>{x.nameEn}</Typography.Text>}</Space>}
                extra={<Tag color="green">{p.approved(x.approvedAt ?? "")}</Tag>}>
                <Space direction="vertical" size={space.sm} style={{ width: "100%" }}>
                  <Typography.Text>{x.summary}</Typography.Text>
                  {x.termLabels.length > 0 && <Space size={[4, 4]} wrap>{x.termLabels.map((l) => <Tag key={l}>{l}</Tag>)}</Space>}
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>{x.specCount ? p.specs(x.specCount) : p.noSpecs}</Typography.Text>
                  <Typography.Text strong>{p.recs}</Typography.Text>
                  {x.recommendations.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={p.noRecs} /> : (
                    <List size="small" dataSource={x.recommendations} renderItem={(r) => (
                      <List.Item><Space direction="vertical" size={2}>
                        <Space wrap><ClaimBadge kind="ai_inferred" /><span>{r.statement}</span></Space>
                        <Link to={`/reports?analysis=${encodeURIComponent(r.analysis.analysisId)}`}>{r.analysis.title}</Link>
                      </Space></List.Item>
                    )} />
                  )}
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </>
  );
}
