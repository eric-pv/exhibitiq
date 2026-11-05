/**
 * Viewer display preferences (per browser). Eric 2026-11-05: the analysis cost is shown in the competition and
 * hidden in the production version — a checkbox; the build default comes from VITE_SHOW_COST ("0" hides it).
 */
const KEY = "exhibitiq.display.showCost";
export const COST_DEFAULT = (import.meta.env.VITE_SHOW_COST ?? "1") !== "0";
export function loadShowCost(): boolean {
  try { const v = localStorage.getItem(KEY); return v === null ? COST_DEFAULT : v === "1"; } catch { return COST_DEFAULT; }
}
export function saveShowCost(v: boolean) {
  try { localStorage.setItem(KEY, v ? "1" : "0"); } catch { /* storage blocked: preference lasts for this page only */ }
}
