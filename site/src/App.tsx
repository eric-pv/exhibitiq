import { Route, Routes, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./components/states/ErrorBoundary";
import { AppLayout } from "./components/layout/AppLayout";
import { PageHeader } from "./components/layout/PageHeader";
import { UnderConstruction } from "./components/states/States";
import { NAV_ITEMS } from "./navigation";
import { DesignSystemPage } from "./pages/DesignSystemPage";
import { OverviewPage } from "./pages/OverviewPage";
import { CompaniesPage } from "./pages/CompaniesPage";
import { CompanyDetailPage } from "./pages/CompanyDetailPage";
import { OpportunitiesPage } from "./pages/OpportunitiesPage";
import { ExhibitionDetailPage, ExhibitionsPage } from "./pages/ExhibitionsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ComparePage } from "./pages/ComparePage";
import { StatusPage } from "./pages/StatusPage";

const BUILT: Record<string, () => JSX.Element> = { overview: OverviewPage, companies: CompaniesPage, opportunities: OpportunitiesPage, exhibitions: ExhibitionsPage, reports: ReportsPage, settings: SettingsPage, intel: ComparePage, status: StatusPage };

/** Routes for the 8 main menu items. Pages that are not built yet show the unified 「建置中」 state. */
export default function App() {
  const { pathname } = useLocation();
  return (
    <AppLayout>
      <ErrorBoundary resetKey={pathname}>
      <Routes>
        {NAV_ITEMS.map((n) => (
          <Route
            key={n.key}
            path={n.path}
            element={
              BUILT[n.key] ? (
                (() => { const Page = BUILT[n.key]; return <Page />; })()
              ) : (
                <>
                  <PageHeader title={n.label} />
                  <UnderConstruction workItem={n.plannedIn} />
                </>
              )
            }
          />
        ))}
        <Route path="/exhibitions/:exhibitionId" element={<ExhibitionDetailPage />} />
        <Route path="/companies/:companyId" element={<CompanyDetailPage />} />
        <Route path="/design" element={<DesignSystemPage />} />
        <Route path="*" element={<UnderConstruction workItem="—" />} />
      </Routes>
      </ErrorBoundary>
    </AppLayout>
  );
}
