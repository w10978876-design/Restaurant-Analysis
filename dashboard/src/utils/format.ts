/**
 * 统一数值与百分比展示：小数保留两位，占比/率以 xx.xx% 显示
 */

/** 是否为“比例/率/占比”类列名（用于自动识别百分比列） */
export function isPercentLikeColumn(name: string): boolean {
  const n = String(name);
  return (
    n.includes('率') ||
    n.includes('占比') ||
    n.includes('环比') ||
    n.includes('同比') ||
    n.includes('转化率') ||
    n.includes('活跃度') ||
    n.includes('MoM') ||
    n.includes('WoW')
  );
}

/** 数值保留两位小数；整数不补 .00；大数千分位 */
export function formatNumber(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'number' ? value : parseFloat(String(value).replace(/,/g, ''));
  if (Number.isNaN(num)) return String(value ?? '');
  if (Number.isInteger(num)) return num.toLocaleString('zh-CN');
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** 百分比：0.05 → "5.00%"，"33.33%" 保持两位小数，非数字原文返回 */
export function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const s = String(value).trim();
  if (/^[\d.]+%$/.test(s)) {
    const num = parseFloat(s.replace('%', ''));
    return Number.isNaN(num) ? s : `${num.toFixed(2)}%`;
  }
  const num = parseFloat(s.replace(/,/g, ''));
  if (Number.isNaN(num)) return s;
  if (num > 1 && num <= 100) return `${num.toFixed(2)}%`;
  if (num >= 0 && num <= 1) return `${(num * 100).toFixed(2)}%`;
  if (num > 100) return `${num.toFixed(2)}%`;
  return `${(num * 100).toFixed(2)}%`;
}

/** 表格单元格展示：根据列名与值判断用数字还是百分比 */
export function formatCell(
  columnName: string,
  value: string | number | null | undefined
): string {
  if (value === null || value === undefined) return '—';
  const s = String(value).trim();

  // 日期 / 时间 / 时段类字段：直接原样展示，避免被当作数字截断（如 2026-02-01 → 2026）
  const col = String(columnName);
  const isDateLike =
    col.includes('日期') ||
    col.toLowerCase().includes('date') ||
    col.includes('时间') ||
    col.toLowerCase().includes('time') ||
    col.includes('周起始日') ||
    col.includes('周') ||
    col.includes('星期') ||
    col.includes('时段') ||
    col.toLowerCase().includes('month');
  const looksLikeDateOrTime =
    /^\d{4}-\d{1,2}-\d{1,2}/.test(s) || // 2026-02-01
    /^\d{1,2}:\d{2}/.test(s) || // 10:00 或 10:00-11:30
    s.includes('至') || // 2026-02-01 至 2026-02-28
    s.includes('周'); // 周一、周日

  if (isDateLike || looksLikeDateOrTime) {
    return s;
  }

  // 名称类字段（券名称、菜品名称等）直接原样展示，避免将「200元代金券」解析成数字 200
  const isNameLike =
    col.includes('名称') ||
    col.toLowerCase().includes('name') ||
    col.includes('券') ||
    col.includes('菜品');
  if (isNameLike) {
    return s;
  }

  if (isPercentLikeColumn(columnName)) {
    if (/无正向|—|^-$/.test(s)) return s;
    return formatPercent(value);
  }
  const num = typeof value === 'number' ? value : parseFloat(s.replace(/,/g, ''));
  if (Number.isNaN(num)) return s;
  return formatNumber(num);
}
