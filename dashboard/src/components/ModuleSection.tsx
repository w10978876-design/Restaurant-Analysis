import { useState } from 'react';
import { motion } from 'motion/react';
import { Clock3, Maximize2, X } from 'lucide-react';
import { findSection, findTable, type Report } from '../data/report';
import { DataTable } from './DataTable';

interface ModuleSectionProps {
  report: Report | null;
  sectionId: string;
  title?: string;
  description?: string;
}

export function ModuleSection({ report, sectionId, title, description }: ModuleSectionProps) {
  const sec = findSection(report, sectionId);
  if (!sec) return null;

  // 特殊处理：2_time 营业时段交叉 → 默认只展示 Top3/Bottom3，完整交叉放在弹窗中
  if (sectionId === '2_time') {
    const [open, setOpen] = useState(false);
    const crossTable = findTable(sec, '星期×时段');
    const summaryTable = findTable(sec, '最忙Top3与冷清Bottom3');

    const hasContent =
      (summaryTable && summaryTable.rows && summaryTable.rows.length > 0) ||
      (crossTable && crossTable.rows && crossTable.rows.length > 0);

    if (!hasContent) {
      return (
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
        >
          <h2 className="mb-1 text-lg font-bold text-gray-900">{title ?? sec.title}</h2>
          {description && <p className="mb-4 text-sm text-gray-500">{description}</p>}
          <p className="text-sm text-gray-500">本餐厅在当前周期暂无营业时段交叉数据。</p>
        </motion.section>
      );
    }

    return (
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-gray-900">{title ?? '营业时段交叉'}</h2>
            <p className="mt-1 text-sm text-gray-500">
              最忙与冷清的「星期 × 时段」组合概览，完整交叉表可通过右侧按钮查看。
            </p>
          </div>
          {crossTable && (
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
            >
              <Clock3 className="h-3.5 w-3.5" />
              查看完整营业时段交叉
            </button>
          )}
        </div>

        {summaryTable ? (
          <div className="mt-2">
            <DataTable table={summaryTable} defaultVisibleRows={6} />
          </div>
        ) : (
          <p className="mt-2 text-sm text-gray-500">当前周期暂无 Top3/Bottom3 汇总，仅可在弹窗中查看完整交叉表。</p>
        )}

        {open && crossTable && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
            <div className="max-h-[80vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
              <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
                <div className="flex items-center gap-2">
                  <Maximize2 className="h-4 w-4 text-gray-500" />
                  <div>
                    <p className="text-sm font-semibold text-gray-900">完整营业时段交叉</p>
                    <p className="text-xs text-gray-500">星期 × 营业时段的销售额与订单数分布</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  aria-label="关闭"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="max-h-[70vh] overflow-auto p-5">
                <DataTable table={crossTable} defaultVisibleRows={20} />
              </div>
            </div>
          </div>
        )}
      </motion.section>
    );
  }

  const mainTable = findTable(sec, '');
  const otherTables = sec.tables.filter((t) => t !== mainTable);

  const hasContent =
    (sec.conclusions && sec.conclusions.length > 0) ||
    (mainTable && mainTable.rows && mainTable.rows.length > 0) ||
    otherTables.some((t) => t.rows && t.rows.length > 0);

  if (!hasContent) {
    return (
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
      >
        <h2 className="mb-1 text-lg font-bold text-gray-900">{title ?? sec.title}</h2>
        {description && <p className="mb-4 text-sm text-gray-500">{description}</p>}
        <p className="text-sm text-gray-500">本餐厅在当前周期暂无相关数据。</p>
      </motion.section>
    );
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <h2 className="mb-1 text-lg font-bold text-gray-900">{title ?? sec.title}</h2>
      {description && <p className="mb-4 text-sm text-gray-500">{description}</p>}
      {!description && sec.conclusions.length > 0 && (
        <ul className="mb-4 list-inside list-disc space-y-1 text-sm text-gray-700">
          {sec.conclusions.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}

      {mainTable && (
        <div className="mt-2">
          <DataTable table={mainTable} defaultVisibleRows={5} />
        </div>
      )}

      {otherTables.length > 0 && (
        <div className="mt-4 space-y-4">
          {otherTables.map((t) => (
            <div key={t.name}>
              <p className="mb-2 text-xs font-medium text-gray-500">{t.name}</p>
              <DataTable table={t} defaultVisibleRows={5} />
            </div>
          ))}
        </div>
      )}
    </motion.section>
  );
}

