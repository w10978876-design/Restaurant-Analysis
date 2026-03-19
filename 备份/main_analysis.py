#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
餐饮数据分析入口：直接调用 main_analysis_v2_backup 执行完整分析。
使用：python main_analysis.py  或  python3 main_analysis.py
"""
import runpy
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
backup_script = os.path.join(script_dir, "main_analysis_v2_backup.py")
if not os.path.exists(backup_script):
    raise FileNotFoundError(f"未找到分析脚本：{backup_script}")

runpy.run_path(backup_script, run_name="__main__")
