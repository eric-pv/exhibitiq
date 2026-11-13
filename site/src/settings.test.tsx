import { act, fireEvent, render, screen } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { MemoryRouter } from "react-router-dom";
// @ts-expect-error plain ESM build script without type declarations
import { REPO } from "../scripts/build-bundle.mjs";
import App from "./App";
import { forSubmission, loadDrafts, profileHash, profileStates, sha256Hex, validateProfile } from "./data/profiles";
import { bundle } from "./data/repository";
import type { AnalysisProfile } from "./data/types";

vi.mock("echarts", () => ({ init: () => ({ setOption() {}, on() {}, resize() {}, dispose() {} }) }));
beforeEach(() => localStorage.clear());

test("browser SHA-256 and profile hash equal Python's (profile_check.py)", () => {
  expect(sha256Hex("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  expect(sha256Hex("中文 é")).toBe(execFileSync("python3", ["-c", "import hashlib;print(hashlib.sha256('中文 é'.encode()).hexdigest())"], { encoding: "utf8" }).trim());
  const py = JSON.parse(execFileSync("python3", ["-c", `
import sys,json;sys.path.insert(0,${JSON.stringify(join(REPO, "tests", "contract"))});import profile_check as pf
print(json.dumps({k:pf.profile_hash(v) for k,v in pf.load_profiles().items()}))`], { encoding: "utf8" }));
  expect(Object.keys(py).length).toBeGreaterThan(0);
  for (const { profile, hash } of bundle.settings.profiles) {
    expect(profileHash(profile)).toBe(py[profile.profile_id]);
    expect(hash).toBe(py[profile.profile_id]);
  }
});

test("browser validation follows the schema and profile rules", () => {
  const p = structuredClone(bundle.settings.profiles[0].profile) as AnalysisProfile;
  expect(validateProfile(p)).toEqual([]);
  expect(validateProfile({ ...p, mode: "military_only" }).length).toBeGreaterThan(0);
  expect(validateProfile({ ...p, keywords: [...p.keywords, p.keywords[0]] })).toContain("關鍵字代碼（term_id）重複");
  expect(validateProfile({ ...p, mode: "industry_research", targets: { bxr_product_ids: ["bxr-x"] } })).toContain("B、C 模式不能使用 BXR 產品卡");
  expect(validateProfile({ ...p, keywords: [{ term_id: "custom.fire", category: "my-own", label: "消防", enabled: true }] })).toEqual([]); // any domain
});

test("three states: draft differs from submitted; submission bumps the version only when content changed", () => {
  const sub = bundle.settings.profiles[0].profile;
  expect(profileStates({})[0].unsubmitted).toBe(false);
  const draft = { ...structuredClone(sub), name: "改過的名稱" };
  const st = profileStates({ [sub.profile_id]: draft }).find((x) => x.profileId === sub.profile_id)!;
  expect(st.unsubmitted).toBe(true);
  expect(forSubmission(draft, sub).version).toBe(sub.version + 1);
  expect(forSubmission(structuredClone(sub), sub)).toEqual(sub);
});

const renderAt = (p: string) => render(<ConfigProvider locale={zhTW}><MemoryRouter initialEntries={[p]}><App /></MemoryRouter></ConfigProvider>);

test("settings page: adding a keyword creates a persisted local draft and warns it is not submitted", () => {
  renderAt("/settings");
  expect(screen.getByTestId("settings-flow")).toBeTruthy();
  expect(screen.queryByTestId("unsubmitted-warning")).toBeNull();
  const input = screen.getByTestId("keyword-add").querySelector("input") ?? (screen.getByTestId("keyword-add") as HTMLInputElement);
  act(() => { fireEvent.change(input, { target: { value: "Laser Optics" } }); });
  act(() => { fireEvent.keyDown(input, { key: "Enter", code: "Enter", keyCode: 13 }); });
  expect(screen.getByTestId("unsubmitted-warning")).toBeTruthy();
  const drafts = loadDrafts();
  const id = Object.keys(drafts)[0];
  expect(drafts[id].keywords.some((k) => k.label === "Laser Optics" && k.enabled)).toBe(true);
});
