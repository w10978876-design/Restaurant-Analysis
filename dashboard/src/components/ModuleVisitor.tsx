import { useState } from 'react';
import { motion } from 'motion/react';
import { Users, Maximize2, X } from 'lucide-react';
import { findSection, findTable, type Report } from '../data/report';
import { DataTable } from './DataTable';

interface ModuleVisitorProps {
  report: Report | null;
}

export function ModuleVisitor({ report }: ModuleVisitorProps) {
  const [open, setOpen] = useState(false);
  const sec = findSection(report, '12_visitor');
  if (!sec) return null;

  const kpiTable = findTable(sec, '进馆转化率概览');
  const detailTable = findTable(sec, '日度进馆与用餐对照');
  const kpiRows = kpiTable?.rows ?? [];

  if (!kpiRows.length && !detailTable) return null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.12 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-5 shadow-lg shadow-gray-200/50"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="mb-1 text-lg font-bold text-gray-900">进馆游客与转化率</h2>
          <p className="text-sm text-gray-500">
            查看有游客量数据的天数与平均进馆转化率，明细按日度对照进馆人数与用餐人数。
          </p>
        </div>
        {detailTable && (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
          >
            <Users className="h-3.5 w-3.5" />
            查看日度进馆与用餐
          </button>
        )}
      </div>

      {kpiRows.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {kpiRows.map((row, idx) => (
            <div
              key={idx}
              className="rounded-xl border border-emerald-100 bg-emerald-50/70 px-3 py-2.5"
            >
              <p className="text-xs text-gray-500">{row[0]}</p>
              <p className="mt-1 text-base font-semibold text-emerald-700">
                {String(row[1])}
                {row[2] ? <span className="ml-1 text-xs text-gray-500">{row[2]}</span> : null}
              </p>
            </div>
          ))}
        </div>
      )}

      {open && detailTable && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-gray-500" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">日度进馆与用餐对照</p>
                  <p className="text-xs text-gray-500">按日期查看进馆人数、用餐人数与转化率</p>
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
              <DataTable table={detailTable} defaultVisibleRows={10} />
            </div>
          </div>
        </div>
      )}
    </motion.section>
  );
}

