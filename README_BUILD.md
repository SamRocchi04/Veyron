# Come aggiornare il sito

Le pagine HTML nella radice sono GENERATE: non modificarle a mano.

- Contenuto delle pagine: `src/pages/<nome>.html`
- Header / menu / footer / icone: `src/partials/` (una modifica vale per tutte le pagine)
- Dati dell'attività (P. IVA, sede, PEC, REA): `data/azienda.json`. Alimentano footer, privacy, termini e JSON-LD;
  i campi vuoti non vengono pubblicati e il build li segnala.
- Statistiche di visita: `data/analytics.json`. Con `"attivo": false` non viene caricato nulla e la privacy
  dice che non ci sono analytics. Per attivarle: crea l'account (Plausible, Umami...), incolla lo snippet
  `<script ...></script>` in `snippet`, scrivi il `provider`, metti `"attivo": true` e rilancia il build:
  lo script entra in tutte le pagine e la privacy policy si aggiorna da sola. Gli eventi «Form inviato»,
  «Form errore» e «Calendario caricato» partono da soli (vanno creati come obiettivi nel pannello del provider).
- Modulo di contatto: `form_key` in `data/azienda.json` e' la access key di Web3Forms (web3forms.com), collegata
  all'email di destinazione dei messaggi. `check-form.yml` (da lanciare a mano da Actions) invia un messaggio `[TEST AUTOMATICO]`;
  non e' programmato perche' Web3Forms gratuito puo' bloccare le richieste dai server GitHub. Per un controllo
  affidabile invia un messaggio dal sito pubblico.
- `risultati.html` è solo un redirect verso `percorsi.html` (la pagina si chiamava Risultati).
- Rigenera tutto: `python3 Script_Python/build_site.py` (`--check` per verificare)
- Immagini nuove: metti il JPG in `img/`, poi `python3 Script_Python/ottimizza_immagini.py`
  (le `<img>` diventano `<picture>` AVIF/WebP in automatico)
- Benchmark: `python3 Script_Python/build_backtest_page.py` (con export AIDA) oppure
  `... --from-json` per rigenerare la pagina dai dati esistenti in `data/benchmark.json`.
  Nella home i numeri del Benchmark sono letti da quel JSON.
- La pagina Benchmark carica i dati con fetch: provala con un server
  (`python3 -m http.server`), non con doppio clic.

## Pubblicazione (solo i file pubblici)
- `python3 Script_Python/make_dist.py` crea `dist/` con soltanto ciò che va online
  (pagine, CSS/JS, font, immagini, `data/benchmark.json`). `src/`, gli script, i README e
  `data/azienda.json` (dati interni) restano fuori.
- `.github/workflows/deploy.yml` pubblica `dist/` su GitHub Pages. Per attivarlo:
  Settings > Pages > Source = "GitHub Actions", poi lancialo a mano e, se il sito è ok,
  decommenta il trigger `push`.
- Lo script R è in `Script_R/`; `__pycache__` è ignorato da `.gitignore`.

