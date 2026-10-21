(async function(){
  "use strict";
  const DATA_URL = (document.currentScript && document.currentScript.dataset.json) || 'data/benchmark.json';
  if (typeof Chart === 'undefined') {
    console.error('Veyron backtest: Chart.js non disponibile, la dashboard interattiva resta disabilitata.');
    return;
  }
  try {
  const resp = await fetch(DATA_URL);
  if (!resp.ok) throw new Error('Dati non disponibili (' + resp.status + '). Serve un server web: da file:// il caricamento è bloccato.');
  const DATA = await resp.json();
  const SECTOR_COLORS = {'Alimentare':'#1F4E79','Metallurgia e Prodotti in Metallo':'#B7862B','Edilizia e Costruzioni':'#3C7D58','Packaging':'#4F8FA3','Trasporti e Logistica':'#A5483B','Turismo e Ristorazione':'#7B8696'};
  DATA.sectorColors = DATA.sectors.map((s,i) => SECTOR_COLORS[s] || (DATA.sectorColors||[])[i] || '#7B8696');

  const COLORS = {
    teal:'#12385B', gold:'#85600F', secure:'#2B7A43', rose:'#A33A2F',
    paper:'#16202B', paperDim:'#485160', paperFaint:'#697180', line:'rgba(22,32,43,0.12)'
  };

  Chart.defaults.color = COLORS.paperDim;
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 11.5;
  Chart.defaults.borderColor = COLORS.line;

  const METRICS = {};
  DATA.metrics.forEach(m => { METRICS[m.id] = m; });

  function fmtMetric(v, metricId){
    if (v === null || v === undefined || isNaN(v)) return 'n.d.';
    const m = METRICS[metricId];
    if (!m) return String(v);
    if (m.unita === '%') return v.toFixed(1) + '%';
    if (m.unita === 'volte') return v.toFixed(2) + '×';
    return v.toLocaleString('it-IT', { maximumFractionDigits: 0 }) + ' k€';
  }
  function avg(arr){ const v = (arr||[]).filter(x => x !== null && x !== undefined && !isNaN(x)); return v.length ? v.reduce((a,b)=>a+b,0)/v.length : null; }
  function lastValid(arr){
    for (let i = arr.length - 1; i >= 0; i--) { if (arr[i] !== null && arr[i] !== undefined) return arr[i]; }
    return null;
  }
  function hexToRgba(hex, a){
    const h = hex.replace('#','');
    const r = parseInt(h.substring(0,2),16), g = parseInt(h.substring(2,4),16), b = parseInt(h.substring(4,6),16);
    return `rgba(${r},${g},${b},${a})`;
  }

  const tooltipBase = {
    backgroundColor: '#16202B', borderColor: 'rgba(22,32,43,0.9)', borderWidth: 1,
    titleColor: '#F6F3EC', bodyColor: '#D5DBE3', padding: 10, boxPadding: 4,
    titleFont: { family: "'Fraunces', sans-serif", weight: '500' },
    bodyFont: { family: "'IBM Plex Mono', monospace", size: 11.5 }
  };

  const centerTextPlugin = {
    id: 'centerText',
    afterDraw(chart){
      const cfg = chart.config.options.plugins && chart.config.options.plugins.centerText;
      if (!cfg) return;
      const { ctx, chartArea: { width, height, left, top } } = chart;
      ctx.save();
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = COLORS.paper;
      ctx.font = "600 22px 'IBM Plex Mono', monospace";
      ctx.fillText(cfg.big, left + width/2, top + height/2 - 9);
      ctx.fillStyle = COLORS.paperDim;
      ctx.font = "11.5px 'Inter', sans-serif";
      ctx.fillText(cfg.small, left + width/2, top + height/2 + 14);
      ctx.restore();
    }
  };
  Chart.register(centerTextPlugin);

  // ==================== GRAFICI "REALE VS OBIETTIVO" (generici, per metrica) ==
  const charts = {};

  function metricChartOptions(metricId){
    return {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', align: 'start', labels: { usePointStyle: true, boxWidth: 8, padding: 14 } },
        tooltip: Object.assign({}, tooltipBase, { callbacks: { label: (c)=> `${c.dataset.label}: ${fmtMetric(c.parsed.y, metricId)}` } })
      },
      scales: {
        y: { ticks: { callback: (v)=> fmtMetric(v, metricId) }, grid: { color: COLORS.line } },
        x: { grid: { display: false } }
      }
    };
  }

  function buildMetricChart(canvasId, metricId, initialRec, obiettivoLabel){
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: DATA.tLabels,
        datasets: [
          { label: 'Reale', data: initialRec[metricId].reale, borderColor: COLORS.teal, backgroundColor: hexToRgba(COLORS.teal, 0.12), borderWidth: 3, pointRadius: 4, tension: 0.2, fill: false, spanGaps: true },
          { label: obiettivoLabel || 'Obiettivo (miglior quartile)', data: initialRec[metricId].obiettivo, borderColor: COLORS.gold, borderDash: [5,4], borderWidth: 1.8, pointRadius: 3, tension: 0.2, spanGaps: true }
        ]
      },
      options: metricChartOptions(metricId)
    });
  }

  function updateMetricChart(chart, metricId, rec){
    chart.data.datasets[0].data = rec[metricId].reale;
    chart.data.datasets[1].data = rec[metricId].obiettivo;
    chart.update();
  }

  charts.featuredEbitda = buildMetricChart('chartFeaturedEbitda', 'ebitda_margin', DATA.companies.__ALL__);
  charts.featuredRoe = buildMetricChart('chartFeaturedRoe', 'roe', DATA.companies.__ALL__);

  charts.detailEbitda = buildMetricChart('chartDetailEbitda', 'ebitda_margin', DATA.companies.__ALL__);
  charts.detailRoe = buildMetricChart('chartDetailRoe', 'roe', DATA.companies.__ALL__);
  charts.detailRotazione = buildMetricChart('chartDetailRotazione', 'rotazione_ci', DATA.companies.__ALL__);

  charts.costi = buildMetricChart('chartCosti', 'costi_operativi', DATA.companies.__ALL__, 'Ipotetico (al ritmo del miglior quartile)');
  charts.capitale = buildMetricChart('chartCapitale', 'capitale_investito_netto', DATA.companies.__ALL__, 'Ipotetico (al ritmo del miglior quartile)');
  charts.rotazioneWide = buildMetricChart('chartRotazioneWide', 'rotazione_ci', DATA.companies.__ALL__);

  // ==================== DONUT SETTORI =====================================
  function buildDonut(canvasId, values, centerBig, centerSmall){
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
      type: 'doughnut',
      data: { labels: DATA.sectors, datasets: [{ data: values, backgroundColor: DATA.sectorColors, borderColor: '#FFFDF8', borderWidth: 2, offset: DATA.sectors.map(()=>0) }] },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '66%',
        plugins: {
          legend: { display: false },
          tooltip: Object.assign({}, tooltipBase, { callbacks: { label: (c)=> `${c.label}: ${c.parsed}` } }),
          centerText: { big: centerBig, small: centerSmall }
        }
      }
    });
  }
  function buildLegend(elId, colors){
    const el = document.getElementById(elId);
    el.innerHTML = DATA.sectors.map((s,i)=>
      `<span class="legend-item"><span class="legend-dot" style="background:${colors[i]}"></span>${s} <b id="${elId}-v${i}"></b></span>`
    ).join('');
  }
  function setLegendValues(elId, values){
    values.forEach((v,i)=>{ const n = document.getElementById(`${elId}-v${i}`); if (n) n.textContent = v; });
  }
  charts.sectorDonut = buildDonut('chartSectorDonut', DATA.sectorCounts, String(DATA.meta.storicoCompleto), 'PMI con storico completo');
  buildLegend('legendSector', DATA.sectorColors); setLegendValues('legendSector', DATA.sectorCounts);

  function updateSectorHighlight(sector){
    const ch = charts.sectorDonut;
    if (!ch) return;
    ch.data.datasets[0].backgroundColor = DATA.sectorColors.map((c,i)=> (!sector || DATA.sectors[i] === sector) ? c : hexToRgba(c, 0.16));
    ch.data.datasets[0].offset = DATA.sectors.map(s => s === sector ? 14 : 0);
    ch.update();
  }

  // ==================== FUNNEL ============================================
  charts.funnel = new Chart(document.getElementById('chartFunnel').getContext('2d'), {
    data: {
      labels: DATA.funnel.labels,
      datasets: [
        { type: 'bar', data: DATA.funnel.values, backgroundColor: [COLORS.paperDim, COLORS.gold, COLORS.teal], barThickness: 46 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: tooltipBase },
      scales: { y: { beginAtZero: true, grid: { color: COLORS.line } }, x: { grid: { display: false } } }
    }
  });

  // ==================== RING ==============================================
  const RING_C = 2 * Math.PI * 87;
  function setRing(pct){
    const clamped = Math.max(0, Math.min(1, pct === null ? 0 : pct));
    const color = (pct !== null && pct >= 0) ? COLORS.secure : COLORS.rose;
    const dash = RING_C * clamped;
    const el = document.getElementById('ringProgress');
    el.setAttribute('stroke-dasharray', `${dash.toFixed(2)} ${(RING_C - dash).toFixed(2)}`);
    el.setAttribute('stroke', color);
    el.style.filter = `drop-shadow(0 0 10px ${color}88)`;
    const t = document.getElementById('ringText');
    t.textContent = pct === null ? 'n.d.' : Math.round(pct*100) + '%';
    t.setAttribute('fill', color);
  }

  // ==================== RENDER PER SELEZIONE ==============================
  function renderDetailCharts(rec){
    updateMetricChart(charts.detailEbitda, 'ebitda_margin', rec);
    updateMetricChart(charts.detailRoe, 'roe', rec);
    updateMetricChart(charts.detailRotazione, 'rotazione_ci', rec);
    const isSel = rec !== DATA.companies.__ALL__;
    document.getElementById('detailSub').textContent = isSel
      ? `${rec.displayName}${rec.settore ? ' — ' + rec.settore : ''}`
      : "Media di tutte le PMI analizzate — usa il selettore in cima alla pagina per vedere una singola azienda o la media di un settore.";
  }

  function renderImpatto(rec){
    updateMetricChart(charts.costi, 'costi_operativi', rec);
    updateMetricChart(charts.capitale, 'capitale_investito_netto', rec);
    updateMetricChart(charts.rotazioneWide, 'rotazione_ci', rec);
    const isSel = rec !== DATA.companies.__ALL__;
    const label = isSel ? rec.displayName : 'media di tutte le PMI';
    document.getElementById('costiSub').textContent = `${label} — migliaia di EUR, per anno`;
    document.getElementById('capitaleSub').textContent = `${label} — migliaia di EUR, per anno`;

    const realeT0 = lastValid(rec.costi_operativi.reale);
    const obiettivoT0 = lastValid(rec.costi_operativi.obiettivo);
    let pct = null;
    if (realeT0 !== null && obiettivoT0 !== null && realeT0 !== 0) {
      pct = (realeT0 - obiettivoT0) / Math.abs(realeT0);
    }
    setRing(pct);
    document.getElementById('ringSub').textContent = isSel
      ? `${label} — % di differenza dei costi operativi rispetto al benchmark, ultimo anno (stima teorica)`
      : "% di differenza dei costi operativi rispetto al benchmark, ultimo anno (stima teorica)";

    const capRealeT0 = lastValid(rec.capitale_investito_netto.reale);
    const capObiettivoT0 = lastValid(rec.capitale_investito_netto.obiettivo);
    const risparmioT0 = (realeT0 !== null && obiettivoT0 !== null) ? (realeT0 - obiettivoT0) : null;
    const capitaleDeltaT0 = (capRealeT0 !== null && capObiettivoT0 !== null) ? (capRealeT0 - capObiettivoT0) : null;
    const summary = document.getElementById('summaryList');
    summary.innerHTML = `
      <div class="summary-line"><span>Divario teorico sui costi operativi (ultimo anno)</span><span>${risparmioT0 === null ? 'n.d.' : fmtMetric(risparmioT0, 'costi_operativi')}</span></div>
      <div class="summary-line"><span>Capitale investito vs obiettivo (ultimo anno)</span><span>${capitaleDeltaT0 === null ? 'n.d.' : fmtMetric(capitaleDeltaT0, 'capitale_investito_netto')}</span></div>
      <div class="summary-line"><span>Orizzonte analizzato</span><span>${DATA.meta.orizzonteAnni} anni</span></div>
    `;
  }

  function renderCompanySummary(rec, key){
    const box = document.getElementById('companySummary');
    if (key === '__ALL__') { box.hidden = true; return; }
    box.hidden = false;
    const isSector = rec.isAggregate === true;
    box.innerHTML = `
      <div class="cs-item"><div class="cs-label">${isSector ? 'Settore' : 'Azienda'}</div><div class="cs-val" style="color:var(--paper)">${isSector ? rec.settore : rec.displayName}</div></div>
      ${isSector ? '' : `<div class="cs-item"><div class="cs-label">Settore</div><div class="cs-val" style="font-size:13.5px; color:var(--paper-dim); font-family:Inter,sans-serif;">${rec.settore}</div></div>`}
      <div class="cs-item"><div class="cs-label">EBITDA/Vendite (ultimo anno)</div><div class="cs-val">${fmtMetric(lastValid(rec.ebitda_margin.reale), 'ebitda_margin')}<div class="cs-val-sub">obiettivo ${fmtMetric(lastValid(rec.ebitda_margin.obiettivo), 'ebitda_margin')}</div></div></div>
      <div class="cs-item"><div class="cs-label">ROE (ultimo anno)</div><div class="cs-val" style="color:var(--gold-vivid)">${fmtMetric(lastValid(rec.roe.reale), 'roe')}<div class="cs-val-sub">obiettivo ${fmtMetric(lastValid(rec.roe.obiettivo), 'roe')}</div></div></div>
      <div class="cs-item"><div class="cs-label">Rotazione capitale investito</div><div class="cs-val">${fmtMetric(lastValid(rec.rotazione_ci.reale), 'rotazione_ci')}</div></div>
      ${rec.annoUltimo ? `<div class="cs-item"><div class="cs-label">Ultimo bilancio</div><div class="cs-val" style="font-size:14px; color:var(--paper-dim);">${rec.annoUltimo}</div></div>` : ''}
    `;
  }

  // Slug breve del settore per i link diretti: #settore=alimentare, #settore=packaging, ...
  function sectorSlug(name){
    return name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().split(/[^a-z0-9]+/)[0];
  }

  // ==================== SELEZIONE AZIENDA/SETTORE =========================
  function selectRecord(key, opts){
    opts = opts || {};
    const rec = DATA.companies[key];
    if (!rec) return;
    const companySel = document.getElementById('companySelect');
    const sectorSel = document.getElementById('sectorSelect');
    const isAggregateChoice = key === '__ALL__' || key.indexOf('SETTORE::') === 0;
    if (isAggregateChoice) {
      if (sectorSel.value !== key) sectorSel.value = key;
      companySel.value = '';
    } else {
      if (companySel.value !== key) companySel.value = key;
      sectorSel.value = '__ALL__';
    }
    if (!opts.skipHash) {
      if (key === '__ALL__') history.replaceState(null, '', location.pathname + location.search);
      else if (key.indexOf('SETTORE::') === 0) history.replaceState(null, '', location.pathname + location.search + '#settore=' + sectorSlug(key.slice(9)));
      else history.replaceState(null, '', '#azienda=' + encodeURIComponent(key));
    }
    renderDetailCharts(rec);
    renderImpatto(rec);
    updateSectorHighlight(rec.settore);
    renderCompanySummary(rec, key);
  }

  // ==================== SELETTORI (dropdown azienda + dropdown settore) ===
  (function initSelect(){
    const companySel = document.getElementById('companySelect');
    const placeholder = document.createElement('option');
    placeholder.value = ''; placeholder.textContent = "— seleziona un'azienda —"; placeholder.disabled = true; placeholder.selected = true;
    companySel.appendChild(placeholder);
    DATA.sectors.forEach(sector=>{
      const grp = document.createElement('optgroup');
      grp.label = sector;
      DATA.companyOrder.filter(k => DATA.companies[k].settore === sector).forEach(k=>{
        const o = document.createElement('option'); o.value = k; o.textContent = DATA.companies[k].displayName; grp.appendChild(o);
      });
      companySel.appendChild(grp);
    });
    companySel.addEventListener('change', (e)=> { if (e.target.value) selectRecord(e.target.value); });

    const sectorSel = document.getElementById('sectorSelect');
    const optAll = document.createElement('option');
    optAll.value = '__ALL__'; optAll.textContent = DATA.companies.__ALL__.displayName;
    sectorSel.appendChild(optAll);
    DATA.sectors.forEach(sector=>{
      const key = 'SETTORE::' + sector;
      const o = document.createElement('option');
      o.value = key; o.textContent = DATA.companies[key].displayName;
      sectorSel.appendChild(o);
    });
    sectorSel.addEventListener('change', (e)=> selectRecord(e.target.value));
  })();

  // ==================== SELEZIONE INIZIALE (da URL hash) ==================
  (function initSelection(){
    const m = location.hash.match(/azienda=([^&]+)/);
    const raw = m ? decodeURIComponent(m[1]) : null;
    const ms = location.hash.match(/settore=([^&]+)/);
    const slug = ms ? decodeURIComponent(ms[1]).toLowerCase() : null;
    const sec = slug ? DATA.sectors.find(x => sectorSlug(x) === slug) : null;
    const initial = (raw && DATA.companies[raw]) ? raw : (sec ? 'SETTORE::' + sec : '__ALL__');
    selectRecord(initial, { skipHash: true });
  })();
  } catch (err) {
    console.error('Veyron backtest: errore nella dashboard interattiva, il resto della pagina resta comunque visibile:', err);
  }
})();
