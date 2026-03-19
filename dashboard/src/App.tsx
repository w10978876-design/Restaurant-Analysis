import { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { Header } from './components/Header';
import { ModuleSales } from './components/ModuleSales';
import { ModuleUser } from './components/ModuleUser';
import { ModuleDish } from './components/ModuleDish';
import { ModuleStaffLost } from './components/ModuleStaffLost';
import { ModuleRemarks } from './components/ModuleRemarks';
import { ModuleSoldout } from './components/ModuleSoldout';
import { ModuleVisitor } from './components/ModuleVisitor';
import { ModuleGroupon } from './components/ModuleGroupon';
import { ModuleDiscount } from './components/ModuleDiscount';
import { loadReport, findSection, findTable, type Report } from './data/report';
import { AnimatedNumber } from './components/AnimatedNumber';
import { formatNumber } from './utils/format';
import { loadIndex, type ReportIndex, type IndexPeriod } from './data/index';
import { ModuleTimeCross } from './components/ModuleTimeCross';
import { PageSection } from './components/PageSection';
import { ModuleStaffPerformance } from './components/ModuleStaffPerformance';

function OverviewBlock({ report }: { report: Report | null }) {
  const sec = findSection(report, '1_sales');
  const kpiTable = findTable(sec, '核心指标');
  const summary = report?.overview?.summary ?? [];
  const restaurantName = report?.meta?.restaurant ?? '当前餐厅';
  const dataRange = report?.meta?.dataRange ?? '';

  const kpiRows = kpiTable?.rows ?? [];
  const totalSales = kpiRows.find((r) => String(r[0]).includes('总销售额'))?.[1];
  const totalOrders = kpiRows.find((r) => String(r[0]).includes('总客流量') || String(r[0]).includes('已结账'))?.[1];
  const aov = kpiRows.find((r) => String(r[0]).includes('平均客单价'))?.[1];
  const people = kpiRows.find((r) => String(r[0]).includes('总用餐人数'))?.[1];
  const dailySales = kpiRows.find((r) => String(r[0]).includes('日均销售额'))?.[1];

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-indigo-200/80 bg-gradient-to-br from-indigo-50/90 to-white p-6 shadow-lg shadow-indigo-100/50"
    >
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-bold text-gray-900">{restaurantName}</h2>
        {dataRange && (
          <p className="text-sm text-gray-500">{dataRange.replace(/^数据时间范围：?/, '')}</p>
        )}
      </div>
      <p className="mb-4 text-sm text-gray-600">
        选择上方餐厅与报告周期可切换数据；下方为当前周期核心指标与各维度分析。
      </p>
      {summary.length > 0 && (
        <ul className="mb-6 list-inside list-disc space-y-1 text-sm text-gray-700">
          {summary.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {[
          { label: '总销售额', value: totalSales, unit: '元' },
          { label: '已结账订单', value: totalOrders, unit: '单' },
          { label: '平均客单价', value: aov, unit: '元' },
          { label: '总用餐人数', value: people, unit: '人' },
          { label: '日均销售额', value: dailySales, unit: '元' },
        ]
          .filter((x) => x.value != null && x.value !== '')
          .map((item) => {
            const display = formatNumber(item.value);
            return (
              <div
                key={item.label}
                className="rounded-xl border border-gray-200 bg-white/80 px-3 py-2.5 shadow-sm"
              >
                <p className="text-xs text-gray-500">{item.label}</p>
                <p className="text-lg font-bold text-indigo-600">
                  <AnimatedNumber value={display} />
                  {item.unit && <span className="ml-0.5 text-sm font-normal text-gray-500">{item.unit}</span>}
                </p>
              </div>
            );
          })}
      </div>
    </motion.section>
  );
}

function parseEndDateFromRangeKey(rangeKey: string): Date | null {
  const parts = rangeKey.split('_');
  if (parts.length !== 2) return null;
  const end = new Date(parts[1]);
  return Number.isNaN(end.getTime()) ? null : end;
}

function findDefaultPeriod(index: ReportIndex): { restaurantId: string; period: IndexPeriod } | null {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  let bestPast: { restaurantId: string; period: IndexPeriod; end: Date } | null = null;
  let bestFuture: { restaurantId: string; period: IndexPeriod; end: Date } | null = null;

  for (const restaurant of index.restaurants ?? []) {
    for (const period of restaurant.periods ?? []) {
      const endDate = parseEndDateFromRangeKey(period.rangeKey);
      if (!endDate) continue;

      if (endDate.getTime() <= today.getTime()) {
        // 过去或今天：选「结束日期最大」的那个
        if (!bestPast || endDate.getTime() > bestPast.end.getTime()) {
          bestPast = { restaurantId: restaurant.id, period, end: endDate };
        }
      } else {
        // 未来：选「结束日期最早」的那个
        if (!bestFuture || endDate.getTime() < bestFuture.end.getTime()) {
          bestFuture = { restaurantId: restaurant.id, period, end: endDate };
        }
      }
    }
  }

  if (bestPast) {
    return { restaurantId: bestPast.restaurantId, period: bestPast.period };
  }
  if (bestFuture) {
    return { restaurantId: bestFuture.restaurantId, period: bestFuture.period };
  }
  return null;
}

function App() {
  const [reportIndex, setReportIndex] = useState<ReportIndex | null>(null);
  const [selectedRestaurantId, setSelectedRestaurantId] = useState<string | null>(null);
  const [selectedRangeKey, setSelectedRangeKey] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dailyTarget, setDailyTarget] = useState(2500);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      setLoading(true);
      setError(null);
      try {
        const index = await loadIndex();
        if (cancelled) return;
        setReportIndex(index);

        const selection = findDefaultPeriod(index);
        if (!selection) {
          throw new Error('索引中没有可用的报告周期，请先运行分析脚本生成数据。');
        }

        setSelectedRestaurantId(selection.restaurantId);
        setSelectedRangeKey(selection.period.rangeKey);

        const reportData = await loadReport(selection.period.reportPath);
        if (cancelled) return;
        setReport(reportData);
      } catch (e: unknown) {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : '加载失败';
        setError(message);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void init();

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <motion.div
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="text-lg text-gray-500"
        >
          加载报告中…
        </motion.div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center">
          <p className="font-medium text-red-800">{error}</p>
          <p className="mt-2 text-sm text-red-600">请先运行分析脚本生成 report.json，并放入本项目的 public 目录。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-12">
      <Header
        reportIndex={reportIndex}
        selectedRestaurantId={selectedRestaurantId}
        selectedRangeKey={selectedRangeKey}
        onSelectionChange={({ restaurantId, rangeKey }) => {
          setSelectedRestaurantId(restaurantId);
          setSelectedRangeKey(rangeKey);
          const nextRestaurant =
            reportIndex?.restaurants.find((r) => r.id === restaurantId) ??
            reportIndex?.restaurants[0];
          const nextPeriod =
            nextRestaurant?.periods.find((p) => p.rangeKey === rangeKey) ??
            nextRestaurant?.periods[0];
          if (nextPeriod) {
            setLoading(true);
            setError(null);
            loadReport(nextPeriod.reportPath)
              .then((data) => {
                setReport(data);
              })
              .catch((e: unknown) => {
                const message = e instanceof Error ? e.message : '加载失败';
                setError(message);
              })
              .finally(() => {
                setLoading(false);
              });
          }
        }}
      />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="space-y-10">
          <PageSection label="经营概览">
            <OverviewBlock report={report} />
          </PageSection>

          <PageSection label="销售与趋势">
            <ModuleSales
              report={report}
              dailyTarget={dailyTarget}
              onDailyTargetChange={setDailyTarget}
            />
          </PageSection>

          <PageSection label="时段结构">
            <ModuleTimeCross report={report} />
          </PageSection>

          <PageSection label="用户与价值">
            <ModuleUser report={report} />
            <ModuleVisitor report={report} />
          </PageSection>

          <PageSection label="菜品与风险">
            <ModuleDish report={report} />
            <ModuleSoldout report={report} />
            <ModuleRemarks report={report} />
          </PageSection>

          <PageSection label="优惠与团购">
            <ModuleGroupon report={report} />
            <ModuleDiscount report={report} />
          </PageSection>

          <PageSection label="经营效能">
            <ModuleStaffLost report={report} />
            <ModuleStaffPerformance report={report} />
          </PageSection>
        </div>
      </main>
    </div>
  );
}

export default App;
