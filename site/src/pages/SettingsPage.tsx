import { CopyOutlined, DeleteOutlined, DownloadOutlined, EditOutlined, PlusOutlined, RollbackOutlined, UploadOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Descriptions, Input, InputNumber, List, Modal, Radio, Row, Select, Space, Switch, Table, Tabs, Tag, Typography, Upload } from "antd";
import { useMemo, useState } from "react";
import { PageHeader } from "../components/layout/PageHeader";
import { DataOriginBanner } from "../components/status/DataOriginBanner";
import { blankProfile, forSubmission, loadDrafts, profileHash, profileStates, saveDrafts, slug, validateProfile, type Drafts, type ProfileState } from "../data/profiles";
import { bundle } from "../data/repository";
import { REL_TYPES, type AnalysisMode, type AnalysisProfile, type Keyword } from "../data/types";
import { t } from "../i18n/zh-TW";
import { color, space } from "../theme/tokens";

const s = t.settings;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const download = (name: string, text: string) => {
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  Object.assign(document.createElement("a"), { href: url, download: name }).click();
  URL.revokeObjectURL(url);
};

function StateTags({ st }: { st: ProfileState }) {
  return (
    <Space size={4} wrap data-testid={`state-${st.profileId}`}>
      {st.unsubmitted && <Tag color="orange" data-state="draft">{s.state.draft}</Tag>}
      {st.submitted ? <Tag color="blue" data-state="submitted">{s.state.submitted(st.submitted.version)}</Tag> : <Tag data-state="not-submitted">{s.state.notSubmitted}</Tag>}
      {st.analyses.length > 0 && <Tag color="green" data-state="used">{s.state.used(st.analyses.length)}</Tag>}
    </Space>
  );
}

/** 分析設定 (W2-06): modes, topics, keywords, relationship signals, score weights, import/export. */
export function SettingsPage() {
  const [drafts, setDrafts] = useState<Drafts>(() => loadDrafts());
  const states = useMemo(() => profileStates(drafts), [drafts]);
  const [selected, setSelected] = useState<string>(() => states[0]?.profileId ?? "");
  const [stored, setStored] = useState(true);
  const st = states.find((x) => x.profileId === selected) ?? states[0];
  const current: AnalysisProfile | null = st ? (st.draft ?? st.submitted) : null;
  const errors = useMemo(() => (current ? validateProfile(current) : []), [current]);
  const commit = (next: Drafts) => { setDrafts(next); setStored(saveDrafts(next)); };
  const update = (fn: (p: AnalysisProfile) => void) => { if (!current) return; const p = clone(current); fn(p); commit({ ...drafts, [p.profile_id]: p }); };
  const ask = (title: string, initial: string, ok: (v: string) => void) => {
    let v = initial;
    Modal.confirm({ title, content: <Input defaultValue={initial} onChange={(e) => (v = e.target.value)} data-testid="modal-input" />, onOk: () => v.trim() && ok(v.trim()) });
  };
  const create = (base: AnalysisProfile | null, name: string) => {
    let id = slug(name); while (states.some((x) => x.profileId === id)) id += "-2";
    const p = base ? { ...clone(base), profile_id: id, name, version: 1 } : blankProfile(id, name);
    commit({ ...drafts, [id]: p }); setSelected(id);
  };
  const remove = () => {
    if (!st) return;
    const next = { ...drafts }; delete next[st.profileId]; commit(next);
    if (!st.submitted) setSelected(states.find((x) => x.profileId !== st.profileId)?.profileId ?? "");
  };
  const importFile = async (file: File) => {
    try {
      const doc = JSON.parse(await file.text());
      const errs = validateProfile(doc);
      if (errs.length) { Modal.error({ title: s.importInvalid, content: errs.join("；") }); return false; }
      commit({ ...drafts, [doc.profile_id]: doc }); setSelected(doc.profile_id);
    } catch { Modal.error({ title: s.importInvalid, content: s.notJson }); }
    return false;
  };

  const kwCols = [
    { title: s.kw.enabled, width: 70, render: (_: unknown, k: Keyword, i: number) => <Switch size="small" checked={k.enabled} onChange={(v) => update((p) => { p.keywords[i].enabled = v; })} aria-label={s.kw.enabled} /> },
    { title: s.kw.label, render: (_: unknown, k: Keyword, i: number) => <Input value={k.label} onChange={(e) => update((p) => { p.keywords[i].label = e.target.value; })} /> },
    { title: s.kw.labelEn, render: (_: unknown, k: Keyword, i: number) => <Input value={k.label_en ?? ""} onChange={(e) => update((p) => { if (e.target.value) p.keywords[i].label_en = e.target.value; else delete p.keywords[i].label_en; })} /> },
    { title: s.kw.synonyms, width: 260, render: (_: unknown, k: Keyword, i: number) => <Select mode="tags" style={{ width: "100%" }} value={k.synonyms ?? []} open={false} tokenSeparators={[",", "，"]}
        onChange={(v: string[]) => update((p) => { if (v.length) p.keywords[i].synonyms = [...new Set(v)]; else delete p.keywords[i].synonyms; })} /> },
    { title: s.kw.category, width: 170, render: (_: unknown, k: Keyword, i: number) => <Select showSearch style={{ width: "100%" }} value={k.category}
        options={[...new Set([...s.categories.map((c) => c.value), ...(current?.keywords.map((x) => x.category) ?? [])])].map((v) => ({ value: v, label: s.categories.find((c) => c.value === v)?.label ?? v }))}
        onChange={(v) => update((p) => { p.keywords[i].category = v; })} /> },
    { title: s.kw.id, render: (_: unknown, k: Keyword) => <Typography.Text code style={{ fontSize: 12 }}>{k.term_id}</Typography.Text> },
    { title: "", width: 50, render: (_: unknown, _k: Keyword, i: number) => <Button size="small" danger icon={<DeleteOutlined />} aria-label={s.kw.remove} onClick={() => update((p) => { p.keywords.splice(i, 1); })} /> },
  ];
  const addKeyword = (label: string) => update((p) => {
    let id = `custom.${slug(label)}`; while (p.keywords.some((k) => k.term_id === id)) id += "-2";
    p.keywords.push({ term_id: id, category: "technology", label, enabled: true });
  });
  const models = bundle.settings.scoreModels;
  const model = models.find((m) => m.scoreModelId === current?.score_model?.score_model_id);

  return (
    <>
      <PageHeader title={t.nav.settings} />
      <DataOriginBanner origin={bundle.dataOrigin} />
      <Alert type="info" showIcon style={{ margin: `${space.md}px 0` }} data-testid="settings-flow" message={s.flowTitle}
        description={<ol style={{ margin: 0, paddingLeft: 20 }}>{s.flow.map((x) => <li key={x}>{x}</li>)}</ol>} />
      {!stored && <Alert type="warning" showIcon message={s.storageOff} style={{ marginBottom: space.md }} />}
      <Row gutter={[space.md, space.md]}>
        <Col xs={24} lg={8}>
          <Card title={s.topics} data-testid="profile-list" extra={
            <Space size={4}>
              <Button size="small" icon={<PlusOutlined />} onClick={() => ask(s.newTopic, "", (n) => create(null, n))} data-testid="profile-new">{s.add}</Button>
              <Upload accept=".json,application/json" showUploadList={false} beforeUpload={importFile}><Button size="small" icon={<UploadOutlined />} data-testid="profile-import">{s.import}</Button></Upload>
            </Space>}>
            <List dataSource={states} renderItem={(x) => (
              <List.Item onClick={() => setSelected(x.profileId)} style={{ cursor: "pointer", background: x.profileId === st?.profileId ? color.brandSoft : undefined, paddingInline: 8 }} data-testid="profile-item">
                <Space direction="vertical" size={2}><Typography.Text strong>{x.name}</Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>{s.modes[(x.draft ?? x.submitted)!.mode].short}</Typography.Text><StateTags st={x} /></Space>
              </List.Item>
            )} />
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          {!current || !st ? <Card>{s.empty}</Card> : (
            <Card data-testid="profile-editor" title={<Space wrap>{current.name}<StateTags st={st} /></Space>} extra={
              <Space size={4} wrap>
                <Button size="small" icon={<EditOutlined />} onClick={() => ask(s.rename, current.name, (n) => update((p) => { p.name = n; }))} data-testid="profile-rename">{s.renameBtn}</Button>
                <Button size="small" icon={<CopyOutlined />} onClick={() => create(current, `${current.name} ${s.copySuffix}`)} data-testid="profile-copy">{s.copy}</Button>
                {st.draft && st.submitted && <Button size="small" icon={<RollbackOutlined />} onClick={remove}>{s.discard}</Button>}
                {st.draft && !st.submitted && <Button size="small" danger icon={<DeleteOutlined />} onClick={() => Modal.confirm({ title: s.deleteConfirm(current.name), onOk: remove })} data-testid="profile-delete">{s.delete}</Button>}
              </Space>}>
              {st.unsubmitted && <Alert type="warning" showIcon style={{ marginBottom: space.md }} message={s.unsubmittedWarn} data-testid="unsubmitted-warning" />}
              {errors.length > 0 && <Alert type="error" showIcon style={{ marginBottom: space.md }} message={s.invalid} description={errors.join("；")} data-testid="profile-errors" />}
              <Space direction="vertical" size={space.md} style={{ width: "100%" }}>
                <Input.TextArea value={current.description ?? ""} placeholder={s.description} autoSize onChange={(e) => update((p) => { if (e.target.value) p.description = e.target.value; else delete p.description; })} />
                <Radio.Group value={current.mode} onChange={(e) => update((p) => { p.mode = e.target.value as AnalysisMode; if (p.mode !== "bxr_opportunity" && p.targets) delete p.targets.bxr_product_ids; })} data-testid="mode">
                  <Space direction="vertical">{(Object.keys(s.modes) as AnalysisMode[]).map((m) => <Radio key={m} value={m}><b>{s.modes[m].short}</b>　<Typography.Text type="secondary">{s.modes[m].desc}</Typography.Text></Radio>)}</Space>
                </Radio.Group>
                <Tabs items={[
                  { key: "kw", label: s.tabs.keywords(current.keywords.filter((k) => k.enabled).length, current.keywords.length), children: (
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Input.Search enterButton={s.kw.add} placeholder={s.kw.addPlaceholder} onSearch={(v) => v.trim() && addKeyword(v.trim())} data-testid="keyword-add" allowClear />
                      <Table<Keyword> size="small" rowKey="term_id" dataSource={current.keywords} columns={kwCols} pagination={{ pageSize: 15 }} scroll={{ x: 900 }} data-testid="keyword-table" />
                    </Space>) },
                  { key: "rel", label: s.tabs.relationships, children: (
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Typography.Text type="secondary">{s.relHint}</Typography.Text>
                      {REL_TYPES.map((r) => (
                        <div key={r}><Typography.Text strong>{t.opportunities.relType[r]}</Typography.Text>
                          <Select mode="tags" open={false} style={{ width: "100%" }} value={current.relationship_signals?.[r] ?? []} tokenSeparators={[",", "，"]}
                            onChange={(v: string[]) => update((p) => { p.relationship_signals = { ...(p.relationship_signals ?? {}), [r]: [...new Set(v)] }; if (!v.length) delete p.relationship_signals[r]; })} data-testid={`signals-${r}`} />
                        </div>))}
                    </Space>) },
                  { key: "score", label: s.tabs.scoring, children: (
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Typography.Text type="secondary">{s.scoreHint}</Typography.Text>
                      <Select style={{ width: 280 }} value={current.score_model?.score_model_id ?? ""} data-testid="score-model"
                        options={[{ value: "", label: s.noScore }, ...models.map((m) => ({ value: m.scoreModelId, label: `${m.scoreModelId}（${m.approvalStatus === "approved" ? "已核定" : "草稿"}）` }))]}
                        onChange={(v) => update((p) => { if (!v) delete p.score_model; else p.score_model = { score_model_id: v, weights: Object.fromEntries(models.find((m) => m.scoreModelId === v)!.factors.map((f) => [f.factorId, f.defaultMax])) }; })} />
                      {model && current.score_model && (
                        <Descriptions size="small" column={1} bordered items={model.factors.map((f) => ({ key: f.factorId, label: f.label, children:
                          <InputNumber min={0} precision={0} value={current.score_model!.weights[f.factorId] ?? f.defaultMax} onChange={(v) => update((p) => { p.score_model!.weights[f.factorId] = Math.max(0, Math.round(Number(v ?? 0))); })} addonAfter={s.points} /> }))} />
                      )}
                    </Space>) },
                  { key: "targets", label: s.tabs.targets, children: (
                    current.mode === "bxr_opportunity" ? (
                      <Space direction="vertical" style={{ width: "100%" }}>
                        <Alert type="warning" showIcon message={s.productsDraft} />
                        <Select mode="multiple" style={{ width: "100%" }} value={current.targets?.bxr_product_ids ?? []} data-testid="products"
                          options={bundle.settings.products.map((p) => ({ value: p.productId, label: `${p.name}${p.approvalStatus === "approved" ? "" : "（待審核）"}` }))}
                          onChange={(v: string[]) => update((p) => { p.targets = { ...(p.targets ?? {}), bxr_product_ids: v }; })} />
                      </Space>
                    ) : (
                      <Space direction="vertical" style={{ width: "100%" }}>
                        <Typography.Text type="secondary">{current.mode === "competitor_research" ? s.competitorHint : s.industryHint}</Typography.Text>
                        {current.mode === "competitor_research" && <>
                          <Typography.Text strong>{s.companies}</Typography.Text>
                          <Select mode="tags" open={false} style={{ width: "100%" }} value={current.targets?.company_names ?? []} onChange={(v: string[]) => update((p) => { p.targets = { ...(p.targets ?? {}), company_names: v }; })} />
                          <Typography.Text strong>{s.focus}</Typography.Text>
                          <Select mode="multiple" style={{ width: "100%" }} value={current.targets?.focus_term_ids ?? []} options={current.keywords.map((k) => ({ value: k.term_id, label: k.label }))}
                            onChange={(v: string[]) => update((p) => { p.targets = { ...(p.targets ?? {}), focus_term_ids: v }; })} />
                        </>}
                      </Space>
                    )) },
                  { key: "submit", label: s.tabs.submit, children: (
                    <Space direction="vertical" style={{ width: "100%" }} data-testid="submit-panel">
                      <Descriptions size="small" column={1} items={[
                        { key: "s", label: s.submittedVersion, children: st.submitted ? `v${st.submitted.version}（${st.submittedHash!.slice(0, 19)}…）` : s.state.notSubmitted },
                        { key: "d", label: s.localVersion, children: st.draft ? `${profileHash(st.draft).slice(0, 19)}…${st.unsubmitted ? `（${s.state.draft}）` : ""}` : s.sameAsSubmitted },
                        { key: "a", label: s.usedBy, children: st.analyses.length ? st.analyses.map((a) => `${a.title}（v${a.profileVersion}${a.matchesSubmitted ? "" : `，${s.olderVersion}`}）`).join("；") : s.notUsed },
                      ]} />
                      <Space wrap>
                        <Button type="primary" icon={<DownloadOutlined />} disabled={errors.length > 0} data-testid="profile-export"
                          onClick={() => download(`${current.profile_id}.json`, JSON.stringify(forSubmission(current, st.submitted), null, 2) + "\n")}>{s.export}</Button>
                        <Typography.Text code>{s.submitPath}</Typography.Text>
                      </Space>
                      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>{s.submitSteps}</Typography.Paragraph>
                    </Space>) },
                ]} />
              </Space>
            </Card>
          )}
        </Col>
      </Row>
    </>
  );
}
