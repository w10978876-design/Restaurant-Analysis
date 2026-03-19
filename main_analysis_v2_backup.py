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
            "staff": ["操作人", "操作员", "收银员"],
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
            "time": ["下单时间"],
            "refund_tag": ["退单标识"],
            # 取餐号优先，其次才是桌牌号/桌号/台号
            "table": ["取餐号", "桌牌号", "桌号", "台号"],
            "order_remark": ["整单备注"],
            # 新增字段：优惠方式、敏感操作
            "discount_method": ["优惠方式"],
            "sensitive_action": ["敏感操作"],
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
    # 将所有“占比 / 比率 / 转化率 / 率”类列统一格式化为百分比字符串（保留两位小数）
    for c in df.columns:
        col_name = str(c)
        if any(k in col_name for k in ["占比", "比率", "转化率"]) or col_name.endswith("率"):
            if pd.api.types.is_numeric_dtype(df[c]):
                s = pd.to_numeric(df[c], errors="coerce")
                s = (s * 100).round(2)
                df[c] = s.map(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    for c in df.columns:
        if hasattr(df[c].dtype, "name") and "period" in str(df[c].dtype).lower():
            df[c] = df[c].astype(str)
        else:
            df[c] = df[c].fillna("").astype(str)
    return {"columns": list(df.columns), "rows": df.values.tolist()}


def format_percent_columns_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """
    在导出到 Excel 前，将 DataFrame 中所有“占比 / 比率 / 转化率 / 率”类列
    统一格式化为百分比字符串（保留两位小数），以便在【餐饮数据化分析结论】中直接查看。
    """
    if df is None or df.empty:
        return df
    df = df.copy()
    for c in df.columns:
        col_name = str(c)
        if (
            any(k in col_name for k in ["占比", "比率", "转化率", "环比"])
            or col_name.endswith("率")
        ):
            if pd.api.types.is_numeric_dtype(df[c]):
                s = pd.to_numeric(df[c], errors="coerce")
                s = (s * 100).round(2)
                df[c] = s.map(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    return df


# 全局包装 DataFrame.to_excel：
# 只要写出的目标是“餐饮数据化分析结论_*.xlsx”，且列名中包含“占比 / 比率 / 转化率 / 率”，
# 就在写入 Excel 之前把这些列格式化为百分比字符串（保留两位小数）。
_ORIG_TO_EXCEL = pd.DataFrame.to_excel


def _percent_to_excel(self, *args, **kwargs):  # type: ignore[override]
    """
    全局包装 DataFrame.to_excel：
    - 在写入 Excel 前，对当前 DataFrame 中所有“占比 / 比率 / 转化率 / 率”类列
      统一格式化为百分比字符串（保留两位小数）。
    - 这样无论写到哪个 Sheet，分析结论表中的所有占比/比率字段都会以 xx.xx% 形式显示。
    """
    df_fmt = format_percent_columns_for_excel(self)
    return _ORIG_TO_EXCEL(df_fmt, *args, **kwargs)


pd.DataFrame.to_excel = _percent_to_excel  # type: ignore[assignment]


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


def load_optional_table(
    filename: str,
    mapping: dict,
    numeric_keys: list | None = None,
):
    """
    读取可选源表：若文件不存在则返回空 DataFrame，不影响主流程。
    """
    numeric_keys = numeric_keys or []
    if not os.path.exists(filename):
        return pd.DataFrame(columns=list(mapping.keys()))

    raw = pd.read_excel(filename, nrows=5)
    rename_dict = {}
    for internal, kws in mapping.items():
        col = find_actual_column(raw.columns, kws)
        if col is not None:
            rename_dict[col] = internal
    read_kwargs = {}
    df = pd.read_excel(filename, **read_kwargs)
    df = df.rename(columns=rename_dict)
    # 补齐缺失字段
    for internal in mapping.keys():
        if internal not in df.columns:
            df[internal] = np.nan if internal in numeric_keys else ""
    return df


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

    # 调试：确认订单表是否识别到优惠方式 / 敏感操作
    print("🔎 订单表字段检查：")
    print(f"   - df_orders.columns 是否包含 discount_method: {'discount_method' in df_orders.columns}")
    print(f"   - df_orders.columns 是否包含 sensitive_action: {'sensitive_action' in df_orders.columns}")
    if "discount_method" in df_orders.columns:
        dm_non_empty = (
            df_orders["discount_method"].astype(str).str.strip().replace({"nan": "", "None": ""}) != ""
        ).sum()
        print(f"   - df_orders.discount_method 非空条数: {int(dm_non_empty)}")
    if "sensitive_action" in df_orders.columns:
        sa_non_empty = (
            df_orders["sensitive_action"].astype(str).str.strip().replace({"nan": "", "None": ""}) != ""
        ).sum()
        print(f"   - df_orders.sensitive_action 非空条数: {int(sa_non_empty)}")

    # 可选表：团购核销明细、菜品沽清售罄统计、进馆游客量表
    # 可选表：团购核销明细、菜品沽清售罄统计、进馆游客量表
    _groupon_file = "团购核销明细表.xlsx" if os.path.exists("团购核销明细表.xlsx") else "团购核销明细.xlsx"
    df_groupon = load_optional_table(
        _groupon_file,
        mapping={
            "platform": ["团购平台"],
            "project_name": ["平台项目名称"],
            "cashier_project": ["收银项目名称"],
            "coupon_code": ["团购券码"],
            "time": ["核销/撤销时间"],
            "id": ["订单编号", "订单号", "单号"],
            "order_source": ["订单来源"],
            "op_type": ["操作类型"],
            "operator": ["操作人"],
            "qty": ["次卡核销/撤销份数"],
            "price_market": ["门市价(元)"],
            "price_group": ["团购价格(元)"],
            "price_customer": ["顾客购买价(元)"],
        },
        numeric_keys=["qty", "price_market", "price_group", "price_customer"],
    )

    df_soldout = load_optional_table(
        "菜品沽清售罄统计.xlsx",
        mapping={
            "date": ["日期"],
            "dish_code": ["菜品编码"],
            "dish": ["菜品名称"],
            "category": ["菜品分类"],
            "spec": ["规格"],
            "unit": ["单位"],
            "soldout_type": ["沽清类型"],
            "soldout_time": ["沽清时间"],
            "soldout_reason": ["沽清原因"],
            "resume_time": ["解沽时间"],
            "duration": ["沽清时长"],
            "operator": ["操作人"],
        },
        numeric_keys=[],
    )

    # 进馆游客量表：兼容多种文件名（xlsx/xls）与列名（人数 / 进馆人数）
    _visitor_candidates = [
        "进馆游客量表.xlsx",
        "进馆游客量表.xls",
        "进馆游客量.xlsx",
        "进馆游客量.xls",
        "游客人数统计.xlsx",
        "游客人数统计.xls",
    ]
    _visitors_file = None
    for _cand in _visitor_candidates:
        if os.path.exists(_cand):
            _visitors_file = _cand
            break
    if _visitors_file is None:
        _visitors_file = "进馆游客量表.xlsx"  # 不存在则后续返回空表
    df_visitors = load_optional_table(
        _visitors_file,
        mapping={
            "date": ["日期"],
            "visitors": ["人数", "进馆人数"],
        },
        numeric_keys=["visitors"],
    )
    # 针对「游客人数统计」这类多 Sheet 模板：优先选择真正只有「日期 / 人数」两列的 Sheet
    try:
        import pandas as _pd_vis
        _xls = _pd_vis.ExcelFile(_visitors_file)
        _best = None
        for _sheet in _xls.sheet_names:
            _df_s = _pd_vis.read_excel(_visitors_file, sheet_name=_sheet)
            cols = [str(c) for c in _df_s.columns]
            if len(cols) == 2 and any("日期" in c for c in cols) and any("人数" in c for c in cols):
                _best = _df_s
                break
        if _best is not None:
            # 标准化为内部字段：date / visitors
            col_date = [c for c in _best.columns if "日期" in str(c)][0]
            col_vis = [c for c in _best.columns if "人数" in str(c)][0]
            df_visitors = pd.DataFrame(
                {
                    "date": _best[col_date],
                    "visitors": _best[col_vis],
                }
            )
    except Exception:
        # 任何异常都不影响主流程，保持 df_visitors 现状
        pass

    # 统一时间列
    for df in [df_orders, df_pay, df_refunds]:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")

    # 提前算数据时间段与输出目录（宽表/分析表写入独立目录，不与数据源混放）
    _pay_clean = df_pay.dropna(subset=["time", "amount"])
    if not _pay_clean.empty:
        _d0 = _pay_clean["time"].min().normalize()
        _d1 = _pay_clean["time"].max().normalize()
        _data_range_str = _d0.strftime("%Y-%m-%d") + "_" + _d1.strftime("%Y-%m-%d")
    else:
        _data_range_str = datetime.now().strftime("%Y-%m-%d")
    _restaurant_name = os.path.basename(os.getcwd())
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _output_dir = os.path.join(_script_dir, "output", _restaurant_name, _data_range_str)
    os.makedirs(_output_dir, exist_ok=True)
    _version_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ===== 宽表 =====
    df_sales["dish_status"] = "SALE"
    df_refunds["dish_status"] = "REFUND"
    df_all_dishes = pd.concat([df_sales, df_refunds], ignore_index=True)

    df_discounts_agg = df_discounts.groupby("id").agg(
        {
            "discount_amount": "sum",
            "discount_name": lambda x: "; ".join(sorted(set(str(v) for v in x if pd.notna(v)))),
            "discount_reason": lambda x: "; ".join(sorted(set(str(v) for v in x if pd.notna(v)))),
            "discount_type": lambda x: "; ".join(sorted(set(str(v) for v in x if pd.notna(v)))),
        }
    ).reset_index()

    # 宽表以订单明细为底表，再拼菜品、支付、优惠
    df_wide = pd.merge(df_orders[df_orders["id"] != ""], df_all_dishes, on="id", how="left")
    df_wide = pd.merge(df_wide, df_pay, on="id", how="left", suffixes=("", "_pay"))
    df_wide = pd.merge(df_wide, df_discounts_agg, on="id", how="left")
    # 防止映射缺失，显式把订单里的优惠方式和敏感操作再补一遍到宽表
    extra_cols = [c for c in ["discount_method", "sensitive_action"] if c in df_orders.columns]
    if extra_cols:
        df_wide = pd.merge(
            df_wide,
            df_orders[["id"] + extra_cols],
            on="id",
            how="left",
            suffixes=("", "_orders"),
        )

    # 调试：确认宽表是否真正带上优惠方式 / 敏感操作
    print("🔎 宽表字段检查：")
    print(f"   - df_wide.columns 是否包含 discount_method: {'discount_method' in df_wide.columns}")
    print(f"   - df_wide.columns 是否包含 sensitive_action: {'sensitive_action' in df_wide.columns}")
    if "discount_method" in df_wide.columns:
        dm_non_empty_wide = (
            df_wide["discount_method"].astype(str).str.strip().replace({"nan": "", "None": ""}) != ""
        ).sum()
        print(f"   - df_wide.discount_method 非空条数: {int(dm_non_empty_wide)}")
        print("   - df_wide.discount_method 前5条:", df_wide["discount_method"].head(5).tolist())
    if "sensitive_action" in df_wide.columns:
        sa_non_empty_wide = (
            df_wide["sensitive_action"].astype(str).str.strip().replace({"nan": "", "None": ""}) != ""
        ).sum()
        print(f"   - df_wide.sensitive_action 非空条数: {int(sa_non_empty_wide)}")
        print("   - df_wide.sensitive_action 前5条:", df_wide["sensitive_action"].head(5).tolist())

    wide_file = os.path.join(_output_dir, f"餐饮业务全量宽表_{_restaurant_name}_{_data_range_str}_{_version_ts}.xlsx")
    df_wide.to_excel(wide_file, index=False)

    print(f"① 宽表导出：{wide_file}")

    # ===== 1. 销售趋势 =====
    # 1.1 订单级金额口径：
    # - 金额：基于【全部订单】的「支付合计(元)」（若无则回退为销售明细汇总），避免漏掉未能识别用户的支付；
    # - 订单数：仅统计 status == "已结账" 的订单，代表有效客流。
    df_orders_amt = df_orders.copy()
    pay_col_orders = find_actual_column(df_orders.columns, ["支付合计"])
    if pay_col_orders is not None:
        df_orders_amt["order_amount"] = pd.to_numeric(
            df_orders_amt[pay_col_orders], errors="coerce"
        )
    else:
        order_sales = (
            df_sales.groupby("id")["price"]
            .sum()
            .reset_index()
            .rename(columns={"price": "order_amount"})
        )
        df_orders_amt = df_orders_amt.merge(order_sales, on="id", how="left")
    df_orders_amt["order_amount"] = (
        pd.to_numeric(df_orders_amt["order_amount"], errors="coerce").fillna(0)
    )
    df_orders_amt["time"] = pd.to_datetime(df_orders_amt["time"], errors="coerce")
    df_orders_amt = df_orders_amt.dropna(subset=["time"])
    df_orders_amt["month"] = df_orders_amt["time"].dt.to_period("M")
    df_orders_amt["week"] = df_orders_amt["time"].dt.to_period("W")

    # 已结账订单视角（用于订单数）
    df_orders_paid = df_orders_amt[df_orders_amt["status"] == "已结账"].copy()
    df_orders_paid["month"] = df_orders_paid["time"].dt.to_period("M")
    df_orders_paid["week"] = df_orders_paid["time"].dt.to_period("W")

    monthly_sales_amt = (
        df_orders_amt.groupby("month")["order_amount"].sum().reset_index()
    )
    monthly_orders = (
        df_orders_paid.groupby("month")["id"].nunique().reset_index()
    )
    monthly_sales = (
        monthly_sales_amt.merge(monthly_orders, on="month", how="left")
        .rename(columns={"order_amount": "销售额", "id": "订单数"})
        .fillna({"订单数": 0})
    )
    # 销售额月环比（保留原公式，改列名便于理解）
    monthly_sales["销售额月环比"] = monthly_sales["销售额"].pct_change()

    weekly_amt = (
        df_orders_amt.groupby("week")["order_amount"].sum().reset_index()
    )
    weekly_orders = (
        df_orders_paid.groupby("week")["id"].nunique().reset_index()
    )
    weekly_raw = (
        weekly_amt.merge(weekly_orders, on="week", how="left")
        .rename(columns={"order_amount": "销售额", "id": "订单数"})
        .fillna({"订单数": 0})
    )
    weekly_raw["周起始日"] = weekly_raw["week"].dt.start_time
    data_start = df_orders_amt["time"].min().normalize()
    data_end = df_orders_amt["time"].max().normalize()
    full_weeks = weekly_raw[
        (weekly_raw["周起始日"] > data_start - pd.to_timedelta(data_start.weekday(), unit="D"))
        & (weekly_raw["周起始日"] + pd.Timedelta(days=7) <= data_end + pd.Timedelta(days=1))
    ].copy()
    full_weeks = full_weeks.sort_values("周起始日")
    # 销售额周环比（保留原公式，改列名便于理解）
    full_weeks["销售额周环比"] = full_weeks["销售额"].pct_change()
    weekly_sales = full_weeks[["周起始日", "销售额", "订单数", "销售额周环比"]]

    # 销售趋势与时段交叉之外的“可识别用户”分析，仍基于支付明细（只包含有 payer 的记录）
    df_pay_clean = df_pay.dropna(subset=["time", "amount"]).copy()

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

    # 各层级优惠响应：按宽表中的 discount_name + 实际有优惠金额统计“有折扣用户”
    df_platform_disc = df_wide.copy()
    df_platform_disc["id_str"] = df_platform_disc["id"].astype(str)
    # 严格清洗 discount_name：视 "", "--", "nan", "None" 等为无优惠名称
    name_col = "discount_name"
    if name_col in df_platform_disc.columns:
        df_platform_disc["disc_name_clean"] = (
            df_platform_disc[name_col]
            .astype(str)
            .str.strip()
            .replace({"nan": "", "NaN": "", "None": "", "NONE": ""})
        )
    else:
        df_platform_disc["disc_name_clean"] = ""
    df_platform_disc["has_disc_name"] = ~df_platform_disc["disc_name_clean"].isin(
        ["", "--"]
    )
    # 订单级优惠金额：若列缺失或为空则当作 0，仅保留实际有优惠金额的订单
    disc_amt_col = "discount_amount" if "discount_amount" in df_platform_disc.columns else None
    if disc_amt_col:
        df_platform_disc["_disc_amt"] = pd.to_numeric(
            df_platform_disc[disc_amt_col], errors="coerce"
        ).fillna(0.0)
    else:
        df_platform_disc["_disc_amt"] = 0.0
    df_platform_disc = (
        df_platform_disc[
            (df_platform_disc["has_disc_name"]) & (df_platform_disc["_disc_amt"] > 0)
        ]
        .dropna(subset=["id_str"])
        .sort_values("id_str")
        .drop_duplicates(subset=["id_str"])
    )
    if not df_platform_disc.empty:
        df_platform_disc = df_platform_disc.merge(
            user_rfm[["payer", "segment"]], on="payer", how="left"
        )
        disc_response_summary = (
            df_platform_disc.groupby("segment")
            .agg(
                有折扣用户数=("payer", "nunique"),
                有折扣用户订单数=("id_str", "nunique"),
                有折扣用户金额=("discount_amount", "sum"),
            )
            .reset_index()
        )
        total_orders_by_seg = (
            seg_orders.groupby("segment")["订单数"].sum().reset_index()
        )
        disc_response_summary = disc_response_summary.merge(
            total_orders_by_seg, on="segment", how="left"
        )
        disc_response_summary["有折扣订单占比"] = (
            disc_response_summary["有折扣用户订单数"] / disc_response_summary["订单数"]
        )
        disc_response_summary = disc_response_summary.rename(
            columns={"订单数": "总订单数"}
        )
    else:
        disc_response_summary = pd.DataFrame(
            columns=[
                "segment",
                "有折扣用户数",
                "有折扣用户订单数",
                "有折扣用户金额",
                "总订单数",
                "有折扣订单占比",
            ]
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

    # ===== 3. 优惠因果分析（优惠类型 + 折扣原因）=====
    # 使用优惠明细中的折扣原因：
    # - 如果 FIELD_CONFIG 已经把「折扣优惠原因」映射为 discount_reason，就直接清洗该列
    # - 否则再尝试按中文列名识别一次
    if "discount_reason" in df_discounts.columns:
        df_discounts["discount_reason"] = (
            df_discounts["discount_reason"].astype(str).str.strip().replace({"": "--"})
        )
    else:
        reason_col = find_actual_column(
            df_discounts.columns, ["折扣优惠原因", "折扣原因", "优惠原因"]
        )
        if reason_col is not None:
            df_discounts["discount_reason"] = (
                df_discounts[reason_col].astype(str).str.strip().replace({"": "--"})
            )
        else:
            df_discounts["discount_reason"] = "--"
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

    # 风险菜品：退菜额>0 且 退菜率≥5% 且 销售额在 Top30%
    if not dish_final.empty:
        sales_threshold = dish_final["销售额"].quantile(0.7)
        risk_dishes = dish_final[
            (dish_final["退菜额"] > 0)
            & (dish_final["退菜率"] >= 0.05)
            & (dish_final["销售额"] >= sales_threshold)
        ].copy().sort_values("退菜率", ascending=False)
    else:
        risk_dishes = pd.DataFrame(columns=dish_final.columns)

    # 关键备注词分析：基于整单备注 + 菜品 + 时段 + 星期
    df_order_rem = df_orders[["id", "order_remark"]].copy()
    df_order_rem["备注词"] = df_order_rem["order_remark"].astype(str).str.strip().replace({"": "--"})
    # 统计备注频次（-- 视为无备注，后面剔除）
    remark_freq_all = df_order_rem["备注词"].value_counts().reset_index()
    remark_freq_all.columns = ["备注词", "频次"]
    remark_freq_all = remark_freq_all[remark_freq_all["备注词"] != "--"]
    # 关联菜品与时间
    df_rem_detail = pd.merge(
        df_sales[["id", "dish"]],
        df_pay[["id", "time"]],
        on="id",
        how="left",
    )
    df_rem_detail = pd.merge(df_rem_detail, df_order_rem[["id", "备注词"]], on="id", how="left")
    # 去掉无备注（--）
    df_rem_detail = df_rem_detail[df_rem_detail["备注词"] != "--"]
    if not df_rem_detail.empty:
        df_rem_detail["time"] = pd.to_datetime(df_rem_detail["time"], errors="coerce")
        df_rem_detail["weekday"] = df_rem_detail["time"].dt.weekday
        df_rem_detail["星期"] = df_rem_detail["weekday"].map(
            lambda x: WEEKDAY_CN[int(x)] if pd.notna(x) and 0 <= int(x) < 7 else ""
        )
        df_rem_detail["时段"] = df_rem_detail["time"].apply(classify_daypart)

        def top_mode(s):
            s = s.dropna()
            if s.empty:
                return ""
            return s.value_counts().idxmax()

        remark_top = (
            df_rem_detail.groupby("备注词")
            .agg({"dish": top_mode, "时段": top_mode, "星期": top_mode})
            .reset_index()
            .rename(columns={"dish": "关联菜品", "时段": "高发时段", "星期": "高发星期"})
        )
        remark_analysis = remark_freq_all.merge(remark_top, on="备注词", how="left")
    else:
        remark_analysis = pd.DataFrame(columns=["备注词", "频次", "关联菜品", "高发时段", "高发星期"])

    # 菜品-时段销量占比：菜品在各时段销量的占比
    df_dish_time = pd.merge(
        df_sales[["id", "dish", "qty"]],
        df_pay[["id", "time"]],
        on="id",
        how="left",
    )
    if not df_dish_time.empty:
        df_dish_time["daypart"] = df_dish_time["time"].apply(classify_daypart)
        dish_time = df_dish_time.groupby(["dish", "daypart"])["qty"].sum().reset_index()
        total_qty = dish_time.groupby("dish")["qty"].sum().rename("总销量")
        dish_time = dish_time.merge(total_qty, on="dish", how="left")
        dish_time["占比"] = dish_time["qty"] / dish_time["总销量"]
        dish_time_pivot = (
            dish_time.pivot_table(
                index="dish",
                columns="daypart",
                values="占比",
                fill_value=0,
            )
            .reset_index()
            .rename(columns={"dish": "菜品"})
        )
    else:
        dish_time_pivot = pd.DataFrame(columns=["菜品", "早餐", "午餐", "下午茶", "晚餐", "夜宵"])

    # 菜品关联度：同一订单内共现菜品对 Top30
    df_pairs_src = df_sales[["id", "dish"]].dropna()
    pair_counts = {}
    for oid, group in df_pairs_src.groupby("id"):
        dishes = sorted(set(group["dish"].dropna().tolist()))
        if len(dishes) < 2:
            continue
        for a, b in itertools.combinations(dishes, 2):
            key = (a, b)
            pair_counts[key] = pair_counts.get(key, 0) + 1
    if pair_counts:
        pairs = pd.DataFrame(
            [(k[0], k[1], v) for k, v in pair_counts.items()],
            columns=["菜品A", "菜品B", "共现订单数"],
        ).sort_values("共现订单数", ascending=False).head(30)
    else:
        pairs = pd.DataFrame(columns=["菜品A", "菜品B", "共现订单数"])

    # ===== 5. 员工表现（销售额 / 订单数 / 客单价 / 退菜率 / 优惠率 / 备注活跃度）=====
    exclude_pattern = r"00000|00015|顾客/系统|收银"
    # 基础销售统计：剔除虚拟账号
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

    # 员工退菜率：退菜量 / 销售量
    if not df_refunds.empty:
        df_staff_refund = df_refunds[
            ~df_refunds["staff"].astype(str).str.contains(exclude_pattern, na=False)
        ].copy()
        staff_refund_qty = df_staff_refund.groupby("staff")["qty"].sum()
    else:
        staff_refund_qty = pd.Series(dtype=float)
    staff_sale_qty = df_staff_sales.groupby("staff")["qty"].sum()
    staff_refund_rate = (staff_refund_qty / staff_sale_qty).fillna(0)

    # 员工优惠率：有优惠的订单数 / 总订单数
    df_disc_staff = df_wide[
        (df_wide["discount_amount"] > 0)
        & (~df_wide["staff"].astype(str).str.contains(exclude_pattern, na=False))
    ].copy()
    staff_disc_orders = df_disc_staff.groupby("staff")["id"].nunique()
    staff_discount_rate = (
        staff_disc_orders / staff_base.set_index("staff")["订单数"]
    ).fillna(0)

    # 备注活跃度：有备注订单数 / 总订单数
    df_staff_remark = df_staff_sales.copy()
    df_staff_remark["has_remark"] = (
        df_staff_remark["remark"].astype(str).str.strip().ne("")
    )
    staff_remark_orders = df_staff_remark.groupby("staff")["has_remark"].sum()
    staff_remark_rate = (
        staff_remark_orders / staff_base.set_index("staff")["订单数"]
    ).fillna(0)

    staff_report = staff_base.copy()
    staff_report["退菜率"] = staff_report["staff"].map(staff_refund_rate).fillna(0)
    staff_report["优惠率"] = staff_report["staff"].map(staff_discount_rate).fillna(0)
    staff_report["备注活跃度"] = staff_report["staff"].map(staff_remark_rate).fillna(0)
    staff_report = staff_report.sort_values("销售额", ascending=False)

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
    # 有效订单与用餐人数：仅以订单明细为准（状态=已结账），不再依赖支付明细或退单标识
    # 金额口径：基于【全部订单】的 order_amount（df_orders_amt），与销售趋势金额一致
    total_people = (
        pd.to_numeric(df_orders_paid.get("people", 0), errors="coerce")
        .fillna(0)
        .sum()
    )
    # 总销售额 = 全量订单的 order_amount 求和；订单数 = 已结账订单数
    total_sales = df_orders_amt["order_amount"].sum()
    total_orders = df_orders_paid["id"].nunique()
    aov = total_sales / total_orders if total_orders else 0
    if not df_orders_paid.empty:
        d0 = df_orders_paid["time"].min().normalize()
        d1 = df_orders_paid["time"].max().normalize()
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

    # ===== 9. 敏感操作分析 =====
    # 先以【订单明细】为底表，按“敏感操作≠空且≠--，再按日期+取餐号去重”的口径统计一版
    if "sensitive_action" in df_orders.columns:
        df_sens_raw = df_orders.copy()
        df_sens_raw["sensitive_action_clean"] = (
            df_sens_raw["sensitive_action"].astype(str).str.strip()
        )
        mask = (df_sens_raw["sensitive_action_clean"] != "") & (
            df_sens_raw["sensitive_action_clean"] != "--"
        )
        df_sens_raw = df_sens_raw[mask].copy()

        if not df_sens_raw.empty:
            # 时间、日期、取餐号
            df_sens_raw["time"] = pd.to_datetime(
                df_sens_raw["time"], errors="coerce"
            )
            df_sens_raw["date"] = df_sens_raw["time"].dt.normalize()
            df_sens_raw["table_clean"] = (
                df_sens_raw["table"].astype(str).str.strip()
            )

            # 订单数口径：只在「取餐号非空，且同一天下有重复取餐号」的组合上去重
            df_tmp = df_sens_raw.copy()
            # 仅在取餐号非空的记录上统计同日同取餐号出现次数
            has_table_mask = df_tmp["table_clean"] != ""
            df_tmp["_grp_size"] = 0
            df_tmp.loc[has_table_mask, "_grp_size"] = (
                df_tmp[has_table_mask]
                .groupby(["date", "table_clean"])["id"]
                .transform("size")
            )
            # 需要去重的组合：同日同取餐号至少出现 2 次，且取餐号非空
            df_tmp["_need_dedup"] = (df_tmp["_grp_size"] >= 2) & has_table_mask

            # 对需要去重的组合按 (date, table_clean) 保留一条；其它记录全部保留
            base_sens_dups = (
                df_tmp[df_tmp["_need_dedup"]]
                .drop_duplicates(subset=["date", "table_clean"])
            )
            base_sens_non_dups = df_tmp[~df_tmp["_need_dedup"]]
            base_sens = pd.concat(
                [base_sens_dups, base_sens_non_dups], ignore_index=True
            ).drop(columns=["_grp_size", "_need_dedup"])

            # 9.1 金额口径：从订单表中找到“支付合计(元)”和“订单优惠(元)”列（与订单数口径解耦）
            pay_col = find_actual_column(df_orders.columns, ["支付合计"])
            disc_col = find_actual_column(df_orders.columns, ["订单优惠"])
            df_orders_amt = df_orders.copy()
            if pay_col is not None:
                df_orders_amt["_pay_total"] = pd.to_numeric(
                    df_orders_amt[pay_col], errors="coerce"
                ).fillna(0)
            else:
                df_orders_amt["_pay_total"] = 0.0
            if disc_col is not None:
                df_orders_amt["_order_disc"] = pd.to_numeric(
                    df_orders_amt[disc_col], errors="coerce"
                ).fillna(0)
            else:
                df_orders_amt["_order_disc"] = 0.0

            # 分母：全部订单的支付合计(元)求和
            total_pay_sum = df_orders_amt["_pay_total"].sum()

            # 分子（敏感金额）：在所有敏感行上计算，不受订单数去重影响
            df_sens_amt = df_sens_raw.merge(
                df_orders_amt[["id", "_pay_total", "_order_disc"]],
                on="id",
                how="left",
            )
            # 支付合计中的负数部分取绝对值，相当于 |min(pay_total, 0)|
            neg_part = (-df_sens_amt["_pay_total"]).clip(lower=0)
            # 每行敏感金额 = 负数支付合计的绝对值 + 订单优惠(元)
            df_sens_amt["_sens_amount"] = neg_part + df_sens_amt["_order_disc"]

            # 9.2 按敏感操作类型汇总：订单数 + 敏感金额
            # 订单数：按规则去重后的 base_sens；金额：按所有敏感行 df_sens_amt 累加
            sens_counts = (
                base_sens.groupby("sensitive_action_clean")["table_clean"]
                .size()
                .reset_index()
                .rename(columns={"table_clean": "订单数"})
            )
            sens_amount = (
                df_sens_amt.groupby("sensitive_action_clean")["_sens_amount"]
                .sum()
                .reset_index()
                .rename(columns={"_sens_amount": "涉及金额"})
            )
            # 每单敏感金额汇总，为与优惠订单做重叠分析准备
            sens_by_id = (
                df_sens_amt.groupby("id")["_sens_amount"]
                .sum()
                .reset_index()
                .rename(columns={"_sens_amount": "敏感金额"})
            )
            sens_summary = sens_counts.merge(
                sens_amount, on="sensitive_action_clean", how="left"
            ).rename(columns={"sensitive_action_clean": "敏感操作类型"})
            sens_summary["涉及金额"] = sens_summary["涉及金额"].fillna(0)
            # 占比改为金额占比：敏感金额 / 全部支付合计(元)
            sens_summary["占比"] = (
                sens_summary["涉及金额"] / total_pay_sum
                if total_pay_sum
                else 0
            )

            # 9.2 敏感操作发生日期分布（按【日期+取餐号】去重后的每日敏感订单数）
            sens_by_date = (
                base_sens.groupby("date")["table_clean"]
                .nunique()
                .reset_index()
                .rename(columns={"table_clean": "订单数"})
            )
            sens_by_date["日期"] = sens_by_date["date"].astype(str)
            sens_by_date = sens_by_date[["日期", "订单数"]]

            # 9.3 敏感操作操作人分布（基于订单明细的 staff）
            if "staff" in df_orders.columns:
                df_sens_staff = base_sens.copy()
                df_sens_staff["staff_clean"] = (
                    df_sens_staff["staff"].astype(str).str.strip()
                )
                # 简单剔除虚拟账号
                df_sens_staff = df_sens_staff[
                    ~df_sens_staff["staff_clean"].str.contains(
                        r"00000|顾客/系统|收银", na=False
                    )
                ]
                sens_by_operator = (
                    df_sens_staff.groupby("staff_clean")["table_clean"]
                    .size()
                    .reset_index()
                    .rename(
                        columns={
                            "staff_clean": "操作人",
                            "table_clean": "订单数",
                        }
                    )
                )
            else:
                sens_by_operator = pd.DataFrame(
                    columns=["操作人", "订单数"]
                )

            # 公共辅助函数：求众数（用于高发操作类型 / 高发时段）
            def _top_action(s: pd.Series) -> str:
                s = s.dropna().astype(str).str.strip()
                if s.empty:
                    return ""
                m = s.mode()
                return m.iat[0] if not m.empty else ""

            # 9.4 敏感操作时段分布：按你给的4个时段 + 超出时段用具体 HH:MM，基于去重后的 base_sens
            def sens_time_bucket(t):
                if pd.isna(t):
                    return ""
                h, m = t.hour, t.minute
                mins = h * 60 + m
                if 10 * 60 <= mins <= 11 * 60 + 30:
                    return "10:00-11:30"
                elif 11 * 60 + 30 < mins <= 14 * 60 + 29:
                    return "11:30-14:29"
                elif 14 * 60 + 30 <= mins <= 17 * 60 + 59:
                    return "14:30-17:59"
                elif 18 * 60 <= mins <= 20 * 60 + 59:
                    return "18:00-20:59"
                # 超出四个核心时段：直接用具体时间点
                return t.strftime("%H:%M")

            base_sens["time_bucket"] = base_sens["time"].apply(sens_time_bucket)
            sens_by_daypart = (
                base_sens.groupby("time_bucket")
                .agg(
                    订单数=("table_clean", "size"),
                    高发类型=("sensitive_action_clean", _top_action),
                )
                .reset_index()
                .rename(columns={"time_bucket": "时段"})
            )

            # 9.5 敏感订单整单备注(原因)统计：保持原表不变
            if "order_remark" in df_orders.columns:
                df_sens_rem = base_sens.copy()
                df_sens_rem["remark_clean"] = (
                    df_sens_rem["order_remark"]
                    .astype(str)
                    .str.strip()
                    .replace({"": "未填写", "--": "未填写"})
                )

                sens_remark_freq = (
                    df_sens_rem.groupby("remark_clean")
                    .agg(
                        订单数=("table_clean", "size"),
                        高发操作类型=("sensitive_action_clean", _top_action),
                        高发时段=("time_bucket", _top_action),
                    )
                    .reset_index()
                    .rename(columns={"remark_clean": "备注内容"})
                )

                # 额外一张表：整单备注 + 优惠类型/原因分布（确保所有敏感订单都进入）
                disc_reason_per_id = (
                    df_discounts.groupby("id")
                    .agg(
                        优惠类型=("discount_name", _top_action),
                        优惠原因=("discount_reason", _top_action),
                    )
                    .reset_index()
                )
                has_disc_ids = set(disc_reason_per_id["id"])
                # 有优惠明细的敏感订单
                df_sens_with_disc = df_sens_rem[
                    df_sens_rem["id"].isin(has_disc_ids)
                ].merge(disc_reason_per_id, on="id", how="left")
                df_sens_with_disc["有优惠记录"] = 1
                # 无优惠明细的敏感订单：强制补“未填写”的优惠类型/原因
                df_sens_no_disc = df_sens_rem[
                    ~df_sens_rem["id"].isin(has_disc_ids)
                ].copy()
                if not df_sens_no_disc.empty:
                    df_sens_no_disc["优惠类型"] = "未填写"
                    df_sens_no_disc["优惠原因"] = "未填写"
                    df_sens_no_disc["有优惠记录"] = 0
                # 合并两部分，确保所有敏感订单都进入交叉表
                df_sens_rem_with_disc = pd.concat(
                    [df_sens_with_disc, df_sens_no_disc], ignore_index=True
                )
                # 将缺失/占位符统一归为“未填写”，确保“备注=未填写 且 优惠原因=未填写”的组合能被统计出来
                for col in ["优惠类型", "优惠原因"]:
                    df_sens_rem_with_disc[col] = (
                        df_sens_rem_with_disc[col]
                        .astype(str)
                        .str.strip()
                        .replace({"": "未填写", "nan": "未填写", "--": "未填写"})
                    )
                # 交叉显示：整单备注(原因) × 优惠类型 × 优惠原因
                sens_remark_with_disc = (
                    df_sens_rem_with_disc.groupby(
                        ["remark_clean", "优惠类型", "优惠原因"]
                    )
                    .agg(
                        订单数=("table_clean", "size"),
                        高发操作类型=("sensitive_action_clean", _top_action),
                        高发时段=("time_bucket", _top_action),
                        有优惠记录=("有优惠记录", "max"),
                    )
                    .reset_index()
                    .rename(
                        columns={
                            "remark_clean": "备注内容",
                        }
                    )
                )
            else:
                sens_remark_freq = pd.DataFrame(
                    columns=["备注内容", "订单数", "高发操作类型", "高发时段"]
                )
                sens_remark_with_disc = pd.DataFrame(
                    columns=["备注内容", "优惠类型", "优惠原因", "订单数", "高发操作类型", "高发时段"]
                )
        else:
            sens_summary = pd.DataFrame(
                columns=["敏感操作类型", "订单数", "涉及金额", "占比"]
            )
            sens_by_date = pd.DataFrame(columns=["日期", "订单数"])
            sens_by_daypart = pd.DataFrame(columns=["时段", "订单数"])
            sens_by_operator = pd.DataFrame(columns=["操作人", "订单数"])
            sens_remark_freq = pd.DataFrame(
                columns=["备注内容", "订单数", "高发操作类型", "高发时段"]
            )
            sens_remark_with_disc = pd.DataFrame(
                columns=["备注内容", "优惠类型", "优惠原因", "订单数", "高发操作类型", "高发时段", "有优惠记录"]
            )
            sens_by_id = pd.DataFrame(columns=["id", "敏感金额"])
    else:
        sens_summary = pd.DataFrame(
            columns=["敏感操作类型", "订单数", "涉及金额", "占比"]
        )
        sens_by_date = pd.DataFrame(columns=["日期", "订单数"])
        sens_by_daypart = pd.DataFrame(columns=["时段", "订单数"])
        sens_by_operator = pd.DataFrame(columns=["操作人", "订单数"])
        sens_remark_freq = pd.DataFrame(
            columns=["备注内容", "订单数", "高发操作类型", "高发时段"]
        )
        sens_remark_with_disc = pd.DataFrame(
            columns=["备注内容", "优惠类型", "优惠原因", "订单数", "高发操作类型", "高发时段", "有优惠记录"]
        )
        sens_by_id = pd.DataFrame(columns=["id", "敏感金额"])

    # ===== 10. 团购核销分析 =====
    if not df_groupon.empty and "id" in df_groupon.columns:
        g = df_groupon.copy()
        g["id"] = g["id"].apply(clean_id)
        g["coupon_code"] = g.get("coupon_code", "").astype(str).str.strip()
        # 时间字段
        if "time" in g.columns:
            g["time"] = pd.to_datetime(g["time"], errors="coerce")
            g["date"] = g["time"].dt.normalize()
        else:
            g["time"] = pd.NaT
            g["date"] = pd.NaT

        # 操作类型：消费=有效核销，撤销=无效
        op_col = "op_type" if "op_type" in g.columns else None
        if op_col:
            g["op_type"] = g[op_col].astype(str).str.strip()
        else:
            g["op_type"] = ""

        g["weekday_cn"] = g["date"].dt.dayofweek.map(
            lambda i: WEEKDAY_CN[i] if pd.notna(i) else ""
        )

        def _time_bucket(t):
            if pd.isna(t):
                return ""
            h, m = t.hour, t.minute
            minutes = h * 60 + m
            if 10 * 60 <= minutes <= 11 * 60 + 30:
                return "10:00-11:30"
            elif 11 * 60 + 30 < minutes <= 14 * 60 + 29:
                return "11:30-14:29"
            elif 14 * 60 + 30 <= minutes <= 17 * 60 + 59:
                return "14:30-17:59"
            elif 18 * 60 <= minutes <= 20 * 60 + 59:
                return "18:00-20:59"
            else:
                return "其他"

        g["time_bucket"] = g["time"].apply(_time_bucket)

        # 有效订单总数（按已结账订单）
        total_valid_orders = df_orders_paid["id"].nunique()

        # 拆分消费 & 撤销
        g_valid = g[g["op_type"] == "消费"].copy()
        g_cancel = g[g["op_type"] == "撤销"].copy()

        # -------- 正常消费券（主分析）--------
        order_ids = (
            g_valid["id"].astype(str).replace("", pd.NA).dropna().unique().tolist()
        )
        coupon_ids = (
            g_valid["coupon_code"]
            .astype(str)
            .replace("", pd.NA)
            .dropna()
            .unique()
            .tolist()
        )
        groupon_order_count = len(order_ids)
        groupon_coupon_count = len(coupon_ids)

        # 团购销售额：直接用团购核销表中的顾客购买价（仅消费记录）
        if "price_customer" in g_valid.columns and not g_valid["price_customer"].notna().any():
            # load_optional_table 未正确映射时，退回原始中文列名中带“顾客购买”的那一列
            price_cols = [
                c
                for c in g_valid.columns
                if "顾客" in str(c) and "购买" in str(c)
            ]
            price_col = price_cols[0] if price_cols else "price_customer"
        else:
            price_col = "price_customer"
        price_series = g_valid.get(price_col, 0)
        groupon_sales = (
            pd.to_numeric(price_series, errors="coerce").fillna(0).sum()
        )

        groupon_share_orders = (
            groupon_order_count / total_valid_orders if total_valid_orders else 0
        )
        groupon_share_coupons = (
            groupon_coupon_count / total_valid_orders if total_valid_orders else 0
        )

        # 全部有效订单金额之和：优先用订单表中的订单金额列，其次回退 total_sales
        if "order_amount" in df_orders_paid.columns:
            total_order_sales = pd.to_numeric(
                df_orders_paid["order_amount"], errors="coerce"
            ).fillna(0).sum()
        else:
            total_order_sales = total_sales

        groupon_share_sales = (
            groupon_sales / total_order_sales if total_order_sales else 0
        )

        # 同一订单下有多张已消费券的订单数
        multi_coupon_orders = (
            g_valid.groupby("id")["coupon_code"]
            .nunique()
            .reset_index(name="券数")
        )
        multi_coupon_order_count = (multi_coupon_orders["券数"] >= 2).sum()
        multi_coupon_order_share = (
            multi_coupon_order_count / total_valid_orders if total_valid_orders else 0
        )

        groupon_overview = pd.DataFrame(
            [
                ["团购订单数(消费)", groupon_order_count, "单"],
                ["团购订单占比(按有效订单)", f"{groupon_share_orders*100:.1f}%", ""],
                ["团购券笔数(消费)", groupon_coupon_count, "笔"],
                ["团购券笔数占比(按有效订单)", f"{groupon_share_coupons*100:.1f}%", ""],
                ["团购销售额(消费)", f"{groupon_sales:,.1f}", "元"],
                ["团购销售额占比(按订单口径)", f"{groupon_share_sales*100:.1f}%", ""],
                ["单笔多券订单数(消费)", multi_coupon_order_count, "单"],
                [
                    "单笔多券订单占比(按有效订单)",
                    f"{multi_coupon_order_share*100:.1f}%",
                    "",
                ],
            ],
            columns=["指标", "数值", "单位"],
        )

        # 日期分布：订单数 & 券笔数 & 金额 + 占比（仅消费）
        if groupon_order_count or groupon_coupon_count:
            by_date = g_valid.dropna(subset=["date"]).copy()
            grp = by_date.groupby(["date", "weekday_cn"])
            orders_by_date = (
                grp["id"]
                .nunique()
                .reset_index()
                .rename(columns={"id": "团购订单数"})
            )
            coupons_by_date = (
                grp["coupon_code"]
                .nunique()
                .reset_index()
                .rename(columns={"coupon_code": "团购券笔数"})
            )
            groupon_by_date = pd.merge(
                orders_by_date,
                coupons_by_date,
                on=["date", "weekday_cn"],
                how="outer",
            ).fillna(0)
            # 金额：使用与总体相同的金额列（price_col，必要时回退到中文“顾客购买价(元)”）
            sales_by_date = (
                grp[price_col]
                .apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum())
                .reset_index()
                .rename(columns={price_col: "团购销售额"})
            )
            groupon_by_date = pd.merge(
                groupon_by_date, sales_by_date, on=["date", "weekday_cn"], how="left"
            ).fillna(0)
            groupon_by_date["订单占比"] = (
                groupon_by_date["团购订单数"] / total_valid_orders
                if total_valid_orders
                else 0
            )
            groupon_by_date["券笔数占比"] = (
                groupon_by_date["团购券笔数"] / total_valid_orders
                if total_valid_orders
                else 0
            )
            groupon_by_date["金额占比"] = (
                groupon_by_date["团购销售额"] / total_order_sales
                if total_order_sales
                else 0
            )
            groupon_by_date = groupon_by_date.sort_values("date")
            groupon_by_date["日期"] = groupon_by_date["date"].astype(str)
            groupon_by_date = groupon_by_date[
                [
                    "日期",
                    "weekday_cn",
                    "团购订单数",
                    "订单占比",
                    "团购券笔数",
                    "券笔数占比",
                    "团购销售额",
                    "金额占比",
                ]
            ].rename(columns={"weekday_cn": "星期"})
        else:
            groupon_by_date = pd.DataFrame(
                columns=[
                    "日期",
                    "星期",
                    "团购订单数",
                    "订单占比",
                    "团购券笔数",
                    "券笔数占比",
                ]
            )

        # 时段分布：订单数 & 券笔数 & 金额 + 占比（按具体时间段，仅消费）
        if groupon_order_count or groupon_coupon_count:
            by_tb = g_valid[g_valid["time_bucket"] != ""].copy()
            grp2 = by_tb.groupby("time_bucket")
            orders_by_tb = (
                grp2["id"]
                .nunique()
                .reset_index()
                .rename(columns={"id": "团购订单数"})
            )
            coupons_by_tb = (
                grp2["coupon_code"]
                .nunique()
                .reset_index()
                .rename(columns={"coupon_code": "团购券笔数"})
            )
            groupon_by_time = pd.merge(
                orders_by_tb, coupons_by_tb, on="time_bucket", how="outer"
            ).fillna(0)
            sales_by_tb = (
                grp2[price_col]
                .apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum())
                .reset_index()
                .rename(columns={price_col: "团购销售额"})
            )
            groupon_by_time = pd.merge(
                groupon_by_time, sales_by_tb, on="time_bucket", how="left"
            ).fillna(0)
            groupon_by_time["订单占比"] = (
                groupon_by_time["团购订单数"] / total_valid_orders
                if total_valid_orders
                else 0
            )
            groupon_by_time["券笔数占比"] = (
                groupon_by_time["团购券笔数"] / total_valid_orders
                if total_valid_orders
                else 0
            )
            groupon_by_time["金额占比"] = (
                groupon_by_time["团购销售额"] / total_order_sales
                if total_order_sales
                else 0
            )
            groupon_by_time = groupon_by_time.rename(
                columns={"time_bucket": "时间段"}
            )
        else:
            groupon_by_time = pd.DataFrame(
                columns=[
                    "时间段",
                    "团购订单数",
                    "订单占比",
                    "团购券笔数",
                    "券笔数占比",
                ]
            )

        # 按券名称（平台项目名称）分析效果（仅消费记录）
        if "project_name" in g_valid.columns:
            tmp = g_valid.copy()
            # 订单数 & 券笔数
            proj = (
                tmp.groupby("project_name")
                .agg(
                    团购订单数=(
                        "id",
                        lambda x: x.astype(str).replace("", pd.NA).dropna().nunique(),
                    ),
                    团购券笔数=(
                        "coupon_code",
                        lambda x: x.astype(str).replace("", pd.NA).dropna().nunique(),
                    ),
                )
                .reset_index()
            )

            # 销售额：直接用顾客购买价（若 price_customer 为空则回退到原始中文列）
            if "price_customer" in tmp.columns and not tmp["price_customer"].notna().any():
                price_cols = [
                    c
                    for c in tmp.columns
                    if "顾客" in str(c) and "购买" in str(c)
                ]
                price_col = price_cols[0] if price_cols else "price_customer"
            else:
                price_col = "price_customer"
            proj_sales_agg = (
                tmp.groupby("project_name")[price_col]
                .apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum())
                .reset_index()
                .rename(columns={price_col: "团购销售额"})
            )
            proj = proj.merge(proj_sales_agg, on="project_name", how="left")
            proj["团购销售额"] = proj["团购销售额"].fillna(0)

            # 占比（在团购内部）
            total_groupon_orders = proj["团购订单数"].sum()
            total_groupon_coupons = proj["团购券笔数"].sum()
            total_groupon_sales = proj["团购销售额"].sum()
            proj["订单占比"] = (
                proj["团购订单数"] / total_groupon_orders
                if total_groupon_orders
                else 0
            )
            proj["券笔数占比"] = (
                proj["团购券笔数"] / total_groupon_coupons
                if total_groupon_coupons
                else 0
            )
            proj["金额占比"] = (
                proj["团购销售额"] / total_groupon_sales
                if total_groupon_sales
                else 0
            )

            # 高发日期 / 星期 / 时间段
            def _top_mode(series):
                s = series.dropna().astype(str)
                if s.empty:
                    return ""
                mode = s.mode()
                return mode.iat[0] if not mode.empty else ""

            tmp["date_str"] = tmp["date"].dt.strftime("%Y-%m-%d")
            proj_extra = (
                tmp.groupby("project_name")
                .agg(
                    高发日期=("date_str", _top_mode),
                    高发星期=("weekday_cn", _top_mode),
                    高发时间段=("time_bucket", _top_mode),
                )
                .reset_index()
            )
            groupon_by_project = proj.merge(
                proj_extra, on="project_name", how="left"
            )
            groupon_by_project = groupon_by_project.rename(
                columns={"project_name": "券名称"}
            )
        else:
            groupon_by_project = pd.DataFrame(
                columns=[
                    "券名称",
                    "团购订单数",
                    "团购券笔数",
                    "团购销售额",
                    "订单占比",
                    "券笔数占比",
                    "金额占比",
                    "高发日期",
                    "高发星期",
                    "高发时间段",
                ]
            )

        # -------- 撤销记录统计 --------
        if not g_cancel.empty:
            cancel_order_count = (
                g_cancel["id"].astype(str).replace("", pd.NA).dropna().nunique()
            )
            cancel_coupon_count = (
                g_cancel["coupon_code"]
                .astype(str)
                .replace("", pd.NA)
                .dropna()
                .nunique()
            )
            cancel_by_project = (
                g_cancel.groupby("project_name")
                .agg(
                    撤销券笔数=(
                        "coupon_code",
                        lambda x: x.astype(str).replace("", pd.NA).dropna().nunique(),
                    ),
                    撤销订单数=(
                        "id",
                        lambda x: x.astype(str).replace("", pd.NA).dropna().nunique(),
                    ),
                )
                .reset_index()
                .sort_values("撤销券笔数", ascending=False)
            )
            groupon_cancel_overview = pd.DataFrame(
                [
                    ["撤销券笔数", cancel_coupon_count, "笔"],
                    ["撤销订单数", cancel_order_count, "单"],
                ],
                columns=["指标", "数值", "单位"],
            )
            groupon_cancel_top_project = cancel_by_project.rename(
                columns={"project_name": "券名称"}
            )
        else:
            groupon_cancel_overview = pd.DataFrame(
                columns=["指标", "数值", "单位"]
            )
            groupon_cancel_top_project = pd.DataFrame(
                columns=["券名称", "撤销券笔数", "撤销订单数"]
            )
    else:
        groupon_overview = pd.DataFrame(columns=["指标", "数值", "单位"])
        groupon_by_date = pd.DataFrame(
            columns=[
                "日期",
                "星期",
                "团购订单数",
                "订单占比",
                "团购券笔数",
                "券笔数占比",
            ]
        )
        groupon_by_time = pd.DataFrame(
            columns=[
                "时间段",
                "团购订单数",
                "订单占比",
                "团购券笔数",
                "券笔数占比",
            ]
        )
        groupon_by_project = pd.DataFrame(
            columns=[
                "券名称",
                "团购订单数",
                "团购券笔数",
                "团购销售额",
                "订单占比",
                "券笔数占比",
                "金额占比",
                "高发日期",
                "高发星期",
                "高发时间段",
            ]
        )

    # ===== 11. 菜品沽清售罄分析 =====
    if not df_soldout.empty:
        # 基础拷贝与时间字段
        so = df_soldout.copy()
        so["soldout_time"] = pd.to_datetime(so["soldout_time"], errors="coerce")
        so["resume_time"] = pd.to_datetime(so.get("resume_time"), errors="coerce")
        so["sold_date"] = so["soldout_time"].dt.normalize()
        so["weekday_cn"] = so["sold_date"].dt.dayofweek.map(lambda i: WEEKDAY_CN[i])
        so["daypart"] = so["soldout_time"].apply(classify_daypart)

        # 统一计算单次停售时长（分钟）：优先用文本「沽清时长」，否则用解沽-沽清
        import re

        def _parse_duration_to_min(v):
            if pd.isna(v):
                return np.nan
            s = str(v).strip()
            # 先识别“X小时Y分钟”
            h = m = 0.0
            mh = re.search(r"([0-9.]+)\s*小?时", s)
            if mh:
                h = float(mh.group(1))
            mm = re.search(r"([0-9.]+)\s*分", s)
            if mm:
                m = float(mm.group(1))
            if h or m:
                return h * 60 + m
            # 纯数字，按分钟处理
            n = pd.to_numeric(s, errors="coerce")
            return float(n) if pd.notna(n) else np.nan

        so["dur_min"] = np.nan
        if "duration" in so.columns:
            so["dur_min"] = so["duration"].apply(_parse_duration_to_min)
        # 用时间差兜底
        mask_na = so["dur_min"].isna()
        if mask_na.any() and "resume_time" in so.columns and "soldout_time" in so.columns:
            delta = (so.loc[mask_na, "resume_time"] - so.loc[mask_na, "soldout_time"]).dt.total_seconds() / 60
            so.loc[mask_na, "dur_min"] = delta
        # 去掉负值
        so["dur_min"] = so["dur_min"].where(so["dur_min"] >= 0)

        # 将分钟转换为“天”或“小时”的可读格式：>=1 天用天，否则用小时
        def _fmt_minutes(mins):
            if pd.isna(mins):
                return ""
            mins = float(mins)
            if mins >= 1440:  # 24*60
                return f"{mins / 1440:.1f}天"
            else:
                return f"{mins / 60:.1f}小时"

        # 1) 菜品维度总览：整月哪些菜被停过、次数和时长
        # 每道菜涉及的日期详情
        date_detail = (
            so.dropna(subset=["sold_date"])
            .assign(_date_str=so["sold_date"].dt.strftime("%Y-%m-%d"))
            .groupby("dish")["_date_str"]
            .agg(lambda x: "、".join(sorted(set(x))))
            .rename("涉及日期详情")
            .reset_index()
        )

        dish_month_summary = (
            so.groupby("dish")
            .agg(
                被沽清次数=("dish", "count"),
                涉及日期数=("sold_date", "nunique"),
                合计停售时长_分钟=("dur_min", "sum"),
                平均单次停售时长_分钟=("dur_min", "mean"),
                主要沽清类型=(
                    "soldout_type",
                    lambda x: x.mode().iat[0] if not x.mode().empty else "",
                ),
                原因原始=(
                    "soldout_reason",
                    lambda x: (
                        (
                            x.astype(str)
                            .str.strip()
                            .replace("", pd.NA)
                            .dropna()
                            .mode()
                            .iat[0]
                        )
                        if not x.astype(str)
                        .str.strip()
                        .replace("", pd.NA)
                        .dropna()
                        .mode()
                        .empty
                        else ""
                    ),
                ),
            )
            .reset_index()
        )

        # 合并日期详情
        dish_month_summary = dish_month_summary.merge(date_detail, on="dish", how="left")

        # 时长格式化为天/小时，并重命名列
        dish_month_summary["合计停售时长"] = dish_month_summary[
            "合计停售时长_分钟"
        ].apply(_fmt_minutes)
        dish_month_summary["平均单次停售时长"] = dish_month_summary[
            "平均单次停售时长_分钟"
        ].apply(_fmt_minutes)
        dish_month_summary = dish_month_summary.drop(
            columns=["合计停售时长_分钟", "平均单次停售时长_分钟"]
        )

        # 原因：为空则显示“未填写”
        dish_month_summary["原因"] = dish_month_summary["原因原始"].astype(str).str.strip()
        dish_month_summary.loc[dish_month_summary["原因"] == "", "原因"] = "未填写"
        dish_month_summary = dish_month_summary.drop(columns=["原因原始"])

        dish_month_summary = dish_month_summary.sort_values(
            by="被沽清次数", ascending=False
        )

        # 2) 菜 × 类型 × 操作人
        dish_type = (
            so.groupby(["dish", "soldout_type", "operator"])
            .agg(
                停售次数=("dish", "count"),
                合计停售时长_分钟=("dur_min", "sum"),
            )
            .reset_index()
        )
        dish_type["合计停售时长"] = dish_type["合计停售时长_分钟"].apply(_fmt_minutes)
        dish_type = dish_type.drop(columns=["合计停售时长_分钟"])

        # 4) 按星期汇总：每个星期一行，日期/操作人/菜品作为详情
        week_rows = []
        for wk, grp_w in so.groupby("weekday_cn"):
            if grp_w.empty:
                continue
            # 该星期涉及的所有日期
            dates = sorted(
                {
                    d.strftime("%Y-%m-%d")
                    for d in grp_w["sold_date"].dropna().unique().tolist()
                }
            )
            date_str = "、".join(dates)
            # 该星期涉及的所有操作人
            ops = sorted(
                {
                    str(o).strip()
                    for o in grp_w["operator"].dropna().tolist()
                    if str(o).strip() != ""
                }
            )
            op_str = "、".join(ops) if ops else "-"
            # 被停售菜品数 + 菜名详情
            dishes = [
                str(d).strip()
                for d in grp_w["dish"].dropna().unique().tolist()
                if str(d).strip() != ""
            ]
            dish_cnt = len(dishes)
            if dish_cnt:
                dish_detail = f"{dish_cnt}道/" + "、".join(dishes)
            else:
                dish_detail = "0道"
            total_minutes = grp_w["dur_min"].sum()
            week_rows.append(
                [
                    wk,
                    date_str,
                    op_str,
                    dish_detail,
                    _fmt_minutes(total_minutes),
                ]
            )
        soldout_by_date = pd.DataFrame(
            week_rows, columns=["星期", "日期", "操作人", "被停售菜品数", "总停售时长"]
        )

        # 5) 时段维度：每个营业时段(4个固定时间段)的菜品数 / 事件数 / 总时长 + 详情
        def _soldout_time_bucket(t):
            if pd.isna(t):
                return ""
            h, m = t.hour, t.minute
            minutes = h * 60 + m
            # 四个固定分析时段
            if 10 * 60 <= minutes <= 11 * 60 + 30:
                return "10:00-11:30"
            elif 11 * 60 + 30 < minutes <= 14 * 60 + 29:
                return "11:30-14:29"
            elif 14 * 60 + 30 <= minutes <= 17 * 60 + 59:
                return "14:30-17:59"
            elif 18 * 60 <= minutes <= 20 * 60 + 59:
                return "18:00-20:59"
            # 不在四个核心时段内，直接用具体时间点作为“时段”标签，便于分析
            return t.strftime("%H:%M")

        so["time_bucket_so"] = so["soldout_time"].apply(_soldout_time_bucket)
        base_time = (
            so.groupby("time_bucket_so")
            .agg(
                被停售菜品数=("dish", "nunique"),
                停售事件数=("dish", "count"),
                总停售时长_分钟=("dur_min", "sum"),
            )
            .reset_index()
        )

        # 该时段内所有被停售菜品详情：3道/菜A、菜B、菜C
        def _dish_detail(group):
            dishes = [
                str(d).strip()
                for d in group["dish"].dropna().unique().tolist()
                if str(d).strip() != ""
            ]
            if not dishes:
                return "0道"
            return f"{len(dishes)}道/" + "、".join(dishes)

        # 该时段内所有操作人（去重）："张三、李四"
        def _ops_detail(group):
            ops = sorted(
                {
                    str(o).strip()
                    for o in group["operator"].dropna().tolist()
                    if str(o).strip() != ""
                }
            )
            return "、".join(ops) if ops else "-"

        # 该时段内所有沽清类型（去重）："售罄、停售"
        def _type_detail(group):
            types = sorted(
                {
                    str(t).strip()
                    for t in group["soldout_type"].dropna().tolist()
                    if str(t).strip() != ""
                }
            )
            return "、".join(types) if types else "-"

        detail_time = (
            so.groupby("time_bucket_so")
            .apply(
                lambda g2: pd.Series(
                    {
                        "被停售菜品详情": _dish_detail(g2),
                        "操作人": _ops_detail(g2),
                        "沽清类型": _type_detail(g2),
                    }
                )
            )
            .reset_index()
        )

        soldout_by_time = base_time.merge(
            detail_time, on="time_bucket_so", how="left"
        ).rename(columns={"time_bucket_so": "时段"})

        soldout_by_time["总停售时长"] = soldout_by_time["总停售时长_分钟"].apply(
            _fmt_minutes
        )
        soldout_by_time = soldout_by_time[
            ["时段", "被停售菜品数", "停售事件数", "总停售时长", "被停售菜品详情", "操作人", "沽清类型"]
        ]

        # 6) 概览：被停售菜品总数、事件总数、总时长
        soldout_overview = pd.DataFrame(
            [
                ["被沽清菜品数", so["dish"].nunique(), "道"],
                ["沽清事件总数", len(so), "次"],
                [
                    "合计停售时长",
                    _fmt_minutes(so["dur_min"].sum()),
                    "",
                ],
                [
                    "平均单次停售时长",
                    _fmt_minutes(so["dur_min"].mean())
                    if so["dur_min"].notna().any()
                    else "-",
                    "",
                ],
            ],
            columns=["指标", "数值", "单位"],
        )
    else:
        soldout_overview = pd.DataFrame(columns=["指标", "数值", "单位"])
        dish_month_summary = pd.DataFrame(
            columns=[
                "dish",
                "被沽清次数",
                "涉及日期数",
                "涉及日期详情",
                "合计停售时长",
                "平均单次停售时长",
                "主要沽清类型",
                "原因",
            ]
        )
        soldout_by_type = pd.DataFrame(
            columns=["沽清类型", "菜品数", "停售次数", "总停售时长_分钟"]
        )
        soldout_by_date = pd.DataFrame(
            columns=["日期", "星期", "被停售菜品数", "总停售时长_分钟"]
        )
        soldout_by_time = pd.DataFrame(
            columns=["时段", "被停售菜品数", "停售事件数", "总停售时长_分钟"]
        )

    # ===== 12. 进馆游客量与转化率 =====
    # 游客量：来自「游客人数统计」等表的进馆人数
    # 用餐人数：只从订单表推算，按「日期 + 桌号」聚合后取每日桌最大人数再求和，以尽量避免重复计数
    if not df_visitors.empty and "visitors" in df_visitors.columns and "date" in df_visitors.columns:
        df_visitors = df_visitors.copy()
        df_visitors["date"] = pd.to_datetime(df_visitors["date"], errors="coerce").dt.normalize()
        df_visitors["visitors"] = pd.to_numeric(df_visitors["visitors"], errors="coerce")
        df_visitors = df_visitors.dropna(subset=["date"])

        # 从已结账订单中推算每日「到店人数」：按订单去重后按日累计
        daily_people_agg = df_orders_paid.copy()
        daily_people_agg["date"] = pd.to_datetime(daily_people_agg["time"], errors="coerce").dt.normalize()
        daily_people_agg["people"] = pd.to_numeric(daily_people_agg["people"], errors="coerce")
        # 先按 (date, id) 去重，避免同一订单多条记录重复计数，然后按日求和
        daily_people_agg = (
            daily_people_agg.dropna(subset=["people"])
            .groupby(["date", "id"])["people"]
            .max()
            .reset_index()
            .groupby("date")["people"]
            .sum()
            .reset_index()
        )

        # 使用 left 合并，保留所有进馆日期，无订单日期填 0，便于看到数据
        visitor_merge = df_visitors.merge(daily_people_agg, on="date", how="left")
        visitor_merge["people"] = visitor_merge["people"].fillna(0)
        visitor_merge["转化率"] = visitor_merge["people"] / visitor_merge["visitors"].replace(0, np.nan)
        visitor_daily = visitor_merge[["date", "visitors", "people", "转化率"]].rename(
            columns={"date": "日期", "visitors": "进馆人数", "people": "用餐人数"}
        )
        visitor_daily["日期"] = visitor_daily["日期"].astype(str)

        avg_cvr = visitor_daily["转化率"].mean()
        visitor_summary = pd.DataFrame(
            [
                ["有数据天数", len(visitor_daily), "天"],
                ["平均转化率", f"{avg_cvr*100:.1f}%" if pd.notna(avg_cvr) else "-", ""],
            ],
            columns=["指标", "数值", "单位"],
        )
    else:
        visitor_daily = pd.DataFrame(columns=["日期", "进馆人数", "用餐人数", "转化率"])
        visitor_summary = pd.DataFrame(columns=["指标", "数值", "单位"])

    # ===== 导出多 Sheet 结论表 =====
    report_file = os.path.join(_output_dir, f"餐饮数据化分析结论_{_restaurant_name}_{_data_range_str}_{_version_ts}.xlsx")
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

        # 2_时段交叉：金额来自【全部订单】的 order_amount，订单数仅统计已结账订单
        sheet = "2_时段交叉"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        # 金额视角（防御性处理，确保存在 order_amount 列）
        df_time_amt = df_orders_amt.copy()
        if "order_amount" not in df_time_amt.columns:
            _pay_col_orders = find_actual_column(df_orders.columns, ["支付合计"])
            if _pay_col_orders is not None:
                df_time_amt["order_amount"] = pd.to_numeric(
                    df_time_amt[_pay_col_orders], errors="coerce"
                )
            else:
                _order_sales = (
                    df_sales.groupby("id")["price"]
                    .sum()
                    .reset_index()
                    .rename(columns={"price": "order_amount"})
                )
                df_time_amt = df_time_amt.merge(_order_sales, on="id", how="left")
            df_time_amt["order_amount"] = pd.to_numeric(
                df_time_amt["order_amount"], errors="coerce"
            ).fillna(0)
        df_time_amt["weekday"] = df_time_amt["time"].dt.weekday
        df_time_amt["weekday_cn"] = df_time_amt["weekday"].map(
            lambda x: WEEKDAY_CN[int(x)] if pd.notna(x) and 0 <= int(x) < 7 else ""
        )
        df_time_amt["daypart"] = df_time_amt["time"].apply(classify_daypart)
        time_sales = (
            df_time_amt.groupby(["weekday_cn", "daypart"])["order_amount"]
            .sum()
            .reset_index()
        )
        # 订单数视角（仅已结账）
        df_time_paid = df_orders_paid.copy()
        df_time_paid["weekday"] = df_time_paid["time"].dt.weekday
        df_time_paid["weekday_cn"] = df_time_paid["weekday"].map(
            lambda x: WEEKDAY_CN[int(x)] if pd.notna(x) and 0 <= int(x) < 7 else ""
        )
        df_time_paid["daypart"] = df_time_paid["time"].apply(classify_daypart)
        time_orders = (
            df_time_paid.groupby(["weekday_cn", "daypart"])["id"]
            .nunique()
            .reset_index()
        )
        time_pivot = (
            time_sales.merge(time_orders, on=["weekday_cn", "daypart"], how="left")
            .rename(
                columns={
                    "weekday_cn": "星期",
                    "daypart": "时段",
                    "order_amount": "销售额",
                    "id": "订单数",
                }
            )
            .fillna({"订单数": 0})
        )
        # 只保留“星期”和“时段”都有明确取值的记录，避免空-空的汇总行
        time_pivot = time_pivot[
            (time_pivot["星期"].astype(str).str.strip() != "")
            & (time_pivot["时段"].astype(str).str.strip() != "")
        ]
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

            def _calc_refund_rate(rr):
                base_sales = dish_sales.get(rr["菜品"], 0)
                # 有正常销售额 → 按“退菜金额 / 销售额”计算退菜率
                if base_sales and base_sales != 0:
                    return rr["退菜金额"] / base_sales
                # 没有任何正向销售，但有退菜金额 → 标注为说明文字，方便业务解读
                if rr["退菜金额"] and rr["退菜金额"] != 0:
                    return "无正向销售，仅退菜"
                # 既无销售也无退菜 → 视为 0
                return 0

            refund_by_dish["退菜率"] = refund_by_dish.apply(_calc_refund_rate, axis=1)
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
        pd.DataFrame([["【各层级优惠响应(有折扣用户)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        disc_response_summary.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(disc_response_summary) + 3
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
        pd.DataFrame([["【员工汇总(销售额/退菜率/优惠率/备注)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        staff_report.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)

        # 6_菜品分析（菜品汇总 / 风险菜品 / 关键备注词 / 菜品-时段占比 / 关联度）
        sheet = "6_菜品分析"
        pd.DataFrame([["核心结论"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        r = 2
        dish_sheet = dish_final.rename(columns={"dish": "菜品"})
        pd.DataFrame([["【菜品汇总(按销售额从高到低，含各分层订购占比)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        dish_sheet.sort_values("销售额", ascending=False).to_excel(
            writer, sheet_name=sheet, startrow=r + 1, index=False
        )
        r = r + len(dish_sheet) + 3
        pd.DataFrame([["【风险菜品(按退菜率从高到低，含各分层占比)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        risk_dishes.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(risk_dishes) + 3
        pd.DataFrame([["【关键备注词分析(菜品/时段/星期)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        remark_analysis.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(remark_analysis) + 3
        pd.DataFrame([["【菜品-时段销量占比】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        dish_time_pivot.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(dish_time_pivot) + 3
        pd.DataFrame([["【菜品关联度(共现订单数Top30)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        pairs.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)

        # 7_优惠分析（总体占比 / 优惠方式分布 / 星期分布 / 时段分布 / 用户/菜品/员工）
        sheet = "7_优惠分析"
        pd.DataFrame([["核心结论"]]).to_excel(
            writer, sheet_name=sheet, startrow=0, index=False, header=False
        )
        r = 2

        # ===== 7.1 订单集合：有优惠方式 + 无敏感标识（基于宽表）=====
        df_wide_tmp = df_wide.copy()
        df_wide_tmp["id_str"] = df_wide_tmp["id"].astype(str)
        df_wide_tmp["disc_method_clean"] = (
            df_wide_tmp.get("discount_method", "").astype(str).str.strip()
        )
        df_wide_tmp["sens_clean"] = (
            df_wide_tmp.get("sensitive_action", "").astype(str).str.strip()
        )
        df_wide_tmp["has_disc_method"] = ~df_wide_tmp["disc_method_clean"].isin(
            ["", "--"]
        )
        df_wide_tmp["has_sensitive"] = ~df_wide_tmp["sens_clean"].isin(["", "--"])

        order_flags = (
            df_wide_tmp.dropna(subset=["id_str"])
            .groupby("id_str")
            .agg(
                has_disc_method=("has_disc_method", "any"),
                has_sensitive=("has_sensitive", "any"),
            )
            .reset_index()
        )

        target_ids = order_flags[
            (order_flags["has_disc_method"]) & (~order_flags["has_sensitive"])
        ]["id_str"]
        target_id_set = set(target_ids)

        df_wide_nosens = df_wide_tmp[df_wide_tmp["id_str"].isin(target_id_set)].copy()

        # ===== 7.2 订单级优惠金额：统一来自宽表中的「订单优惠(元)」，按订单去重 =====
        disc_col_in_wide = find_actual_column(df_wide_nosens.columns, ["订单优惠"])
        if disc_col_in_wide is not None:
            df_wide_nosens["_order_disc"] = pd.to_numeric(
                df_wide_nosens[disc_col_in_wide], errors="coerce"
            ).fillna(0)
        else:
            df_wide_nosens["_order_disc"] = 0.0

        if not df_wide_nosens.empty:
            # 先按订单去重，再取每单一次「订单优惠(元)」作为该单的优惠金额，避免一单多行被重复累加
            order_level = (
                df_wide_nosens.dropna(subset=["id_str"])
                .sort_values("id_str")
                .drop_duplicates(subset=["id_str"])
            )
            df_disc_orders = order_level[["id_str", "_order_disc"]].rename(
                columns={"id_str": "id", "_order_disc": "优惠金额"}
            )
        else:
            df_disc_orders = pd.DataFrame(columns=["id", "优惠金额"])

        disc_total_amt = df_disc_orders["优惠金额"].sum()
        disc_order_count = df_disc_orders["id"].nunique()

        # 7.2 总体优惠占比
        overall_disc = pd.DataFrame(
            [
                ["总优惠金额", disc_total_amt, "元"],
                [
                    "占全期销售额",
                    (disc_total_amt / total_sales) if total_sales else 0,
                    "占比",
                ],
                ["优惠订单数", disc_order_count, "单"],
                [
                    "占已结账订单",
                    (disc_order_count / total_orders) if total_orders else 0,
                    "占比",
                ],
            ],
            columns=["指标", "数值", "单位"],
        )
        pd.DataFrame([["【总体优惠占比(与总订单对比)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        overall_disc_x = format_percent_columns_for_excel(overall_disc)
        overall_disc_x.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(overall_disc) + 3

        # 7.3 优惠方式分布（discount_method）
        pd.DataFrame([["【优惠方式分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        if not df_wide_nosens.empty and not df_disc_orders.empty:
            order_method = (
                df_wide_nosens[["id_str", "disc_method_clean"]]
                .dropna(subset=["id_str"])
                .drop_duplicates(subset=["id_str"])
            )
            df_disc_with_method = df_disc_orders.merge(
                order_method, left_on="id", right_on="id_str", how="left"
            )
            method_dist = (
                df_disc_with_method.groupby("disc_method_clean")["优惠金额"]
                .agg(["sum", "count"])
                .reset_index()
                .rename(
                    columns={
                        "disc_method_clean": "优惠方式",
                        "sum": "优惠金额",
                        "count": "订单数",
                    }
                )
            )
            total_disc_amt2 = method_dist["优惠金额"].sum()
            method_dist["金额占比"] = (
                method_dist["优惠金额"] / total_disc_amt2 if total_disc_amt2 else 0
            )
        else:
            method_dist = pd.DataFrame(
                columns=["优惠方式", "优惠金额", "订单数", "金额占比"]
            )
        method_dist.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(method_dist) + 3

        # 7.4 订单级时间信息（用于星期 / 时段 / 用户特征）
        if not df_disc_orders.empty:
            # 营业日期与时间列（宽表中为营业日期_x / time_x）
            date_col = find_actual_column(df_wide_nosens.columns, ["营业日期"])
            time_col = "time_x" if "time_x" in df_wide_nosens.columns else (
                "time_pay" if "time_pay" in df_wide_nosens.columns else "time"
            )
            base_per_order = (
                df_wide_nosens.dropna(subset=["id_str"])
                .sort_values(time_col)
                .drop_duplicates(subset=["id_str"])
            )
            cols_to_merge = ["id_str", "payer"]
            if time_col in df_wide_nosens.columns:
                cols_to_merge.append(time_col)
            if date_col is not None:
                cols_to_merge.append(date_col)

            df_disc_orders_time = df_disc_orders.merge(
                base_per_order[cols_to_merge],
                left_on="id",
                right_on="id_str",
                how="left",
            )
            if time_col in df_disc_orders_time.columns:
                df_disc_orders_time[time_col] = pd.to_datetime(
                    df_disc_orders_time[time_col], errors="coerce"
                )
            if date_col is not None:
                df_disc_orders_time["date"] = pd.to_datetime(
                    df_disc_orders_time[date_col], errors="coerce"
                ).dt.normalize()
            else:
                # 回退：从时间列推导日期
                df_disc_orders_time["date"] = df_disc_orders_time[time_col].dt.normalize()

            # 7.5 优惠星期分布（金额按订单去重，补充示例日期）
            df_disc_orders_time["weekday"] = df_disc_orders_time[time_col].dt.weekday
            df_disc_orders_time["weekday_cn"] = df_disc_orders_time["weekday"].map(
                lambda x: WEEKDAY_CN[int(x)] if pd.notna(x) and 0 <= int(x) < 7 else ""
            )
            df_disc_orders_time["日期"] = df_disc_orders_time["date"].astype(str)
            disc_by_weekday = (
                df_disc_orders_time.groupby("weekday_cn")
                .agg(
                    优惠金额=("优惠金额", "sum"),
                    订单数=("id", "nunique"),
                    示例日期=(
                        "日期",
                        lambda s: ", ".join(
                            sorted(
                                set(
                                    str(v)
                                    for v in s
                                    if pd.notna(v) and str(v) not in ["", "nan"]
                                )
                            )[:3]
                        ),
                    ),
                )
                .reset_index()
                .rename(columns={"weekday_cn": "星期"})
            )

            # 7.6 优惠时段分布：4 个具体时段 + 其他
            def _disc_time_bucket(t):
                if pd.isna(t):
                    return ""
                h, m = t.hour, t.minute
                mins = h * 60 + m
                if 10 * 60 <= mins <= 11 * 60 + 30:
                    return "10:00-11:30"
                elif 11 * 60 + 30 < mins <= 14 * 60 + 29:
                    return "11:30-14:29"
                elif 14 * 60 + 30 <= mins <= 17 * 60 + 59:
                    return "14:30-17:59"
                elif 18 * 60 <= mins <= 20 * 60 + 59:
                    return "18:00-20:59"
                else:
                    return "其他"

            df_disc_orders_time["time_bucket"] = df_disc_orders_time[time_col].apply(
                _disc_time_bucket
            )
            disc_by_daypart = (
                df_disc_orders_time.groupby("time_bucket")
                .agg(
                    优惠金额=("优惠金额", "sum"),
                    订单数=("id", "nunique"),
                )
                .reset_index()
                .rename(columns={"time_bucket": "时段"})
            )

            # 7.7 优惠用户特征
            user_disc = (
                df_disc_orders_time.groupby("payer")
                .agg({"id": "nunique", "优惠金额": "sum"})
                .reset_index()
                .rename(columns={"id": "优惠订单数", "优惠金额": "优惠金额"})
            )
            total_orders_by_payer = (
                df_wide_nosens.groupby("payer")["id_str"]
                .nunique()
                .reset_index()
                .rename(columns={"id_str": "总订单数"})
            )
            user_disc = user_disc.merge(total_orders_by_payer, on="payer", how="left")
            user_disc["优惠订单占比"] = user_disc["优惠订单数"] / user_disc["总订单数"]
            user_disc = user_disc.merge(
                user_rfm[["payer", "segment"]], on="payer", how="left"
            )
            disc_user_feature = user_disc.rename(
                columns={"payer": "付款人", "segment": "用户类型"}
            ).sort_values("优惠金额", ascending=False)
        else:
            disc_by_weekday = pd.DataFrame(
                columns=["星期", "优惠金额", "订单数", "示例日期"]
            )
            disc_by_daypart = pd.DataFrame(columns=["时段", "优惠金额", "订单数"])
            disc_user_feature = pd.DataFrame(
                columns=["付款人", "优惠订单数", "优惠金额", "总订单数", "优惠订单占比", "用户类型"]
            )

        # 7.8 优惠关联菜品 Top15：按订单数从大到小排序，金额以菜品优惠(元)为准（若存在）
        if not df_disc_orders.empty:
            df_disc_dish = df_wide_nosens[
                df_wide_nosens["id_str"].isin(df_disc_orders["id"])
            ][["id_str", "dish"]].dropna(subset=["id_str", "dish"])
            df_disc_dish = df_disc_dish.drop_duplicates(subset=["id_str", "dish"])

            # 优先使用宽表中的「菜品优惠(元)」列；若不存在则回退到订单级优惠金额
            dish_disc_col = find_actual_column(df_wide_nosens.columns, ["菜品优惠"])
            if dish_disc_col is not None:
                dish_disc_df = df_wide_nosens[
                    df_wide_nosens["id_str"].isin(df_disc_orders["id"])
                ][["id_str", "dish", dish_disc_col]].copy()
                dish_disc_df = dish_disc_df.dropna(subset=["id_str", "dish"])
                dish_disc_df[dish_disc_col] = pd.to_numeric(
                    dish_disc_df[dish_disc_col], errors="coerce"
                ).fillna(0)
                disc_dish = (
                    dish_disc_df.groupby("dish")
                    .agg(
                        优惠金额=(dish_disc_col, "sum"),
                        订单数=("id_str", "nunique"),
                    )
                    .reset_index()
                    .rename(columns={"dish": "菜品"})
                )
            else:
                # 回退方案：使用订单级优惠金额
                df_disc_dish = df_disc_dish.merge(
                    df_disc_orders, left_on="id_str", right_on="id", how="left"
                )
                disc_dish = (
                    df_disc_dish.groupby("dish")
                    .agg(
                        优惠金额=("优惠金额", "sum"),
                        订单数=("id_str", "nunique"),
                    )
                    .reset_index()
                    .rename(columns={"dish": "菜品"})
                )
            disc_dish_top15 = disc_dish.sort_values(
                ["订单数", "优惠金额"], ascending=[False, False]
            ).head(15)
        else:
            disc_dish_top15 = pd.DataFrame(columns=["菜品", "优惠金额", "订单数"])

        # 7.9 员工维度优惠占比(已剔除虚拟账号)，优惠金额按订单级处理
        if not df_disc_orders.empty:
            exclude_pattern = r"00000|00015|顾客/系统|收银"
            staff_per_order = df_wide_nosens[["id_str", "staff"]].copy()
            staff_per_order = staff_per_order[
                ~staff_per_order["staff"].astype(str).str.contains(
                    exclude_pattern, na=False
                )
            ]
            staff_per_order = staff_per_order.drop_duplicates(subset=["id_str"])
            df_disc_staff = df_disc_orders.merge(
                staff_per_order, left_on="id", right_on="id_str", how="left"
            ).dropna(subset=["staff"])
            staff_disc = (
                df_disc_staff.groupby("staff")
                .agg({"优惠金额": "sum", "id": "nunique"})
                .reset_index()
                .rename(columns={"id": "优惠订单数"})
            )
            staff_orders = staff_report[["staff", "订单数"]].rename(
                columns={"订单数": "总订单数"}
            )
            staff_disc = staff_disc.merge(staff_orders, on="staff", how="left")
            staff_disc["优惠订单占比"] = (
                staff_disc["优惠订单数"] / staff_disc["总订单数"]
            )
            disc_staff_summary = staff_disc.rename(columns={"staff": "员工"})
        else:
            disc_staff_summary = pd.DataFrame(
                columns=["员工", "优惠金额", "优惠订单数", "总订单数", "优惠订单占比"]
            )

        # 写入 7 章各表
        pd.DataFrame([["【优惠方式分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        method_dist_x = format_percent_columns_for_excel(method_dist)
        method_dist_x.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(method_dist) + 3

        pd.DataFrame([["【优惠星期分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        disc_by_weekday_x = format_percent_columns_for_excel(disc_by_weekday)
        disc_by_weekday_x.to_excel(
            writer, sheet_name=sheet, startrow=r + 1, index=False
        )
        r = r + len(disc_by_weekday) + 3

        pd.DataFrame([["【优惠时段分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        disc_by_daypart_x = format_percent_columns_for_excel(disc_by_daypart)
        disc_by_daypart_x.to_excel(
            writer, sheet_name=sheet, startrow=r + 1, index=False
        )
        r = r + len(disc_by_daypart) + 3

        pd.DataFrame([["【优惠用户特征(谁/几次/金额)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        disc_user_feature_x = format_percent_columns_for_excel(disc_user_feature)
        disc_user_feature_x.to_excel(
            writer, sheet_name=sheet, startrow=r + 1, index=False
        )
        r = r + len(disc_user_feature) + 3

        pd.DataFrame([["【优惠关联菜品Top15】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        disc_dish_top15.to_excel(writer, sheet_name=sheet, startrow=r + 1, index=False)
        r = r + len(disc_dish_top15) + 3

        pd.DataFrame([["【员工维度优惠占比(已剔除虚拟账号)】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r, index=False, header=False
        )
        disc_staff_summary_x = format_percent_columns_for_excel(disc_staff_summary)
        disc_staff_summary_x.to_excel(
            writer, sheet_name=sheet, startrow=r + 1, index=False
        )
        r = r + len(disc_staff_summary) + 3

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

        # 9_敏感操作分析
        sheet = "9_敏感操作分析"
        pd.DataFrame([["敏感操作类型、订单数、涉及金额、占比；发生时段与操作人分布，以及整单备注原因（含高发操作类型/时段）和日期分布。"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        r9 = 2
        sens_summary.to_excel(writer, sheet_name=sheet, startrow=r9, index=False)
        r9 += len(sens_summary) + 2
        pd.DataFrame([["【敏感操作时段分布】"]]).to_excel(writer, sheet_name=sheet, startrow=r9, index=False, header=False)
        sens_by_daypart.to_excel(writer, sheet_name=sheet, startrow=r9 + 1, index=False)
        r9 += 1 + len(sens_by_daypart) + 2
        pd.DataFrame([["【敏感操作操作人分布】"]]).to_excel(writer, sheet_name=sheet, startrow=r9, index=False, header=False)
        sens_by_operator.to_excel(writer, sheet_name=sheet, startrow=r9 + 1, index=False)
        r9 += 1 + len(sens_by_operator) + 2
        pd.DataFrame([["【敏感订单整单备注(原因)统计】"]]).to_excel(writer, sheet_name=sheet, startrow=r9, index=False, header=False)
        sens_remark_freq.to_excel(writer, sheet_name=sheet, startrow=r9 + 1, index=False)
        r9 += 1 + len(sens_remark_freq) + 2
        pd.DataFrame([["【敏感订单整单备注(原因)+优惠原因分布】"]]).to_excel(writer, sheet_name=sheet, startrow=r9, index=False, header=False)
        sens_remark_with_disc.to_excel(writer, sheet_name=sheet, startrow=r9 + 1, index=False)
        r9 += 1 + len(sens_remark_with_disc) + 2
        pd.DataFrame([["【敏感操作发生日期分布】"]]).to_excel(writer, sheet_name=sheet, startrow=r9, index=False, header=False)
        sens_by_date.to_excel(writer, sheet_name=sheet, startrow=r9 + 1, index=False)

        # 10_团购核销分析
        sheet = "10_团购核销分析"
        pd.DataFrame(
            [
                [
                    "团购订单数/券笔数/销售额在整体中的占比，以及团购核销在日期与具体时间段上的分布和各券名称的效果。"
                ]
            ]
        ).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        r10 = 2
        pd.DataFrame([["【团购总体指标】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r10, index=False, header=False
        )
        groupon_overview.to_excel(
            writer, sheet_name=sheet, startrow=r10 + 1, index=False
        )
        r10 = r10 + len(groupon_overview) + 3

        pd.DataFrame([["【按日期的团购分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r10, index=False, header=False
        )
        groupon_by_date.to_excel(
            writer, sheet_name=sheet, startrow=r10 + 1, index=False
        )
        r10 = r10 + len(groupon_by_date) + 3

        pd.DataFrame([["【按时间段的团购分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r10, index=False, header=False
        )
        groupon_by_time.to_excel(
            writer, sheet_name=sheet, startrow=r10 + 1, index=False
        )
        r10 = r10 + len(groupon_by_time) + 3

        pd.DataFrame([["【按券名称(平台项目名称)的团购效果】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r10, index=False, header=False
        )
        groupon_by_project.to_excel(
            writer, sheet_name=sheet, startrow=r10 + 1, index=False
        )
        r10 = r10 + len(groupon_by_project) + 3

        pd.DataFrame([["【团购撤销概览】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r10, index=False, header=False
        )
        groupon_cancel_overview.to_excel(
            writer, sheet_name=sheet, startrow=r10 + 1, index=False
        )
        r10 = r10 + len(groupon_cancel_overview) + 3

        pd.DataFrame([["【撤销主要集中在哪些团购券】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r10, index=False, header=False
        )
        groupon_cancel_top_project.to_excel(
            writer, sheet_name=sheet, startrow=r10 + 1, index=False
        )

        # 11_菜品沽清售罄分析
        sheet = "11_菜品沽清售罄分析"
        pd.DataFrame([["本期被沽清菜品概览、沽清类型分布、按日期/星期与时段的停售分布。"]]).to_excel(
            writer, sheet_name=sheet, startrow=0, index=False, header=False
        )
        r11 = 2
        # 概览
        soldout_overview.to_excel(writer, sheet_name=sheet, startrow=r11, index=False)
        r11 += len(soldout_overview) + 2
        # 菜品维度总览
        pd.DataFrame([["【被沽清菜品汇总（整月）】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r11, index=False, header=False
        )
        dish_month_summary.to_excel(
            writer, sheet_name=sheet, startrow=r11 + 1, index=False
        )
        r11 += 1 + len(dish_month_summary) + 2
        # 日期/星期
        pd.DataFrame([["【按日期/星期的停售分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r11, index=False, header=False
        )
        soldout_by_date.to_excel(
            writer, sheet_name=sheet, startrow=r11 + 1, index=False
        )
        r11 += 1 + len(soldout_by_date) + 2
        # 时段
        pd.DataFrame([["【按营业时段的停售分布】"]]).to_excel(
            writer, sheet_name=sheet, startrow=r11, index=False, header=False
        )
        soldout_by_time.to_excel(
            writer, sheet_name=sheet, startrow=r11 + 1, index=False
        )

        # 12_进馆游客量与转化率
        sheet = "12_进馆游客量与转化率"
        pd.DataFrame([["进馆人数与用餐人数对照、转化率（仅当有游客量数据时）。"]]).to_excel(writer, sheet_name=sheet, startrow=0, index=False, header=False)
        visitor_summary.to_excel(writer, sheet_name=sheet, startrow=2, index=False)
        visitor_daily.to_excel(writer, sheet_name=sheet, startrow=2 + len(visitor_summary) + 2, index=False)

    # 各层级响应概览：融合平台优惠响应 + 高退菜客户 + 有折扣用户
    seg_response = segment_summary.copy()

    # 1) 从「高退菜客户」聚合到分层
    if not high_refund.empty:
        high_refund_with_seg = high_refund.merge(
            user_rfm[["payer", "segment"]],
            left_on="付款人",
            right_on="payer",
            how="left",
        )
        refund_by_seg = (
            high_refund_with_seg.groupby("segment")
            .agg(
                高退菜客户数=("付款人", "nunique"),
                高退菜订单数=("退菜订单数", "sum"),
            )
            .reset_index()
        )
        seg_response = (
            seg_response.reset_index()
            .merge(refund_by_seg, on="segment", how="left")
            .set_index("segment")
        )
    else:
        seg_response["高退菜客户数"] = 0
        seg_response["高退菜订单数"] = 0

    # 2) 从「优惠用户特征(谁/几次/金额)」聚合到分层：用于“平台优惠客户”
    if not disc_user_feature.empty:
        promo_by_seg = (
            disc_user_feature.groupby("用户类型")
            .agg(
                平台优惠客户数=("付款人", "nunique"),
                平台优惠订单数=("优惠订单数", "sum"),
                平台优惠金额=("优惠金额", "sum"),
            )
            .reset_index()
            .rename(columns={"用户类型": "segment"})
        )
        seg_response = (
            seg_response.reset_index()
            .merge(promo_by_seg, on="segment", how="left")
            .set_index("segment")
        )
    else:
        seg_response["平台优惠客户数"] = 0
        seg_response["平台优惠订单数"] = 0
        seg_response["平台优惠金额"] = 0

    # 3) 补充“有折扣用户”口径（discount_name）
    if not disc_response_summary.empty:
        seg_response = (
            seg_response.reset_index()
            .merge(disc_response_summary, on="segment", how="left")
            .set_index("segment")
        )
    else:
        seg_response["有折扣用户数"] = 0
        seg_response["有折扣用户订单数"] = 0
        seg_response["有折扣用户金额"] = 0
        seg_response["总订单数"] = 0
        seg_response["有折扣订单占比"] = 0

    seg_response = seg_response.reset_index()

    # ===== 前端用 JSON 摘要（与 8 个 Sheet 结论表一致）=====
    total_people_seg = segment_summary["人数"].sum() if "人数" in segment_summary.columns else 0
    data_range = ""
    if not df_orders_amt.empty:
        tmin, tmax = df_orders_amt["time"].min(), df_orders_amt["time"].max()
        if pd.notna(tmin) and pd.notna(tmax):
            data_range = f"数据时间范围：{tmin.strftime('%Y-%m-%d')} 至 {tmax.strftime('%Y-%m-%d')}"

    # 2_时段交叉 所用数据（与 Excel 一致，在 with 外复用逻辑）
    # 金额：全部订单的 order_amount；订单数：仅已结账订单（防御性保证存在 order_amount）
    df_time_amt = df_orders_amt.copy()
    if "order_amount" not in df_time_amt.columns:
        _pay_col_orders = find_actual_column(df_orders.columns, ["支付合计"])
        if _pay_col_orders is not None:
            df_time_amt["order_amount"] = pd.to_numeric(
                df_time_amt[_pay_col_orders], errors="coerce"
            )
        else:
            _order_sales = (
                df_sales.groupby("id")["price"]
                .sum()
                .reset_index()
                .rename(columns={"price": "order_amount"})
            )
            df_time_amt = df_time_amt.merge(_order_sales, on="id", how="left")
        df_time_amt["order_amount"] = pd.to_numeric(
            df_time_amt["order_amount"], errors="coerce"
        ).fillna(0)
    df_time_amt["weekday"] = df_time_amt["time"].dt.weekday
    df_time_amt["weekday_cn"] = df_time_amt["weekday"].map(
        lambda x: WEEKDAY_CN[int(x)] if pd.notna(x) and 0 <= int(x) < 7 else ""
    )
    df_time_amt["daypart"] = df_time_amt["time"].apply(classify_daypart)
    time_sales = (
        df_time_amt.groupby(["weekday_cn", "daypart"])["order_amount"]
        .sum()
        .reset_index()
    )
    df_time_paid = df_orders_paid.copy()
    df_time_paid["weekday"] = df_time_paid["time"].dt.weekday
    df_time_paid["weekday_cn"] = df_time_paid["weekday"].map(
        lambda x: WEEKDAY_CN[int(x)] if pd.notna(x) and 0 <= int(x) < 7 else ""
    )
    df_time_paid["daypart"] = df_time_paid["time"].apply(classify_daypart)
    time_orders = (
        df_time_paid.groupby(["weekday_cn", "daypart"])["id"]
        .nunique()
        .reset_index()
    )
    time_pivot = (
        time_sales.merge(time_orders, on=["weekday_cn", "daypart"], how="left")
        .rename(
            columns={
                "weekday_cn": "星期",
                "daypart": "时段",
                "order_amount": "销售额",
                "id": "订单数",
            }
        )
        .fillna({"订单数": 0})
    )
    # 只保留“星期”和“时段”都有明确取值的记录
    time_pivot = time_pivot[
        (time_pivot["星期"].astype(str).str.strip() != "")
        & (time_pivot["时段"].astype(str).str.strip() != "")
    ]
    total_time_sales = time_pivot["销售额"].sum()
    time_pivot["营收占比"] = time_pivot["销售额"] / total_time_sales if total_time_sales else 0
    top3 = time_pivot.sort_values("销售额", ascending=False).head(3).copy()
    top3["类型"] = "最忙"
    bottom3 = time_pivot.sort_values("销售额", ascending=True).head(3).copy()
    bottom3["类型"] = "冷清"
    busy_cold = pd.concat([top3, bottom3], ignore_index=True)

    user_detail = user_rfm.rename(
        columns={
            "payer": "付款人",
            "last_visit": "最近消费时间",
            "frequency": "订单数",
            "monetary": "总消费金额",
            "segment": "用户类型",
        }
    )

    report_json = {
        "meta": {
            "generatedAt": datetime.now().isoformat(),
            "dataRange": data_range,
            "restaurant": _restaurant_name,
            "rangeKey": _data_range_str,
            "wideFile": os.path.basename(wide_file),
            "reportFile": os.path.basename(report_file),
        },
        "overview": {
            "summary": core_lines,
            "cards": [
                {"label": "总销售额", "value": f"{total_sales:,.0f}", "unit": "元"},
                {"label": "已结账订单", "value": str(int(total_orders)), "unit": "单"},
                {"label": "平均客单价", "value": f"{aov:.1f}", "unit": "元"},
                {"label": "用户分层人数", "value": str(int(total_people_seg)), "unit": "人"},
            ],
        },
        "sections": [
            {
                "id": "1_sales",
                "title": "一、销售趋势",
                "conclusions": core_lines,
                "tables": [
                    {"name": "核心指标矩阵", **df_to_json_table(kpi_matrix)},
                    {"name": "流失订单汇总(退款完成/已撤单)", **df_to_json_table(lost_summary)},
                    {"name": "月度趋势与MoM", **df_to_json_table(monthly_sales)},
                    {"name": "周度趋势与WoW(仅完整自然周)", **df_to_json_table(weekly_sales)},
                ],
            },
            {
                "id": "2_time",
                "title": "二、时段交叉",
                "conclusions": ["按「星期 + 营业时段」交叉统计营收与订单数；营收占比见下表。"],
                "tables": [
                    {"name": "星期×时段(销售额与占比)", **df_to_json_table(time_pivot)},
                    {"name": "最忙Top3与冷清Bottom3", **df_to_json_table(busy_cold)},
                ],
            },
            {
                "id": "3_refund",
                "title": "三、退菜分析",
                "conclusions": ["退菜率 Top5 菜品、退菜备注高频词、高退菜客户（总订单≥2 且退菜订单数>0）。"],
                "tables": [
                    {"name": "退菜率Top5菜品", **df_to_json_table(refund_top5)},
                    {"name": "退菜备注高频词", **df_to_json_table(remark_freq)},
                    {"name": "高退菜客户", **df_to_json_table(high_refund)},
                ],
            },
            {
                "id": "4_user",
                "title": "四、用户分层",
                "conclusions": ["按 RFM 分层：新客 / 一般活跃 / 沉睡唤醒 / 高价值忠诚；各层级时段、支付方式、优惠响应见下表。"],
                "tables": [
                    {"name": "用户分层汇总", **df_to_json_table(segment_summary.reset_index())},
                    {"name": "各层级响应概览", **df_to_json_table(seg_response)},
                    {"name": "各层级时段分布", **df_to_json_table(seg_time_pivot)},
                    {"name": "各层级支付方式", **df_to_json_table(pay_pivot)},
                    {"name": "各层级优惠响应", **df_to_json_table(disc_response_summary)},
                    {"name": "分层用户明细", **df_to_json_table(user_detail.head(200))},
                ],
            },
            {
                "id": "5_staff",
                "title": "五、员工表现",
                "conclusions": ["已剔除收银(00015)、顾客/系统(00000)等虚拟账号；员工销售额、订单数、客单价、退菜率、优惠率见下表。"],
                "tables": [
                    {"name": "员工汇总(销售额/退菜率/优惠率/备注)", **df_to_json_table(staff_report.sort_values("销售额", ascending=False))},
                ],
            },
            {
                "id": "6_dish",
                "title": "六、菜品分析",
                "conclusions": ["菜品汇总(按销售额从高到低)、风险菜品、关键备注词、菜品-时段销量占比、菜品关联度 Top30。"],
                "tables": [
                    {"name": "菜品汇总(按销售额从高到低)", **df_to_json_table(dish_sheet.sort_values("销售额", ascending=False).head(80))},
                    {"name": "风险菜品(按退菜率从高到低)", **df_to_json_table(risk_dishes)},
                    {"name": "关键备注词分析(菜品/时段/星期)", **df_to_json_table(remark_analysis)},
                    {"name": "菜品-时段销量占比", **df_to_json_table(dish_time_pivot)},
                    {"name": "菜品关联度(共现订单数Top30)", **df_to_json_table(pairs)},
                ],
            },
            {
                "id": "7_discount",
                "title": "七、优惠分析",
                "conclusions": ["总体优惠占比、优惠方式分布、优惠在星期和营业时段上的分布、涉及用户特征、关联菜品 Top15 以及员工维度优惠占比（均基于无敏感标识订单，金额统一按订单优惠(元)口径统计）。"],
                "tables": [
                    {"name": "总体优惠占比(与总订单对比)", **df_to_json_table(overall_disc)},
                    {"name": "优惠方式分布", **df_to_json_table(method_dist)},
                    {"name": "优惠星期分布", **df_to_json_table(disc_by_weekday)},
                    {"name": "优惠时段分布", **df_to_json_table(disc_by_daypart)},
                    {"name": "优惠用户特征(谁/几次/金额)", **df_to_json_table(disc_user_feature)},
                    {"name": "优惠关联菜品Top15", **df_to_json_table(disc_dish_top15)},
                    {"name": "员工维度优惠占比(已剔除虚拟账号)", **df_to_json_table(disc_staff_summary)},
                ],
            },
            {
                "id": "8_lost",
                "title": "八、流失订单分析",
                "conclusions": [f"流失订单：退款完成 {refund_lost_orders} 单，已撤单 {cancel_lost_orders} 单；按状态、按月、按周及整单备注高频词见下表。"],
                "tables": [
                    {"name": "按状态汇总", **df_to_json_table(lost_by_status)},
                    {"name": "流失订单按月", **df_to_json_table(lost_by_month)},
                    {"name": "流失订单按周(按周起始日)", **df_to_json_table(lost_by_week)},
                    {"name": "流失订单整单备注高频词", **df_to_json_table(lost_remark)},
                ],
            },
            {
                "id": "9_sensitive",
                "title": "九、敏感操作分析",
                "conclusions": ["敏感操作类型、订单数、涉及金额及占比；发生时段与操作人分布，以及整单备注原因（含高发操作类型/时段）和日期分布，并联动展现与优惠原因的关系。"],
                "tables": [
                    {"name": "敏感操作汇总", **df_to_json_table(sens_summary)},
                    {"name": "敏感操作时段分布", **df_to_json_table(sens_by_daypart)},
                    {"name": "敏感操作操作人分布", **df_to_json_table(sens_by_operator)},
                    {"name": "敏感订单整单备注(原因)统计", **df_to_json_table(sens_remark_freq)},
                    {"name": "敏感订单整单备注(原因)+优惠原因分布", **df_to_json_table(sens_remark_with_disc)},
                    {"name": "敏感操作发生日期分布", **df_to_json_table(sens_by_date)},
                ],
            },
            {
                "id": "10_groupon",
                "title": "十、团购核销分析",
                "conclusions": ["团购订单数/券笔数/销售额在整体中的占比，以及团购核销在日期与具体时间段上的分布和各券名称的效果。"],
                "tables": [
                    {"name": "团购总体指标", **df_to_json_table(groupon_overview)},
                    {"name": "按日期的团购分布", **df_to_json_table(groupon_by_date)},
                    {"name": "按时间段的团购分布", **df_to_json_table(groupon_by_time)},
                    {"name": "按券名称(平台项目名称)的团购效果", **df_to_json_table(groupon_by_project)},
                    {"name": "团购撤销概览", **df_to_json_table(groupon_cancel_overview)},
                    {"name": "撤销主要集中在哪些团购券", **df_to_json_table(groupon_cancel_top_project)},
                ],
            },
            {
                "id": "11_soldout",
                "title": "十一、菜品沽清售罄分析",
                "conclusions": ["本期有哪些菜被沽清过、各菜的停售次数与合计/平均停售时长，以及这些停售在日期/星期与营业时段（含菜品、操作人、沽清类型详情）上的分布。"],
                "tables": [
                    {"name": "沽清售罄概览", **df_to_json_table(soldout_overview)},
                    {"name": "被沽清菜品汇总（整月）", **df_to_json_table(dish_month_summary)},
                    {"name": "按日期/星期的停售分布", **df_to_json_table(soldout_by_date)},
                    {"name": "按营业时段的停售分布", **df_to_json_table(soldout_by_time)},
                ],
            },
            {
                "id": "12_visitor",
                "title": "十二、进馆游客量与转化率",
                "conclusions": ["进馆人数与用餐人数对照、日转化率（仅当有游客量数据时展示）。"],
                "tables": [
                    {"name": "进馆转化率概览", **df_to_json_table(visitor_summary)},
                    {"name": "日度进馆与用餐对照", **df_to_json_table(visitor_daily)},
                ],
            },
        ],
    }

    json_path = os.path.join(_output_dir, "report.json")
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
        # 当作为独立脚本在终端运行时，保留按回车退出的交互；
        # 当由调度器以非交互批处理方式调用时，可通过环境变量 BATCH_MODE=1 跳过等待。
        import os

        if os.environ.get("BATCH_MODE") != "1":
            input("\n分析完成，按回车键退出...")

