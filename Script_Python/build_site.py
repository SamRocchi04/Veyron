#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_site.py
=============
Assembla le pagine del sito a partire da src/ e le scrive nella cartella
principale (la stessa che viene pubblicata: index.html, metodo.html, ...).

Perche' esiste
--------------
Header, menu mobile, footer e icone erano copiati a mano in 10 file.
Ora vivono UNA volta sola in src/partials/ e questo script li inserisce in
ogni pagina. Per cambiare una voce di menu: modifica src/partials/header.html
e rilancia lo script.

Struttura
---------
    src/partials/header.html      header + menu mobile
    src/partials/footer.html      footer
    src/partials/head-icons.html  favicon / apple-touch-icon
    src/pages/<nome>.html         contenuto di ogni pagina (-> <nome>.html)

Uso
---
    python3 Script_Python/build_site.py            # genera tutte le pagine
    python3 Script_Python/build_site.py --check    # non scrive: esce con codice 1
                                                   # se qualche pagina e' obsoleta

Direttiva di pagina (prima riga di ogni file in src/pages/)
----------------------------------------------------------
    <!-- page: active=metodo footer=t-dark base=- -->

    active  voce di menu da evidenziare (aria-current). '-' = nessuna
    footer  classe del <footer> (t-dark, t-navy...). '-' = nessuna
    base    prefisso dei link: '-' = relativi, '/' = assoluti (pagina 404)

Segnaposto disponibili nei file sorgente
----------------------------------------
    {{> nome}}              inserisce src/partials/nome.html
    {{base}}                prefisso link della pagina (vedi 'base')
    {{cur:slug}}            ' aria-current="page"' se slug == active
    {{footer_class}}        ' class="..."' per il <footer>, oppure nulla
    {{asset:percorso}}      percorso + ?v=<hash del file> (cache-busting)
    {{meta:chiave|formato}} numero preso da data/benchmark.json -> meta
                            formati: pct1 (6,8%), int (1.582), dec1 (6,8), dec2 (1,52), sdec1 (+7,1)

Immagini
--------
Ogni <img src="img/nome.jpg"> per cui esistono le varianti
img/nome-<larghezza>.avif/.webp (vedi ottimizza_immagini.py) viene
trasformato automaticamente in <picture> con srcset AVIF/WebP + fallback JPG,
con width/height reali, decoding="async" e:
    - loading="lazy" di default;
    - loading="eager" + fetchpriority="high" se la pagina lo dichiara
      (immagini hero sopra la piega, da NON caricare in lazy).
Attributo opzionale data-sizes="..." per sovrascrivere l'attributo sizes.

Dati strutturati e sitemap
--------------------------
Lo script aggiunge da solo nel <head>: BreadcrumbList (tutte le pagine tranne
home e 404) e FAQPage (se ci sono blocchi <div class="faq-item">). Genera
anche sitemap.xml con le date lastmod prese da git.

Dipendenze: Python 3.8+, Pillow (solo per leggere le dimensioni delle immagini).
"""
import datetime
import glob
import hashlib
import html as htmlmod
import json
import os
import re
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
PARTIALS = os.path.join(SRC, "partials")
PAGES = os.path.join(SRC, "pages")

DIRECTIVE_RE = re.compile(r"\A<!--\s*page:\s*(.*?)\s*-->\s*\n")
TOKEN_RE = re.compile(r"\{\{\s*(.*?)\s*\}\}")
DEFAULT_SIZES = "(min-width:1180px) 1116px, 100vw"
HERO_SIZES = "100vw"


# ----------------------------------------------------------------- helpers
def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def file_hash(rel_path):
    full = os.path.join(ROOT, rel_path)
    if not os.path.exists(full):
        raise SystemExit(f"[errore] asset non trovato: {rel_path}")
    with open(full, "rb") as f:
        data = f.read().replace(b"\r\n", b"\n")  # stesso hash su Windows e Linux/CI
    return hashlib.md5(data).hexdigest()[:8]


def load_meta():
    path = os.path.join(ROOT, "data", "benchmark.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta", {})
    meta["nSettori"] = len(meta.get("settoriInclusi", []))
    # Valori derivati (usati, ad esempio, dalla banda a scorrimento della home)
    meta["gapEbitdaT0"] = meta["ebitdaMarginObiettivoT0"] - meta["ebitdaMarginRealeT0"]
    meta["gapRoeT0"] = meta["roeObiettivoT0"] - meta["roeRealeT0"]
    meta["gapRotazioneT0"] = meta["rotazioneObiettivoT0"] - meta["rotazioneRealeT0"]
    try:
        meta["ebitdaMarginRealeInizio"] = data["companies"]["__ALL__"]["ebitda_margin"]["reale"][0]
    except (KeyError, IndexError):
        pass
    return meta


def it_number(x, decimals=0):
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


FORMATS = {
    "pct1": lambda v: it_number(v, 1) + "%",
    "dec1": lambda v: it_number(v, 1),
    "int": lambda v: it_number(v, 0),
    "dec2": lambda v: it_number(v, 2),
    "sdec1": lambda v: ("+" if v >= 0 else "\u2212") + it_number(abs(v), 1),  # +7,1 / \u22122,0
    "sdec2": lambda v: ("+" if v >= 0 else "\u2212") + it_number(abs(v), 2),
}


def parse_directive(text, name):
    m = DIRECTIVE_RE.match(text)
    if not m:
        raise SystemExit(f"[errore] {name}: manca la direttiva '<!-- page: ... -->' in prima riga")
    ctx = {"active": "", "footer": "", "base": ""}
    for pair in m.group(1).split():
        k, _, v = pair.partition("=")
        if k not in ctx:
            raise SystemExit(f"[errore] {name}: chiave sconosciuta '{k}' nella direttiva")
        ctx[k] = "" if v == "-" else v
    return ctx, text[m.end():]


# ------------------------------------------------------------- immagini
def picture_for(attrs, ctx):
    """Restituisce l'HTML <picture> per un <img> locale, o None se non applicabile."""
    src = attrs.get("src", "")
    m = re.fullmatch(r"(?:/)?img/([\w\-]+)\.jpg", src)
    if not m:
        return None
    name = m.group(1)
    widths = sorted(
        int(re.search(r"-(\d+)\.avif$", p).group(1))
        for p in glob.glob(os.path.join(ROOT, "img", f"{name}-*.avif"))
    )
    if not widths:
        return None
    jpg = os.path.join(ROOT, "img", f"{name}.jpg")
    with Image.open(jpg) as im:
        w0, h0 = im.size
    is_hero = attrs.get("loading") == "eager"
    sizes = attrs.pop("data-sizes", None) or (HERO_SIZES if is_hero else DEFAULT_SIZES)
    prefix = "/" if src.startswith("/") else ""

    def srcset(ext):
        return ", ".join(f"{prefix}img/{name}-{w}.{ext} {w}w" for w in widths)

    img_attrs = dict(attrs)
    img_attrs["width"], img_attrs["height"] = str(w0), str(h0)  # dimensioni reali: niente layout shift
    img_attrs.setdefault("loading", "lazy")
    img_attrs["decoding"] = "async"
    if is_hero:
        img_attrs["fetchpriority"] = "high"
    order = ["src", "alt", "class", "loading", "decoding", "fetchpriority", "width", "height"]
    keys = [k for k in order if k in img_attrs] + [k for k in img_attrs if k not in order]
    img_html = "<img " + " ".join(f'{k}="{img_attrs[k]}"' for k in keys) + ">"
    return (
        "<picture>"
        f'<source type="image/avif" srcset="{srcset("avif")}" sizes="{sizes}">'
        f'<source type="image/webp" srcset="{srcset("webp")}" sizes="{sizes}">'
        f"{img_html}</picture>"
    )


def enhance_images(html, ctx):
    def repl(m):
        attrs = dict(re.findall(r'([\w\-]+)="([^"]*)"', m.group(1)))
        pic = picture_for(attrs, ctx)
        return pic if pic else m.group(0)

    return re.sub(r"<img\b([^>]*?)>", repl, html)


# ------------------------------------------------------------- espansione
def expand(text, ctx, meta, partials):
    # 1) include (annidabili)
    for _ in range(5):
        new = re.sub(r"\{\{>\s*([\w\-]+)\s*\}\}", lambda m: partials[m.group(1)].rstrip("\n"), text)
        if new == text:
            break
        text = new

    # 2) segnaposto
    def token(m):
        t = m.group(1)
        if t == "base":
            return ctx["base"]
        if t == "footer_class":
            return f' class="{ctx["footer"]}"' if ctx["footer"] else ""
        if t.startswith("cur:"):
            return ' aria-current="page"' if t[4:] == ctx["active"] else ""
        if t.startswith("asset:"):
            p = t[6:]
            return f'{ctx["base"]}{p}?v={file_hash(p)}'
        if t.startswith("meta:"):
            key, _, fmt = t[5:].partition("|")
            if key not in meta:
                raise SystemExit(f"[errore] meta '{key}' assente in data/benchmark.json")
            return FORMATS[fmt or "dec1"](meta[key])
        return m.group(0)  # sconosciuto: lasciato com'e' (es. codice JS/CSS con {{ }})

    text = TOKEN_RE.sub(token, text)
    return enhance_images(text, ctx)


# ------------------------------------------------------------- JSON-LD
SITE_URL = "https://www.veyron.it"


def _plain(fragment):
    """Testo semplice da un frammento HTML (niente tag, entita' decodificate)."""
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _ld(obj):
    return ('<script type="application/ld+json">\n'
            + json.dumps(obj, ensure_ascii=False, indent=2) + "\n</script>\n")


def jsonld_extras(slug, out):
    """Dati strutturati generati dal contenuto stesso della pagina:
    - BreadcrumbList (Home > Pagina) su tutte le pagine indicizzabili tranne la home;
    - FAQPage se la pagina contiene blocchi <div class="faq-item"> (resta
      sempre allineata al testo visibile, non va duplicata a mano)."""
    blocks = []
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', out)
    title = re.search(r"<title>(.*?)</title>", out, re.S)
    if slug not in ("index", "404") and canon and title:
        label = _plain(title.group(1)).split(" \u2014 ")[0].strip()
        blocks.append(_ld({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": label, "item": canon.group(1)},
            ],
        }))
    faqs = re.findall(r'<div class="faq-item">\s*<h3>(.*?)</h3>\s*<p>(.*?)</p>', out, re.S)
    if faqs:
        blocks.append(_ld({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": _plain(q),
                 "acceptedAnswer": {"@type": "Answer", "text": _plain(a)}}
                for q, a in faqs
            ],
        }))
    return "".join(blocks)


# ------------------------------------------------------------- sitemap
SITEMAP_ORDER = ["index", "chi-siamo", "metodo", "soluzioni", "risultati",
                 "backtest", "contatti", "privacy", "termini"]
# Pagine il cui contenuto dipende anche da altri file (oltre a src/pages/<nome>.html)
LASTMOD_EXTRA = {"index": ["data/benchmark.json"], "backtest": ["data/benchmark.json"]}


def _last_change(rel):
    """Data (YYYY-MM-DD) dell'ultima modifica di un file: ultimo commit git se il
    file e' pulito, oggi se ha modifiche non committate, altrimenti la data del file."""
    today = datetime.date.today().isoformat()
    try:
        dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        if dirty:
            return today
        d = subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.strip()
        if d:
            return d
    except (OSError, subprocess.CalledProcessError):
        pass
    full = os.path.join(ROOT, rel)
    if os.path.exists(full):
        return datetime.date.fromtimestamp(os.path.getmtime(full)).isoformat()
    return today


def sitemap_xml(slugs):
    ordered = [s for s in SITEMAP_ORDER if s in slugs] + sorted(s for s in slugs if s not in SITEMAP_ORDER)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for slug in ordered:
        deps = [f"src/pages/{slug}.html"] + LASTMOD_EXTRA.get(slug, [])
        lastmod = max(_last_change(d) for d in deps)
        path = "" if slug == "index" else f"{slug}.html"
        lines.append(f"  <url><loc>{SITE_URL}/{path}</loc><lastmod>{lastmod}</lastmod></url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _strip_lastmod(xml):
    return re.sub(r"<lastmod>.*?</lastmod>", "", xml)


def build(check=False):
    partials = {
        os.path.splitext(os.path.basename(p))[0]: read(p)
        for p in glob.glob(os.path.join(PARTIALS, "*.html"))
    }
    meta = load_meta()
    stale, written = [], 0
    indexable = []
    for page in sorted(glob.glob(os.path.join(PAGES, "*.html"))):
        name = os.path.basename(page)
        ctx, body = parse_directive(read(page), name)
        out = expand(body, ctx, meta, partials)
        slug = name[:-5]
        extras = jsonld_extras(slug, out)
        if extras:
            out = out.replace("</head>", extras + "</head>", 1)
        if "noindex" not in out and slug != "404":
            indexable.append(slug)
        left = re.findall(r"\{\{\s*(?:>|base|cur:|asset:|meta:|footer_class)[^}]*\}\}", out)
        if left:
            raise SystemExit(f"[errore] {name}: segnaposto non risolti: {left[:3]}")
        dest = os.path.join(ROOT, name)
        current = read(dest) if os.path.exists(dest) else None
        if current != out:
            stale.append(name)
            if not check:
                with open(dest, "w", encoding="utf-8", newline="\n") as f:
                    f.write(out)
                written += 1
    # sitemap.xml: generata dalle pagine indicizzabili (in --check si confronta
    # l'elenco degli URL, non le date lastmod, che dipendono dalla storia git)
    sm_path = os.path.join(ROOT, "sitemap.xml")
    sm_new = sitemap_xml(indexable)
    sm_cur = read(sm_path) if os.path.exists(sm_path) else ""
    if _strip_lastmod(sm_cur) != _strip_lastmod(sm_new):
        stale.append("sitemap.xml")
    if check:
        if stale:
            print("Pagine obsolete (rilancia build_site.py):", ", ".join(stale))
            sys.exit(1)
        print("OK: tutte le pagine sono aggiornate.")
    else:
        if sm_cur != sm_new:
            with open(sm_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(sm_new)
        print(f"Build completata: {written} pagine riscritte, "
              f"{len(glob.glob(os.path.join(PAGES, '*.html'))) - written} invariate.")


if __name__ == "__main__":
    build(check="--check" in sys.argv)
