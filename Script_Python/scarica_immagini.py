#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scarica_immagini.py
-------------------
Scarica in ../img le 8 foto Unsplash usate dal sito, cosi' vengono servite
dal tuo dominio (nessuna richiesta a terzi quando un utente visita il sito).
Serve una connessione internet. Licenza Unsplash: uso libero, anche commerciale.

USO:  python3 scarica_immagini.py
"""
import os, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "img")
os.makedirs(OUT, exist_ok=True)

# (nome file, id foto Unsplash, larghezza)
FOTO = [
    ("hero-chi-siamo.jpg",   "photo-1506787497326-c2736dde1bef", 1920),
    ("chi-siamo-team.jpg",   "photo-1758876203026-99a024dc43b9", 1800),
    ("hero-contatti.jpg",    "photo-1588196749597-9ff075ee6b5b", 1920),
    ("home-team.jpg",        "photo-1517048676732-d65bc937f952", 1800),
    ("hero-metodo.jpg",      "photo-1460925895917-afdab827c52f", 1920),
    ("hero-risultati.jpg",   "photo-1591696205602-2f950c417cb9", 1920),
    ("soluzioni-blocco.jpg", "photo-1526628953301-3e589a6a8b74", 1800),
    ("hero-soluzioni.jpg",   "photo-1666875753105-c63a6f3bdc86", 1920),
]

for nome, pid, w in FOTO:
    url = "https://images.unsplash.com/%s?auto=format&fit=crop&w=%d&q=75" % (pid, w)
    dest = os.path.join(OUT, nome)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
            f.write(r.read())
        print("ok   ", nome, "(%d KB)" % (os.path.getsize(dest) // 1024))
    except Exception as e:
        print("ERRORE", nome, "-", e)
