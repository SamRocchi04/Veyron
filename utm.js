/* Propaga i parametri utm_* dall'URL corrente ai link interni, così arrivano
   fino a contatti.html e da lì a Calendly. Nessun cookie, nessuno storage,
   nessuna richiesta di rete: legge solo l'indirizzo della pagina. */
(function () {
  var keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
  var params = new URLSearchParams(location.search);
  var found = {};
  var any = false;
  keys.forEach(function (k) {
    var v = params.get(k);
    if (v) { found[k] = v.slice(0, 100); any = true; }
  });
  if (!any) return;
  document.querySelectorAll('a[href]').forEach(function (a) {
    var h = a.getAttribute('href');
    if (!h || /^(#|mailto:|tel:|[a-z][a-z0-9+.-]*:|\/\/)/i.test(h)) return;
    var hashAt = h.indexOf('#');
    var hash = hashAt > -1 ? h.slice(hashAt) : '';
    var rest = hashAt > -1 ? h.slice(0, hashAt) : h;
    var qAt = rest.indexOf('?');
    var path = qAt > -1 ? rest.slice(0, qAt) : rest;
    var q = new URLSearchParams(qAt > -1 ? rest.slice(qAt + 1) : '');
    keys.forEach(function (k) { if (found[k] && !q.has(k)) q.set(k, found[k]); });
    a.setAttribute('href', path + '?' + q.toString() + hash);
  });
})();
