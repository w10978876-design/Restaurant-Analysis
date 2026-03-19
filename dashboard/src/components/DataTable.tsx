import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { ReportTable } from '../data/report';
import { formatCell } from '../utils/format';

const DEFAULT_VISIBLE = 5;

/** 若最后一列是「单位」，则隐藏该列，并将单位合并到前一列的表头与单元格 */
function useNormalizedColumns(table: ReportTable | null) {
  return useMemo(() => {
    if (!table?.columns?.length) return { columns: [] as string[], unitColIndex: -1 };
    const cols = table.columns;
    const unitColIndex =
      cols[cols.length - 1] === '单位' ? cols.length - 1 : -1;
    const columns =
      unitColIndex >= 0 ? cols.slice(0, unitColIndex) : [...cols];
    return { columns, unitColIndex };
  }, [table]);
}

interface DataTableProps {
  table: ReportTable | null;
  defaultVisibleRows?: number;
  className?: string;
}

export function DataTable({
  table,
  defaultVisibleRows = DEFAULT_VISIBLE,
  className = '',
}: DataTableProps) {
  const [expanded, setExpanded] = useState(false);
  const { columns, unitColIndex } = useNormalizedColumns(table);
  if (!table?.columns?.length || !columns.length) return null;

  const rows = table.rows ?? [];
  const visibleRows = expanded ? rows : rows.slice(0, defaultVisibleRows);
  const hasMore = rows.length > defaultVisibleRows;

  /** 表头：仅当单位列所有行相同时才合并到前一列表头，否则不写单位（单位已在单元格内展示） */
  const headerLabels = useMemo(() => {
    if (unitColIndex < 0) return columns;
    const units = rows.map((r) => r[unitColIndex]);
    const allSame =
      units.length > 0 && units.every((u) => String(u) === String(units[0]));
    const unit = allSame && units[0] != null ? String(units[0]) : '';
    return columns.map((col, i) =>
      i === columns.length - 1 && unit ? `${col} (${unit})` : col
    );
  }, [columns, unitColIndex, rows]);

  return (
    <div className={`overflow-x-auto rounded-xl border border-gray-200 bg-white ${className}`}>
      <table className="w-full min-w-[400px] text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            {headerLabels.map((col, i) => (
              <th
                key={i}
                className="px-4 py-3 text-left font-semibold text-gray-700"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <AnimatePresence mode="popLayout">
            {visibleRows.map((row, ri) => (
              <motion.tr
                key={ri}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="border-b border-gray-100 even:bg-gray-50/50"
              >
                {columns.map((colName, ci) => {
                  const raw = row[ci];
                  const unit =
                    unitColIndex >= 0 && ci === columns.length - 1
                      ? row[unitColIndex]
                      : null;
                  const display = formatCell(colName, raw);
                  const suffix =
                    unit != null && unit !== '' ? ` ${String(unit)}` : '';
                  return (
                    <td key={ci} className="px-4 py-2.5 text-gray-800">
                      {display}
                      {suffix}
                    </td>
                  );
                })}
              </motion.tr>
            ))}
          </AnimatePresence>
        </tbody>
      </table>
      {hasMore && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex w-full items-center justify-center gap-1 border-t border-gray-200 bg-gray-50 py-2 text-sm font-medium text-blue-600 hover:bg-gray-100"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-4 w-4" />
              收起
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" />
              展开全部（共 {rows.length} 行）
            </>
          )}
        </button>
      )}
    </div>
  );
}
