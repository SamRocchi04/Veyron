#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compila_dati_societari.py
-------------------------
Sostituisce in un colpo solo i segnaposto [[...]] presenti nel sito
(footer, contatti, privacy, termini) con i dati reali di Veyron.

USO
  1. Compila il dizionario DATI qui sotto.
  2. Esegui:  python3 compila_dati_societari.py
  3. Lo script elenca eventuali segnaposto rimasti vuoti.

Aggiorna anche build_backtest_page.py, cosi' se rigeneri backtest.html
i dati restano.
"""
import glob, html, os, re

DATI = {
    "RAGIONE_SOCIALE": "",   # es. "Veyron S.r.l." (o nome e cognome se ditta individuale)
    "PIVA":            "",   # es. "01234567890"
    "SEDE_LEGALE":     "",   # es. "Via Roma 1, 40100 Bologna (BO)"
    "PEC":             "",   # es. "veyron@pec.it"
    "FORO":            "",   # citta' del foro competente, es. "Bologna"
}

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = glob.glob(os.path.join(BASE, "*.html")) + [os.path.join(BASE, "Script_Python", "build_backtest_page.py")]

for chiave, valore in DATI.items():
    if not valore.strip():
        continue
    pat = re.compile(r'<span class="placeholder">\[\[%s\]\]</span>' % re.escape(chiave))
    for f in files:
        s = open(f, encoding="utf-8").read()
        nuovo = pat.sub(lambda m: html.escape(valore.strip(), quote=False), s)
        if nuovo != s:
            open(f, "w", encoding="utf-8").write(nuovo)

rimasti = {}
for f in files:
    for k in re.findall(r'\[\[([A-Z_]+)\]\]', open(f, encoding="utf-8").read()):
        rimasti.setdefault(k, set()).add(os.path.basename(f))
if rimasti:
    print("ATTENZIONE - segnaposto ancora da compilare:")
    for k, fl in rimasti.items():
        print("  [[%s]]  in: %s" % (k, ", ".join(sorted(fl))))
else:
    print("Fatto: nessun segnaposto rimasto.")
