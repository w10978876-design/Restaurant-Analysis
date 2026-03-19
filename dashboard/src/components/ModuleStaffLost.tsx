import { useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { AlertTriangle, Maximize2, X } from 'lucide-react';
import { findSection, findTable, type Report } from '../data/report';
import { DataTable } from './DataTable';
import { AnimatedNumber } from './AnimatedNumber';
import { formatPercent } from '../utils/format';

interface ModuleStaffLostProps {
  report: Report | null;
}

export function ModuleStaffLost({ report }: ModuleStaffLostProps) {
  const [openTimeDate, setOpenTimeDate] = useState(false);
  const [openRemarkDetail, setOpenRemarkDetail] = useState(false);

  const lostSec = findSection(report, '8_lost');
  const sensSec = findSection(report, '9_sensitive');
  const lostByStatus = findTable(lostSec, '按状态汇总');
  const sensSummary = findTable(sensSec, '敏感操作汇总');
  const sensTime = findTable(sensSec, '敏感操作时段分布');
  const sensDate = findTable(sensSec, '敏感操作发生日期分布');
  const sensRemark = findTable(sensSec, '敏感订单整单备注(原因)统计');
  const sensRemarkDetail = findTable(sensSec, '敏感订单整单备注(原因)+优惠原因分布');

  const lostStats = useMemo(() => {
    let total = 0;
    if (lostByStatus?.rows?.length) {
      total = lostByStatus.rows.reduce((s, r) => s + (Number(r[1]) || 0), 0);
    } else {
      const summary = report?.overview?.summary ?? [];
      const m = summary[1]?.match(/(\d+)\s*单/);
      if (m) total = parseInt(m[1], 10) || 0;
    }
    return { total };
  }, [lostByStatus, report?.overview?.summary]);

  const sensLostRate = useMemo(() => {
    if (!sensSummary?.rows?.length) return 0;
    const sensTotal = sensSummary.rows.reduce((s, r) => s + (Number(r[1]) || 0), 0);
    if (!sensTotal || !Number.isFinite(sensTotal)) return 0;
    return lostStats.total / sensTotal;
  }, [sensSummary, lostStats.total]);

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <h2 className="mb-1 text-lg font-bold text-gray-900">敏感操作</h2>
      <p className="mb-6 text-sm text-gray-500">
        聚焦敏感操作的类型、时段与整单备注原因，帮助识别潜在风险与异常行为。
      </p>

      {/* 第一部分：敏感操作类型 & 时段（左右并列小卡片） */}
      <section className="mb-8 grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col rounded-xl border border-gray-200 bg-white/90 p-4 shadow-sm">
          <p className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-600">
            <AlertTriangle className="h-4 w-4 text-orange-500" />
            敏感操作类型概览
          </p>
          <div className="mt-1 max-h-[220px] flex-1 overflow-y-auto pr-1">
            <DataTable table={sensSummary} defaultVisibleRows={5} />
          </div>
        </div>

        <div className="flex flex-col rounded-xl border border-gray-200 bg-white/90 p-4 shadow-sm">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-gray-600">敏感操作时段分布</p>
            {sensDate && (
              <button
                type="button"
                onClick={() => setOpenTimeDate(true)}
                className="text-xs font-medium text-orange-600 hover:text-orange-800"
              >
                查看按日期分布
              </button>
            )}
          </div>
          <div className="mt-1 max-h-[220px] flex-1 overflow-y-auto pr-1">
            <DataTable table={sensTime} defaultVisibleRows={5} />
          </div>
        </div>
      </section>

      {/* 第二部分：敏感订单整单备注（原因）统计 */}
      <section>
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-sm font-medium text-gray-600">
            敏感订单整单备注（原因）统计
          </p>
          {sensRemarkDetail && (
            <button
              type="button"
              onClick={() => setOpenRemarkDetail(true)}
              className="text-xs font-medium text-orange-600 hover:text-orange-800"
            >
              查看备注+优惠原因分布
            </button>
          )}
        </div>
        <p className="mb-2 text-xs text-gray-500">
          当前周期共有{' '}
          <span className="font-semibold text-gray-800">
            <AnimatedNumber value={lostStats.total} />
          </span>{' '}
          单流失订单，占敏感订单约{' '}
          <span className="font-semibold text-orange-600">
            <AnimatedNumber value={formatPercent(sensLostRate)} />
          </span>
          ，下表为对应的整单备注（原因）统计。
        </p>
        <div className="max-h-[200px] overflow-y-auto pr-1">
          <DataTable table={sensRemark} defaultVisibleRows={5} />
        </div>
      </section>

      {openTimeDate && sensDate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-gray-500" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">敏感操作发生日期分布</p>
                  <p className="text-xs text-gray-500">从日期与星期视角查看敏感操作的集中情况</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpenTimeDate(false)}
                className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-5">
              <DataTable table={sensDate} defaultVisibleRows={10} />
            </div>
          </div>
        </div>
      )}

      {openRemarkDetail && sensRemarkDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-gray-500" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    敏感订单整单备注（原因）+ 优惠原因分布
                  </p>
                  <p className="text-xs text-gray-500">结合备注与优惠原因，识别高风险场景</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpenRemarkDetail(false)}
                className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-5">
              <DataTable table={sensRemarkDetail} defaultVisibleRows={10} />
            </div>
          </div>
        </div>
      )}
    </motion.section>
  );
}
