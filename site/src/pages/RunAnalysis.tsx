import { Alert, Button, Card, Select, Space, Typography } from "antd";
import { useState } from "react";
import { bundle, type ExhibitionRow } from "../data/repository";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";

const r = t.exhibitions.run;
/** Same split as session_tools.prepare: the top N companies in detail, the rest as one line each. */
export const TOP_DEFAULT = 40;
export function estimateInputTokens(companies: number, top = TOP_DEFAULT) {
  const detail = Math.min(top, companies);
  return 6000 + 1500 + detail * 350 + (companies - detail) * 15; // Skill instructions + fixed brief + per company (rough, ±30%)
}
export function analysisInstruction(exhibitionId: string, year: number, profileId: string) {
  const T = "python skills/exhibitiq/scripts/exhibitiq_tools.py";
  return [
    `用 ExhibitIQ Skill 分析展覽 ${exhibitionId} ${year} 年，分析主題 ${profileId}。依序執行：`,
    `1. ${T} prepare ${exhibitionId} ${year} --profile ${profileId}`,
    `2. 只讀 prepare 產生的 brief.json，在 draft.json 填寫 title、summary、conclusions、uncertainties、relationships、recommendations、evidence_source_ids（scores 保持不變；不寫金額）`,
    `3. ${T} finalize <draft.json> <package_dir>（路徑照 prepare 的輸出）；不通過就修正後重跑`,
    `4. 開 PR 到 dev/ai-intelligence，回報驗證結果、品質警告與報告路徑`,
  ].join("\n");
}

/** W3-07 companion (Eric 2026-11-09): analysis runs in a Claude Code session on the owner's subscription. The page only prepares the instruction. */
export function RunAnalysis({ row }: { row: ExhibitionRow }) {
  const editions = row.editions.filter((e) => e.latest);
  const profiles = bundle.settings.profiles.map((p) => p.profile);
  const [year, setYear] = useState(editions[0]?.year);
  const [profileId, setProfileId] = useState(profiles.find((p) => p.mode === "bxr_opportunity")?.profile_id ?? profiles[0]?.profile_id);
  const [copied, setCopied] = useState<null | boolean>(null);
  if (editions.length === 0 || !profileId || year === undefined) return (
    <Card title={r.title} data-testid="run-analysis"><Typography.Text type="secondary">{r.noPackage}</Typography.Text></Card>
  );
  const ed = editions.find((e) => e.year === year)!;
  const text = analysisInstruction(row.exhibitionId, year, profileId);
  const copy = async () => { try { await navigator.clipboard.writeText(text); setCopied(true); } catch { setCopied(false); } };
  return (
    <Card title={r.title} data-testid="run-analysis">
      <Typography.Paragraph type="secondary">{r.intro}</Typography.Paragraph>
      <Space wrap style={{ marginBottom: space.sm }}>
        <Select value={year} onChange={setYear} options={editions.map((e) => ({ value: e.year, label: `${e.year}` }))} style={{ width: 120 }} data-testid="run-year" />
        <Select value={profileId} onChange={setProfileId} options={profiles.map((p) => ({ value: p.profile_id, label: `${p.name}（${t.settings.modes[p.mode].short}）` }))} style={{ minWidth: 240 }} data-testid="run-profile" />
      </Space>
      <Alert type="info" showIcon style={{ marginBottom: space.sm }} data-testid="run-estimate"
        message={r.estimate(ed.latest!.completeness.collected, estimateInputTokens(ed.latest!.completeness.collected))} description={r.estimateNote} />
      <pre data-testid="run-instruction" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", margin: `0 0 ${space.sm}px` }}>{text}</pre>
      <Space wrap>
        <Button type="primary" onClick={copy} data-testid="run-copy">{copied === true ? r.copied : r.copy}</Button>
        {copied === false && <Typography.Text type="secondary">{r.copyFailed}</Typography.Text>}
      </Space>
    </Card>
  );
}
