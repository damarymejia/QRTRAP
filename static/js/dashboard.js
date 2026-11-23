(() => {
  'use strict';
  const csrf = document.querySelector('meta[name="csrf"]').content;
  const $ = (s, r = document) => r.querySelector(s);
  const fmt = n => new Intl.NumberFormat('es-HN').format(n);
  const charts = {};
  let range = 'hour', last = null;

  const COLORS = {curiosidad:'#4f7cff', utilidad:'#ff6b3d', urgencia:'#8a3ffc', informativa:'#12b5a0'};
  const QCOL = {
    q1: ['#4f7cff', '#ffb020', '#12b5a0', '#98a2b3'],
    q2: ['#12b5a0', '#ffb020', '#f0506e'],
    q3: ['#12b5a0', '#f0506e', '#98a2b3'],
    q4: ['#12b5a0', '#ffb020', '#f0506e'],
  };
  const TIPO = {scan: 'Escaneo', read: 'Lectura', response: 'Respuesta'};

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = '#6b7488';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;

  function upsert(id, config) {
    if (charts[id]) {
      charts[id].data = config.data;
      if (config.options) charts[id].options = config.options;
      charts[id].update();
    } else {
      charts[id] = new Chart(document.getElementById(id), config);
    }
  }

  const grid = {color: '#eef1f8', drawBorder: false};
  const intTicks = {precision: 0};

  function render(s) {
    last = s;
    $('#updated').textContent = 'actualizado a las ' + s.updated;
    $('#demo-banner').hidden = s.demo_count === 0;
    $('#btn-clear').hidden = s.demo_count === 0;
    $('#btn-seed').hidden = s.demo_count > 0;

    // KPI por estrategia
    s.variants.forEach(v => {
      const card = $(`.kpi[data-slug="${v.slug}"]`);
      card.querySelector('[data-f=scan]').textContent = fmt(v.scan);
      card.querySelector('[data-f=read]').textContent = fmt(v.read);
      card.querySelector('[data-f=response]').textContent = fmt(v.response);
      card.querySelector('[data-f=resp_rate]').textContent = v.resp_rate + '% resp.';
    });

    // Tiles
    const t = {scan: fmt(s.totals.scan), read_rate: s.read_rate + '%', resp_rate: s.resp_rate + '%',
               verified_pct: s.verified_pct + '%', changed_pct: s.changed_pct + '%'};
    Object.entries(t).forEach(([k, v]) => { $(`[data-t=${k}]`).textContent = v; });

    // Barras: total por estrategia
    const labels = s.variants.map(v => v.nombre);
    upsert('c-total', {
      type: 'bar',
      data: {labels, datasets: [
        {label: 'Escaneos', data: s.variants.map(v => v.scan), backgroundColor: '#2f4bd6', borderRadius: 5},
        {label: 'Lecturas', data: s.variants.map(v => v.read), backgroundColor: '#7a93ff', borderRadius: 5},
        {label: 'Respuestas', data: s.variants.map(v => v.response), backgroundColor: '#c3cffd', borderRadius: 5},
      ]},
      options: {responsive: true, maintainAspectRatio: false, interaction: {mode: 'index', intersect: false},
        plugins: {legend: {position: 'bottom'}},
        scales: {x: {grid: {display: false}, ticks: {maxRotation: 0, callback(v) {
                    const l = this.getLabelForValue(v); return l.length > 12 ? l.split(' ') : l; }}},
                 y: {beginAtZero: true, grid, ticks: intTicks}}},
    });

    // Línea del tiempo
    const tl = s.timeline[range];
    upsert('c-line', {
      type: 'line',
      data: {labels: tl.labels, datasets: s.variants.map(v => ({
        label: v.nombre, data: tl.series[v.slug], borderColor: COLORS[v.slug], backgroundColor: COLORS[v.slug],
        cubicInterpolationMode: 'monotone', tension: .35, borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 5,
      }))},
      options: {responsive: true, maintainAspectRatio: false, interaction: {mode: 'index', intersect: false},
        plugins: {legend: {position: 'bottom'}},
        scales: {x: {grid: {display: false}, ticks: {maxTicksLimit: range === 'hour' ? 8 : 7}},
                 y: {beginAtZero: true, grid, ticks: intTicks}}},
    });

    // Dona: motivación (Q1 total)
    const q1 = s.questions[0];
    const vals = q1.opciones.map(o => q1.total[o.key]);
    const n = vals.reduce((a, b) => a + b, 0);
    $('#donut-n').textContent = fmt(n);
    upsert('c-donut', {
      type: 'doughnut',
      data: {labels: q1.opciones.map(o => o.label), datasets: [{
        data: n ? vals : [1], backgroundColor: n ? QCOL.q1 : ['#e6eaf3'], borderWidth: 3, borderColor: '#fff', hoverOffset: 4}]},
      options: {responsive: true, maintainAspectRatio: false, cutout: '72%', plugins: {legend: {display: false}, tooltip: {enabled: n > 0}}},
    });
    $('#donut-legend').innerHTML = q1.opciones.map(o => `<li><i></i>${o.label}<b>${q1.total[o.key]}</b></li>`).join('');
    document.querySelectorAll('#donut-legend i').forEach((el, i) => { el.style.background = QCOL.q1[i]; });  // CSSOM: permitido por la CSP

    // Tabla
    const body = $('#tbl-body');
    if (!s.recent.length) {
      body.innerHTML = '<tr><td colspan="4" class="empty">Aún no hay eventos. Escanea un código o carga los datos de demostración.</td></tr>';
    } else {
      body.innerHTML = s.recent.map(e => `<tr>
        <td><span class="chip v-${e.variant}"><i></i>${e.nombre}</span></td>
        <td><span class="badge ${e.type}">${e.tipo}</span></td>
        <td>${e.fecha}</td><td class="mono">#${e.visit}</td></tr>`).join('');
    }

    // Ranking de conversión
    const rk = [...s.variants].sort((a, b) => b.resp_rate - a.resp_rate);
    const max = Math.max(...rk.map(v => v.resp_rate), 1);
    $('#rank').innerHTML = rk.map(v => `<li class="v-${v.slug}">
      <div class="r-top"><span class="chip v-${v.slug}"><i></i>${v.nombre}</span><b>${v.resp_rate}%</b></div>
      <div class="bar"><i data-w="${(v.resp_rate / max * 100).toFixed(1)}"></i></div>
      <div class="r-sub">${v.response} de ${v.scan} escaneos respondieron · ${v.read_rate}% leyó la explicación</div></li>`).join('');
    requestAnimationFrame(() => document.querySelectorAll('#rank .bar i').forEach(i => { i.style.width = i.dataset.w + '%'; }));

    // Preguntas por estrategia (barras 100% apiladas)
    s.questions.forEach(q => {
      const keys = q.opciones.map(o => o.key);
      upsert('c-' + q.id, {
        type: 'bar',
        data: {labels: s.variants.map(v => v.nombre), datasets: q.opciones.map((o, i) => ({
          label: o.label, backgroundColor: QCOL[q.id][i],
          data: s.variants.map(v => {
            const row = q.por_variante[v.slug]; const tot = keys.reduce((a, k) => a + row[k], 0);
            return tot ? +(100 * row[o.key] / tot).toFixed(1) : 0;
          }),
          counts: s.variants.map(v => q.por_variante[v.slug][o.key]),
        }))},
        options: {indexAxis: 'y', responsive: true, maintainAspectRatio: false,
          plugins: {legend: {position: 'bottom', labels: {boxWidth: 8, font: {size: 11}}},
            tooltip: {callbacks: {label: c => ` ${c.dataset.label}: ${c.dataset.counts[c.dataIndex]} (${c.parsed.x}%)`}}},
          scales: {x: {stacked: true, max: 100, grid, ticks: {callback: v => v + '%', maxTicksLimit: 5}},
                   y: {stacked: true, grid: {display: false}, ticks: {callback(v) {
                      const l = this.getLabelForValue(v); return l.length > 11 ? l.split(' ')[0] : l; }}}}},
      });
    });
  }

  async function load() {
    try {
      const r = await fetch('/admin/api/stats', {credentials: 'same-origin'});
      if (r.status === 401 || r.redirected) { location.href = '/admin/login'; return; }
      render(await r.json());
    } catch (e) { $('#updated').textContent = 'sin conexión con el servidor'; }
  }

  async function post(url) {
    await fetch(url, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRF-Token': csrf}});
    load();
  }

  $('#btn-refresh').addEventListener('click', load);
  $('#btn-seed').addEventListener('click', () => post('/admin/demo/seed'));
  $('#btn-clear').addEventListener('click', () => {
    if (confirm('¿Borrar todos los datos de demostración? Los datos reales no se tocan.')) post('/admin/demo/clear');
  });
  $('#seg-range').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    range = b.dataset.r;
    document.querySelectorAll('#seg-range button').forEach(x => x.classList.toggle('on', x === b));
    if (last) render(last);
  });

  load();
  setInterval(() => { if (!document.hidden) load(); }, 30000);
})();
