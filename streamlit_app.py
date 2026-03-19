#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
INDEX_JSON = OUTPUT_DIR / "index.json"
DIST_DIR = ROOT / "dashboard" / "dist"


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_fetch_override(index_payload: dict, report_by_path: dict) -> str:
    # 用 JS 拦截前端的 fetch('/output/index.json') 和 fetch('/output/.../report.json')
    # 直接返回 Streamlit 侧已加载的 JSON，避免需要在 Streamlit 里额外开静态路由。
    return f"""
<script>
(() => {{
  const INDEX = {json.dumps(index_payload, ensure_ascii=False)};
  const REPORTS = {json.dumps(report_by_path, ensure_ascii=False)};

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {{
    try {{
      const url = (typeof input === 'string') ? input : (input && input.url) ? input.url : '';
      const normalized = url.startsWith('http') ? (new URL(url)).pathname : url;

      if (normalized === '/output/index.json') {{
        return new Response(JSON.stringify(INDEX), {{
          status: 200,
          headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
        }});
      }}

      if (normalized.startsWith('/output/') && normalized.endsWith('/report.json')) {{
        const key = normalized.startsWith('/') ? normalized.slice(1) : normalized; // 'output/.../report.json'
        const payload = REPORTS[key];
        if (payload) {{
          return new Response(JSON.stringify(payload), {{
            status: 200,
            headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
          }});
        }}
        return new Response(JSON.stringify({{ error: 'report.json not found', path: key }}), {{
          status: 404,
          headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
        }});
      }}
    }} catch (e) {{
      // fallthrough
    }}
    return originalFetch(input, init);
  }};
}})();
</script>
"""


def _render_dashboard_from_dist(index_payload: dict) -> None:
    if not DIST_DIR.exists():
        st.error("未找到 `dashboard/dist/`。请先在本地构建前端：`cd dashboard && npm install && npm run build`。")
        st.stop()

    # dist/index.html 里是 /assets/*.js 和 /assets/*.css 的绝对路径；在 Streamlit 里改为内联。
    css_candidates = sorted((DIST_DIR / "assets").glob("*.css"))
    js_candidates = sorted((DIST_DIR / "assets").glob("*.js"))
    if not css_candidates or not js_candidates:
        st.error("`dashboard/dist/assets` 中未找到 .css 或 .js 文件，请确认前端已构建成功。")
        st.stop()

    css_text = "\n\n".join(_load_text(p) for p in css_candidates)
    js_text = "\n\n".join(_load_text(p) for p in js_candidates)

    # 预加载所有报告 JSON（让前端切换门店/周期时不依赖静态服务器）
    report_by_path: dict[str, dict] = {}
    for restaurant in index_payload.get("restaurants", []) or []:
        for period in restaurant.get("periods", []) or []:
            report_path = period.get("reportPath")
            if not report_path:
                continue
            report_file = ROOT / report_path
            if report_file.exists():
                report_by_path[report_path] = _load_json(report_file)

    html = f"""
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>餐饮数据化分析</title>
    <style>{css_text}</style>
  </head>
  <body>
    <div id="root"></div>
    {_build_fetch_override(index_payload=index_payload, report_by_path=report_by_path)}
    <script type="module">{js_text}</script>
  </body>
</html>
"""

    # Streamlit Cloud / 本地都用这个渲染，页面就是你原本的 dashboard 设计
    components.html(html, height=1200, scrolling=True)


st.set_page_config(page_title="餐饮数据化分析", layout="wide")

if not INDEX_JSON.exists():
    st.warning("未找到 `output/index.json`。请先运行：`python main_analysis.py` 生成输出。")
    st.stop()

index = _load_json(INDEX_JSON)
_render_dashboard_from_dist(index_payload=index)
