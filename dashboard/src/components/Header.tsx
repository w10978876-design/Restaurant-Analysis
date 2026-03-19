import { motion } from 'motion/react';
import { Store, Calendar, Activity } from 'lucide-react';
import type { ReportIndex } from '../data/index';

interface HeaderProps {
  reportIndex: ReportIndex | null;
  selectedRestaurantId: string | null;
  selectedRangeKey: string | null;
  onSelectionChange?: (value: { restaurantId: string | null; rangeKey: string | null }) => void;
}

export function Header({ reportIndex, selectedRestaurantId, selectedRangeKey, onSelectionChange }: HeaderProps) {
  const restaurants = reportIndex?.restaurants ?? [];
  const currentRestaurant =
    restaurants.find((r) => r.id === selectedRestaurantId) ?? restaurants[0] ?? null;
  const periods = currentRestaurant?.periods ?? [];

  const handleRestaurantChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const restaurantId = event.target.value || null;
    const nextRestaurant =
      restaurants.find((r) => r.id === restaurantId) ?? restaurants[0] ?? null;
    const nextPeriods = nextRestaurant?.periods ?? [];
    const nextRangeKey =
      nextPeriods.find((p) => p.rangeKey === selectedRangeKey)?.rangeKey ??
      nextPeriods[0]?.rangeKey ??
      null;

    onSelectionChange?.({ restaurantId, rangeKey: nextRangeKey });
  };

  const handlePeriodChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const rangeKey = event.target.value || null;
    onSelectionChange?.({ restaurantId: selectedRestaurantId, rangeKey });
  };

  return (
    <header className="sticky top-0 z-50 border-b border-white/40 bg-[var(--color-glass-bg)] backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-600">
            <Store className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900">夕佳悦餐厅经营分析</h1>
            <p className="text-xs text-gray-500">基于宽表与多模块的单页洞察</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-500" />
            <select
              className="rounded-lg border border-gray-200 bg-white/80 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              aria-label="报告周期"
              value={selectedRangeKey ?? (periods[0]?.rangeKey ?? '')}
              onChange={handlePeriodChange}
              disabled={!periods.length}
            >
              {periods.length === 0 ? (
                <option value="">无可用周期</option>
              ) : (
                periods.map((p) => (
                  <option key={p.rangeKey} value={p.rangeKey}>
                    {p.dataRange || p.rangeKey}
                  </option>
                ))
              )}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <Store className="h-4 w-4 text-gray-500" />
            <select
              className="rounded-lg border border-gray-200 bg-white/80 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              aria-label="餐厅选择"
              value={selectedRestaurantId ?? (restaurants[0]?.id ?? '')}
              onChange={handleRestaurantChange}
              disabled={!restaurants.length}
            >
              {restaurants.length === 0 ? (
                <option value="">无餐厅</option>
              ) : (
                restaurants.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))
              )}
            </select>
          </div>
          <motion.span
            className="animate-breathe flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700"
            aria-label="实时分析模式"
          >
            <Activity className="h-3.5 w-3.5" />
            实时分析模式
          </motion.span>
        </div>
      </div>
    </header>
  );
}
