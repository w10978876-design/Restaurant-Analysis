import { useState } from 'react';
import { motion } from 'motion/react';
import { TicketPercent, Maximize2, X } from 'lucide-react';
import { findSection, findTable, type Report } from '../data/report';
import { DataTable } from './DataTable';

interface ModuleGrouponProps {
  report: Report | null;
}

export function ModuleGroupon({ report }: ModuleGrouponProps) {
  const [openByDate, setOpenByDate] = useState(false);
  const [openCancel, setOpenCancel] = useState(false);

  const sec = findSection(report, '10_groupon');
  if (!sec) return null;

  const kpiTable = findTable(sec, '团购总体指标');
  const byDateTable = findTable(sec, '按日期的团购分布');
  const byTimeTable = findTable(sec, '按时间段的团购分布');
  const byCouponTable = findTable(sec, '按券名称(平台项目名称)的团购效果');
  const cancelKpiTable = findTable(sec, '团购撤销概览');
  const cancelDetailTable = findTable(sec, '撤销主要集中在哪些团购券');

  const kpiRows = kpiTable?.rows ?? [];

  if (!kpiRows.length && !byTimeTable && !byCouponTable) return null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="mb-1 text-lg font-bold text-gray-900">团购核销分析</h2>
          <p className="text-sm text-gray-500">
            了解团购订单在整体中的占比，以及在时间段和券名称维度上的表现与撤销情况。
          </p>
        </div>
        <TicketPercent className="h-5 w-5 text-violet-500" />
      </div>

      {kpiRows.length > 0 && (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {kpiRows.slice(0, 8).map((row, idx) => (
            <div
              key={idx}
              className="rounded-xl border border-violet-100 bg-violet-50/70 px-3 py-2.5"
            >
              <p className="text-xs text-gray-500">{row[0]}</p>
              <p className="mt-1 text-base font-semibold text-violet-700">
                {String(row[1])}
                {row[2] ? <span className="ml-1 text-xs text-gray-500">{row[2]}</span> : null}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2 items-stretch">
        <div className="flex flex-col h-full">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-gray-600">按时间段的团购分布</p>
            {byDateTable && (
              <button
                type="button"
                onClick={() => setOpenByDate(true)}
                className="text-xs font-medium text-violet-700 hover:text-violet-900"
              >
                查看按日期分布
              </button>
            )}
          </div>
          <div className="mt-1 flex-1 min-h-[220px] max-h-[320px] overflow-y-auto pr-1">
            <DataTable table={byTimeTable} defaultVisibleRows={5} />
          </div>
        </div>

        <div className="flex flex-col h-full">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-gray-600">按券名称的团购效果</p>
            {(cancelKpiTable || cancelDetailTable) && (
              <button
                type="button"
                onClick={() => setOpenCancel(true)}
                className="text-xs font-medium text-violet-700 hover:text-violet-900"
              >
                查看撤销情况
              </button>
            )}
          </div>
          <div className="mt-1 flex-1 min-h-[220px] max-h-[320px] overflow-y-auto pr-1">
            <DataTable table={byCouponTable} defaultVisibleRows={5} />
          </div>
        </div>
      </div>

      {openByDate && byDateTable && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-gray-500" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">按日期的团购分布</p>
                  <p className="text-xs text-gray-500">每天的团购订单、券笔数与销售额占比</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpenByDate(false)}
                className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-5">
              <DataTable table={byDateTable} defaultVisibleRows={10} />
            </div>
          </div>
        </div>
      )}

      {openCancel && (cancelKpiTable || cancelDetailTable) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-gray-500" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">团购撤销概览</p>
                  <p className="text-xs text-gray-500">撤销总量及主要集中在哪些团购券</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpenCancel(false)}
                className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-5 space-y-4">
              {cancelKpiTable && (
                <div>
                  <p className="mb-2 text-xs font-medium text-gray-600">撤销总体情况</p>
                  <DataTable table={cancelKpiTable} defaultVisibleRows={5} />
                </div>
              )}
              {cancelDetailTable && (
                <div>
                  <p className="mb-2 text-xs font-medium text-gray-600">撤销主要集中券种</p>
                  <DataTable table={cancelDetailTable} defaultVisibleRows={10} />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </motion.section>
  );
}

