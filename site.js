const header = document.getElementById('siteHeader');
if (header) {
  window.addEventListener('scroll', () => {
    header.classList.toggle('scrolled', window.scrollY > 20);
  }, { passive: true });
}

(function revealSetup() {
  var reveals = document.querySelectorAll('[data-reveal]');
  if (!reveals.length) return;
  var showAll = function () {
    reveals.forEach(function (el) { el.classList.add('in-view'); });
  };
  try {
    if (!('IntersectionObserver' in window)) {
      showAll();
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('in-view');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.15 });
    reveals.forEach(function (el) { io.observe(el); });
  } catch (err) {
    showAll();
  }
})();


const statNums = document.querySelectorAll('.stat-num');
if (statNums.length && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const animateNum = (el) => {
    const target = parseInt(el.textContent, 10);
    if (isNaN(target)) return;
    const dur = 900;
    const start = performance.now();
    const step = (now) => {
      const p = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(eased * target);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const numIo = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        animateNum(e.target);
        numIo.unobserve(e.target);
      }
    });
  }, { threshold: 0.6 });
  statNums.forEach(el => numIo.observe(el));
}



const navToggle = document.getElementById('navToggle');
const mobileNav = document.getElementById('mobileNav');
if (navToggle && mobileNav) {
  const closeNav = () => {
    navToggle.setAttribute('aria-expanded', 'false');
    navToggle.setAttribute('aria-label', 'Apri il menu');
    mobileNav.classList.remove('open');
    mobileNav.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('nav-open');
  };
  navToggle.addEventListener('click', () => {
    const isOpen = navToggle.getAttribute('aria-expanded') === 'true';
    navToggle.setAttribute('aria-expanded', String(!isOpen));
    navToggle.setAttribute('aria-label', isOpen ? 'Apri il menu' : 'Chiudi il menu');
    mobileNav.classList.toggle('open', !isOpen);
    mobileNav.setAttribute('aria-hidden', String(isOpen));
    document.body.classList.toggle('nav-open', !isOpen);
  });
  mobileNav.querySelectorAll('a').forEach(a => a.addEventListener('click', closeNav));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeNav();
  });
  window.addEventListener('resize', () => {
    if (window.innerWidth > 860) closeNav();
  });
}


// Banda dati a scorrimento (home): duplica il gruppo per il loop continuo,
// calcola la durata per mantenere una velocita' costante, offre pausa/riprendi.
(function tickerSetup() {
  var ticker = document.querySelector('[data-ticker]');
  if (!ticker) return;
  var track = ticker.querySelector('.ticker-track');
  var group = ticker.querySelector('.ticker-group');
  var btn = ticker.querySelector('.ticker-toggle');
  if (!track || !group) return;

  var clone = group.cloneNode(true);
  clone.setAttribute('aria-hidden', 'true');
  track.appendChild(clone);

  var SPEED = 45; // px al secondo
  var setDuration = function () {
    var w = group.getBoundingClientRect().width;
    if (w) track.style.setProperty('--tk-dur', (w / SPEED).toFixed(1) + 's');
  };
  setDuration();
  if ('ResizeObserver' in window) new ResizeObserver(setDuration).observe(group);
  else window.addEventListener('resize', setDuration, { passive: true });

  var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  var sync = function () { ticker.classList.toggle('is-ready', !mq.matches); };
  sync();
  if (mq.addEventListener) mq.addEventListener('change', sync);

  if (btn) {
    btn.addEventListener('click', function () {
      var paused = ticker.classList.toggle('is-paused');
      btn.setAttribute('aria-pressed', String(paused));
      btn.setAttribute('aria-label', paused
        ? 'Riprendi lo scorrimento dei dati'
        : 'Metti in pausa lo scorrimento dei dati');
    });
  }
})();

/* Eventi di conversione per le statistiche. Se non e' caricato nessuno strumento
   di analytics (data/analytics.json) non fa nulla e non invia nessuna richiesta. */
window.vTrack = function (name) {
  try {
    if (typeof window.plausible === 'function') window.plausible(name);
    else if (window.umami && typeof window.umami.track === 'function') window.umami.track(name);
    else if (typeof window.vGaEvent === 'function') window.vGaEvent(name);
  } catch (e) { /* le statistiche non devono mai rompere il sito */ }
};


// Contatori animati: leggono il numero scritto nell'HTML (formato italiano, es. 6,8% o 1.582) e lo fanno crescere.
(function countSetup() {
  var els = document.querySelectorAll('[data-count]');
  if (!els.length || window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
  var RE = /^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(\s*[%a-zA-Z]*)$/;
  var fmt = function (v, dec) {
    return v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
      .replace(/,/g, '§').replace(/\./g, ',').replace(/§/g, '.');
  };
  var run = function (el) {
    var m = RE.exec(el.textContent.trim());
    if (!m) return;
    var dec = m[2] ? m[2].length : 0;
    var target = parseFloat(m[1].replace(/\./g, '') + (m[2] ? '.' + m[2] : ''));
    var suffix = m[3] || '';
    var dur = 1300, t0 = performance.now();
    var step = function (now) {
      var p = Math.min((now - t0) / dur, 1);
      el.textContent = fmt(target * (1 - Math.pow(1 - p, 4)), dec) + suffix;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { run(e.target); io.unobserve(e.target); }
    });
  }, { threshold: 0.4 });
  els.forEach(function (el) { io.observe(el); });
})();

// Cruscotto della hero (decorativo): cursore sul grafico e riga attiva nel feed.
(function consoleSetup() {
  var svg = document.querySelector('.cs-svg');
  if (svg) {
    var parse = function (sel) {
      return svg.querySelector(sel).getAttribute('points').trim().split(/\s+/).map(function (p) {
        var a = p.split(','); return [parseFloat(a[0]), parseFloat(a[1])];
      });
    };
    var vals = svg.getAttribute('data-vals').split(',').map(Number);
    var labels = svg.getAttribute('data-labels').split(',');
    var real = parseInt(svg.getAttribute('data-real'), 10);
    var pts = parse('.cs-line').concat(parse('.cs-fc').slice(1));
    var cur = svg.querySelector('.cs-cursor');
    var line = svg.querySelector('.cs-cur-line');
    var dot = svg.querySelector('.cs-cur-dot');
    var tip = document.querySelector('.cs-tip');
    var VW = 600, VH = 226;
    var hide = function () { cur.setAttribute('hidden', ''); tip.setAttribute('hidden', ''); };
    svg.addEventListener('pointermove', function (e) {
      var r = svg.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width * VW, best = 0;
      for (var i = 1; i < pts.length; i++) if (Math.abs(pts[i][0] - x) < Math.abs(pts[best][0] - x)) best = i;
      line.setAttribute('x1', pts[best][0]); line.setAttribute('x2', pts[best][0]);
      dot.setAttribute('cx', pts[best][0]); dot.setAttribute('cy', pts[best][1]);
      cur.removeAttribute('hidden');
      tip.innerHTML = '<span>' + labels[best] + (best >= real ? ' · prev.' : '') + '</span>€' + vals[best] + ' k';
      tip.style.left = (svg.offsetLeft + pts[best][0] / VW * r.width) + 'px';
      tip.style.top = (svg.offsetTop + pts[best][1] / VH * r.height) + 'px';
      tip.removeAttribute('hidden');
    });
    svg.addEventListener('pointerleave', hide);
  }
  var rows = document.querySelectorAll('.cs-feed li');
  if (rows.length > 1 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    var i = 0;
    rows[0].classList.add('is-on');
    setInterval(function () {
      rows[i].classList.remove('is-on');
      i = (i + 1) % rows.length;
      rows[i].classList.add('is-on');
    }, 2800);
  }
})();
