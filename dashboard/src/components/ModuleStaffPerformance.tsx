import { motion } from 'motion/react';
import { Users } from 'lucide-react';
import { findSection, findTable, type Report } from '../data/report';
import { DataTable } from './DataTable';

interface ModuleStaffPerformanceProps {
  report: Report | null;
}

export function ModuleStaffPerformance({ report }: ModuleStaffPerformanceProps) {
  const staffSec = findSection(report, '5_staff');
  const staffTable = findTable(staffSec, '员工汇总');

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="rounded-2xl border border-gray-200/80 bg-white/90 p-6 shadow-lg shadow-gray-200/50"
    >
      <h2 className="mb-1 text-lg font-bold text-gray-900">员工表现</h2>
      <p className="mb-4 text-sm text-gray-500">
        从员工维度查看销售额、客单价与退菜率，识别表现突出的员工与需要关注的岗位。
      </p>
      <p className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-600">
        <Users className="h-4 w-4" />
        员工汇总（销售额 / 客单价 / 退菜率）
      </p>
      <div className="mt-1 max-h-[420px] overflow-y-auto pr-1">
        <DataTable table={staffTable} defaultVisibleRows={5} />
      </div>
    </motion.section>
  );
}

