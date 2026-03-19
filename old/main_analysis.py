import sys
import os
from datetime import datetime
import json
import io
import pandas as pd
import numpy as np
from google import genai

# 解决 Mac 终端显示中文问题
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ==========================================
# 1. 配置区域 (增强字段映射)
# ==========================================
GEMINI_API_KEY = "您的_GEMINI_API_KEY" 

FIELD_CONFIG = {
    "pay": {"file": "支付明细.xlsx", "mapping": {"id": ["业务单号", "订单号"], "amount": ["交易金额", "金额"], "payer": ["付款人", "客户"], "time": ["交易时间", "支付时间"], "method": ["支付方式", "结算方式"]}},
    "sales": {"file": "销售明细.xlsx", "mapping": {"id": ["订单编号", "订单号"], "dish": ["菜品名称", "项目名称"], "qty": ["销售数量", "数量"], "price": ["销售额", "金额"], "staff": ["收银员", "点菜员", "服务员"], "remark": ["备注"], "type": ["用餐方式", "订单类型"]}},
    "refunds": {"file": "退菜明细.xlsx", "mapping": {"id": ["订单编号", "订单号"], "dish": ["菜品名称"], "qty": ["销售数量", "数量"], "price": ["销售额", "金额"], "staff": ["操作员", "操作人", "收银员"], "remark": ["退菜原因", "备注"], "time": ["退菜时间", "时间"]}},
    "orders": {"file": "订单明细.xlsx", "mapping": {"id": ["订单号", "单号"], "people": ["用餐人数", "人数"], "status": ["订单状态", "状态"], "time": ["下单时间", "时间"], "refund_tag": ["退单标识"], "table": ["桌号", "台号"]}},
    "discounts": {"file": "优惠明细.xlsx", "mapping": {"id": ["订单编号", "订单号"], "discount_amount": ["折扣优惠金额", "优惠金额"], "discount_name": ["折扣优惠名称", "优惠名称"]} }
}

def clean_id(s):
    if pd.isna(s): return ""
    s = str(s).strip()
    if s in ["--", "null", "nan", "None", "0", ""]: return ""
    if s.endswith('.0'): s = s[:-2]
    return s

def find_actual_column(df_cols, target_keywords):
    for col in df_cols:
        clean_col = str(col).strip().replace('(', '（').replace(')', '）')
        for kw in target_keywords:
            if kw in clean_col: return col
    return None

def run_catering_analysis():
    print("🚀 正在启动餐饮业务 AI 自动化分析系统 V28.0 (运营全景版)...")
    
    # --- A. 数据加载与对齐 ---
    dfs = {}
    for key, config in FIELD_CONFIG.items():
        path = config["file"]
        if not os.path.exists(path):
            print(f"❌ 找不到文件: {path}"); return
        raw_df = pd.read_excel(path, nrows=5)
        rename_dict = {find_actual_column(raw_df.columns, kw): internal for internal, kw in config["mapping"].items() if find_actual_column(raw_df.columns, kw)}
        df = pd.read_excel(path, dtype={k: str for k, v in rename_dict.items() if v == 'id'})
        df = df.rename(columns=rename_dict)
        for internal in config["mapping"].keys():
            if internal not in df.columns:
                df[internal] = np.nan if internal in ['amount', 'price', 'qty', 'discount_amount', 'people'] else ""
        if 'id' in df.columns: df['id'] = df['id'].apply(clean_id)
        dfs[key] = df

    # --- B. 宽表构建 (核心轴) ---
    df_orders, df_pay, df_sales, df_refunds, df_discounts = dfs['orders'], dfs['pay'], dfs['sales'], dfs['refunds'], dfs['discounts']
    for df in [df_orders, df_pay, df_refunds]: df['time'] = pd.to_datetime(df['time'], errors='coerce')
    
    df_sales['dish_status'] = 'SALE'
    df_refunds['dish_status'] = 'REFUND'
    df_all_dishes = pd.concat([df_sales, df_refunds], ignore_index=True)
    
    # 聚合优惠信息，保留备注线索
    df_discounts_agg = df_discounts.groupby('id').agg({
        'discount_amount': 'sum',
        'discount_name': lambda x: '; '.join(x.unique().astype(str))
    }).reset_index()
    
    df_wide = pd.merge(df_orders[df_orders['id'] != ""], df_all_dishes, on='id', how='left')
    df_wide = pd.merge(df_wide, df_pay, on='id', how='left', suffixes=('', '_pay'))
    df_wide = pd.merge(df_wide, df_discounts_agg, on='id', how='left')
    
    wide_file = f"餐饮业务全量宽表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df_wide.to_excel(wide_file, index=False)

    # --- C. 餐饮运营深度分析引擎 ---
    print("📊 正在执行运营全景深度分析...")
    
    # 1. 销售趋势与环比 (月/周/日)
    df_pay_clean = df_pay.dropna(subset=['time', 'amount'])
    df_pay_clean['month'] = df_pay_clean['time'].dt.to_period('M')
    df_pay_clean['week'] = df_pay_clean['time'].dt.to_period('W')
    
    monthly_sales = df_pay_clean.groupby('month').agg({'amount': 'sum', 'id': 'nunique'}).reset_index()
    monthly_sales['MoM'] = monthly_sales['amount'].pct_change()
    
    # 2. 用户群体分层 (RFM 洞察)
    df_persona = df_pay[df_pay['payer'] != ""].copy()
    user_rfm = df_persona.groupby('payer').agg({'time': ['max', 'count'], 'amount': 'sum'}).reset_index()
    user_rfm.columns = ['payer', 'last_visit', 'frequency', 'monetary']
    
    def segment_user(row):
        if row['frequency'] >= 3: return '忠诚客户'
        if row['frequency'] == 2: return '活跃客户'
        return '新客户'
    user_rfm['segment'] = user_rfm.apply(segment_user, axis=1)
    
    # 核心结论：不同群体的消费特征
    segment_analysis = user_rfm.groupby('segment').agg({
        'payer': 'count',
        'monetary': 'mean',
        'frequency': 'mean'
    }).rename(columns={'payer': '总人数', 'monetary': '平均贡献', 'frequency': '平均频次'})

    # 3. 优惠因果分析 (为什么打折？)
    # 关联宽表中的备注，寻找优惠原因
    df_discount_context = df_wide[df_wide['discount_amount'] > 0].copy()
    discount_reason = df_discount_context.groupby(['discount_name', 'remark']).agg({
        'discount_amount': 'sum',
        'id': 'nunique'
    }).sort_values('discount_amount', ascending=False).head(15).reset_index()

    # 4. 菜品运营全景 (销量/退菜/备注/受众)
    dish_stats = df_sales.groupby('dish').agg({
        'qty': 'sum',
        'price': 'sum',
        'remark': lambda x: '; '.join(x.dropna().unique()[:3])
    }).reset_index()
    
    # 关联菜品与用户分层
    df_dish_user = pd.merge(df_sales[['id', 'dish']], pd.merge(df_pay[['id', 'payer']], user_rfm[['payer', 'segment']], on='payer'), on='id')
    dish_target = df_dish_user.groupby('dish')['segment'].agg(lambda x: x.mode().iloc[0] if not x.empty else "未知").reset_index()
    dish_final = pd.merge(dish_stats, dish_target, on='dish')
    
    # 关联退菜率
    dish_refund_qty = df_refunds.groupby('dish')['qty'].sum()
    dish_final['退菜率'] = dish_final['dish'].map(dish_refund_qty / df_sales.groupby('dish')['qty'].sum()).fillna(0)

    # 5. 异常与撤单审计
    exclude_staff = ['00000', '00015', '系统', '收银', '顾客', '']
    df_staff_act = df_sales[~df_sales['staff'].isin(exclude_staff)]
    staff_report = df_staff_act.groupby('staff').agg({
        'price': 'sum',
        'id': 'nunique',
        'remark': lambda x: '; '.join(x.dropna().unique()[:2])
    }).reset_index()

    # --- D. 综合报告导出 (单页综合) ---
    report_file = f"餐饮经营综合分析报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with pd.ExcelWriter(report_file, engine='openpyxl') as writer:
        row = 0
        def write_sect(title, df, r):
            pd.DataFrame([[f"【{title}】"]]).to_excel(writer, sheet_name='运营全景分析', startrow=r, index=False, header=False)
            df.to_excel(writer, sheet_name='运营全景分析', startrow=r+1, index=False)
            return r + len(df) + 3

        # 1. 销售趋势
        row = write_sect("一、销售趋势与月度环比 (MoM)", monthly_sales, row)
        # 2. 用户分层画像 (核心结论)
        row = write_sect("二、用户分层群体画像 (谁在支撑你的营收？)", segment_analysis, row)
        # 3. 优惠因果分析 (为什么打折？)
        row = write_sect("三、优惠因果分析 (优惠名称 + 订单备注关联)", discount_reason, row)
        # 4. 菜品运营全景 (销量/退菜/主攻人群)
        row = write_sect("四、菜品运营全景 (Top 20 菜品深度分析)", dish_final.sort_values('price', ascending=False).head(20), row)
        # 5. 员工表现与备注行为
        row = write_sect("五、员工服务表现 (已剔除系统号)", staff_report.sort_values('price', ascending=False), row)

    print("\n" + "="*60)
    print("✅ 首席分析师任务圆满完成！")
    print("-" * 60)
    print(f"1. 原始底座：{wide_file}")
    print(f"2. 综合报告：{report_file}")
    print(f"💡 报告已实现：用户群体化分层、优惠因果关联、菜品主攻人群识别。")
    print("="*60)

if __name__ == "__main__":
    run_catering_analysis()
    input("\n分析完成，按回车键退出...")