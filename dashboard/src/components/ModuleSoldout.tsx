import { useState, useMemo } from 'react';
import { motion } from 'motion/react';
import { Snowflake, CalendarClock, Maximize2, X } from 'lucide-react';
import { findSection, findTable, type Report, type ReportTable } from '../data/report';
import { DataTable } from './DataTable';

interface ModuleSoldoutProps {
  report: Report | null;
}

function buildSummaryTable(table: ReportTable | null): ReportTable | null {
  if (!table) return null;
  // 原列：dish, 被沽清次数, 涉及日期数, 主要沽清类型, 涉及日期详情, 合计停售时长, 平均单次停售时长, 原因
  const columns = ['菜品', '沽清次数', '发生天数', '主要类型', '备注原因'];
  const idxDish = table.columns.findIndex((c) => c.includes('dish') || c.includes('菜品'));
  const idxCount = table.columns.findIndex((c) => c.includes('被沽清次数'));
  const idxDays = table.columns.findIndex((c) => c.includes('涉及日期数'));
  const idxType = table.columns.findIndex((c) => c.includes('主要沽清类型'));
  const idxReason = table.columns.findIndex((c) => c.includes('原因'));
  const rows = table.rows.map((row) => [
    idxDish >= 0 ? row[idxDish] : '',
    idxCount >= 0 ? row[idxCount] : '',
    idxDays >= 0 ? row[idxDays] : '',
    idxType >= 0
      ? String(row[idxType] ?? '')
          .replace(/按总数设置/g, '按总数')
          .replace(/按周期设置/g, '按周期')
      : '',
    idxReason >= 0 ? row[idxReason] : '',
  ]);
  return { name: table.name, columns, rows };
}

function buildDateDetailTable(table: ReportTable | null): ReportTable | null {
  if (!table) return null;
  const idxDish = table.columns.findIndex((c) => c.includes('dish') || c.includes('菜品'));
  const idxDetail = table.columns.findIndex((c) => c.includes('涉及日期详情'));
  const idxTotal = table.columns.findIndex((c) => c.includes('合计停售时长'));
  const idxAvg = table.columns.findIndex((c) => c.includes('平均单次停售时长'));
  if (idxDish < 0 || idxDetail < 0) return null;
  const columns = ['菜品', '涉及日期详情', '合计停售时长', '平均单次停售时长'];
  const rows = table.rows.map((row) => [
    row[idxDish],
    row[idxDetail],
    idxTotal >= 0 ? row[idxTotal] : '',
    idxAvg >= 0 ? row[idxAvg] : '',
  ]);
  return { name: '涉及日期详情', columns, rows };
}

export function ModuleSoldout({ report }: ModuleSoldoutProps) {
  const [openDateDetail, setOpenDateDetail] = useState(false);
  const [openByDay, setOpenByDay] = useState(false);

  const sec = findSection(report, '11_soldout');
  if (!sec) return null;

  const kpiTable = findTable(sec, '沽清售罄概览');
  const summaryTableRaw = findTable(sec, '被沽清菜品汇总');
  const byDayTable = findTable(sec, '按日期/星期的停售分布');
  const byTimeTableRaw = findTable(sec, '按营业时段的停售分布');

  const byTimeTable = useMemo(() => {
    if (!byTimeTableRaw) return null;
    // 原列：时段, 被停售菜品数, 停售事件数, 总停售时长, 被停售菜品详情, 操作人, 沽清类型
    const idxTime = byTimeTableRaw.columns.findIndex((c) => c.includes('时段'));
    const idxCount = byTimeTableRaw.columns.findIndex((c) => c.includes('被停售菜品数'));
    const idxEvents = byTimeTableRaw.columns.findIndex((c) => c.includes('停售事件数'));
    const idxStaff = byTimeTableRaw.columns.findIndex((c) => c.includes('操作人'));
    const idxType = byTimeTableRaw.columns.findIndex((c) => c.includes('沽清类型'));
    const columns = ['时段', '被停售菜品数', '停售事件数', '操作人', '沽清类型'];
    const rows = byTimeTableRaw.rows.map((row) => {
      const rawType = idxType >= 0 ? String(row[idxType] ?? '') : '';
      const normalizedType = rawType
        .replace(/按总数设置/g, '按总数')
        .replace(/按周期设置/g, '按周期');
      return [
        idxTime >= 0 ? row[idxTime] : '',
        idxCount >= 0 ? row[idxCount] : '',
        idxEvents >= 0 ? row[idxEvents] : '',
        idxStaff >= 0 ? row[idxStaff] : '',
        normalizedType,
      ];
    });
    return { name: byTimeTableRaw.name, columns, rows };
  }, [byTimeTableRaw]);

  const summaryTable = useMemo(
    () => buildSummaryTable(summaryTableRaw),
    [summaryTableRaw]
  );
  const dateDetailTable = useMemo(
    () => buildDateDetailTable(summaryTableRaw),
    [summaryTableRaw]
  );

  const kpiRows = kpiTable?.rows ?? [];

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="mb-1 text-lg font-bold text-gray-900">菜品沽清与售罄</h2>
          <p className="text-sm text-gray-500">
            关注被沽清菜品数量、停售时长与高发时段，帮助优化备货与上架节奏。
          </p>
        </div>
        <Snowflake className="h-5 w-5 text-sky-400" />
      </div>

      {kpiRows.length > 0 && (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {kpiRows.slice(0, 4).map((row, idx) => (
            <div
              key={idx}
              className="rounded-xl border border-sky-100 bg-sky-50/70 px-3 py-2.5"
            >
              <p className="text-xs text-gray-500">{row[0]}</p>
              <p className="mt-1 text-base font-semibold text-sky-700">
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
            <p className="text-sm font-medium text-gray-600">被沽清菜品汇总（整月）</p>
            {dateDetailTable && (
              <button
                type="button"
                onClick={() => setOpenDateDetail(true)}
                className="text-xs font-medium text-sky-700 hover:text-sky-900"
              >
                查看涉及日期详情
              </button>
            )}
          </div>
          <div className="mt-1 flex-1 min-h-[220px] max-h-[320px] overflow-y-auto pr-1">
            <DataTable table={summaryTable} defaultVisibleRows={5} />
          </div>
        </div>

        <div className="flex flex-col h-full">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-gray-600">按营业时段的停售分布</p>
            {byDayTable && (
              <button
                type="button"
                onClick={() => setOpenByDay(true)}
                className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:text-sky-900"
              >
                <CalendarClock className="h-3.5 w-3.5" />
                查看按日期/星期分布
              </button>
            )}
          </div>
          <div className="mt-1 flex-1 min-h-[220px] max-h-[320px] overflow-y-auto pr-1">
            <DataTable table={byTimeTable} defaultVisibleRows={5} />
          </div>
        </div>
      </div>

      {openDateDetail && dateDetailTable && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-gray-500" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">涉及日期详情</p>
                  <p className="text-xs text-gray-500">各被沽清菜品对应的具体停售日期</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpenDateDetail(false)}
                className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-5">
              <DataTable table={dateDetailTable} defaultVisibleRows={10} />
            </div>
          </div>
        </div>
      )}

      {openByDay && byDayTable && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-gray-500" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">按日期/星期的停售分布</p>
                  <p className="text-xs text-gray-500">从日期与星期视角查看停售菜品与时长</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpenByDay(false)}
                className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-5">
              <DataTable table={byDayTable} defaultVisibleRows={10} />
            </div>
          </div>
        </div>
      )}
    </motion.section>
  );
}

