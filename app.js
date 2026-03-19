/**
 * 餐饮门店经营仪表板 - 前端逻辑
 * 只读取 report.json，不修改后端脚本和 Excel 结构。
 */

(function () {
  var rawData = null;

  function $(id) { return document.getElementById(id); }

  function showToast(msg) {
    var t = $('toast');
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    setTimeout(function () { t.hidden = true; }, 2500);
  }

  function escapeHtml(s) {
    if (s == null) return '';
    var div = document.createElement('div');
    div.textContent = String(s);
    return div.innerHTML;
  }

  function findSection(id) {
    var sections = rawData && rawData.sections ? rawData.sections : [];
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].id === id) return sections[i];
    }
    return null;
  }

  function findTable(section, namePart) {
    if (!section || !section.tables) return null;
    for (var i = 0; i < section.tables.length; i++) {
      var t = section.tables[i];
      if (t.name && t.name.indexOf(namePart) >= 0) return t;
    }
    return section.tables[0] || null;
  }

  function renderTable(containerId, table) {
    var c = $(containerId);
    if (!c || !table || !table.columns) return;
    var html = '<div class="table-wrap"><table class="table"><thead><tr>';
    for (var i = 0; i < table.columns.length; i++) {
      html += '<th>' + escapeHtml(table.columns[i]) + '</th>';
    }
    html += '</tr></thead><tbody>';
    var rows = table.rows || [];
    for (var r = 0; r < rows.length; r++) {
      html += '<tr>';
      var row = rows[r];
      for (var j = 0; j < row.length; j++) {
        html += '<td>' + escapeHtml(row[j]) + '</td>';
      }
      html += '</tr>';
    }
    html += '</tbody></table></div>';
    c.innerHTML = html;
  }

  function bindToggleButtons() {
    var buttons = document.querySelectorAll('[data-toggle]');
    for (var i = 0; i < buttons.length; i++) {
      (function (btn) {
        btn.addEventListener('click', function () {
          var id = btn.getAttribute('data-toggle');
          var sec = $(id);
          if (!sec) return;
          var hidden = sec.hasAttribute('hidden');
          if (hidden) sec.removeAttribute('hidden'); else sec.setAttribute('hidden', '');
        });
      })(buttons[i]);
    }
  }

  function renderInsightHero() {
    var body = $('insight-body');
    var metaEl = $('insight-report-file');
    if (!rawData || !body) return;
    var summary = (rawData.overview && rawData.overview.summary) || [];
    var html = '<p>本期关键结论：</p>';
    if (summary.length) {
      html += '<ul>';
      for (var i = 0; i < summary.length; i++) {
        html += '<li>' + escapeHtml(summary[i]) + '</li>';
      }
      html += '</ul>';
    }
    body.innerHTML = html;
    if (metaEl && rawData.meta && rawData.meta.reportFile) {
      metaEl.textContent = '数据源：' + rawData.meta.reportFile;
    }
  }

  function initFilters() {
    var meta = rawData && rawData.meta ? rawData.meta : {};
    var dr = meta.dataRange;
    var startInput = $('date-start');
    var endInput = $('date-end');
    var text = $('data-range-text');
    if (dr && startInput && endInput && text) {
      var m = dr.match(/(\d{4}-\d{2}-\d{2}).*(\d{4}-\d{2}-\d{2})/);
      if (m) {
        startInput.value = m[1];
        endInput.value = m[2];
        text.textContent = dr + '（当前版本基于全期数据展示）';
      }
    }
    var btn = $('apply-filter');
    if (btn) {
      btn.addEventListener('click', function () {
        showToast('当前版本基于全期数据展示，日期筛选暂不重新计算。');
      });
    }
  }

  // 核心 KPI
  function renderKpi() {
    var row = $('kpi-row');
    if (!row) return;
    var cards = [];
    var overview = rawData.overview || {};
    var sec = findSection('1_sales');
    var kpiTable = findTable(sec, '核心指标矩阵');

    function fromKpi(labelPart) {
      if (!kpiTable) return null;
      var rows = kpiTable.rows || [];
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        if (String(r[0]).indexOf(labelPart) >= 0) return r;
      }
      return null;
    }

    var totalSales = fromKpi('总销售额');
    var totalOrders = fromKpi('总客流量');
    var aov = fromKpi('平均客单价');
    var people = fromKpi('总用餐人数');
    var daily = fromKpi('日均销售额');
    var lostRatio = null;
    if (overview.summary && overview.summary.length > 1) {
      var m2 = overview.summary[1].match(/(\d+\.\d+)%/);
      if (m2) lostRatio = m2[1] + '%';
    }

    function numFormat(n, digits) {
      var x = Number(n);
      if (isNaN(x)) return '-';
      var fixed = typeof digits === 'number' ? x.toFixed(digits) : String(Math.round(x));
      return fixed.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    cards.push({ label: '总销售额', value: totalSales ? numFormat(totalSales[1], 0) : '-', unit: '元' });
    cards.push({ label: '已结账订单数', value: totalOrders ? numFormat(totalOrders[1], 0) : '-', unit: '单' });
    cards.push({ label: '平均客单价', value: aov ? Number(aov[1]).toFixed(1) : '-', unit: '元' });
    cards.push({ label: '总用餐人数', value: people ? numFormat(people[1], 0) : '-', unit: '人' });
    cards.push({ label: '流失订单占比', value: lostRatio || '-', unit: '' });
    cards.push({ label: '日均销售额', value: daily ? numFormat(daily[1], 0) : '-', unit: '元' });

    var html = '';
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      html += '<div class="kpi-card">';
      html += '<div class="kpi-label">' + escapeHtml(c.label) + '</div>';
      html += '<div class="kpi-value">' + escapeHtml(c.value);
      if (c.unit) html += '<span class="kpi-unit"> ' + escapeHtml(c.unit) + '</span>';
      html += '</div></div>';
    }
    row.innerHTML = html;
  }

  // 销售趋势
  function renderSales() {
    var sec = findSection('1_sales');
    var conclEl = $('sales-conclusion');
    if (sec && sec.conclusions && conclEl) {
      var html = '';
      for (var i = 0; i < sec.conclusions.length; i++) {
        html += '<p>' + escapeHtml(sec.conclusions[i]) + '</p>';
      }
      conclEl.innerHTML = html;
    }
    renderTable('sales-kpi-table', findTable(sec, '核心指标'));
    var monthTable = findTable(sec, '月度趋势');
    var weekTable = findTable(sec, '周度趋势');
    renderTable('sales-month-table', monthTable);
    renderTable('sales-week-table', weekTable);

    if (window.echarts && monthTable) {
      var dom = $('chart-sales-month');
      if (dom) {
        var chart = echarts.init(dom);
        var rows = monthTable.rows || [];
        var months = [];
        var sales = [];
        var orders = [];
        for (var i = 0; i < rows.length; i++) {
          months.push(rows[i][0]);
          sales.push(Number(rows[i][1]));
          orders.push(Number(rows[i][2]));
        }
        chart.setOption({
          tooltip: { trigger: 'axis' },
          legend: { data: ['销售额', '订单数'] },
          grid: { left: 40, right: 50, top: 30, bottom: 30 },
          xAxis: { type: 'category', data: months },
          yAxis: [
            { type: 'value', name: '销售额' },
            { type: 'value', name: '订单数', position: 'right' }
          ],
          series: [
            { name: '销售额', type: 'line', smooth: true, areaStyle: { opacity: 0.15 }, data: sales },
            { name: '订单数', type: 'line', smooth: true, lineStyle: { type: 'dashed' }, yAxisIndex: 1, data: orders }
          ]
        });
      }
    }

    if (window.echarts && weekTable) {
      var dom2 = $('chart-sales-week');
      if (dom2) {
        var chart2 = echarts.init(dom2);
        var rows2 = weekTable.rows || [];
        var weeks = [];
        var salesW = [];
        for (var j = 0; j < rows2.length; j++) {
          weeks.push(rows2[j][0]);
          salesW.push(Number(rows2[j][1]));
        }
        chart2.setOption({
          tooltip: { trigger: 'axis' },
          grid: { left: 40, right: 20, top: 30, bottom: 60 },
          xAxis: { type: 'category', data: weeks, axisLabel: { rotate: 45 } },
          yAxis: { type: 'value', name: '销售额' },
          series: [{ name: '销售额', type: 'bar', data: salesW, itemStyle: { color: '#4f46e5' } }]
        });
      }
    }
  }

  // 时段交叉
  function renderTime() {
    var sec = findSection('2_time');
    var pivot = findTable(sec, '星期×时段');
    renderTable('time-table', pivot);
    if (window.echarts && pivot) {
      var dom = $('chart-time-heat');
      if (dom) {
        var chart = echarts.init(dom);
        var rows = pivot.rows || [];
        var days = [];
        var parts = [];
        var values = [];
        for (var i = 0; i < rows.length; i++) {
          var d = rows[i][0];
          var p = rows[i][1];
          var v = Number(rows[i][2]);
          if (days.indexOf(d) < 0) days.push(d);
          if (parts.indexOf(p) < 0) parts.push(p);
          values.push([parts.indexOf(p), days.indexOf(d), v]);
        }
        var max = 0;
        for (var k = 0; k < values.length; k++) if (values[k][2] > max) max = values[k][2];
        chart.setOption({
          tooltip: {
            formatter: function (p) {
              var v = p.data;
              return days[v[1]] + ' ' + parts[v[0]] + '<br/>销售额：' + v[2].toFixed(0);
            }
          },
          grid: { left: 60, right: 20, top: 20, bottom: 40 },
          xAxis: { type: 'category', data: parts },
          yAxis: { type: 'category', data: days },
          visualMap: { min: 0, max: max, calculable: false, orient: 'horizontal', left: 'center', bottom: 0 },
          series: [{ type: 'heatmap', data: values }]
        });
      }
    }
    var topSec = $('time-top-bottom');
    var tb = findTable(sec, '最忙Top3');
    if (topSec && tb) {
      var rows2 = tb.rows || [];
      var busy = [];
      var cold = [];
      for (var i2 = 0; i2 < rows2.length; i2++) {
        if (String(rows2[i2][5]).indexOf('最忙') >= 0) busy.push(rows2[i2]);
        else if (String(rows2[i2][5]).indexOf('冷清') >= 0) cold.push(rows2[i2]);
      }
      var html = '';
      var maxBusy = 0;
      for (var b = 0; b < busy.length; b++) if (busy[b][2] > maxBusy) maxBusy = busy[b][2];
      html += '<div class="card"><div class="card-header">最忙 Top3</div><div class="card-body"><ul class="rank-list">';
      for (var bi = 0; bi < busy.length; bi++) {
        var pct = maxBusy > 0 ? (busy[bi][2] / maxBusy) * 100 : 0;
        html += '<li class="rank-item"><span class="rank-index">' + (bi + 1) + '</span><span class="rank-name">' + escapeHtml(busy[bi][0] + ' ' + busy[bi][1]) + '</span><span class="rank-value">' + escapeHtml(Number(busy[bi][2]).toFixed(0)) + '</span><div class="progress"><div class="progress-inner" style="width:' + pct + '%"></div></div></li>';
      }
      html += '</ul></div></div>';
      var maxCold = 0;
      for (var c = 0; c < cold.length; c++) if (cold[c][2] > maxCold) maxCold = cold[c][2];
      html += '<div class="card"><div class="card-header">冷清 Bottom3</div><div class="card-body"><ul class="rank-list">';
      for (var ci = 0; ci < cold.length; ci++) {
        var pct2 = maxCold > 0 ? (cold[ci][2] / maxCold) * 100 : 0;
        html += '<li class="rank-item"><span class="rank-index">' + (ci + 1) + '</span><span class="rank-name">' + escapeHtml(cold[ci][0] + ' ' + cold[ci][1]) + '</span><span class="rank-value">' + escapeHtml(Number(cold[ci][2]).toFixed(0)) + '</span><div class="progress"><div class="progress-inner" style="width:' + pct2 + '%"></div></div></li>';
      }
      html += '</ul></div></div>';
      topSec.innerHTML = html;
    }
  }

  // 用户分层
  function renderUser() {
    var sec = findSection('4_user');
    var summary = findTable(sec, '用户分层汇总');
    var segCards = $('user-seg-cards');
    if (summary && segCards) {
      var rows = summary.rows || [];
      var html = '';
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        html += '<div class="kpi-card">';
        html += '<div class="kpi-label">' + escapeHtml(r[0]) + '</div>';
        html += '<div class="kpi-value">' + escapeHtml(r[1]) + '<span class="kpi-unit"> 人</span></div>';
        html += '<div class="kpi-label">人均消费 ' + escapeHtml(r[2]) + ' 元 · 频次 ' + escapeHtml(r[3]) + ' 次 · R 天 ' + escapeHtml(r[4]) + '</div>';
        html += '</div>';
      }
      segCards.innerHTML = html;
    }
    renderTable('user-summary-table', summary);
    var detail = findTable(sec, '分层用户明细');
    if (detail) renderTable('user-detail-table', detail);

    // donut 图：用户分层占比
    if (window.echarts && summary) {
      var domPie = $('chart-user-seg');
      if (domPie) {
        var chartPie = echarts.init(domPie);
        var rowsP = summary.rows || [];
        var dataPie = [];
        for (var pi = 0; pi < rowsP.length; pi++) {
          dataPie.push({ name: rowsP[pi][0], value: Number(rowsP[pi][1] || 0) });
        }
        chartPie.setOption({
          tooltip: { trigger: 'item' },
          legend: { orient: 'vertical', left: 'left' },
          series: [{ type: 'pie', radius: ['50%', '75%'], data: dataPie }]
        });
      }
    }

    var timeTable = findTable(sec, '各层级时段分布');
    if (window.echarts && timeTable) {
      var dom = $('chart-user-time');
      if (dom) {
        var chart = echarts.init(dom);
        var rows2 = timeTable.rows || [];
        var segs = [];
        var cols = timeTable.columns.slice(1);
        for (var i2 = 0; i2 < rows2.length; i2++) segs.push(rows2[i2][0]);
        var series = [];
        for (var ci = 0; ci < cols.length; ci++) {
          var dataArr = [];
          for (var ri = 0; ri < rows2.length; ri++) dataArr.push(Number(rows2[ri][ci + 1] || 0));
          series.push({ name: cols[ci], type: 'bar', stack: 'time', data: dataArr });
        }
        chart.setOption({
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          legend: { data: cols },
          grid: { left: 40, right: 20, top: 30, bottom: 30 },
          xAxis: { type: 'category', data: segs },
          yAxis: { type: 'value' },
          series: series
        });
      }
    }

    var discTable = findTable(sec, '各层级优惠响应');
    if (window.echarts && discTable) {
      var dom2 = $('chart-user-discount');
      if (dom2) {
        var chart2 = echarts.init(dom2);
        var rows3 = discTable.rows || [];
        var segs2 = [];
        var discOrders = [];
        var discAmt = [];
        for (var i3 = 0; i3 < rows3.length; i3++) {
          segs2.push(rows3[i3][0]);
          discOrders.push(Number(rows3[i3][1] || 0));
          discAmt.push(Number(rows3[i3][2] || 0));
        }
        chart2.setOption({
          tooltip: { trigger: 'axis' },
          legend: { data: ['优惠订单数', '优惠金额'] },
          grid: { left: 40, right: 40, top: 30, bottom: 30 },
          xAxis: { type: 'category', data: segs2 },
          yAxis: [
            { type: 'value', name: '订单数' },
            { type: 'value', name: '金额', position: 'right' }
          ],
          series: [
            { name: '优惠订单数', type: 'bar', data: discOrders },
            { name: '优惠金额', type: 'line', yAxisIndex: 1, data: discAmt }
          ]
        });
      }
    }
  }

  // 菜品
  function renderDish() {
    var sec = findSection('6_dish');
    var sum = findTable(sec, '菜品汇总');
    var risk = findTable(sec, '风险菜品');
    var topEl = $('dish-top-list');
    var riskEl = $('dish-risk-list');
    if (sum && topEl) {
      var rows = (sum.rows || []).slice(0, 10);
      var html = '<ul class="rank-list">';
      for (var i = 0; i < rows.length; i++) {
        html += '<li class="rank-item"><span class="rank-index">' + (i + 1) + '</span><span class="rank-name">' + escapeHtml(rows[i][0]) + '</span><span class="rank-value">' + escapeHtml(rows[i][2]) + '</span></li>';
      }
      html += '</ul>';
      topEl.innerHTML = html;
    }
    if (risk && riskEl) {
      var rowsR = (risk.rows || []).slice(0, 10);
      var rateCol = risk.columns ? risk.columns.indexOf('退菜率') : -1;
      var html2 = '<ul class="rank-list">';
      for (var j = 0; j < rowsR.length; j++) {
        var rate = rateCol >= 0 ? rowsR[j][rateCol] : '';
        html2 += '<li class="rank-item"><span class="rank-index">' + (j + 1) + '</span><span class="rank-name">' + escapeHtml(rowsR[j][0]) + '</span><span class="rank-value">退菜率 ' + escapeHtml(rate) + '</span></li>';
      }
      html2 += '</ul>';
      riskEl.innerHTML = html2;
    }
    renderTable('dish-summary-table', sum);
    renderTable('dish-risk-table', risk);
  }

  // 员工
  function renderStaff() {
    var sec = findSection('5_staff');
    var t = findTable(sec, '员工汇总');
    renderTable('staff-table', t);
    if (window.echarts && t) {
      var dom = $('chart-staff-sales');
      if (dom) {
        var chart = echarts.init(dom);
        var rows = t.rows || [];
        var names = [];
        var sales = [];
        for (var i = 0; i < rows.length; i++) {
          names.push(rows[i][0]);
          sales.push(Number(rows[i][1] || 0));
        }
        chart.setOption({
          tooltip: { trigger: 'axis' },
          grid: { left: 40, right: 20, top: 30, bottom: 80 },
          xAxis: { type: 'category', data: names, axisLabel: { rotate: 60 } },
          yAxis: { type: 'value', name: '销售额' },
          series: [{ type: 'bar', data: sales, itemStyle: { color: '#4f46e5' } }]
        });
      }
    }
  }

  // 优惠
  function renderDiscount() {
    var sec = findSection('7_discount');
    var overall = findTable(sec, '总体优惠占比');
    var typeTable = findTable(sec, '优惠类型金额');
    var kpiEl = $('discount-kpi');
    if (overall && kpiEl) {
      var rows = overall.rows || [];
      var html = '<div class="kpi-row">';
      for (var i = 0; i < rows.length; i++) {
        html += '<div class="kpi-card"><div class="kpi-label">' + escapeHtml(rows[i][0]) + '</div><div class="kpi-value">' + escapeHtml(rows[i][1]);
        if (rows[i][2]) html += '<span class="kpi-unit"> ' + escapeHtml(rows[i][2]) + '</span>';
        html += '</div></div>';
      }
      html += '</div>';
      kpiEl.innerHTML = html;
    }
    if (window.echarts && typeTable) {
      var dom = $('chart-discount-type');
      if (dom) {
        var chart = echarts.init(dom);
        var rows2 = typeTable.rows || [];
        var data = [];
        for (var j = 0; j < rows2.length; j++) {
          data.push({ name: rows2[j][0], value: Number(rows2[j][1] || 0) });
        }
        chart.setOption({
          tooltip: { trigger: 'item' },
          legend: { orient: 'vertical', left: 'left' },
          series: [{ type: 'pie', radius: ['40%', '70%'], data: data }]
        });
      }
    }
    renderTable('discount-reason-table', findTable(sec, '折扣原因分布'));
    renderTable('discount-type-reason-table', findTable(sec, '优惠类型+折扣原因'));
  }

  // 流失订单
  function renderLost() {
    var sec = findSection('8_lost');
    var monthTable = findTable(sec, '流失订单按月');
    var weekTable = findTable(sec, '流失订单按周');
    var remarkTable = findTable(sec, '备注高频词');
    if (weekTable) renderTable('lost-week-table', weekTable);
    if (remarkTable) {
      var el = $('lost-remark-tags');
      if (el) {
        var rows = remarkTable.rows || [];
        var html = '<div class="tag-list">';
        for (var i = 0; i < rows.length; i++) {
          html += '<span class="tag">' + escapeHtml(rows[i][0]) + ' ×' + escapeHtml(rows[i][1]) + '</span>';
        }
        html += '</div>';
        el.innerHTML = html;
      }
    }
    if (window.echarts && monthTable) {
      var dom = $('chart-lost-month');
      if (dom) {
        var chart = echarts.init(dom);
        var rows2 = monthTable.rows || [];
        var xs = [];
        var ys = [];
        for (var j = 0; j < rows2.length; j++) {
          xs.push(rows2[j][0]);
          ys.push(Number(rows2[j][1] || 0));
        }
        chart.setOption({
          tooltip: { trigger: 'axis' },
          grid: { left: 40, right: 20, top: 30, bottom: 40 },
          xAxis: { type: 'category', data: xs },
          yAxis: { type: 'value', name: '订单数' },
          series: [{ type: 'bar', data: ys, itemStyle: { color: '#4f46e5' } }]
        });
      }
    }
  }

  function initAll() {
    if (!rawData) return;
    renderInsightHero();
    initFilters();
    renderKpi();
    renderSales();
    renderTime();
    renderUser();
    renderDish();
    renderStaff();
    renderDiscount();
    renderLost();
    bindToggleButtons();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var loading = document.querySelector('.loading');
    var errorBox = document.querySelector('.error');
    if (loading) loading.style.display = 'flex';
    if (errorBox) errorBox.style.display = 'none';
    fetch('report.json')
      .then(function (res) { return res.json(); })
      .then(function (d) {
        rawData = d;
        if (loading) loading.style.display = 'none';
        initAll();
      })
      .catch(function (e) {
        if (loading) loading.style.display = 'none';
        if (errorBox) {
          errorBox.style.display = 'block';
          errorBox.textContent = '加载 report.json 失败：' + (e && e.message ? e.message : String(e));
        }
      });
  });
})();
