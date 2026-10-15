#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ottimizza_immagini.py
=====================
Genera da ogni JPG in img/ le varianti responsive AVIF + WebP + JPG
(larghezze 640 / 1024 / 1600 / originale) usate dai tag <picture>.

Uso (dalla cartella del sito):
    python3 Script_Python/ottimizza_immagini.py

Dipendenze: Pillow (con supporto WebP e AVIF).
I file sorgente restano img/<nome>.jpg (fallback); le varianti vengono
scritte come img/<nome>-<larghezza>.avif|webp.
"""
import os, sys, glob
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "img")
WIDTHS = [640, 1024, 1600]
Q_WEBP, Q_AVIF = 74, 52

def main():
    tot_in = tot_out = 0
    for src in sorted(glob.glob(os.path.join(IMG, "*.jpg"))):
        name = os.path.splitext(os.path.basename(src))[0]
        im = Image.open(src).convert("RGB")
        w0, h0 = im.size
        sizes = [w for w in WIDTHS if w < w0] + [w0]
        for w in sizes:
            h = round(h0 * w / w0)
            r = im if w == w0 else im.resize((w, h), Image.LANCZOS)
            for ext, kw in (("webp", dict(quality=Q_WEBP, method=6)),
                            ("avif", dict(quality=Q_AVIF, speed=6))):
                out = os.path.join(IMG, f"{name}-{w}.{ext}")
                r.save(out, ext.upper(), **kw)
        print(f"{name}.jpg {w0}x{h0} -> varianti {sizes}")

if __name__ == "__main__":
    main()
