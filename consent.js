/* Consenso e statistiche (Google Analytics 4).
   Viene incluso in tutte le pagine da data/analytics.json (attivo: true).
   - Finche' il visitatore non clicca «Accetta» NON viene caricato nessuno script
     di Google e non parte nessuna richiesta di rete verso Google.
   - La scelta e' salvata nel browser (localStorage, chiave veyron_consent) e si
     puo' cambiare dal link «Preferenze cookie» nel footer.
   L'ID di misurazione (G-XXXXXXXXXX) si legge dall'attributo data-ga del tag <script>. */
(function () {
  var tag = document.currentScript;
  var ID = tag && tag.getAttribute('data-ga');
  if (!ID) return;

  var KEY = 'veyron_consent';
  var loaded = false;

  function read() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function write(v) {
    try { localStorage.setItem(KEY, v); } catch (e) { /* storage bloccato: la scelta vale solo per questa pagina */ }
  }

  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  window.gtag('consent', 'default', {
    analytics_storage: 'denied',
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied'
  });

  function load() {
    window['ga-disable-' + ID] = false;
    window.gtag('consent', 'update', { analytics_storage: 'granted' });
    if (loaded) return;
    loaded = true;
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(ID);
    document.head.appendChild(s);
    window.gtag('js', new Date());
    window.gtag('config', ID);
  }

  function unload() {
    window['ga-disable-' + ID] = true;
    window.gtag('consent', 'update', { analytics_storage: 'denied' });
    // rimuove i cookie di Google Analytics (_ga, _ga_XXXX) gia' impostati
    var host = location.hostname.split('.');
    var domains = [location.hostname, '.' + location.hostname];
    if (host.length > 2) domains.push('.' + host.slice(-2).join('.'));
    document.cookie.split(';').forEach(function (c) {
      var name = c.split('=')[0].trim();
      if (name === '_ga' || name.indexOf('_ga_') === 0 || name === '_gid') {
        domains.forEach(function (d) {
          document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=' + d;
        });
        document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
      }
    });
  }

  // Eventi di conversione (usati da vTrack in site.js): solo con consenso attivo
  window.vGaEvent = function (name) {
    if (!loaded || window['ga-disable-' + ID]) return;
    window.gtag('event', String(name).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''));
  };

  var banner = null;

  function close() {
    if (banner && banner.parentNode) banner.parentNode.removeChild(banner);
    banner = null;
  }

  function choose(v) {
    write(v);
    if (v === 'granted') load(); else unload();
    close();
  }

  function css() {
    if (document.getElementById('vc-style')) return;
    var st = document.createElement('style');
    st.id = 'vc-style';
    st.textContent =
      '.vc{position:fixed;left:16px;right:16px;bottom:16px;z-index:9999;max-width:620px;margin:0 auto;' +
      'background:var(--ink,#F5F3EE);color:var(--paper,#151A21);border:1px solid var(--line-strong,rgba(21,26,33,.2));' +
      'border-radius:var(--radius,6px);box-shadow:0 12px 32px -8px rgba(21,26,33,.3);padding:18px 20px;' +
      'font:400 14px/1.55 var(--sans,system-ui,sans-serif)}' +
      '.vc p{margin:0 0 14px}.vc a{color:var(--teal,#0E3A5F);text-decoration:underline}' +
      '.vc-row{display:flex;gap:10px;flex-wrap:wrap}' +
      '.vc button{flex:1 1 140px;font:600 14px var(--sans,system-ui,sans-serif);padding:11px 16px;cursor:pointer;' +
      'border-radius:var(--radius,6px);border:1px solid var(--teal,#0E3A5F);background:transparent;color:var(--teal,#0E3A5F)}' +
      '.vc button:hover{background:var(--teal-dim,rgba(14,58,95,.07))}' +
      '.vc button:focus-visible{outline:2px solid var(--teal,#0E3A5F);outline-offset:2px}';
    document.head.appendChild(st);
  }

  function show(focus) {
    if (banner) return;
    css();
    banner = document.createElement('div');
    banner.className = 'vc';
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-label', 'Preferenze cookie');
    banner.innerHTML =
      '<p>Usiamo Google Analytics, solo con il tuo consenso, per capire come viene usato il sito. ' +
      'Se rifiuti, non viene caricato nulla di Google. Puoi cambiare idea in ogni momento da «Preferenze cookie» nel footer. ' +
      '<a href="privacy.html#cookie">Maggiori informazioni</a></p>' +
      '<div class="vc-row"><button type="button" data-v="denied">Rifiuta</button>' +
      '<button type="button" data-v="granted">Accetta</button></div>';
    banner.addEventListener('click', function (e) {
      var v = e.target && e.target.getAttribute && e.target.getAttribute('data-v');
      if (v) choose(v);
    });
    document.body.appendChild(banner);
    var first = banner.querySelector('button');
    if (focus && first) first.focus();
  }

  var saved = read();
  if (saved === 'granted') load();

  function init() {
    if (saved !== 'granted' && saved !== 'denied') show(false);
    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest && e.target.closest('[data-cookie-prefs]');
      if (!a) return;
      e.preventDefault();
      show(true);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
