import { Grid, Layout, Menu, Typography } from "antd";
import { useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { t } from "../../i18n/zh-TW";
import { NAV_ITEMS } from "../../navigation";
import { color, layout, space } from "../../theme/tokens";

/** Shared shell: header + collapsible side navigation + content. Used by every page. */
export function AppLayout({ banner, children }: { banner?: ReactNode; children: ReactNode }) {
  const screens = Grid.useBreakpoint();
  const isMobile = !screens[layout.mobileBreakpoint];
  const [collapsed, setCollapsed] = useState<boolean | null>(null);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const current = NAV_ITEMS.find((n) => n.path === pathname) ?? NAV_ITEMS.find((n) => n.path !== "/" && pathname.startsWith(n.path));
  const isCollapsed = collapsed ?? isMobile;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Sider
        width={layout.siderWidth}
        breakpoint={layout.mobileBreakpoint}
        collapsedWidth={0}
        collapsed={isCollapsed}
        onCollapse={(c) => setCollapsed(c)}
        theme="light"
        // On mobile the menu overlays the page instead of squeezing the content.
        style={
          isMobile
            ? { borderRight: `1px solid ${color.border}`, position: "fixed", top: 0, left: 0, height: "100vh", zIndex: 1000 }
            : { borderRight: `1px solid ${color.border}` }
        }
        zeroWidthTriggerStyle={{ top: space.sm }}
        data-testid="side-nav"
      >
        {/* Hide the contents when collapsed: a 0-width Sider would otherwise let the menu overflow on top of the page. */}
        <div style={{ display: isCollapsed ? "none" : "block" }}>
        <div style={{ padding: space.md }}>
          <Typography.Title level={4} style={{ margin: 0, color: color.brand }}>{t.appName}</Typography.Title>
          <Typography.Text type="secondary">{t.appSubtitle}</Typography.Text>
        </div>
        <Menu
          mode="inline"
          selectedKeys={current ? [current.key] : []}
          items={NAV_ITEMS.map((n) => ({ key: n.key, icon: n.icon, label: n.label }))}
          onClick={({ key }) => {
            const item = NAV_ITEMS.find((n) => n.key === key);
            if (item) navigate(item.path);
            if (isMobile) setCollapsed(true);
          }}
        />
        </div>
      </Layout.Sider>
      <Layout>
        <Layout.Header style={{ display: "flex", alignItems: "center", borderBottom: `1px solid ${color.border}` }}>
          <Typography.Text strong style={{ marginLeft: isMobile ? space.xl : 0 }}>{current?.label ?? t.appName}</Typography.Text>
        </Layout.Header>
        {banner}
        <Layout.Content style={{ padding: isMobile ? space.md : space.lg }}>
          <div style={{ maxWidth: layout.contentMaxWidth, margin: "0 auto" }}>{children}</div>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
