import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { motion } from 'motion/react';
import { findSection, findTable, type Report } from '../data/report';
import { AnimatedNumber } from './AnimatedNumber';
import { formatNumber, formatPercent } from '../utils/format';

function parseMom(mom: string | number): number | null {
  const v = typeof mom === 'number' ? mom : parseFloat(String(mom));
  if (Number.isNaN(v)) return null;
  return v;
}

interface ModuleSalesProps {
  report: Report | null;
  dailyTarget: number;
  onDailyTargetChange: (v: number) => void;
}

export function ModuleSales({ report, dailyTarget, onDailyTargetChange }: ModuleSalesProps) {
  const sec = findSection(report, '1_sales');
  const monthTable = findTable(sec, '月度趋势');
  const kpiTable = findTable(sec, '核心指标');

  const chartData = useMemo(() => {
    if (!monthTable?.rows?.length) return [];
    return monthTable.rows.map((row) => {
      const mom = parseMom(row[3]);
      return {
        month: String(row[0]),
        销售额: Number(row[1]) || 0,
        订单数: Number(row[2]) || 0,
        MoM: mom != null ? formatPercent(mom) : '—',
      };
    });
  }, [monthTable]);

  const momCards = useMemo(() => {
    if (!monthTable?.rows?.length) return [];
    const withMom = monthTable.rows
      .map((row, i) => ({ month: row[0], mom: parseMom(row[3]), index: i }))
      .filter((x) => x.mom != null);
    return withMom.slice(-3).map((x) => ({
      label: String(x.month),
      value: x.mom! * 100,
    }));
  }, [monthTable]);

  const dailyActual = useMemo(() => {
    if (!kpiTable?.rows) return 0;
    const row = kpiTable.rows.find((r) => String(r[0]).includes('日均销售额'));
    return row ? Number(row[1]) || 0 : 0;
  }, [kpiTable]);

  const progress = dailyTarget > 0 ? Math.min(100, (dailyActual / dailyTarget) * 100) : 0;

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <h2 className="mb-1 text-lg font-bold text-gray-900">销售与市场趋势</h2>
      <p className="mb-6 text-sm text-gray-500">月度销售额与订单数趋势、环比及日均目标</p>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(value: number | undefined) => [value != null ? formatNumber(value) : '—', '']}
                  labelFormatter={(label) => `月份: ${label}`}
                />
                <Legend />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="销售额"
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
                <Area
                  yAxisId="right"
                  type="monotone"
                  dataKey="订单数"
                  stroke="#8b5cf6"
                  fill="#8b5cf6"
                  fillOpacity={0.15}
                  strokeWidth={2}
                  strokeDasharray="4 2"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-medium text-gray-600">月度环比 MoM</p>
            <div className="space-y-2">
              {momCards.map((c) => (
                <div
                  key={c.label}
                  className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2"
                >
                  <span className="text-sm text-gray-600">{c.label}</span>
                  <AnimatedNumber
                    value={`${c.value >= 0 ? '+' : ''}${formatPercent(c.value / 100)}`}
                    className={`font-semibold ${c.value >= 0 ? 'text-green-600' : 'text-red-600'}`}
                  />
                </div>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-gray-600">日均营收目标</p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                step={100}
                value={dailyTarget || ''}
                onChange={(e) => onDailyTargetChange(Number(e.target.value) || 0)}
                placeholder="输入目标(元)"
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-500">元/日</span>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              实际日均：<AnimatedNumber value={formatNumber(dailyActual)} /> 元
            </p>
            {dailyTarget > 0 && (
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-200">
                <motion.div
                  className="h-full rounded-full bg-indigo-500"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.6 }}
                  style={{ maxWidth: '100%' }}
                />
              </div>
            )}
            {dailyTarget > 0 && (
              <p className="mt-1 text-xs text-gray-600">
                达成率：<AnimatedNumber value={formatPercent(progress / 100)} />
              </p>
            )}
          </div>
        </div>
      </div>
    </motion.section>
  );
}
