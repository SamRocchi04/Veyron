#!/usr/bin/env python3
# Cambia il nome dell'immagine di anteprima da og-image.png a og-image-v2.png
# cosi' LinkedIn la considera un file nuovo. Va lanciato dalla cartella del sito.
import glob, os, re, shutil, sys

root = os.getcwd()
if not os.path.exists(os.path.join(root, "og-image.png")) and not os.path.exists(os.path.join(root, "og-image-v2.png")):
    sys.exit("Errore: lancia lo script dalla cartella del sito (quella con og-image.png).")

if os.path.exists(os.path.join(root, "og-image.png")):
    shutil.copy2(os.path.join(root, "og-image.png"), os.path.join(root, "og-image-v2.png"))
    print("Creato og-image-v2.png")

files = (glob.glob("*.html") + glob.glob("src/pages/*.html") + glob.glob("src/partials/*.html")
         + ["Script_Python/build_backtest_page.py"])
n = 0
for f in files:
    if not os.path.exists(f):
        continue
    b = open(f, "rb").read()
    nb = re.sub(rb"og-image\.png", b"og-image-v2.png", b)
    if nb != b:
        open(f, "wb").write(nb)
        n += 1
        print("Aggiornato", f)
print(f"Fatto: {n} file modificati.")
