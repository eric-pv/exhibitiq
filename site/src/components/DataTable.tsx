import { DownloadOutlined } from "@ant-design/icons";
import { Button, Table, type TableProps } from "antd";

/** The single shared table: sorting, pagination, empty state and CSV export (DEVELOPMENT_PLAN §3). */
export function DataTable<T extends object>(props: TableProps<T> & { csv?: () => string; csvName?: string; exportLabel?: string }) {
  const { csv, csvName = "export.csv", exportLabel = "匯出 CSV", ...rest } = props;
  const download = () => {
    if (!csv) return;
    const url = URL.createObjectURL(new Blob([csv()], { type: "text/csv;charset=utf-8" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: csvName });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <>
      {csv && <Button icon={<DownloadOutlined />} onClick={download} style={{ marginBottom: 12 }} data-testid="csv-export">{exportLabel}</Button>}
      <Table<T> size="middle" pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ x: true }} {...rest} />
    </>
  );
}
