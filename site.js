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
