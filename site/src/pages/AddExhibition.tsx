import { Alert, Button, Card, Form, Input, Select, Space, Typography } from "antd";
import { useMemo, useState } from "react";
import { bundle } from "../data/repository";
import { buildRegistration, possibleDuplicates, proposeId, validateRegistration, workflowInputs, workflowUrl, type RegistrationInput } from "../data/registration";
import { t } from "../i18n/zh-TW";
import { space } from "../theme/tokens";

const a = t.exhibitions.add;
const YEAR = new Date().getUTCFullYear();
const yearOptions = Array.from({ length: 8 }, (_, i) => YEAR - 3 + i).map((y) => ({ value: y, label: String(y) }));

/** 新增展覽 (W3-07): prepares the A1-10 registration and links to the D2-13 workflow. Sends nothing anywhere. */
export function AddExhibition() {
  const [v, setV] = useState<RegistrationInput>({ name: "", years: [], requestedBy: "" });
  const [idEdited, setIdEdited] = useState(false);
  const [copied, setCopied] = useState<null | boolean>(null);
  const suggested = useMemo(() => proposeId(v, bundle.exhibitions.map((e) => e.exhibitionId)), [v.name, v.nameEn, v.website]);
  const input = { ...v, exhibitionId: idEdited ? v.exhibitionId : suggested ?? undefined };
  const doc = useMemo(() => buildRegistration(input, new Date()), [JSON.stringify(input)]);
  const errors = validateRegistration(doc);
  const dups = possibleDuplicates(input);
  const json = JSON.stringify(doc, null, 2) + "\n";
  const url = workflowUrl();
  const set = (k: keyof RegistrationInput) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  const copy = async () => { try { await navigator.clipboard.writeText(json); setCopied(true); } catch { setCopied(false); } };
  const download = () => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    link.download = "registration.json";
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return (
    <Card title={a.title} data-testid="add-exhibition" style={{ marginBottom: space.md }}>
      <Typography.Paragraph type="secondary">{a.intro}</Typography.Paragraph>
      <Form layout="vertical" style={{ maxWidth: 720 }}>
        <Form.Item label={a.name} required><Input value={v.name} onChange={set("name")} data-testid="add-name" maxLength={500} /></Form.Item>
        <Space wrap style={{ width: "100%" }} size={space.md}>
          <Form.Item label={a.nameZhHant}><Input value={v.nameZhHant} onChange={set("nameZhHant")} maxLength={500} /></Form.Item>
          <Form.Item label={a.nameEn}><Input value={v.nameEn} onChange={set("nameEn")} data-testid="add-name-en" maxLength={500} /></Form.Item>
          <Form.Item label={a.country}><Input value={v.country} onChange={set("country")} data-testid="add-country" maxLength={2} style={{ width: 100 }} /></Form.Item>
        </Space>
        <Form.Item label={a.website}><Input value={v.website} onChange={set("website")} data-testid="add-website" placeholder="https://" /></Form.Item>
        <Space wrap style={{ width: "100%" }} size={space.md}>
          <Form.Item label={a.years} required>
            <Select mode="multiple" style={{ minWidth: 220 }} value={v.years} options={yearOptions} onChange={(years: number[]) => setV({ ...v, years })} data-testid="add-years" />
          </Form.Item>
          <Form.Item label={a.requestedBy} required><Input value={v.requestedBy} onChange={set("requestedBy")} data-testid="add-requested-by" maxLength={500} /></Form.Item>
        </Space>
        <Form.Item label={a.exhibitionId} help={!suggested && !idEdited ? a.idNone : undefined}>
          <Input value={input.exhibitionId ?? ""} data-testid="add-id" maxLength={40}
            onChange={(e) => { setIdEdited(true); setV({ ...v, exhibitionId: e.target.value }); }} />
        </Form.Item>
      </Form>

      {dups.length > 0 && <Alert type="warning" showIcon data-testid="add-duplicates" style={{ marginBottom: space.sm }}
        message={`${a.duplicates}${dups.map((d) => `${d.name}（${d.exhibitionId}）`).join("、")}`} />}
      {errors.length > 0
        ? <Alert type="info" showIcon data-testid="add-invalid" style={{ marginBottom: space.sm }} message={a.invalid} description={errors.join("；")} />
        : <Alert type="success" showIcon data-testid="add-valid" style={{ marginBottom: space.sm }} message={a.valid} />}

      <pre data-testid="add-json" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", margin: `0 0 ${space.sm}px` }}>{json}</pre>
      <Space wrap style={{ marginBottom: space.md }}>
        <Button onClick={copy} disabled={errors.length > 0} data-testid="add-copy">{copied === true ? a.copied : a.copy}</Button>
        <Button onClick={download} disabled={errors.length > 0} data-testid="add-download">{a.download}</Button>
        {copied === false && <Typography.Text type="secondary">{a.copyFailed}</Typography.Text>}
      </Space>

      <Typography.Title level={5}>{a.next}</Typography.Title>
      {url ? (
        <Space direction="vertical">
          <Button type="primary" href={url} target="_blank" rel="noopener noreferrer" disabled={errors.length > 0} data-testid="add-workflow">{a.openWorkflow}</Button>
          <Typography.Text>{a.inputs}</Typography.Text>
          <ul style={{ margin: 0 }}>{workflowInputs(doc).map(([k, val]) => <li key={k}><Typography.Text code>{k}</Typography.Text>：{val}</li>)}</ul>
        </Space>
      ) : <Alert type="warning" showIcon data-testid="add-no-workflow" message={a.noWorkflow} />}
      <Typography.Paragraph type="secondary" style={{ marginTop: space.sm, marginBottom: 0 }}>{a.status}</Typography.Paragraph>
    </Card>
  );
}
