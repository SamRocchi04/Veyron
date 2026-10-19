#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_dist.py
------------
Copia in dist/ SOLO i file che devono essere pubblicati. Sorgenti (src/),
script (Script_Python/, Script_R/), README, workflow e data/azienda.json
(contiene form_id e altri dati interni) restano fuori dal sito pubblico.

Uso:  python3 Script_Python/build_site.py && python3 Script_Python/make_dist.py
"""
import glob
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")

FILE_GLOBS = ["*.html", "*.css", "*.js", "*.png", "*.ico", "robots.txt", "sitemap.xml", "CNAME"]
DIRS = ["fonts", "img", "vendor"]
DATA_FILES = ["data/benchmark.json"]  # unico dato letto dal browser (fetch)

if os.path.isdir(DIST):
    shutil.rmtree(DIST)
os.makedirs(DIST)

n = 0
for pattern in FILE_GLOBS:
    for src in glob.glob(os.path.join(ROOT, pattern)):
        shutil.copy2(src, DIST)
        n += 1
for d in DIRS:
    shutil.copytree(os.path.join(ROOT, d), os.path.join(DIST, d))
for rel in DATA_FILES:
    os.makedirs(os.path.join(DIST, os.path.dirname(rel)), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, rel), os.path.join(DIST, rel))
open(os.path.join(DIST, ".nojekyll"), "w").close()
print(f"dist/ pronta: {n} file in radice + {', '.join(DIRS)} + {', '.join(DATA_FILES)}")
