import { motion } from 'motion/react';
import { FileText } from 'lucide-react';
import { findSection, findTable, type Report } from '../data/report';
import { DataTable } from './DataTable';

interface ModuleRemarksProps {
  report: Report | null;
}

export function ModuleRemarks({ report }: ModuleRemarksProps) {
  const sec = findSection(report, '6_dish');
  const remarkTable = findTable(sec, '关键备注词分析');

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <h2 className="mb-1 text-lg font-bold text-gray-900">全量备注洞察</h2>
      <p className="mb-6 text-sm text-gray-500">备注词、频次、关联菜品、高发时段与星期（支持展开/收起）</p>

      <div className="flex items-center gap-2 text-sm font-medium text-gray-600">
        <FileText className="h-4 w-4" />
        明细表
      </div>
      <div className="mt-2">
        <DataTable table={remarkTable} defaultVisibleRows={5} />
      </div>
    </motion.section>
  );
}
