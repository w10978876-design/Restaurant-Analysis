import { useMemo } from 'react';
import { motion } from 'motion/react';
import { AlertTriangle, Link2 } from 'lucide-react';
import { findSection, findTable, type Report } from '../data/report';
import { DataTable } from './DataTable';
import { formatNumber, formatPercent } from '../utils/format';

function getRiskLevel(rate: number): '高' | '中' | '低' {
  if (rate >= 0.15) return '高';
  if (rate >= 0.05) return '中';
  return '低';
}

interface ModuleDishProps {
  report: Report | null;
}

export function ModuleDish({ report }: ModuleDishProps) {
  const dishSec = findSection(report, '6_dish');
  const refundSec = findSection(report, '3_refund');

  const cooccurTable = findTable(dishSec, '菜品关联度');
  const refundTopTable = findTable(refundSec, '退菜率Top5菜品');

  const refundCards = useMemo(() => {
    if (!refundTopTable?.rows?.length || !refundTopTable.columns?.length) return [];
    const cols = refundTopTable.columns;
    const iDish = cols.findIndex((c) => c.includes('菜品'));
    const iQty = cols.findIndex((c) => c.includes('退菜数量'));
    const iAmt = cols.findIndex((c) => c.includes('退菜金额'));
    const iOrders = cols.findIndex((c) => c.includes('涉及订单数'));
    const iRate = cols.findIndex((c) => c.includes('退菜率'));
    if (iDish < 0 || iRate < 0) return [];

    return refundTopTable.rows.slice(0, 5).map((row) => {
      const rawRate = row[iRate];
      const rateNum =
        typeof rawRate === 'number'
          ? rawRate
          : typeof rawRate === 'string' && !Number.isNaN(parseFloat(rawRate))
            ? parseFloat(rawRate)
            : null;
      const risk =
        rateNum == null ? '低' : getRiskLevel(rateNum);
      return {
        dish: String(row[iDish]),
        退菜率: rateNum,
        退菜率原文: row[iRate],
        退菜数量: iQty >= 0 ? Number(row[iQty]) || 0 : 0,
        退菜金额: iAmt >= 0 ? Number(row[iAmt]) || 0 : 0,
        涉及订单数: iOrders >= 0 ? Number(row[iOrders]) || 0 : 0,
        风险等级: risk as '高' | '中' | '低',
      };
    });
  }, [refundTopTable]);

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <h2 className="mb-1 text-lg font-bold text-gray-900">菜品与退菜行为</h2>
      <p className="mb-6 text-sm text-gray-500">
        左侧是常一起点的菜品组合，右侧是退菜率 Top 菜品与高退菜率风险标记，关注退菜集中风险。
      </p>

      <div className="grid gap-6 lg:grid-cols-2 items-stretch">
        <div className="flex flex-col h-full">
          <p className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-600">
            <Link2 className="h-4 w-4" />
            菜品共现订单数（A+B 常一起点）
          </p>
          <div className="mt-1 flex-1 min-h-[260px] max-h-[320px] overflow-y-auto pr-1">
            <DataTable table={cooccurTable} defaultVisibleRows={5} />
          </div>
        </div>

        <div className="flex flex-col h-full space-y-3">
          <p className="mb-1 flex items-center gap-2 text-sm font-medium text-gray-600">
            <AlertTriangle className="h-4 w-4 text-pink-500" />
            退菜行为（含高退菜率风险标记）
          </p>
          <div className="space-y-3 flex-1 min-h-[260px] max-h-[320px] overflow-y-auto pr-1">
            {refundCards.map((c, i) => (
              <motion.div
                key={c.dish}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.05 * i }}
                className={`rounded-xl border p-4 ${
                  c.风险等级 === '高'
                    ? 'border-pink-200 bg-pink-50/80'
                    : c.风险等级 === '中'
                      ? 'border-amber-200 bg-amber-50/80'
                      : 'border-gray-200 bg-gray-50/80'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-gray-900">{c.dish}</p>
                    <p className="mt-1 text-xs text-gray-500">
                      退菜率{' '}
                      {c.退菜率 != null
                        ? formatPercent(c.退菜率)
                        : String(c.退菜率原文 ?? '')}{' '}
                      · 退菜金额 {formatNumber(c.退菜金额)} 元 · 退菜订单 {c.涉及订单数} 单
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                      c.风险等级 === '高'
                        ? 'bg-pink-200 text-pink-800'
                        : c.风险等级 === '中'
                          ? 'bg-amber-200 text-amber-800'
                          : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    {c.风险等级 === '低' ? '关注' : `风险${c.风险等级}`}
                  </span>
                </div>
              </motion.div>
            ))}
            {!refundCards.length && (
              <p className="text-xs text-gray-500">当前周期暂无明显的高退菜率菜品。</p>
            )}
          </div>
        </div>
      </div>
    </motion.section>
  );
}

