import { useState } from 'react';
import { motion } from 'motion/react';
import { Clock3, Maximize2, X } from 'lucide-react';
import { findSection, findTable, type Report } from '../data/report';
import { DataTable } from './DataTable';

interface ModuleTimeCrossProps {
  report: Report | null;
}

export function ModuleTimeCross({ report }: ModuleTimeCrossProps) {
  const [open, setOpen] = useState(false);
  const sec = findSection(report, '2_time');
  if (!sec) return null;

  const crossTable = findTable(sec, '星期×时段');
  const summaryTable = findTable(sec, '最忙Top3与冷清Bottom3');

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-gray-900">营业时段交叉</h2>
          <p className="mt-1 text-sm text-gray-500">
            直观查看本周期最忙与最冷清的「星期 × 时段」组合，完整交叉表可在弹窗中查看。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
        >
          <Clock3 className="h-3.5 w-3.5" />
          查看完整营业时段交叉
        </button>
      </div>

      {summaryTable ? (
        <div className="mt-2">
          <DataTable table={summaryTable} defaultVisibleRows={6} />
        </div>
      ) : (
        <p className="mt-2 text-sm text-gray-500">当前周期暂无「最忙/最冷清时段」汇总数据。</p>
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

