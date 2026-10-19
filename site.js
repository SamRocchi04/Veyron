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
  } catch (e) { /* le statistiche non devono mai rompere il sito */ }
};
