# Come aggiornare il sito

Le pagine HTML nella radice sono GENERATE: non modificarle a mano.

- Contenuto delle pagine: `src/pages/<nome>.html`
- Header / menu / footer / icone: `src/partials/` (una modifica vale per tutte le pagine)
- Rigenera tutto: `python3 Script_Python/build_site.py` (`--check` per verificare)
- Immagini nuove: metti il JPG in `img/`, poi `python3 Script_Python/ottimizza_immagini.py`
  (le `<img>` diventano `<picture>` AVIF/WebP in automatico)
- Benchmark: `python3 Script_Python/build_backtest_page.py` (con export AIDA) oppure
  `... --from-json` per rigenerare la pagina dai dati esistenti in `data/benchmark.json`.
  Nella home i numeri del Benchmark sono letti da quel JSON.
- La pagina Benchmark carica i dati con fetch: provala con un server
  (`python3 -m http.server`), non con doppio clic.
