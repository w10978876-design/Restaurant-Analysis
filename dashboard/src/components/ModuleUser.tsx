import { useMemo, useState } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as BarTooltip,
  Legend as BarLegend,
} from 'recharts';
import { motion } from 'motion/react';
import { findSection, findTable, type Report } from '../data/report';
import { formatNumber } from '../utils/format';

const SEG_COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f97316', '#10b981'];

interface ModuleUserProps {
  report: Report | null;
}

export function ModuleUser({ report }: ModuleUserProps) {
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const secUser = findSection(report, '4_user');

  const summaryTable = findTable(secUser, '用户分层汇总');
  const timeTable = findTable(secUser, '各层级时段分布');
  const responseTable = findTable(secUser, '各层级响应概览');

  const pieData = useMemo(() => {
    if (!summaryTable?.rows?.length) return [];
    return summaryTable.rows.map((row, i) => ({
      name: String(row[0]),
      value: Number(row[1]) || 0,
      color: SEG_COLORS[i % SEG_COLORS.length],
    }));
  }, [summaryTable]);

  const timeChartData = useMemo(() => {
    if (!timeTable?.rows?.length || !timeTable.columns?.length) return [];
    const segs = timeTable.rows.map((r) => String(r[0]));
    const periodCols = timeTable.columns.slice(1).filter(Boolean);
    return periodCols.map((col, ci) => ({
      period: col,
      ...Object.fromEntries(segs.map((s, si) => [s, Number(timeTable.rows[si][ci + 1]) || 0])),
    }));
  }, [timeTable]);

  const responseChartData = useMemo(() => {
    if (!responseTable?.rows?.length || !responseTable.columns?.length) return [];

    const cols = responseTable.columns;
    const idxSegment = cols.indexOf('segment');
    const idxHighRefundCustomer = cols.indexOf('高退菜客户数');
    const idxHighRefundOrders = cols.indexOf('高退菜订单数');
    const idxDiscUsers = cols.indexOf('有折扣用户数');
    const idxDiscUserOrders = cols.indexOf('有折扣用户订单数');
    const idxDiscUserAmount = cols.indexOf('有折扣用户金额');
    const idxPlatformCustomers = cols.indexOf('平台优惠客户数');
    const idxPlatformCustomerOrders = cols.indexOf('平台优惠订单数');
    const idxPlatformCustomerAmount = cols.indexOf('平台优惠金额');

    return responseTable.rows.map((row) => ({
      层级: String(row[idxSegment] ?? row[0] ?? ''),
      高退菜客户: idxHighRefundCustomer >= 0 ? Number(row[idxHighRefundCustomer]) || 0 : 0,
      高退菜订单数: idxHighRefundOrders >= 0 ? Number(row[idxHighRefundOrders]) || 0 : 0,
      有折扣用户: idxDiscUsers >= 0 ? Number(row[idxDiscUsers]) || 0 : 0,
      有折扣用户订单数: idxDiscUserOrders >= 0 ? Number(row[idxDiscUserOrders]) || 0 : 0,
      有折扣用户金额: idxDiscUserAmount >= 0 ? Number(row[idxDiscUserAmount]) || 0 : 0,
      平台优惠客户: idxPlatformCustomers >= 0 ? Number(row[idxPlatformCustomers]) || 0 : 0,
      平台优惠订单数: idxPlatformCustomerOrders >= 0 ? Number(row[idxPlatformCustomerOrders]) || 0 : 0,
      平台优惠金额: idxPlatformCustomerAmount >= 0 ? Number(row[idxPlatformCustomerAmount]) || 0 : 0,
    }));
  }, [responseTable]);

  const responseTooltip = ({
    active,
    payload,
  }: {
    active?: boolean;
    payload?: Array<{ payload?: Record<string, number | string> }>;
  }) => {
    if (!active || !payload?.length) return null;
    const row = (payload[0]?.payload ?? {}) as Record<string, number | string>;
    return (
      <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-lg">
        <p className="mb-1 text-sm font-semibold text-gray-900">{String(row.层级 ?? '')}</p>
        {hoveredKey === '高退菜客户' ? (
          <p className="text-sm text-gray-700">
            高退菜客户：{formatNumber(row.高退菜客户 ?? 0)}
            <span className="ml-2 text-gray-500">订单数 {formatNumber(row.高退菜订单数 ?? 0)}</span>
          </p>
        ) : hoveredKey === '平台优惠客户' ? (
          <p className="text-sm text-gray-700">
            平台优惠客户：{formatNumber(row.平台优惠客户 ?? 0)}
            <span className="ml-2 text-gray-500">
              订单数 {formatNumber(row.平台优惠订单数 ?? 0)} 金额 {formatNumber(row.平台优惠金额 ?? 0)}
            </span>
          </p>
        ) : (
          <p className="text-sm text-gray-700">
            有折扣用户：{formatNumber(row.有折扣用户 ?? 0)}
            <span className="ml-2 text-gray-500">
              订单数 {formatNumber(row.有折扣用户订单数 ?? 0)} 金额 {formatNumber(row.有折扣用户金额 ?? 0)}
            </span>
          </p>
        )}
      </div>
    );
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <h2 className="mb-1 text-lg font-bold text-gray-900">用户画像与行为中心</h2>
      <p className="mb-6 text-sm text-gray-500">RFM 分层、时段偏好与优惠响应</p>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col">
          <p className="mb-2 text-sm font-medium text-gray-600">用户价值分布 (RFM)</p>
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={2}
                  dataKey="value"
                  nameKey="name"
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number | undefined) => [formatNumber(v ?? 0), '人数']} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-2">
          <p className="mb-2 text-sm font-medium text-gray-600">各层级时段分布</p>
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={timeChartData}
                layout="vertical"
                margin={{ top: 10, right: 20, left: 60, bottom: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="period" width={50} tick={{ fontSize: 11 }} />
                <BarTooltip formatter={(v: number | undefined) => [formatNumber(v ?? 0), '']} />
                <BarLegend />
                {timeTable?.rows?.map((row, i) => (
                  <Bar
                    key={String(row[0])}
                    dataKey={String(row[0])}
                    stackId="a"
                    fill={SEG_COLORS[i % SEG_COLORS.length]}
                    radius={[0, 2, 2, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="mt-6">
        <p className="mb-2 text-sm font-medium text-gray-600">各层级响应</p>
        <div className="h-[240px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={responseChartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="层级" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <BarTooltip content={responseTooltip as any} />
              <BarLegend />
              <Bar
                name="高退菜客户"
                dataKey="高退菜客户"
                fill="#ef4444"
                radius={[4, 4, 0, 0]}
                onMouseEnter={() => setHoveredKey('高退菜客户')}
                onMouseLeave={() => setHoveredKey(null)}
              />
              <Bar
                name="平台优惠客户"
                dataKey="平台优惠客户"
                fill="#3b82f6"
                radius={[4, 4, 0, 0]}
                onMouseEnter={() => setHoveredKey('平台优惠客户')}
                onMouseLeave={() => setHoveredKey(null)}
              />
              <Bar
                name="有折扣用户"
                dataKey="有折扣用户"
                fill="#8b5cf6"
                radius={[4, 4, 0, 0]}
                onMouseEnter={() => setHoveredKey('有折扣用户')}
                onMouseLeave={() => setHoveredKey(null)}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </motion.section>
  );
}
