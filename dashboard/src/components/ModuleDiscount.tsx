import { useState } from 'react';
import { motion } from 'motion/react';
import { PercentDiamond, Maximize2, X } from 'lucide-react';
import { findSection, findTable, type Report } from '../data/report';
import { DataTable } from './DataTable';

interface ModuleDiscountProps {
  report: Report | null;
}

export function ModuleDiscount({ report }: ModuleDiscountProps) {
  const [openStaff, setOpenStaff] = useState(false);
  const [openByWeek, setOpenByWeek] = useState(false);

  const sec = findSection(report, '7_discount');
  if (!sec) return null;

  const kpiTable = findTable(sec, '总体优惠占比');
  const methodTable = findTable(sec, '优惠方式分布');
  const byTimeTable = findTable(sec, '优惠时段分布');
  const byWeekTable = findTable(sec, '优惠星期分布');
  const staffTable = findTable(sec, '员工维度优惠占比');
  const dishTable = findTable(sec, '优惠关联菜品Top15');

  const kpiRows = kpiTable?.rows ?? [];

  if (!kpiRows.length && !methodTable && !byTimeTable && !dishTable) return null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="mb-1 text-lg font-bold text-gray-900">优惠策略效果</h2>
          <p className="text-sm text-gray-500">
            总体优惠占比、方式结构、时段与关联菜品，帮助评估优惠策略是否精准触达。
          </p>
        </div>
        <PercentDiamond className="h-5 w-5 text-rose-500" />
      </div>

      {kpiRows.length > 0 && (
        <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {kpiRows.slice(0, 4).map((row, idx) => {
            const rawLabel = String(row[0]);
            // 去掉末尾的「占比」等字样，仅保留「占全期销售额」「占已结账订单」等
            const label = rawLabel.replace(/占比.*$/u, '');
            const unit = String(row[2] ?? '');
            const showUnit = unit && !unit.includes('占比');

            // 对「占全期销售额」「占已结账订单」等行，将 0.x 数值转成百分比展示
            const isRatioRow =
              label.includes('占全期销售额') ||
              label.includes('占已结账订单');
            let displayValue: string;
            if (isRatioRow) {
              const num = typeof row[1] === 'number' ? row[1] : parseFloat(String(row[1]));
              displayValue = Number.isNaN(num) ? String(row[1] ?? '') : `${(num * 100).toFixed(2)}%`;
            } else {
              displayValue = String(row[1] ?? '');
            }

            return (
              <div
                key={idx}
                className="rounded-xl border border-rose-100 bg-rose-50/70 px-3 py-2.5"
              >
                <p className="text-xs text-gray-500">{label}</p>
                <p className="mt-1 text-base font-semibold text-rose-700">
                  {displayValue}
                  {showUnit ? (
                    <span className="ml-1 text-xs text-gray-500">{unit}</span>
                  ) : null}
                </p>
              </div>
            );
          })}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2 items-stretch mb-6">
        <div className="flex flex-col h-full">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-gray-600">优惠方式分布</p>
            {staffTable && (
              <button
                type="button"
                onClick={() => setOpenStaff(true)}
                className="text-xs font-medium text-rose-700 hover:text-rose-900"
              >
                查看员工维度
              </button>
            )}
          </div>
          <div className="mt-1 flex-1 min-h-[220px] max-h-[320px] overflow-y-auto pr-1">
            <DataTable table={methodTable} defaultVisibleRows={5} />
          </div>
        </div>

        <div className="flex flex-col h-full">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-gray-600">优惠时段分布</p>
            {byWeekTable && (
              <button
                type="button"
                onClick={() => setOpenByWeek(true)}
                className="text-xs font-medium text-rose-700 hover:text-rose-900"
              >
                查看按星期分布
              </button>
            )}
          </div>
          <div className="mt-1 flex-1 min-h-[220px] max-h-[320px] overflow-y-auto pr-1">
            <DataTable table={byTimeTable} defaultVisibleRows={5} />
          </div>
        </div>
      </div>

      <div>
        <p className="mb-2 text-sm font-medium text-gray-600">优惠关联菜品 Top15</p>
        <div className="max-h-[320px] overflow-y-auto pr-1">
          <DataTable table={dishTable} defaultVisibleRows={5} />
        </div>
      </div>

      {openStaff && staffTable && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-gray-500" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">员工维度优惠占比</p>
                  <p className="text-xs text-gray-500">已剔除虚拟账号，从员工视角查看优惠占比</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpenStaff(false)}
                className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-5">
              <DataTable table={staffTable} defaultVisibleRows={10} />
            </div>
          </div>
        </div>
      )}

      {openByWeek && byWeekTable && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-gray-500" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">优惠星期分布</p>
                  <p className="text-xs text-gray-500">从星期维度查看优惠订单与金额的集中程度</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpenByWeek(false)}
                className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-5">
              <DataTable table={byWeekTable} defaultVisibleRows={10} />
            </div>
          </div>
        </div>
      )}
    </motion.section>
  );
}

