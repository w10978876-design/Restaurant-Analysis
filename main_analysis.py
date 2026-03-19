#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
餐饮数据分析入口（多门店 / 多周期调度器）。

当前阶段目标（步骤 1）：
1. 保持原有「python main_analysis.py → 生成宽表 + 分析结果 + report.json」的用法；
2. 若存在 data/ 子目录且其中有若干门店子目录，则：
   - 遍历每个门店子目录，在该目录下调用原始脚本 main_analysis_v2_backup.py；
   - 使用每次运行生成的 report.json 读取 meta 信息（餐厅名、数据时间范围、宽表/报告文件名）；
   - 将这些文件整理到 output/<餐厅>/<起始_结束>/ 目录；
   - 生成 output/index.json，供前端用于「门店 + 数据周期」选择；
3. 如未检测到 data/ 结构，则退回到单门店旧行为（直接在项目根目录调用备份脚本）。

后续步骤会在不改变本入口脚本形态的前提下，逐步扩展分析逻辑与前端。
"""

import json
import os
import re
import shutil
import sys
import subprocess
from datetime import datetime
from typing import Dict, List, Any


def run_single_legacy(script_dir: str) -> None:
    """兼容旧行为：在项目根目录直接运行备份脚本一次。"""
    backup_script = os.path.join(script_dir, "main_analysis_v2_backup.py")
    if not os.path.exists(backup_script):
        raise FileNotFoundError(f"未找到分析脚本：{backup_script}")

    print("🔁 检测到 data/ 目录不存在，按单门店旧模式运行分析脚本 ...")
    # 与之前版本保持一致：直接在当前进程中执行备份脚本
    import runpy

    runpy.run_path(backup_script, run_name="__main__")


def parse_date_range(data_range_text: str) -> str:
    """
    从 meta.dataRange 文本中抽取起止日期，返回 'YYYY-MM-DD_YYYY-MM-DD' 形式的 key。
    例如：'数据时间范围：2025-11-01 至 2026-01-31' → '2025-11-01_2026-01-31'
    """
    if not data_range_text:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"unknown_{ts}"

    # 尝试匹配两个日期
    m = re.findall(r"(20\\d{2}-\\d{2}-\\d{2})", data_range_text)
    if len(m) >= 2:
        return f"{m[0]}_{m[1]}"

    # 兜底：用非空文本做一个安全 key
    safe = re.sub(r"\\s+", "_", data_range_text.strip())
    safe = re.sub(r"[^0-9A-Za-z_\\-]", "", safe)
    return safe or f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def load_report_meta(report_path: str) -> Dict[str, Any]:
    """读取单个 report.json 的 meta 字段。"""
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta", {}) if isinstance(data, dict) else {}
    return {
        "restaurant": meta.get("restaurant"),
        "dataRange": meta.get("dataRange", ""),
        "rangeKey": meta.get("rangeKey"),
        "wideFile": meta.get("wideFile"),
        "reportFile": meta.get("reportFile"),
    }


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def run_multi_restaurant(script_dir: str) -> None:
    """
    多门店调度模式：
    - data/<门店>/ 为输入目录，每个门店目录中放置原始 Excel 源数据；
    - 在每个门店目录下调用 main_analysis_v2_backup.py 一次；
    - 将生成的宽表 / 分析 Excel / report.json 归档到 output/<门店>/<起止>/；
    - 生成 output/index.json。
    """
    data_root = os.path.join(script_dir, "data")
    if not os.path.isdir(data_root):
        # 没有 data/，回退到旧模式
        run_single_legacy(script_dir)
        return

    backup_script = os.path.join(script_dir, "main_analysis_v2_backup.py")
    if not os.path.exists(backup_script):
        raise FileNotFoundError(f"未找到分析脚本：{backup_script}")

    # 用字典先聚合，再在最后转成列表输出
    restaurants: Dict[str, Dict[str, Any]] = {}
    output_root = os.path.join(script_dir, "output")
    ensure_dir(output_root)

    # 遍历 data/ 下的门店子目录
    restaurant_dirs = [
        d
        for d in os.listdir(data_root)
        if os.path.isdir(os.path.join(data_root, d)) and not d.startswith(".")
    ]

    if not restaurant_dirs:
        print("⚠️ data/ 目录中未发现任何门店子目录，回退到单门店旧模式。")
        run_single_legacy(script_dir)
        return

    print(f"🔍 检测到 {len(restaurant_dirs)} 个门店目录：{', '.join(restaurant_dirs)}")

    for rest_name in restaurant_dirs:
        rest_input_dir = os.path.join(data_root, rest_name)
        print(f"🚀 开始处理门店：{rest_name}  (目录: {rest_input_dir})")

        # 在门店目录下运行原始分析脚本（作为独立进程），以便直接复用现有逻辑
        try:
            subprocess.run(
                [sys.executable, backup_script],
                cwd=rest_input_dir,
                check=True,
                env={**os.environ, "BATCH_MODE": "1"},
            )
        except subprocess.CalledProcessError as e:
            print(f"❌ 门店 {rest_name} 分析脚本执行失败，已跳过。错误：{e}")
            # 不直接 continue：允许复用该门店已有的 output 周期，仍然生成完整 index

        # 分析脚本会将宽表/分析表/report.json 写入 output/<门店>/<数据段>/。
        # 业务端需要“历史多个周期都可下拉查看”，所以这里要收录该门店 output 下的所有周期。
        target_base = os.path.join(output_root, rest_name)
        if not os.path.isdir(target_base):
            print(f"⚠️ 门店 {rest_name} 未生成 output 子目录，已跳过。")
            continue

        # 收集该门店所有周期 report.json
        subdirs = [
            d
            for d in os.listdir(target_base)
            if os.path.isdir(os.path.join(target_base, d))
        ]
        if not subdirs:
            print(f"⚠️ 门店 {rest_name} 的 output 下无数据周期目录，已跳过。")
            continue

        restaurant_entry = restaurants.get(rest_name)
        if restaurant_entry is None:
            restaurant_entry = {"id": rest_name, "name": rest_name, "periods": []}
            restaurants[rest_name] = restaurant_entry

        period_by_key: Dict[str, Dict[str, Any]] = {}
        for subdir in subdirs:
            target_dir = os.path.join(target_base, subdir)
            report_json_path = os.path.join(target_dir, "report.json")
            if not os.path.exists(report_json_path):
                continue

            meta = load_report_meta(report_json_path)
            data_range_text = meta.get("dataRange", "")
            range_key = meta.get("rangeKey") or parse_date_range(data_range_text)

            wide_file_name = meta.get("wideFile") or ""
            analysis_file_name = meta.get("reportFile") or ""

            # 用文件 mtime 做排序依据（新周期更靠前）
            period_entry: Dict[str, Any] = {
                "rangeKey": range_key,
                "dataRange": data_range_text,
                "reportPath": os.path.relpath(report_json_path, script_dir),
                "wideFile": wide_file_name,
                "reportFile": analysis_file_name,
                "__mtime": os.path.getmtime(report_json_path),
            }
            period_by_key[range_key] = period_entry

        # 倒序：越新的周期越靠前
        periods_sorted = sorted(period_by_key.values(), key=lambda x: x["__mtime"], reverse=True)
        for p in periods_sorted:
            p.pop("__mtime", None)
        restaurant_entry["periods"] = periods_sorted

        if restaurant_entry["periods"]:
            newest = restaurant_entry["periods"][0]
            print(f"✅ 门店 {rest_name} 已收录 {len(restaurant_entry['periods'])} 个周期，最新：{newest.get('dataRange','未知')}")
        else:
            print(f"⚠️ 门店 {rest_name} 未找到可用 report.json 周期，已跳过周期索引。")

    # 生成 output/index.json 供前端使用
    index_path = os.path.join(output_root, "index.json")
    index_payload: Dict[str, Any] = {
        "generatedAt": datetime.now().isoformat(),
        "restaurants": list(restaurants.values()),
    }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_payload, f, ensure_ascii=False, indent=2)

    print(f"📁 多门店索引已生成：{index_path}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    run_multi_restaurant(base_dir)

