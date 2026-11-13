import { LinkOutlined, WarningOutlined } from "@ant-design/icons";
import { Descriptions, Popover, Space, Tag, Typography } from "antd";
import type { ReactNode } from "react";
import type { ResolvedSource } from "../../data/repository";
import { t } from "../../i18n/zh-TW";
import { color } from "../../theme/tokens";

const s = t.source;

/** Short date-time for display; the full ISO value stays in the title attribute. */
export const shortTime = (iso: string) => iso.replace("T", " ").replace(/:\d\d(\.\d+)?Z$/, " UTC");

function SourceCard({ src }: { src: Exclude<ResolvedSource, { missing: true }> }) {
  const items = [
    { key: "type", label: "類型", children: s.type[src.sourceType] ?? src.sourceType },
    src.url && { key: "url", label: s.url, children: /^https?:\/\//.test(src.url) ? <a href={src.url} target="_blank" rel="noopener noreferrer">{src.url}</a> : src.url },
    src.publisher && { key: "pub", label: s.publisher, children: src.publisher },
    { key: "at", label: s.retrievedAt, children: <span title={src.retrievedAt}>{shortTime(src.retrievedAt)}</span> },
    src.crawlRunId && { key: "run", label: s.crawlRun, children: <Typography.Text code>{src.crawlRunId}</Typography.Text> },
    { key: "hash", label: s.hash, children: <Typography.Text code title={src.contentSha256}>{src.contentSha256.slice(0, 19)}…</Typography.Text> },
    { key: "snap", label: s.snapshot, children: [s.snapshotStorage[src.snapshot.storage] ?? src.snapshot.storage, src.snapshot.locator, src.snapshot.retainedUntil && s.retainedUntil(src.snapshot.retainedUntil)].filter(Boolean).join("；") },
    src.notes && { key: "notes", label: s.notes, children: src.notes },
  ].filter(Boolean) as { key: string; label: string; children: ReactNode }[];
  return <Descriptions size="small" column={1} items={items} style={{ maxWidth: 420 }} />;
}

/**
 * The single way to cite a source (DEVELOPMENT_PLAN §3 shared components): a numbered tag that opens the
 * source record — type, URL, retrieval time, content hash and snapshot location.
 */
export function SourceRef({ source, index }: { source: ResolvedSource; index?: number }) {
  if ("missing" in source) {
    return <Tag color={color.danger} icon={<WarningOutlined />} data-testid="source-ref" data-source={source.sourceId}>{s.missing}：{source.sourceId}</Tag>;
  }
  const label = `${index !== undefined ? `[${index}] ` : ""}${s.type[source.sourceType] ?? source.sourceType}`;
  return (
    <Popover title={source.title ?? source.sourceId} content={<SourceCard src={source} />} trigger={["hover", "click"]}>
      <Tag icon={<LinkOutlined />} style={{ cursor: "pointer" }} tabIndex={0} data-testid="source-ref" data-source={source.sourceId}>{label}</Tag>
    </Popover>
  );
}

/** A list of sources; numbers refer to the page's source list so the same source keeps the same number. */
export function SourceRefs({ sources, numbering }: { sources: ResolvedSource[]; numbering?: Map<string, number> }) {
  if (sources.length === 0) return <Typography.Text type="secondary">—</Typography.Text>;
  return <Space size={[0, 4]} wrap>{sources.map((src) => <SourceRef key={src.sourceId} source={src} index={numbering?.get(src.sourceId)} />)}</Space>;
}
