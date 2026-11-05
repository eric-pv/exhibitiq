// @ts-expect-error plain ESM script without type declarations
import { scanText } from "../scripts/security-check.mjs";

test("security rules catch credentials and write/LLM APIs, and pass normal text", () => {
  expect(scanText("const t = 'ghp_" + "a".repeat(36) + "'")).toContain("GitHub token");
  expect(scanText("key sk-ant-" + "b".repeat(30))).toContain("Anthropic/OpenAI key");
  expect(scanText("-----BEGIN RSA PRIVATE KEY-----")).toContain("private key");
  expect(scanText("fetch('https://api.github.com/repos/x')")).toContain("GitHub API call");
  expect(scanText("https://github.com/magician-eric/exhibitiq/upload/dev/ai-intelligence/knowledge/analysis-profiles")).toEqual([]);
  expect(scanText("sha256:68fc94dcaeaed1d23842f327b6b3cd05e07cca6610372ebb086622b03fb4d74b")).toEqual([]);
});
