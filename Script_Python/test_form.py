#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_form.py
------------
Invia un messaggio di prova al modulo di contatto (FormSubmit) e esce con
codice 1 se il servizio risponde con un errore: cosi' ti accorgi subito se il
form ha smesso di funzionare, senza aspettare che si perda un contatto vero.

Due controlli in uno:
  1. questo script (lo lancia ogni settimana .github/workflows/check-form.yml):
     verifica che il servizio risponda e che l'indirizzo sia ancora attivo;
  2. tu: il messaggio "[TEST AUTOMATICO]" deve arrivare nella casella
     dell'attivita'. Se una settimana non arriva, c'e' un problema di consegna
     (spam, casella piena, servizio fermo) anche se lo script e' verde.

Uso locale:  python3 Script_Python/test_form.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(ROOT, "data", "azienda.json"), encoding="utf-8") as f:
    az = json.load(f)
ident = (az.get("form_id") or az.get("email") or "").strip()
if not ident:
    sys.exit("[errore] data/azienda.json: serve 'email' o 'form_id'")

url = "https://formsubmit.co/ajax/" + ident
payload = {
    "Nome": "TEST AUTOMATICO",
    "Cognome": "Controllo settimanale",
    "Azienda": "Veyron (verifica del modulo)",
    "email": "test@veyron.it",
    "Problema": "Messaggio di prova inviato dallo script test_form.py. Puoi cancellarlo.",
    "_subject": "[TEST AUTOMATICO] Verifica modulo di contatto Veyron",
    "_template": "table",
    "_captcha": "false",
}
req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://www.veyron.it",
        "Referer": "https://www.veyron.it/contatti.html",
        "User-Agent": "veyron-form-check/1.0",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
        status = r.status
except urllib.error.HTTPError as e:
    body, status = e.read().decode("utf-8", "replace"), e.code
except (urllib.error.URLError, TimeoutError) as e:
    sys.exit(f"[ERRORE] servizio non raggiungibile: {e}")

try:
    ok = str(json.loads(body).get("success")).lower() == "true"
except ValueError:
    ok = False
if status == 200 and ok:
    print("OK: il modulo ha accettato il messaggio di prova.")
else:
    sys.exit(f"[ERRORE] il modulo non funziona (HTTP {status}): {body[:300]}")
