# 夕佳悦餐厅经营分析系统 - 开发交付说明书 (Cursor/AI Developer Edition)

## 1. 项目概述
本项目是一个基于 React 的餐饮大数据分析仪表板，旨在通过模块化（Bento Grid）布局，将零散的餐饮业务数据转化为可交互的经营洞察。

## 2. 技术栈要求
- **框架**: React 18+ (Vite)
- **样式**: Tailwind CSS v4 (使用 `@import "tailwindcss";` 配置)
- **图标**: `lucide-react`
- **图表**: `recharts`
- **动画**: `motion/react` (Framer Motion)
- **类型**: TypeScript

## 3. 核心功能模块

### 3.1 交互式页头 (Header)
- **餐厅选择**: 下拉菜单 (select)，支持多门店切换模拟。
- **报告周期选择**: 下拉菜单 (select)，对应不同的数据快照/时间段。
- **状态标识**: 带有呼吸灯效果的“实时分析模式”标签。

### 3.2 销售与市场趋势 (Module 0)
- **主图表**: AreaChart 展示月度销售额与订单数趋势。
- **MoM 卡片**: 展示月度环比增长/下降百分比。
- **日均目标管理**: 
  - 输入框 (Input) 允许用户设定日均营收目标。
  - 动态进度条 (Progress Bar) 根据实际日均值计算达成率。

### 3.3 用户画像与行为中心 (Module 1)
- **RFM 分层**: PieChart 展示用户价值分布。
- **时段偏好**: 堆叠柱状图 (Stacked BarChart) 展示不同客群在早/午/下午茶的时段分布。
- **优惠响应**: 柱状图展示各客群对折扣的敏感度。

### 3.4 菜品表现与风险中心 (Module 2)
- **关联分析**: 展示菜品共现订单数（如：A菜+B菜经常一起点）。
- **风险预警**: 针对退菜率高的菜品进行卡片式预警，需体现：退菜率、涉及金额、涉及订单数、风险等级（高/中）。

### 3.5 经营效能与流失分析 (Module 3)
- **员工表现**: 矩阵表展示销售额、客单价、退菜率。
- **流失分析**: 
  - 统计流失率与总流失单数。
  - 备注高频词云标识核心痛点（如“错点”、“上菜慢”）。

### 3.6 全量备注洞察 (Module 4)
- **明细表**: 包含日期、**星期**、**时段**、菜品、备注内容、类型。
- **交互**: 支持表格的“展开/收起”。

## 4. 数据结构规范 (Data Schema)
数据存储在 `src/data/report.ts` 中，采用以下结构：
```typescript
{
  meta: { generatedAt, dataRange, reportFile },
  overview: { summary: string[], cards: KPI[] },
  sections: [
    {
      id: string,
      title: string,
      conclusions: string[],
      tables: [
        { name: string, columns: string[], rows: string[][] }
      ]
    }
  ]
}
```

## 5. UI/UX 设计规范
- **布局**: Bento Grid (便当盒布局)，卡片间距 `gap-8`。
- **视觉风格**: 
  - 玻璃拟态 (Glass-morphism) 的固定页头。
  - 语义化颜色：蓝色(稳健/增长)、紫色(品牌)、粉色(警告/风险)、橙色(行动建议)。
- **交互**: 
  - 所有表格默认展示 5 行，支持“展开全部”。
  - 所有的数值变化应有微小的过渡动画。

## 6. 开发注意事项
1. **响应式**: 必须适配移动端，小屏幕下 Bento Grid 应自动降级为单列布局。
2. **性能**: 图表组件需包裹在 `ResponsiveContainer` 中。
3. **扩展性**: 所有的 `DataTable` 组件应能自动处理不同列数的表格数据。
