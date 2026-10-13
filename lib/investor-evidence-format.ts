export function investorEvidenceDateLabel(date: string, precision: string): string {
  if (precision === "unknown" || !date) return "原文未标事件日期";
  return `${date}（${precision === "year" ? "仅年份" : precision === "month" ? "仅月份" : "日级日期"}）`;
}

