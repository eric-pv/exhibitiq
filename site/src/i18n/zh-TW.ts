/** All UI text lives here (Traditional Chinese first; en.ts can mirror these keys later). */
export const t = {
  appName: "ExhibitIQ",
  appSubtitle: "AI 展會情報平台",
  openMenu: "開啟選單",
  nav: {
    overview: "系統總覽",
    exhibitionSearch: "展覽搜尋與新增",
    exhibitionIntel: "展覽情報與比較",
    companies: "參展商與企業情報",
    opportunities: "商機分析與評分",
    products: "BXR 產品推薦",
    reports: "AI 報告中心",
    status: "資料及系統狀態",
  },
  underConstruction: { title: "建置中", body: (item: string) => `此頁面將在 ${item} 加入。` },
  empty: "沒有資料",
  loading: "載入中",
  error: "資料載入失敗",
  claim: {
    verified: "已查證",
    unverified: "待查證",
    human_confirmed: "人工確認",
    insufficient_data: "資料不足",
    ai_inferred: "AI 推論",
    unknown: "未知",
  },
  status: {
    succeeded: "成功", partial: "部分成功", failed: "失敗", cancelled: "已取消",
    passed: "驗證通過", not_run: "未驗證",
    feasible: "可取得", partially_feasible: "部分可取得", not_feasible: "無法取得",
    pending_authorization: "等待授權", not_assessed: "尚未評估",
  },
  completeness: {
    complete: "完整", partial: "不完整", unknown: "完整度未知",
    official: "官方公布", collected: "已取得", notAvailable: "未知",
  },
  origin: {
    synthetic: "合成資料：畫面上的展覽、企業與數字都是虛構的測試資料，不代表任何真實展覽或企業。",
    collected: "真實資料",
  },
} as const;
