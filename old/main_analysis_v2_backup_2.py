import sys
import os
from datetime import datetime
import json
import io
import itertools
import pandas as pd
import numpy as np

# 解决 Mac 终端显示中文问题（避免中文乱码）
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


# ==========================================
# 1. 配置区域：文件名与字段映射
# ==========================================

FIELD_CONFIG = {
    "pay": {
        "file": "支付明细.xlsx",
        "mapping": {
            "id": ["业务单号", "订单号"],
            "amount": ["交易金额", "金额"],
            "payer": ["付款人", "客户"],
            "time": ["交易时间", "支付时间"],
            "method": ["支付方式", "结算方式"],
        },
    },
    "sales": {
        "file": "销售明细.xlsx",
        "mapping": {
            "id": ["订单编号", "订单号"],
            "dish": ["菜品名称", "项目名称"],
            "qty": ["销售数量", "数量"],
            "price": ["销售额", "金额"],
            "staff": ["收银员", "点菜员", "服务员"],
            "remark": ["备注"],
            "type": ["用餐方式", "订单类型"],
        },
    },
    "refunds": {
        "file": "退菜明细.xlsx",
        "mapping": {
            "id": ["订单编号", "订单号"],
            "dish": ["菜品名称"],
            "qty": ["销售数量", "数量"],
            "price": ["销售额", "金额"],
            "staff": ["操作员", "操作人", "收银员"],
            "remark": ["退菜原因", "备注"],
            "time": ["退菜时间", "时间"],
        },
    },
    "orders": {
        "file": "订单明细.xlsx",
        "mapping": {
            "id": ["订单号", "单号"],
            "people": ["用餐人数", "人数"],
            "status": ["订单状态", "状态"],
            "time": ["下单时间", "时间"],
            "refund_tag": ["退单标识"],
            "table": ["桌号", "台号"],
            "order_remark": ["整单备注"],
        },
    },
    "discounts": {
        "file": "优惠明细.xlsx",
        "mapping": {
            "id": ["订单编号", "订单号"],
            "discount_amount": ["折扣优惠金额", "优惠金额"],
            "discount_name": ["折扣优惠名称", "优惠名称"],
            "discount_reason": ["折扣优惠原因", "折扣原因", "优惠原因"],
            "discount_type": ["折扣优惠类型", "优惠类型"],
        },
    },
}

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def clean_id(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    if s in ["--", "null", "nan", "None", "0", ""]:
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    return s


def find_actual_column(columns, keywords):
    for col in columns:
        clean_col = str(col).strip().replace("(", "（").replace(")", "）")
        for kw in keywords:
            if kw in clean_col:
                return col
    return None


def classify_daypart(dt):
    if pd.isna(dt):
        return ""
    h = dt.hour
    if 6 <= h < 11:
        return "早餐"
    if 11 <= h < 15:
        return "午餐"
    if 15 <= h < 18:
        return "下午茶"
    if 18 <= h < 22:
        return "晚餐"
    return "夜宵"


def df_to_json_table(df: pd.DataFrame):
    if df is None or df.empty:
        return {"columns": [], "rows": []}
    df = df.copy()
    for c in df.columns:
        if hasattr(df[c].dtype, "name") and "period" in str(df[c].dtype).lower():
            df[c] = df[c].astype(str)
        else:
            df[c] = df[c].fillna("").astype(str)
    return {"columns": list(df.columns), "rows": df.values.tolist()}


def load_all_data():
    dfs = {}
    for key, cfg in FIELD_CONFIG.items():
        path = cfg["file"]
        if not os.path.exists(path):
            raise FileNotFoundError(f"找不到文件：{path}")
        # 先用前几行推断列名
        raw = pd.read_excel(path, nrows=5)
        rename_dict = {}
        for internal, kws in cfg["mapping"].items():
            col = find_actual_column(raw.columns, kws)
            if col is not None:
                rename_dict[col] = internal
        # 读全量
        read_kwargs = {}
        if any(v == "id" for v in rename_dict.values()):
            id_cols = [k for k, v in rename_dict.items() if v == "id"]
            read_kwargs["dtype"] = {c: str for c in id_cols}
        df = pd.read_excel(path, **read_kwargs)
        df = df.rename(columns=rename_dict)
        # 补齐缺失字段
        for internal in cfg["mapping"].keys():
            if internal not in df.columns:
                df[internal] = (
                    np.nan if internal in ["amount", "price", "qty", "discount_amount", "people"] else ""
                )
        if "id" in df.columns:
            df["id"] = df["id"].apply(clean_id)
        dfs[key] = df
    return dfs


def run_catering_analysis():
    print("🚀 启动餐饮数据化分析 main_analysis_v2 ...")

    dfs = load_all_data()
    df_orders, df_pay, df_sales, df_refunds, df_discounts = (
        dfs["orders"],
        dfs["pay"],
        dfs["sales"],
        dfs["refunds"],
        dfs["discounts"],
    )

    # 统一时间列
    for df in [df_orders, df_pay, df_refunds]:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")

    # ===== 宽表 =====
    df_sales["dish_status"] = "SALE"
    df_refunds["dish_status"] = "REFUND"
    df_all_dishes = pd.concat([df_sales, df_refunds], ignore_index=True)

    df_discounts_agg = df_discounts.groupby("id").agg(
        {
            "discount_amount": "sum",
            "discount_name": lambda x: "; ".join(sorted(set(str(v) for v in x if pd.notna(v)))),
        }
    ).reset_index()

    df_wide = pd.merge(df_orders[df_orders["id"] != ""], df_all_dishes, on="id", how="left")
    df_wide = pd.merge(df_wide, df_pay, on="id", how="left", suffixes=("", "_pay"))
    df_wide = pd.merge(df_wide, df_discounts_agg, on="id", how="left")

    wide_file = f"餐饮业务全量宽表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df_wide.to_excel(wide_file, index=False)

    print(f"① 宽表导出：{wide_file}")

    # ===== 1. 销售趋势 =====
    df_pay_clean = df_pay.dropna(subset=["time", "amount"]).copy()
    df_pay_clean["month"] = df_pay_clean["time"].dt.to_period("M")
    df_pay_clean["week"] = df_pay_clean["time"].dt.to_period("W")

    monthly_sales = (
        df_pay_clean.groupby("month")
        .agg({"amount": "sum", "id": "nunique"})
        .reset_index()
        .rename(columns={"amount": "销售额", "id": "订单数"})
    )
    monthly_sales["MoM"] = monthly_sales["销售额"].pct_change()

    weekly_raw = (
        df_pay_clean.groupby("week")
        .agg({"amount": "sum", "id": "nunique"})
        .reset_index()
        .rename(columns={"amount": "销售额", "id": "订单数"})
    )
    weekly_raw["周起始日"] = weekly_raw["week"].dt.start_time
    data_start = df_pay_clean["time"].min().normalize()
    data_end = df_pay_clean["time"].max().normalize()
    full_weeks = weekly_raw[
        (weekly_raw["周起始日"] > data_start - pd.to_timedelta(data_start.weekday(), unit="D"))
        & (weekly_raw["周起始日"] + pd.Timedelta(days=7) <= data_end + pd.Timedelta(days=1))
    ].copy()
    full_weeks = full_weeks.sort_values("周起始日")
    full_weeks["WoW"] = full_weeks["销售额"].pct_change()
    weekly_sales = full_weeks[["周起始日", "销售额", "订单数", "WoW"]]

    # ===== 2. 用户分层（4 档：新客 / 一般活跃 / 沉睡唤醒 / 高价值忠诚）=====
    df_persona = df_pay[df_pay["payer"] != ""].copy()
    user_rfm = (
        df_persona.groupby("payer")
        .agg({"time": ["max", "count"], "amount": "sum"})
        .reset_index()
    )
    user_rfm.columns = ["payer", "last_visit", "frequency", "monetary"]
    analysis_end = df_persona["time"].max().normalize()
    user_rfm["R_days"] = (analysis_end - user_rfm["last_visit"].dt.normalize()).dt.days

    def segment_user(row):
        # frequency == 1 → 新客
        # frequency >= 2 且 R_days > 65 → 沉睡唤醒
        # frequency >= 2 且 R_days ≤ 65 且 monetary ≥ 100 → 高价值忠诚
        # 其余 frequency >= 2 → 一般活跃
        if row["frequency"] == 1:
            return "新客"
        if row["frequency"] >= 2 and row["R_days"] > 65:
            return "沉睡唤醒"
        if row["frequency"] >= 2 and row["R_days"] <= 65 and row["monetary"] >= 100:
            return "高价值忠诚"
        return "一般活跃"

    user_rfm["segment"] = user_rfm.apply(segment_user, axis=1)

    # 汇总：人数 / 平均消费 / 平均频次 / 平均R天 / 订单数
    segment_summary = (
        user_rfm.groupby("segment")
        .agg(
            {
                "payer": "count",
                "monetary": "mean",
                "frequency": "mean",
                "R_days": "mean",
            }
        )
        .rename(
            columns={
                "payer": "人数",
                "monetary": "平均消费",
                "frequency": "平均频次",
                "R_days": "平均R天",
            }
        )
    )
    seg_orders = (
        df_persona.groupby("payer")["id"]
        .count()
        .reset_index()
        .rename(columns={"id": "订单数"})
    )
    seg_orders = seg_orders.merge(user_rfm[["payer", "segment"]], on="payer", how="left")
    seg_orders_summary = seg_orders.groupby("segment")["订单数"].sum()
    segment_summary["订单数"] = (
        segment_summary.index.map(seg_orders_summary).fillna(0).astype(int)
    )

    # 各层级时段分布：基于支付时间 + 用户分层
    df_seg_time = pd.merge(
        df_pay_clean[["id", "time", "payer"]],
        user_rfm[["payer", "segment"]],
        on="payer",
        how="left",
    )
    df_seg_time["daypart"] = df_seg_time["time"].apply(classify_daypart)
    seg_time_pivot = (
        pd.crosstab(df_seg_time["segment"], df_seg_time["daypart"], normalize="index")
        .reset_index()
        .rename(columns={"segment": "segment"})
    )

    # 各层级支付方式：基于支付方式 + 用户分层
    df_seg_pay = pd.merge(
        df_pay[["id", "payer", "method"]],
        user_rfm[["payer", "segment"]],
        on="payer",
        how="left",
    )
    pay_pivot = (
        pd.crosstab(df_seg_pay["segment"], df_seg_pay["method"], normalize="index")
        .reset_index()
        .rename(columns={"segment": "segment"})
    )

    # 各层级优惠响应：优惠订单数 / 总订单数 + 优惠金额
    if not df_discounts.empty:
        df_seg_disc = pd.merge(
            df_discounts[["id", "discount_amount"]],
            df_pay[["id", "payer"]],
            on="id",
            how="left",
        )
        df_seg_disc = pd.merge(
            df_seg_disc,
            user_rfm[["payer", "segment"]],
            on="payer",
            how="left",
        )
        disc_summary = (
            df_seg_disc.groupby("segment")
            .agg({"id": "nunique", "discount_amount": "sum"})
            .reset_index()
            .rename(columns={"id": "优惠订单数", "discount_amount": "优惠金额"})
        )
        total_orders_by_seg = (
            seg_orders.groupby("segment")["订单数"].sum().reset_index()
        )
        disc_summary = disc_summary.merge(
            total_orders_by_seg, on="segment", how="left"
        )
        disc_summary["优惠订单占比"] = (
            disc_summary["优惠订单数"] / disc_summary["订单数"]
        )
        disc_summary = disc_summary.rename(
            columns={"segment": "segment", "订单数": "总订单数"}
        )
    else:
        disc_summary = pd.DataFrame(
            columns=["segment", "优惠订单数", "优惠金额", "总订单数", "优惠订单占比"]
        )

    # ===== 3. 优惠因果分析（优惠类型 + 折扣原因）=====
    # 使用优惠明细中的折扣原因
    reason_col = find_actual_column(df_discounts.columns, ["折扣优惠原因", "折扣原因", "优惠原因"])
    if reason_col is None:
        df_discounts["discount_reason"] = "--"
    else:
        df_discounts["discount_reason"] = (
            df_discounts[reason_col].astype(str).str.strip().replace({"": "--"})
        )
    discount_reason = (
        df_discounts.groupby(["discount_name", "discount_reason"])
        .agg({"discount_amount": "sum", "id": "nunique"})
        .reset_index()
        .rename(columns={"discount_amount": "优惠金额", "id": "订单数"})
    )

    # ===== 4. 菜品分析（简化版：销量/销售额/退菜率/主攻客群）=====
    dish_stats = (
        df_sales.groupby("dish")
        .agg({"qty": "sum", "price": "sum", "id": "nunique"})
        .reset_index()
        .rename(columns={"qty": "销量", "price": "销售额", "id": "订单数"})
    )
    # 退菜
    if not df_refunds.empty:
        refund_stats = (
            df_refunds.groupby("dish")
            .agg({"qty": "sum", "price": "sum"})
            .reset_index()
            .rename(columns={"qty": "退菜量", "price": "退菜额"})
        )
    else:
        refund_stats = pd.DataFrame(columns=["dish", "退菜量", "退菜额"])
    # 主攻客户层级（按订单对应用户的分层众数）
    df_dish_user = pd.merge(
        df_sales[["id", "dish"]],
        pd.merge(df_pay[["id", "payer"]], user_rfm[["payer", "segment"]], on="payer", how="left"),
        on="id",
        how="left",
    )
    dish_seg_pivot = (
        pd.crosstab(df_dish_user["dish"], df_dish_user["segment"], normalize="index")
        .reset_index()
        .rename(columns={"dish": "dish"})
    )
    dish_target = (
        df_dish_user.groupby("dish")["segment"]
        .agg(lambda x: x.mode().iloc[0] if not x.dropna().empty else "")
        .reset_index()
        .rename(columns={"segment": "主攻客户层级"})
    )
    dish_final = pd.merge(dish_stats, dish_target, on="dish", how="left")
    dish_final = pd.merge(dish_final, dish_seg_pivot, on="dish", how="left")
    dish_final = pd.merge(dish_final, refund_stats, on="dish", how="left")
    dish_final["退菜量"] = dish_final["退菜量"].fillna(0)
    dish_final["退菜额"] = dish_final["退菜额"].fillna(0)
    dish_final["退菜率"] = dish_final.apply(
        lambda r: (r["退菜额"] / r["销售额"]) if r["销售额"] else 0, axis=1
    )

    # ===== 5. 员工表现 =====
    exclude_pattern = r"00000|00015|顾客/系统|收银"
    df_staff_sales = df_sales[
        ~df_sales["staff"].astype(str).str.contains(exclude_pattern, na=False)
    ].copy()
    staff_base = (
        df_staff_sales.groupby("staff")
        .agg({"price": "sum", "id": "nunique"})
        .reset_index()
        .rename(columns={"price": "销售额", "id": "订单数"})
    )
    staff_base["客单价"] = staff_base["销售额"] / staff_base["订单数"]
    staff_report = staff_base.sort_values("销售额", ascending=False)

    # ===== 6. 流失订单分析（按状态/月/周/整单备注高频词）=====
    # 流失订单：订单明细中的“退款完成” + “已撤单”，仅统计有有效订单号
    df_orders_valid = df_orders[df_orders["id"] != ""].copy()
    mask_refund = df_orders_valid["status"].astype(str).str.contains("退款完成", na=False)
    mask_cancel = df_orders_valid["status"].astype(str).str.contains("已撤单", na=False)
    refund_orders = df_orders_valid[mask_refund].copy()
    refund_orders["流失类型"] = "退款完成"
    cancel_orders = df_orders_valid[mask_cancel].copy()
    cancel_orders["流失类型"] = "已撤单"
    df_lost = pd.concat([refund_orders, cancel_orders], ignore_index=True).drop_duplicates(
        subset=["id", "流失类型"]
    )

    lost_by_status = (
        df_lost.groupby("流失类型")["id"].nunique().reset_index().rename(columns={"id": "订单数"})
    )
    if not df_lost.empty:
        df_lost["month"] = pd.to_datetime(df_lost["time"], errors="coerce").dt.to_period("M")
        lost_by_month = (
            df_lost.groupby("month")["id"].nunique().reset_index().rename(columns={"month": "月份", "id": "订单数"})
        )
        df_lost["week"] = pd.to_datetime(df_lost["time"], errors="coerce").dt.to_period("W")
        lost_week = df_lost.groupby("week")["id"].nunique().reset_index()
        lost_week["周起始日"] = lost_week["week"].dt.start_time
        lost_by_week = lost_week[["周起始日", "id"]].rename(columns={"id": "订单数"})
        # 整单备注高频词
        lost_ids = df_lost["id"].unique()
        lost_remark = (
            df_orders[df_orders["id"].isin(lost_ids)]["order_remark"]
            .astype(str)
            .str.strip()
            .replace({"": "--"})
            .value_counts()
            .reset_index()
        )
        lost_remark.columns = ["流失订单备注词", "频次"]
    else:
        lost_by_month = pd.DataFrame(columns=["月份", "订单数"])
        lost_by_week = pd.DataFrame(columns=["周起始日", "订单数"])
        lost_remark = pd.DataFrame(columns=["流失订单备注词", "频次"])

    # ===== 综合指标，用于 1_销售趋势 总览 =====
    total_sales = df_pay_clean["amount"].sum()
    total_orders = df_pay_clean["id"].nunique()
    aov = total_sales / total_orders if total_orders else 0
    df_orders_paid = df_orders[df_orders["id"].isin(df_pay_clean["id"])]
    total_people = pd.to_numeric(df_orders_paid.get("people", 0), errors="coerce").fillna(0).sum()
    if not df_pay_clean.empty:
        d0 = df_pay_clean["time"].min().normalize()
        d1 = df_pay_clean["time"].max().normalize()
        span_days = (d1 - d0).days + 1
    else:
        span_days = 0
    daily_sales = total_sales / span_days if span_days else 0
    daily_orders = total_orders / span_days if span_days else 0
    daily_people = total_people / span_days if span_days else 0

    refund_lost_orders = refund_orders["id"].nunique()
    cancel_lost_orders = cancel_orders["id"].nunique()
    lost_total = refund_lost_orders + cancel_lost_orders
    denom_orders = total_orders + lost_total
    lost_ratio = lost_total / denom_orders if denom_orders else 0

    kpi_matrix = pd.DataFrame(
        [
            ["总销售额", total_sales, "元"],
            ["总客流量(已结账订单数)", total_orders, "单"],
            ["平均客单价 AOV", aov, "元"],
            ["总用餐人数", total_people, "人"],
            ["日均销售额", daily_sales, "元"],
            ["日均订单量", daily_orders, "单"],
            ["日均用餐人数", daily_people, "人"],
            ["流失-退款完成订单数", refund_lost_orders, "单"],
            ["流失-已撤单订单数", cancel_lost_orders, "单"],
        ],
        columns=["指标", "数值", "单位"],
    )
    lost_summary = pd.DataFrame(
        [["退款完成", refund_lost_orders, "单"], ["已撤单", cancel_lost_orders, "单"]],
        columns=["状态", "订单数", "单位"],
    )

    # ===== 导出多 Sheet 结论表 =====
    report_file = f"餐饮数据化分析结论_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with pd.ExcelWriter(report_file, engine="openpyxl") as writer:
        # 1_销售趋势
        sheet = "1_销售趋势"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        core_lines = [
            f"全期总销售额 {total_sales:,.0f} 元，已结账订单数 {total_orders} 单，平均客单价 {aov:.1f} 元；总用餐人数 {int(total_people)} 人。",
            f"流失订单汇总：退款完成 {refund_lost_orders} 单，已撤单 {cancel_lost_orders} 单，占全部订单（已结账+流失） {lost_ratio*100:.1f}%。",
            f"日均销售额 {daily_sales:,.0f} 元，日均订单量 {daily_orders:.1f} 单，日均用餐人数 {daily_people:.1f} 人（统计跨度 {span_days} 天）。",
        ]
        for i, line in enumerate(core_lines, start=1):
            pd.DataFrame([[line]]).to_excel(writer, sheet_name=sheet, startrow=i, index=False, header=False)
        r = len(core_lines) + 2
        pd.DataFrame([["【核心指标矩阵】"]]).to_excel(writer, sheet_name=sheet, startrow=r, index=False, header=False)
        kpi_matrix.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(kpi_matrix) + 3
        pd.DataFrame([["【流失订单汇总(退款完成/已撤单)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        lost_summary.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(lost_summary) + 3
        pd.DataFrame([["【月度趋势与MoM】"]]).to_excel(writer, sheet_name=sheet, startrow=r, index=False, header=False)
        monthly_sales.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(monthly_sales) + 3
        pd.DataFrame([["【周度趋势与WoW(仅完整自然周)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        weekly_sales.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)

        # 2_时段交叉
        sheet = "2_时段交叉"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        df_time = df_pay_clean.copy()
        df_time["weekday"] = df_time["time"].dt.weekday
        df_time["weekday_cn"] = df_time["weekday"].map(
            lambda x: WEEKDAY_CN[int(x)] if pd.notna(x) and 0 <= int(x) < 7 else ""
        )
        df_time["daypart"] = df_time["time"].apply(classify_daypart)
        time_pivot = (
            df_time.groupby(["weekday_cn", "daypart"])
            .agg({"amount": "sum", "id": "nunique"})
            .reset_index()
            .rename(columns={"weekday_cn": "星期", "daypart": "时段", "amount": "销售额", "id": "订单数"})
        )
        total_time_sales = time_pivot["销售额"].sum()
        time_pivot["营收占比"] = time_pivot["销售额"] / total_time_sales if total_time_sales else 0
        top3 = time_pivot.sort_values("销售额", ascending=False).head(3).copy()
        top3["类型"] = "最忙"
        bottom3 = time_pivot.sort_values("销售额", ascending=True).head(3).copy()
        bottom3["类型"] = "冷清"
        busy_cold = pd.concat([top3, bottom3], ignore_index=True)

        cross_lines = ["按「星期 + 营业时段」交叉统计营收与订单数；营收占比见下表。"]
        for i, line in enumerate(cross_lines, start=1):
            pd.DataFrame([[line]]).to_excel(writer, sheet_name=sheet, startrow=i, index=False, header=False)
        r = len(cross_lines) + 2
        pd.DataFrame([["【星期×时段(销售额与占比)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        time_pivot.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(time_pivot) + 3
        pd.DataFrame([["【最忙Top3与冷清Bottom】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        busy_cold.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)

        # 3_退菜分析（简化，只输出 Top5 + 备注高频 + 高退菜客户占位）
        sheet = "3_退菜分析"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        r = 2
        if not df_refunds.empty:
            refund_by_dish = (
                df_refunds.groupby("dish")
                .agg({"qty": "sum", "price": "sum", "id": "nunique"})
                .reset_index()
                .rename(columns={"dish": "菜品", "qty": "退菜数量", "price": "退菜金额", "id": "涉及订单数"})
            )
            dish_sales = df_sales.groupby("dish")["price"].sum()
            refund_by_dish["退菜率"] = refund_by_dish["菜品"].map(dish_sales)
            refund_by_dish["退菜率"] = refund_by_dish.apply(
                lambda rr: (rr["退菜金额"] / rr["退菜率"]) if rr["退菜率"] else 0, axis=1
            )
            refund_top5 = refund_by_dish.nlargest(5, "退菜金额")
            remark_freq = (
                df_refunds["remark"].astype(str).str.strip().replace({"": "--"}).value_counts().reset_index()
            )
            remark_freq.columns = ["退菜备注词", "频次"]
            # 高退菜客户：基于订单数，剔除退菜订单数为 0 的客户
            df_ref_enriched = pd.merge(df_refunds[["id"]], df_pay[["id", "payer"]], on="id", how="left")
            refund_orders_by_payer = (
                df_ref_enriched.groupby("payer")["id"].nunique().reset_index().rename(columns={"id": "退菜订单数"})
            )
            orders_by_payer = (
                df_pay.groupby("payer")["id"].nunique().reset_index().rename(columns={"id": "总订单数"})
            )
            high_refund = pd.merge(orders_by_payer, refund_orders_by_payer, on="payer", how="left").fillna(0)
            # 只保留总订单数≥2 且 有退菜订单的客户
            high_refund = high_refund[
                (high_refund["总订单数"] >= 2) & (high_refund["退菜订单数"] > 0)
            ].copy()
            high_refund["退菜订单占比"] = high_refund["退菜订单数"] / high_refund["总订单数"]
            high_refund = high_refund.sort_values("退菜订单占比", ascending=False)
            high_refund = high_refund.rename(columns={"payer": "付款人"})
        else:
            refund_top5 = pd.DataFrame(columns=["菜品", "退菜数量", "退菜金额", "退菜率", "涉及订单数"])
            remark_freq = pd.DataFrame(columns=["退菜备注词", "频次"])
            high_refund = pd.DataFrame(
                columns=["付款人", "总订单数", "退菜订单数", "退菜订单占比"]
            )

        pd.DataFrame([["【退菜率Top5菜品】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        refund_top5.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(refund_top5) + 3
        pd.DataFrame([["【退菜备注高频词】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        remark_freq.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(remark_freq) + 3
        pd.DataFrame([["【高退菜客户】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        high_refund.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)

        # 4_用户分层（汇总 + 各层级时段/支付方式/优惠响应 + 明细）
        sheet = "4_用户分层"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        r = 2
        pd.DataFrame([["【用户分层汇总】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        segment_summary.reset_index().to_excel(
            writer, sheet_name=sheet, startrow=r + 1, index=False
        )
        r = r + len(segment_summary) + 3
        # 各层级时段分布
        pd.DataFrame([["【各层级时段分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        seg_time_pivot.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(seg_time_pivot) + 3
        # 各层级支付方式
        pd.DataFrame([["【各层级支付方式】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        pay_pivot.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(pay_pivot) + 3
        # 各层级优惠响应
        pd.DataFrame([["【各层级优惠响应】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        disc_summary.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(disc_summary) + 3
        # 分层用户明细
        user_detail = user_rfm.rename(
            columns={
                "payer": "付款人",
                "last_visit": "最近消费时间",
                "frequency": "订单数",
                "monetary": "总消费金额",
                "segment": "用户类型",
            }
        )
        pd.DataFrame([["【分层用户明细】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        user_detail.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)

        # 5_员工表现
        sheet = "5_员工表现"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        r = 2
        pd.DataFrame([["【员工汇总(销售额/客单价)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        staff_report.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)

        # 6_菜品分析（只做菜品汇总，避免再拉太多维度）
        sheet = "6_菜品分析"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        r = 2
        dish_sheet = dish_final.rename(columns={"dish": "菜品"})
        pd.DataFrame([["【菜品汇总(按销售额从高到低)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        dish_sheet.sort_values("销售额", ascending=False).to_excel(
            writer, sheet_name=sheet, startrow=r + 1, index=False
        )

        # 7_优惠分析（类型金额占比 + 原因分布）
        sheet = "7_优惠分析"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        r = 2
        pd.DataFrame([["【优惠类型金额占比】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        discount_reason_type = (
            df_discounts.groupby("discount_name")
            .agg({"discount_amount": "sum", "id": "nunique"})
            .reset_index()
            .rename(columns={"discount_amount": "优惠金额", "id": "订单数"})
        )
        total_disc_amt = discount_reason_type["优惠金额"].sum()
        discount_reason_type["金额占比"] = (
            discount_reason_type["优惠金额"] / total_disc_amt if total_disc_amt else 0
        )
        discount_reason_type.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(discount_reason_type) + 3
        pd.DataFrame([["【折扣原因分布(按原因汇总)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        reason_dist = (
            df_discounts.groupby("discount_reason")
            .agg({"discount_amount": "sum", "id": "nunique"})
            .reset_index()
            .rename(columns={"discount_reason": "折扣原因", "discount_amount": "优惠金额", "id": "订单数"})
        )
        reason_dist.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(reason_dist) + 3
        pd.DataFrame([["【优惠类型+折扣原因分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        type_reason_dist = discount_reason.rename(
            columns={
                "discount_name": "优惠类型",
                "discount_reason": "折扣原因",
                "优惠金额": "优惠金额",
                "订单数": "订单数",
            }
        )
        type_reason_dist.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)

        # 8_流失订单分析
        sheet = "8_流失订单分析"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        r = 2
        pd.DataFrame([["【按状态汇总】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        lost_by_status.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(lost_by_status) + 3
        pd.DataFrame([["【流失订单按月】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        lost_by_month.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(lost_by_month) + 3
        pd.DataFrame([["【流失订单按周(按周起始日)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        lost_by_week.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(lost_by_week) + 3
        pd.DataFrame([["【流失订单整单备注高频词】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        lost_remark.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)

    # ===== 前端用 JSON 摘要（简化版）=====
    total_people_seg = segment_summary["人数"].sum() if "人数" in segment_summary.columns else 0
    data_range = ""
    if not df_pay_clean.empty:
        tmin, tmax = df_pay_clean["time"].min(), df_pay_clean["time"].max()
        if pd.notna(tmin) and pd.notna(tmax):
            data_range = f"数据时间范围：{tmin.strftime('%Y-%m-%d')} 至 {tmax.strftime('%Y-%m-%d')}"

    report_json = {
        "meta": {
            "generatedAt": datetime.now().isoformat(),
            "dataRange": data_range,
            "wideFile": wide_file,
            "reportFile": report_file,
        },
        "overview": {
            "summary": [
                f"全期总销售额 {total_sales:,.0f} 元，已结账订单 {total_orders} 单，平均客单价 {aov:.1f} 元。",
                f"用户分层共 {int(total_people_seg)} 人；菜品与员工表现见各模块。",
            ],
            "cards": [
                {"label": "总销售额", "value": f"{total_sales:,.0f}", "unit": "元"},
                {"label": "已结账订单", "value": str(int(total_orders)), "unit": "单"},
                {"label": "平均客单价", "value": f"{aov:.1f}", "unit": "元"},
                {"label": "用户分层人数", "value": str(int(total_people_seg)), "unit": "人"},
            ],
        },
        "sections": [
            {
                "id": "sales",
                "title": "一、销售趋势与月度环比",
                "conclusions": [
                    f"月度销售额与环比见下表；全期总销售额 {total_sales:,.0f} 元，订单 {total_orders} 单。"
                ],
                "tables": [{"name": "月度趋势与MoM", **df_to_json_table(monthly_sales)}],
            },
            {
                "id": "user",
                "title": "二、用户分层群体画像",
                "conclusions": ["按 RFM 分层为：新客 / 一般活跃 / 沉睡唤醒 / 高价值忠诚；各群体人数与平均贡献见下表。"],
                "tables": [{"name": "用户分层汇总", **df_to_json_table(segment_summary.reset_index())}],
            },
            {
                "id": "discount",
                "title": "三、优惠因果分析",
                "conclusions": ["优惠类型与折扣原因的金额与订单数见下表。"],
                "tables": [{"name": "优惠名称与备注关联", **df_to_json_table(discount_reason)}],
            },
            {
                "id": "dish",
                "title": "四、菜品运营全景",
                "conclusions": ["Top 菜品按销售额排序；含销量、退菜率、主攻客户层级。"],
                "tables": [
                    {
                        "name": "Top 菜品",
                        **df_to_json_table(dish_sheet.sort_values("销售额", ascending=False).head(20)),
                    }
                ],
            },
            {
                "id": "staff",
                "title": "五、员工服务表现",
                "conclusions": ["已剔除系统/收银等虚拟账号；员工销售额与客单价见下表。"],
                "tables": [
                    {
                        "name": "员工汇总",
                        **df_to_json_table(staff_report.sort_values("销售额", ascending=False)),
                    }
                ],
            },
        ],
    }

    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("✅ 餐饮数据化分析 main_analysis_v2 完成")
    print("-" * 60)
    print(f"1. 宽表：{wide_file}")
    print(f"2. 分析结论：{report_file}")
    print(f"3. 前端 JSON：{json_path}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        run_catering_analysis()
    finally:
        input("\n分析完成，按回车键退出...")

