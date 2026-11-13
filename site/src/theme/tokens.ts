/**
 * The ONE source of design tokens for the Dashboard (DEVELOPMENT_PLAN.md §3).
 * Components must take colours, sizes and spacing from here (or from the
 * Ant Design theme built from it) — no hard-coded colours elsewhere.
 */
import type { ThemeConfig } from "antd";

export const color = {
  brand: "#1F4E8C",
  brandSoft: "#E8EEF7",
  text: "#1F2329",
  textMuted: "#5C6370",
  border: "#D9DDE3",
  surface: "#FFFFFF",
  canvas: "#F5F7FA",
  // semantic status colours (always paired with an icon and a text label)
  success: "#2E7D32",
  warning: "#B26A00",
  danger: "#C62828",
  info: "#1565C0",
  neutral: "#616161",
  inference: "#6A1B9A", // AI inference — deliberately distinct from "verified"
  // side menu: the navy of the dark logo (exhibitiq-horizontal-dark.svg), Eric 2026-11-13
  navNavy: "#10243B",
  navNavySelected: "#1F3A5C",
  navText: "#C9D4E3",
  navTextActive: "#FFFFFF",
} as const;

export const space = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 } as const;
export const radius = { sm: 4, md: 8 } as const;
export const fontSize = { sm: 13, base: 15, lg: 17, h3: 21, h2: 26, h1: 32 } as const;
export const layout = { siderWidth: 264, headerHeight: 56, contentMaxWidth: 1280, mobileBreakpoint: "lg" } as const;

export const antdTheme: ThemeConfig = {
  token: {
    colorPrimary: color.brand,
    colorText: color.text,
    colorTextSecondary: color.textMuted,
    // WCAG AA contrast for secondary/description text (Lighthouse W4-04); antd's default 45% black is too light.
    colorTextDescription: color.textMuted,
    colorTextTertiary: color.textMuted,
    colorBorder: color.border,
    colorBgLayout: color.canvas,
    colorSuccess: color.success,
    colorWarning: color.warning,
    colorError: color.danger,
    colorInfo: color.info,
    borderRadius: radius.md,
    fontSize: fontSize.base,
    fontSizeSM: fontSize.sm,
    fontSizeLG: fontSize.lg,
    lineHeight: 1.7,
    fontFamily:
      '-apple-system, "Segoe UI", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", Roboto, "Helvetica Neue", Arial, sans-serif',
  },
  components: {
    Layout: { headerBg: color.surface, siderBg: color.navNavy, triggerBg: color.navNavy, headerHeight: layout.headerHeight, headerPadding: `0 ${space.md}px` },
    Menu: { itemSelectedBg: color.brandSoft, itemSelectedColor: color.brand, itemHeight: 44, fontSize: fontSize.base,
      darkItemBg: color.navNavy, darkSubMenuItemBg: color.navNavy, darkItemSelectedBg: color.navNavySelected,
      darkItemColor: color.navText, darkItemHoverColor: color.navTextActive, darkItemSelectedColor: color.navTextActive },
    Table: { cellPaddingBlock: 14 },
    Card: { headerFontSize: fontSize.lg },
  },
};
