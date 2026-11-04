import {
  AppstoreOutlined, BarChartOutlined, DatabaseOutlined, FileTextOutlined, FundOutlined,
  RocketOutlined, SearchOutlined, TeamOutlined,
} from "@ant-design/icons";
import type { ReactNode } from "react";
import { t } from "./i18n/zh-TW";

/**
 * The 8 main menu items (DEVELOPMENT_PLAN.md §3). Generic: no exhibition is
 * named here; exhibition lists always come from the dataset index.
 * `plannedIn` = the work item that builds the page (shown while it is not built).
 */
export interface NavItem { key: string; path: string; label: string; icon: ReactNode; plannedIn: string }

export const NAV_ITEMS: NavItem[] = [
  { key: "overview", path: "/", label: t.nav.overview, icon: <AppstoreOutlined />, plannedIn: "W1-03" },
  { key: "exhibitions", path: "/exhibitions", label: t.nav.exhibitionSearch, icon: <SearchOutlined />, plannedIn: "W2-01、W3-07" },
  { key: "intel", path: "/intel", label: t.nav.exhibitionIntel, icon: <BarChartOutlined />, plannedIn: "W2-01、W3-01" },
  { key: "companies", path: "/companies", label: t.nav.companies, icon: <TeamOutlined />, plannedIn: "W2-02、W2-03" },
  { key: "opportunities", path: "/opportunities", label: t.nav.opportunities, icon: <FundOutlined />, plannedIn: "W2-04" },
  { key: "products", path: "/products", label: t.nav.products, icon: <RocketOutlined />, plannedIn: "W3-03" },
  { key: "reports", path: "/reports", label: t.nav.reports, icon: <FileTextOutlined />, plannedIn: "W3-04" },
  { key: "status", path: "/status", label: t.nav.status, icon: <DatabaseOutlined />, plannedIn: "W2-05" },
];
