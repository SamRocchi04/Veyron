#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_backtest_page.py  (v4 — dati reali AIDA, strategia "realistico vs obiettivo di settore")
=======================================================================
Genera "backtest.html": la pagina del sito Veyron dedicata a
Backtest, Analisi di Bilancio e Impatto Potenziale.

NOVITA' RISPETTO ALLA V3 (US EDGAR + previsione Ollama)
--------------------------------------------------------
La v3 backtestava un universo di 26 titoli USA quotati, con un modello
Ollama che PREVEDEVA il rendimento futuro e selezionava un Top-8 "come se"
fosse un portafoglio di investimento. Questa v4 sostituisce interamente
quella logica con la strategia di "backtest_aida_PMI_3.R": dati REALI di
bilancio di PMI italiane (export AIDA — Bureau van Dijk), 6 settori target,
e per ciascuna azienda un confronto storico (ultimi ___ORIZZONTE___ anni)
fra:

  - ANDAMENTO REALISTICO  = il valore storico realmente registrato
  - SCENARIO CON LA STRATEGIA (obiettivo di settore) = il livello del
    quartile migliore (default: top 25%) delle aziende comparabili
    (stesso settore, stesso anno relativo) — un obiettivo raggiungibile
    e ancorato a dati reali, non una previsione della consulenza Veyron

su 5 metriche (le stesse dello script R):
  1. EBITDA / Vendite %             (marginalita' operativa)
  2. ROE %                          (redditivita' del capitale proprio)
  3. Rotazione del Capitale Investito (volte)
  4. Costi operativi (Ricavi - EBITDA), migl EUR — "costi risparmiabili"
  5. Capitale Investito Netto, migl EUR — "capitale potenzialmente liberato"

NON e' piu' un backtest di portafoglio azionario: non ci sono piu' equity
curve, pesi di portafoglio, rendimenti previsti/realizzati o un ring di
"accuratezza direzionale" — quei concetti appartenevano alla strategia
precedente (selezione di titoli quotati) e non hanno equivalente qui.
Sono stati sostituiti da contenuti equivalenti ma coerenti con la nuova
strategia (vedi sezioni "Analisi di Bilancio" e "Impatto Potenziale" piu'
sotto nel template HTML).

PRIVACY — IMPORTANTE
----------------------
Lo script R sorgente avvisa esplicitamente: se questi confronti finiscono
in materiale pubblico, la ragione sociale reale va sostituita con una
sigla anonima. Questa pagina e' pubblica (meta robots "index, follow",
canonical su www.veyron.it/backtest.html), quindi l'anonimizzazione qui
NON e' opzionale: ogni azienda mostrata compare come "Azienda N" (N =
posizione nel suo settore), mai con la ragione sociale reale. La ragione
sociale vera viene solo stampata a schermo durante la generazione (uso
interno, per rintracciare a chi si riferisce ogni "Azienda N"), MAI scritta
nel file HTML/JSON generato.

COME FUNZIONA IL DATO
----------------------
Lo script cerca, nella stessa cartella in cui viene eseguito (o in un paio
di percorsi tolleranti, vedi AIDA_FALLBACK_PATHS piu' sotto), un file
Aida_Export_2.xls (o simile) con il foglio "Risultati" cosi' come lo
esporta AIDA (Bureau van Dijk). Se non lo trova, o se il file non ha le
colonne attese, usa un set di DATI DI ESEMPIO chiaramente etichettati come
tali (badge in testa alla pagina), cosi' la pagina e' comunque generabile e
visionabile da subito.

USO
----
    python3 build_backtest_page.py
    # genera ./backtest.html

Dipendenze Python: pandas, numpy, xlrd (per leggere il vecchio formato
.xls di AIDA — "pip install xlrd", NON openpyxl che legge solo .xlsx)
Dipendenze runtime (nel browser): NESSUNA — Chart.js e' incorporato nel
file generato, la pagina funziona anche offline.
=======================================================================
"""

import os
import re
import json
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(SCRIPT_DIR, "backtest.html")
# NOTA: 4.4.4 esiste su npm ma NON e' mai stata pubblicata su cdnjs (li'
# le versioni disponibili saltano da 4.4.1 a 4.5.0) — usare un numero non
# presente su cdnjs qui sotto fa fallire con 404 il download automatico di
# riserva. 4.4.1 e' confermata presente su cdnjs; il file vendorizzato
# insieme allo script e' la stessa 4.4.1 (nessuna differenza rilevante per
# come viene usata qui).
CHARTJS_VERSION = "4.4.1"
CHARTJS_CDN_URL = f"https://cdnjs.cloudflare.com/ajax/libs/Chart.js/{CHARTJS_VERSION}/chart.umd.js"
# Percorso "ufficiale" dove va tenuto il file (consegnato insieme allo
# script): una sottocartella vendor/ accanto allo script.
CHARTJS_VENDOR_PATH = os.path.join(SCRIPT_DIR, "vendor", "chart.umd.js")
# Percorsi alternativi accettati per tolleranza: capita che chi rigenera la
# pagina tenga lo script DENTRO una cartella gia' chiamata "vendor" (in tal
# caso il percorso "ufficiale" sopra punterebbe a un doppio vendor/vendor/
# inesistente), oppure che il file finisca semplicemente nella stessa
# cartella dello script.
CHARTJS_FALLBACK_PATHS = [
    os.path.join(SCRIPT_DIR, "chart.umd.js"),
    os.path.join(os.path.dirname(SCRIPT_DIR), "vendor", "chart.umd.js"),
    os.path.join(os.path.dirname(SCRIPT_DIR), "chart.umd.js"),
]


def load_chartjs_source():
    """Chart.js viene INCORPORATO nel file backtest.html generato (nessuna
    dipendenza da CDN a runtime): se cdnjs.cloudflare.com e' bloccato,
    lento, o irraggiungibile (rete aziendale, offline, ad-blocker), uno
    <script src="..."> esterno lascerebbe "Chart" undefined e romperebbe
    tutta la dashboard. Incorporare la libreria elimina il problema alla
    radice: la pagina non dipende da nessuna rete per funzionare (a parte i
    font Google, che sono solo estetici).

    Cerca prima nel percorso ufficiale (./vendor/chart.umd.js accanto allo
    script) e in un paio di percorsi alternativi tolleranti a errori di
    posizionamento della cartella; se non trova nulla, prova a scaricarla
    una tantum da cdnjs e la salva nel percorso ufficiale per le prossime
    volte.
    """
    for candidate in [CHARTJS_VENDOR_PATH] + CHARTJS_FALLBACK_PATHS:
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return f.read()
    print(f"[i] Chart.js non trovato in nessuno dei percorsi noti (atteso: {CHARTJS_VENDOR_PATH}); provo a scaricarlo da cdnjs...")
    try:
        import urllib.request
        with urllib.request.urlopen(CHARTJS_CDN_URL, timeout=15) as resp:
            src = resp.read().decode("utf-8")
        os.makedirs(os.path.dirname(CHARTJS_VENDOR_PATH), exist_ok=True)
        with open(CHARTJS_VENDOR_PATH, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"[i] Scaricato e salvato in {CHARTJS_VENDOR_PATH} per le prossime esecuzioni.")
        return src
    except Exception as e:
        raise SystemExit(
            "Impossibile trovare o scaricare Chart.js (serve per generare la pagina).\n"
            f"  - Percorso atteso: {CHARTJS_VENDOR_PATH}\n"
            f"  - Download automatico fallito: {e}\n"
            "Scarica manualmente il file da:\n"
            f"  {CHARTJS_CDN_URL}\n"
            "e salvalo in quel percorso, poi rilancia lo script.\n"
            "IMPORTANTE: lo script NON deve stare dentro una cartella gia' "
            "chiamata 'vendor' — deve stare un livello sopra, con il file "
            "chart.umd.js dentro una sua sottocartella vendor/."
        )


CHARTJS_SOURCE = load_chartjs_source()

# =========================================================================
# 1. CONFIGURAZIONE STRATEGIA (mirror di CONFIG in backtest_aida_PMI_3.R)
# =========================================================================
CONFIG = dict(
    # nomi di file accettati per l'export AIDA, cercati nella cartella
    # dello script (e in un paio di percorsi tolleranti, come per Chart.js)
    aida_filename_candidates=["Aida_Export_2.xls", "Aida_Export.xls", "aida_export.xls", "AIDA.xls"],
    aida_sheet="Risultati",
    quantile_top=0.75,               # "obiettivo" per le 3 metriche dove piu' alto e' meglio
    quantile_costo_migliore=0.25,    # "obiettivo" per il rapporto costi/ricavi (piu' basso e' meglio)
    min_aziende_per_settore=15,      # sotto questa soglia un settore viene escluso (benchmark non affidabile)
    orizzonte_anni=5,                # + l'anno "oggi" = 6 punti per azienda
    settori_target=[
        "Alimentare",
        "Metallurgia e Prodotti in Metallo",
        "Edilizia e Costruzioni",
        "Packaging",
        "Trasporti e Logistica",
        "Turismo e Ristorazione",
    ],
    n_pmi_per_settore=5,
    criterio_selezione="top_ricavi",   # "top_ricavi" | "mediane" | "casuali"
    seed_selezione=42,
)

# stessa palette del resto del sito, una voce per settore (ordine fisso di
# CONFIG['settori_target'], cosi' il colore di un settore resta lo stesso
# anche se in un'esecuzione futura un settore venisse escluso)
SETTORE_COLOR_MAP = dict(zip(
    CONFIG["settori_target"],
    ["#0E3A5F", "#875C0E", "#2E7D46", "#3A8FA3", "#A63D3D", "#5B6270"],
))

# le 5 metriche della strategia — "sezione" decide in quale sezione della
# pagina finisce (bilancio = le 3 metriche "di livello", impatto = le 2
# metriche "assolute" che dipendono dalla dimensione dell'azienda)
METRICHE = [
    dict(id="ebitda_margin", titolo="EBITDA / Vendite", titoloBreve="EBITDA/Vendite",
         unita="%", isPct=True, migliore="alto", sezione="bilancio"),
    dict(id="roe", titolo="ROE — Redditività del capitale proprio", titoloBreve="ROE",
         unita="%", isPct=True, migliore="alto", sezione="bilancio"),
    dict(id="rotazione_ci", titolo="Rotazione del Capitale Investito", titoloBreve="Rotazione CI",
         unita="volte", isPct=False, migliore="alto", sezione="bilancio"),
    dict(id="costi_operativi", titolo="Costi operativi (Ricavi − EBITDA)", titoloBreve="Costi operativi",
         unita="Migliaia di EUR", isPct=False, migliore="basso", sezione="impatto"),
    dict(id="capitale_investito_netto", titolo="Capitale Investito Netto", titoloBreve="Capitale Investito",
         unita="Migliaia di EUR", isPct=False, migliore="basso", sezione="impatto"),
]
METRIC_IDS = [m["id"] for m in METRICHE]

T_RANGE = list(range(-CONFIG["orizzonte_anni"], 1))  # es. [-5,-4,-3,-2,-1,0]


def t_label(t):
    if t == 0:
        return "Oggi"
    return f"{-t} anno fa" if t == -1 else f"{-t} anni fa"


T_LABELS = [t_label(t) for t in T_RANGE]


# =========================================================================
# 2. CARICAMENTO E TRASFORMAZIONE DATI AIDA
#    (replica in pandas della logica di backtest_aida_PMI_3.R)
# =========================================================================
def classifica_settore(ateco):
    """Stessa classificazione ATECO->settore dello script R: 'Packaging' e'
    trasversale ad altre divisioni (carta/plastica/metallo/legno) quindi va
    riconosciuto PRIMA delle regole generiche, sui codici a 4 cifre."""
    digits = re.sub(r"[^0-9]", "", str(ateco))
    a = digits.zfill(6)
    a2, a4 = a[:2], a[:4]
    packaging_codes = {"1721", "2222", "2592", "1624"}
    if a4 in packaging_codes:
        return "Packaging"
    if a2 in {"10", "11"}:
        return "Alimentare"
    if a2 in {"24", "25"}:
        return "Metallurgia e Prodotti in Metallo"
    if a2 in {"41", "42", "43"}:
        return "Edilizia e Costruzioni"
    if a2 in {"49", "50", "51", "52", "53"}:
        return "Trasporti e Logistica"
    if a2 in {"55", "56"}:
        return "Turismo e Ristorazione"
    return "Altro"


# pattern usati per rinominare le colonne del file AIDA (nomi lunghi tipo
# "Redditività del capitale proprio (ROE) \n%\nAnno - 3") sui nomi corti
# usati dal resto dello script — stesso approccio "cerca per pattern" di
# rename_by_pattern() in R, cosi' lo script si adatta anche se l'ordine
# delle colonne nell'export cambia
AIDA_RENAME_PATTERNS = [
    (r"^Ricavi delle vendite$", "ricavi"),
    (r"^EBITDA$", "ebitda"),
    (r"^Patrimonio Netto$", "patrimonio_netto"),
    (r"^Posizione finanziaria netta$", "pfn"),
    (r"^EBITDA/Vendite$", "ebitda_margin"),
    (r"^Redditivit.\s+del capitale proprio \(ROE\)", "roe"),
    (r"^Rotaz\.\s*cap\.\s*investito", "rotazione_ci"),
]
AIDA_ESSENTIAL = ["ricavi", "ebitda", "patrimonio_netto", "pfn", "ebitda_margin", "roe", "rotazione_ci"]


def find_aida_file():
    search_dirs = [SCRIPT_DIR, os.path.dirname(SCRIPT_DIR)]
    for d in search_dirs:
        for name in CONFIG["aida_filename_candidates"]:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
        # tollera anche qualunque altro .xls presente nella cartella,
        # nel caso l'export sia stato rinominato
        try:
            for fn in os.listdir(d):
                if fn.lower().endswith(".xls") and "aida" in fn.lower():
                    return os.path.join(d, fn)
        except OSError:
            pass
    return None


def carica_aida_panel(path, sheet):
    """Legge il foglio 'Risultati' dell'export AIDA e lo trasforma in un
    pannello lungo azienda-anno (equivalente di carica_aida() in R)."""
    raw = pd.read_excel(path, sheet_name=sheet, engine="xlrd")
    raw = raw.rename(columns={raw.columns[0]: "riga_export"})

    id_cols = ["riga_export", "Ragione sociale", "Provincia", "Codice fiscale", "Numero CCIAA"]
    col_chiusura_hits = [c for c in raw.columns if str(c).startswith("Chiusura bilancio")]
    col_ateco_hits = [c for c in raw.columns if str(c).startswith("ATECO")]
    if len(col_chiusura_hits) != 1 or len(col_ateco_hits) != 1:
        raise ValueError(
            "Non trovo (o trovo duplicate) le colonne 'Chiusura bilancio' e/o "
            "'ATECO' nel foglio AIDA: controlla che il file esportato sia "
            "quello giusto e che il foglio si chiami 'Risultati'."
        )
    col_chiusura, col_ateco = col_chiusura_hits[0], col_ateco_hits[0]

    raw = raw.copy()
    raw["company_id"] = np.arange(len(raw))
    raw["anno_chiusura_ultimo"] = pd.to_datetime(raw[col_chiusura]).dt.year

    metric_cols = [c for c in raw.columns
                   if c not in id_cols + [col_chiusura, col_ateco, "company_id", "anno_chiusura_ultimo"]]

    def parse_period(colname):
        if "Ultimo anno disp." in colname:
            return 0
        m = re.search(r"Anno - (\d+)", colname)
        return -int(m.group(1)) if m else None

    meta = pd.DataFrame({"colname": metric_cols})
    meta["metric"] = meta["colname"].map(lambda c: str(c).split("\n")[0])
    meta["t"] = meta["colname"].map(parse_period)
    meta = meta[meta["t"].notna()].copy()
    meta["t"] = meta["t"].astype(int)

    long = raw.melt(
        id_vars=["company_id", "Ragione sociale", "Provincia", "anno_chiusura_ultimo", col_ateco],
        value_vars=meta["colname"].tolist(), var_name="colname", value_name="value",
    )
    long = long.merge(meta, on="colname", how="left")
    long["anno"] = long["anno_chiusura_ultimo"] + long["t"]
    long = long.rename(columns={"Ragione sociale": "ragione_sociale", "Provincia": "provincia", col_ateco: "ateco"})
    long = long[["company_id", "ragione_sociale", "provincia", "ateco", "t", "anno", "metric", "value"]]

    wide = long.pivot_table(
        index=["company_id", "ragione_sociale", "provincia", "ateco", "t", "anno"],
        columns="metric", values="value", aggfunc="first",
    ).reset_index()
    wide.columns.name = None

    for pattern, newname in AIDA_RENAME_PATTERNS:
        hits = [c for c in wide.columns if re.search(pattern, str(c))]
        if hits:
            wide = wide.rename(columns={hits[0]: newname})

    mancanti = [c for c in AIDA_ESSENTIAL if c not in wide.columns]
    if mancanti:
        raise ValueError(
            "Colonne essenziali non trovate nel file AIDA (controlla i nomi "
            f"nell'export): {', '.join(mancanti)}"
        )

    for c in AIDA_ESSENTIAL:
        wide[c] = pd.to_numeric(wide[c], errors="coerce")

    wide["settore"] = wide["ateco"].map(classifica_settore)
    return wide.sort_values(["company_id", "anno"]).reset_index(drop=True)


def costruisci_dataset_reale(path):
    """Replica i passi 3-7 di backtest_aida_PMI_3.R e ritorna un dizionario
    con tutto cio' che serve per costruire il payload JSON della pagina."""
    panel = carica_aida_panel(path, CONFIG["aida_sheet"])
    panel = panel[panel["settore"].isin(CONFIG["settori_target"])].copy()

    n_target_t0 = panel[panel["t"] == 0].shape[0]

    orizz = CONFIG["orizzonte_anni"]
    fin = panel[(panel["t"] >= -orizz) & (panel["t"] <= 0)
                & panel["ricavi"].notna() & (panel["ricavi"] > 0)].copy()
    needed_t = set(range(-orizz, 1))
    complete = fin.groupby("company_id")["t"].apply(lambda s: needed_t.issubset(set(s)))
    fin = fin[fin["company_id"].isin(complete[complete].index)].copy()
    fin["costi_operativi"] = fin["ricavi"] - fin["ebitda"]
    fin["capitale_investito_netto"] = fin["patrimonio_netto"] + fin["pfn"]
    fin["costo_su_ricavi"] = fin["costi_operativi"] / fin["ricavi"]

    n_per_settore = fin[fin["t"] == 0].groupby("settore").size()
    settori_ok = [s for s in CONFIG["settori_target"] if n_per_settore.get(s, 0) >= CONFIG["min_aziende_per_settore"]]
    settori_scartati = [s for s in CONFIG["settori_target"] if s not in settori_ok]
    if not settori_ok:
        raise ValueError("Nessun settore ha abbastanza aziende con storico completo (min_aziende_per_settore).")
    fin = fin[fin["settore"].isin(settori_ok)].copy()

    bench = fin.groupby(["settore", "t"]).apply(lambda g: pd.Series({
        "ebitda_margin_obiettivo": g["ebitda_margin"].quantile(CONFIG["quantile_top"]),
        "roe_obiettivo": g["roe"].quantile(CONFIG["quantile_top"]),
        "rotazione_obiettivo": g["rotazione_ci"].quantile(CONFIG["quantile_top"]),
        "costo_su_ricavi_obiettivo": g["costo_su_ricavi"].quantile(CONFIG["quantile_costo_migliore"]),
    }), include_groups=False).reset_index()

    fin_full = fin.merge(bench, on=["settore", "t"], how="left")
    fin_full["costi_ipotetici"] = fin_full["ricavi"] * fin_full["costo_su_ricavi_obiettivo"]
    fin_full["capitale_investito_ipotetico"] = fin_full["ricavi"] / fin_full["rotazione_obiettivo"].clip(lower=0.05)

    candidati = fin[fin["t"] == 0][["company_id", "settore", "ragione_sociale", "ricavi"]]
    criterio = CONFIG["criterio_selezione"]
    n_pmi = CONFIG["n_pmi_per_settore"]
    if criterio == "top_ricavi":
        pmi_sel = candidati.sort_values("ricavi", ascending=False).groupby("settore").head(n_pmi)
    elif criterio == "mediane":
        def _pick_mediane(g):
            med = g["ricavi"].median()
            return g.assign(_d=(g["ricavi"] - med).abs()).sort_values("_d").head(n_pmi).drop(columns="_d")
        pmi_sel = candidati.groupby("settore", group_keys=False).apply(_pick_mediane)
    elif criterio == "casuali":
        pmi_sel = candidati.groupby("settore", group_keys=False).apply(
            lambda g: g.sample(n=min(n_pmi, len(g)), random_state=CONFIG["seed_selezione"])
        )
    else:
        raise ValueError("criterio_selezione non riconosciuto: usa 'top_ricavi', 'mediane' o 'casuali'")

    pmi_sel = pmi_sel.sort_values(["settore", "ricavi"], ascending=[True, False]).reset_index(drop=True)
    pmi_sel["anon_label"] = pmi_sel.groupby("settore").cumcount() + 1

    n_storico_completo = fin[fin["t"] == 0].shape[0]

    return dict(
        fin_full=fin_full,
        settori_ok=settori_ok,
        settori_scartati=settori_scartati,
        n_per_settore=n_per_settore,
        pmi_sel=pmi_sel,
        funnel=dict(nel_perimetro=n_target_t0, storico_completo=n_storico_completo, mostrate=len(pmi_sel)),
    )


# =========================================================================
# 3. DATASET DI ESEMPIO (fallback se non troviamo un export AIDA)
# =========================================================================
def costruisci_dataset_demo():
    """Dataset sintetico con LO STESSO schema di costruisci_dataset_reale():
    usato solo quando nessun export AIDA e' stato trovato accanto allo
    script, cosi' la pagina si puo' comunque generare e visionare. I valori
    sono plausibili e internamente coerenti (obiettivo di settore sempre
    migliore del reale), calibrati sull'ordine di grandezza osservato nei
    dati AIDA reali durante lo sviluppo di questa pagina."""
    rng = np.random.default_rng(7)
    orizz = CONFIG["orizzonte_anni"]
    t_vals = list(range(-orizz, 1))
    settori = CONFIG["settori_target"]
    n_per_settore_demo = 26

    rows = []
    for settore in settori:
        base_ricavi = rng.uniform(3000, 18000)  # migliaia di EUR
        for i in range(1, n_per_settore_demo + 1):
            company_id = f"{settore}_{i}"
            ricavi0 = base_ricavi * rng.uniform(0.4, 2.2)
            trend = rng.uniform(-0.01, 0.03)
            for t in t_vals:
                anni_indietro = -t
                ricavi = ricavi0 * ((1 - trend) ** anni_indietro) * rng.uniform(0.93, 1.07)
                ebitda_margin = float(np.clip(rng.normal(0.075, 0.035), -0.05, 0.30))
                ebitda = ricavi * ebitda_margin
                roe = float(np.clip(rng.normal(0.08, 0.06), -0.2, 0.4))
                rotazione_ci = float(max(0.3, rng.normal(1.4, 0.5)))
                patrimonio_netto = ricavi * rng.uniform(0.15, 0.4)
                pfn = ricavi * rng.uniform(0.05, 0.3)
                rows.append(dict(
                    company_id=company_id, settore=settore,
                    ragione_sociale=f"[demo] {company_id}",
                    t=t, anno=2025 + t,
                    ricavi=ricavi, ebitda=ebitda, ebitda_margin=ebitda_margin,
                    roe=roe, rotazione_ci=rotazione_ci,
                    patrimonio_netto=patrimonio_netto, pfn=pfn,
                ))
    fin = pd.DataFrame(rows)
    fin["costi_operativi"] = fin["ricavi"] - fin["ebitda"]
    fin["capitale_investito_netto"] = fin["patrimonio_netto"] + fin["pfn"]
    fin["costo_su_ricavi"] = fin["costi_operativi"] / fin["ricavi"]

    n_per_settore = fin[fin["t"] == 0].groupby("settore").size()
    settori_ok = list(settori)
    settori_scartati = []

    bench = fin.groupby(["settore", "t"]).apply(lambda g: pd.Series({
        "ebitda_margin_obiettivo": g["ebitda_margin"].quantile(CONFIG["quantile_top"]),
        "roe_obiettivo": g["roe"].quantile(CONFIG["quantile_top"]),
        "rotazione_obiettivo": g["rotazione_ci"].quantile(CONFIG["quantile_top"]),
        "costo_su_ricavi_obiettivo": g["costo_su_ricavi"].quantile(CONFIG["quantile_costo_migliore"]),
    }), include_groups=False).reset_index()
    fin_full = fin.merge(bench, on=["settore", "t"], how="left")
    fin_full["costi_ipotetici"] = fin_full["ricavi"] * fin_full["costo_su_ricavi_obiettivo"]
    fin_full["capitale_investito_ipotetico"] = fin_full["ricavi"] / fin_full["rotazione_obiettivo"].clip(lower=0.05)

    candidati = fin[fin["t"] == 0][["company_id", "settore", "ragione_sociale", "ricavi"]]
    n_pmi = CONFIG["n_pmi_per_settore"]
    pmi_sel = candidati.sort_values("ricavi", ascending=False).groupby("settore").head(n_pmi)
    pmi_sel = pmi_sel.sort_values(["settore", "ricavi"], ascending=[True, False]).reset_index(drop=True)
    pmi_sel["anon_label"] = pmi_sel.groupby("settore").cumcount() + 1

    n_storico_completo = fin[fin["t"] == 0].shape[0]
    n_target_t0 = int(n_storico_completo * 1.6)  # perimetro simulato, plausibile

    return dict(
        fin_full=fin_full, settori_ok=settori_ok, settori_scartati=settori_scartati,
        n_per_settore=n_per_settore, pmi_sel=pmi_sel,
        funnel=dict(nel_perimetro=n_target_t0, storico_completo=n_storico_completo, mostrate=len(pmi_sel)),
    )


# =========================================================================
# 4. SELEZIONE DATI: reali (export AIDA) con fallback al dataset di esempio
# =========================================================================
AIDA_PATH = find_aida_file()
USING_REAL_DATA = False
if AIDA_PATH:
    try:
        DATASET = costruisci_dataset_reale(AIDA_PATH)
        USING_REAL_DATA = True
        print(f"[i] Dati REALI caricati da: {AIDA_PATH}")
    except Exception as e:
        print(f"[!] File AIDA trovato ({AIDA_PATH}) ma non elaborabile: {e}")
        print("[!] Uso il dataset di esempio (demo).")
        DATASET = costruisci_dataset_demo()
else:
    print("[!] Nessun export AIDA trovato accanto allo script (ne' nella cartella superiore).")
    print(f"[!] Nomi cercati: {', '.join(CONFIG['aida_filename_candidates'])} (o qualsiasi *.xls con 'aida' nel nome)")
    print("[!] Uso il dataset di esempio (demo) — la pagina generata mostrera' dati sintetici.")
    DATASET = costruisci_dataset_demo()

print(f"Dati usati per la pagina: {'REALI (export AIDA)' if USING_REAL_DATA else 'DI ESEMPIO (nessun export AIDA trovato o elaborabile)'}")

fin_full = DATASET["fin_full"]
settori_ok = DATASET["settori_ok"]
settori_scartati = DATASET["settori_scartati"]
n_per_settore = DATASET["n_per_settore"]
pmi_sel = DATASET["pmi_sel"]
funnel = DATASET["funnel"]

# IMPORTANTE — privacy: le ragioni sociali reali vengono stampate SOLO qui,
# in console, per riferimento interno dell'utente. Non entrano mai nella
# pagina HTML ne' nel JSON incorporato: la dashboard pubblica usa solo
# etichette anonime ("Azienda N" per settore), come richiesto esplicitamente
# nei commenti dello script R di riferimento.
if USING_REAL_DATA:
    print("\n[i] PMI selezionate — SOLO per riferimento interno, MAI pubblicate sulla pagina:")
    for _, r in pmi_sel.iterrows():
        print(f"    {r['settore']} — Azienda {r['anon_label']}: {r['ragione_sociale']}  (ricavi t0 ≈ {r['ricavi']:.0f} migl EUR)")
    print()


# =========================================================================
# 5. COSTRUZIONE DEL PAYLOAD JSON PER LA DASHBOARD
# =========================================================================
OBIETTIVO_COL = {
    "ebitda_margin": "ebitda_margin_obiettivo",
    "roe": "roe_obiettivo",
    "rotazione_ci": "rotazione_obiettivo",
    "costi_operativi": "costi_ipotetici",
    "capitale_investito_netto": "capitale_investito_ipotetico",
}

def _clean(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return round(float(v), 4)

def metric_series(df_t_indexed, metric_id):
    """Ritorna (reale, obiettivo): due liste allineate a T_RANGE (None dove manca)."""
    obiettivo_col = OBIETTIVO_COL[metric_id]
    reale, obiettivo = [], []
    for t in T_RANGE:
        if t in df_t_indexed.index:
            row = df_t_indexed.loc[t]
            reale.append(_clean(row.get(metric_id)))
            obiettivo.append(_clean(row.get(obiettivo_col)))
        else:
            reale.append(None)
            obiettivo.append(None)
    return reale, obiettivo

def build_record(df, label, settore, is_aggregate, anno_ultimo=None):
    df_t = df.set_index("t")
    rec = dict(displayName=label, settore=settore, isAggregate=is_aggregate)
    if anno_ultimo is not None:
        rec["annoUltimo"] = int(anno_ultimo)
    for metric_id in METRIC_IDS:
        reale, obiettivo = metric_series(df_t, metric_id)
        rec[metric_id] = dict(reale=reale, obiettivo=obiettivo)
    return rec

companies = {}
company_order = []

pmi_ids = pmi_sel["company_id"]

overall_df = fin_full[fin_full["company_id"].isin(pmi_ids)].groupby("t").mean(numeric_only=True).reset_index()
companies["__ALL__"] = build_record(overall_df, "Media di tutte le PMI analizzate", None, True)

for settore in settori_ok:
    ids_s = pmi_sel[pmi_sel["settore"] == settore]["company_id"]
    df_s = fin_full[fin_full["company_id"].isin(ids_s)].groupby("t").mean(numeric_only=True).reset_index()
    companies[f"SETTORE::{settore}"] = build_record(df_s, f"Media settore — {settore}", settore, True)

for _, row in pmi_sel.iterrows():
    key = f"PMI::{row['settore']}::{row['anon_label']}"
    df_c = fin_full[fin_full["company_id"] == row["company_id"]]
    anno_ultimo = None
    if "anno" in df_c.columns:
        r0 = df_c[df_c["t"] == 0]
        if len(r0):
            anno_ultimo = r0.iloc[0]["anno"]
    label = f"Azienda {row['anon_label']}"
    companies[key] = build_record(df_c, label, row["settore"], False, anno_ultimo)
    company_order.append(key)

def val_at0(rec, metric_id, field):
    return rec[metric_id][field][-1]  # T_RANGE termina con t=0

t0_sel = fin_full[(fin_full["t"] == 0) & (fin_full["company_id"].isin(pmi_ids))]
risparmio_medio_t0 = float((t0_sel["costi_operativi"] - t0_sel["costi_ipotetici"]).mean())
capitale_liberabile_medio_t0 = float((t0_sel["capitale_investito_netto"] - t0_sel["capitale_investito_ipotetico"]).mean())

overall_rec = companies["__ALL__"]
meta = dict(
    settoriInclusi=settori_ok,
    settoriEsclusi=settori_scartati,
    criterioSelezione=CONFIG["criterio_selezione"],
    quantileTop=CONFIG["quantile_top"],
    quantileCosto=CONFIG["quantile_costo_migliore"],
    orizzonteAnni=CONFIG["orizzonte_anni"],
    minAziendePerSettore=CONFIG["min_aziende_per_settore"],
    nPmiPerSettore=CONFIG["n_pmi_per_settore"],
    perimetro=int(funnel["nel_perimetro"]),
    storicoCompleto=int(funnel["storico_completo"]),
    mostrate=int(funnel["mostrate"]),
    usingRealData=USING_REAL_DATA,
    ebitdaMarginRealeT0=val_at0(overall_rec, "ebitda_margin", "reale"),
    ebitdaMarginObiettivoT0=val_at0(overall_rec, "ebitda_margin", "obiettivo"),
    roeRealeT0=val_at0(overall_rec, "roe", "reale"),
    roeObiettivoT0=val_at0(overall_rec, "roe", "obiettivo"),
    rotazioneRealeT0=val_at0(overall_rec, "rotazione_ci", "reale"),
    rotazioneObiettivoT0=val_at0(overall_rec, "rotazione_ci", "obiettivo"),
    risparmioMedioT0=round(risparmio_medio_t0, 1),
    capitaleLiberabileMedioT0=round(capitale_liberabile_medio_t0, 1),
)

metrics_payload = [
    {k: m[k] for k in ("id", "titolo", "titoloBreve", "unita", "isPct", "migliore", "sezione")}
    for m in METRICHE
]

payload = dict(
    meta=meta,
    sectors=settori_ok,
    sectorColors=[SETTORE_COLOR_MAP[s] for s in settori_ok],
    sectorCounts=[int(n_per_settore.get(s, 0)) for s in settori_ok],
    metrics=metrics_payload,
    tRange=T_RANGE,
    tLabels=T_LABELS,
    funnel=dict(
        labels=["Nel perimetro (6 settori)", "Storico 5 anni completo", "PMI mostrate"],
        values=[int(funnel["nel_perimetro"]), int(funnel["storico_completo"]), int(funnel["mostrate"])],
    ),
    companies=companies,
    companyOrder=company_order,
)
PAYLOAD_JSON = json.dumps(payload, ensure_ascii=False)

N_SETTORI = len(settori_ok)
N_MOSTRATE = int(funnel["mostrate"])

DATA_BADGE = (
    '<span class="chip now">DATI REALI — BILANCI AIDA</span>' if USING_REAL_DATA else
    '<span class="chip past">DATI DI ESEMPIO</span>'
)
DATA_NOTE = (
    f"{N_MOSTRATE} PMI italiane reali (bilanci AIDA/Bureau van Dijk, ultimi {CONFIG['orizzonte_anni']} anni) su {N_SETTORI} settori, confrontate con il miglior quartile del proprio settore. Anonimizzate: mai il nome dell’azienda, solo “Azienda N”."
    if USING_REAL_DATA else
    "Nessun export AIDA trovato accanto allo script: questa è una versione dimostrativa con dati sintetici plausibili, solo per visionare la pagina prima di collegare i dati reali."
)

def fmt_pct(x, sign=True):
    if x is None:
        return "n.d."
    s = "+" if (sign and x >= 0) else ""
    return f"{s}{x*100:.1f}%"

def fmt_num(x, decimals=1):
    if x is None:
        return "n.d."
    return f"{x:,.{decimals}f}".replace(",", " ")


# =========================================================================
# 6. STILI CSS (design system Veyron — riutilizzati verbatim dalla v3.1)
# =========================================================================
BASE_CSS = r"""/* =========================================================
   VEYRON — Consulenza Data & AI per PMI
   Design system: enterprise tech / security-grade dark theme
   Display: Fraunces · UI/Body: Inter · Dati/Label: IBM Plex Mono
   ========================================================= */

:root{
  --ink:#F5F3EE;
  --ink-2:#EDEBE3;
  --ink-3:#E6E3D9;
  --paper:#151A21;
  --paper-dim:#5B6270;
  --paper-faint:#666C7E;
  --line:rgba(21,26,33,0.11);
  --line-strong:rgba(21,26,33,0.20);
  --teal:#0E3A5F;
  --teal-dim:rgba(14,58,95,0.12);
  --gold:#875C0E;
  --gold-dim:rgba(156,107,18,0.13);
  --secure:#2E7D46;
  --secure-dim:rgba(46,125,70,0.12);
  --mono:'IBM Plex Mono', 'SF Mono', monospace;
  --radius:3px;
  --teal-vivid:#1A62B0;
  --gold-vivid:#C27D0E;
  --maxw:1180px;
}

*{box-sizing:border-box; margin:0; padding:0;}

html{scroll-behavior:smooth;}
@media (prefers-reduced-motion: reduce){
  html{scroll-behavior:auto;}
  *{animation-duration:0.01ms !important; animation-iteration-count:1 !important; transition-duration:0.01ms !important;}
}

body{
  background:
    radial-gradient(ellipse 1000px 560px at 18% -8%, rgba(156,107,18,0.09), transparent 60%),
    radial-gradient(ellipse 1000px 620px at 100% 6%, rgba(14,58,95,0.1), transparent 55%),
    radial-gradient(ellipse 900px 700px at 50% 100%, rgba(156,107,18,0.045), transparent 60%),
    var(--ink);
  color:var(--paper);
  font-family:'Inter', -apple-system, "Segoe UI", sans-serif;
  font-size:16.5px;
  line-height:1.65;
  -webkit-font-smoothing:antialiased;
}

::selection{ background:var(--teal); color:var(--ink); }
a{ color:inherit; text-decoration:none; }

h1,h2,h3,.display{
  font-family:'Fraunces', Arial, sans-serif;
  font-weight:500;
  letter-spacing:-0.005em;
  line-height:1.14;
}

.label{
  font-family:'Inter', sans-serif;
  font-weight:600;
  font-size:12px;
  letter-spacing:0.14em;
  text-transform:uppercase;
}

.wrap{
  max-width:var(--maxw);
  margin:0 auto;
  padding:0 32px;
}

.eyebrow{
  font-family:'Inter', sans-serif;
  font-weight:600;
  font-size:12px;
  letter-spacing:0.16em;
  text-transform:uppercase;
  color:var(--gold);
  display:flex;
  align-items:center;
  gap:10px;
  margin-bottom:20px;
}
.eyebrow::before{
  content:"";
  width:22px;
  height:1px;
  background:var(--gold);
  display:inline-block;
}

:focus-visible{
  outline:2px solid var(--teal);
  outline-offset:3px;
}

.grid-veil{
  position:fixed; inset:0;
  background-image:
    linear-gradient(rgba(21,26,33,0.028) 1px, transparent 1px),
    linear-gradient(90deg, rgba(21,26,33,0.028) 1px, transparent 1px);
  background-size:64px 64px;
  -webkit-mask-image:radial-gradient(ellipse 80% 60% at 50% 0%, black, transparent 75%);
  mask-image:radial-gradient(ellipse 80% 60% at 50% 0%, black, transparent 75%);
  pointer-events:none;
  z-index:0;
}

header{
  position:fixed;
  top:0; left:0; right:0;
  z-index:100;
  padding:24px 0;
  transition:background 0.3s ease, padding 0.3s ease, border-color 0.3s ease;
  border-bottom:1px solid transparent;
}
header.scrolled{
  background:rgba(245,243,238,0.92);
  backdrop-filter:blur(14px);
  padding:16px 0;
  border-bottom:1px solid var(--line);
  box-shadow:0 12px 32px -16px rgba(0,0,0,0.55);
}
nav{
  display:flex;
  align-items:center;
  justify-content:space-between;
}
.logo{
  font-family:'Fraunces', sans-serif;
  font-weight:600;
  font-size:20px;
  letter-spacing:0.01em;
  display:flex;
  align-items:baseline;
  gap:10px;
}
.logo .dot{ color:var(--teal); }
.logo span{
  font-family:'Inter', sans-serif;
  font-weight:500;
  font-size:11px;
  letter-spacing:0.09em;
  color:var(--paper-dim);
  text-transform:uppercase;
}
.nav-links{
  display:flex;
  align-items:center;
  gap:34px;
  font-family:'Inter', sans-serif;
  font-weight:500;
  font-size:13.5px;
  letter-spacing:0.01em;
}
.nav-links a{
  color:var(--paper-dim);
  position:relative;
  padding:4px 0;
  transition:color 0.2s ease;
}
.nav-links a:hover, .nav-links a[aria-current="page"]{ color:var(--paper); }
.nav-links a::after{
  content:"";
  position:absolute; left:0; right:0; bottom:0;
  height:1px;
  background:var(--teal);
  transform:scaleX(0);
  transform-origin:left;
  transition:transform 0.25s ease;
}
.nav-links a:hover::after, .nav-links a[aria-current="page"]::after{ transform:scaleX(1); }

.nav-trailing{ display:flex; align-items:center; }

.btn{
  display:inline-flex;
  align-items:center;
  gap:8px;
  font-family:'Inter', sans-serif;
  font-weight:600;
  font-size:13.5px;
  letter-spacing:0.01em;
  padding:12px 22px;
  border-radius:var(--radius);
  border:1px solid var(--line-strong);
  cursor:pointer;
  transition:transform 0.3s cubic-bezier(.16,1,.3,1), box-shadow 0.3s cubic-bezier(.16,1,.3,1), background 0.25s ease, border-color 0.25s ease, color 0.25s ease;
  white-space:nowrap;
}
.btn-primary{
  background:var(--teal);
  color:var(--ink);
  border-color:var(--teal);
  box-shadow:0 1px 0 rgba(255,255,255,0.08) inset, 0 4px 14px -6px rgba(14,58,95,0.35);
}
.btn-primary:hover{ background:#164E7E; transform:translateY(-2px); box-shadow:0 1px 0 rgba(255,255,255,0.1) inset, 0 14px 30px -10px rgba(14,58,95,0.5); }
.btn-primary:active{ transform:translateY(0); }
.btn-ghost{
  color:var(--paper);
  border-color:var(--line-strong);
}
.btn-ghost:hover{ border-color:var(--teal); color:var(--teal); transform:translateY(-2px); }

.skip-link{
  position:absolute; left:16px; top:-60px;
  background:var(--teal); color:var(--ink);
  padding:10px 18px; border-radius:var(--radius);
  font-family:'Inter', sans-serif; font-weight:600; font-size:13px;
  z-index:300; transition:top 0.2s ease;
}
.skip-link:focus{ top:16px; }

.nav-toggle{
  display:none;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:5px;
  width:42px; height:42px;
  background:none;
  border:1px solid var(--line-strong);
  border-radius:var(--radius);
  cursor:pointer;
  padding:0;
  position:relative;
  z-index:210;
  flex:none;
}
.nav-toggle span{
  display:block;
  width:18px; height:1.5px;
  background:var(--paper);
  transition:transform 0.25s ease, opacity 0.2s ease;
}
.nav-toggle[aria-expanded="true"] span:nth-child(1){ transform:translateY(6.5px) rotate(45deg); }
.nav-toggle[aria-expanded="true"] span:nth-child(2){ opacity:0; }
.nav-toggle[aria-expanded="true"] span:nth-child(3){ transform:translateY(-6.5px) rotate(-45deg); }

.mobile-nav{
  position:fixed; inset:0;
  background:rgba(245,243,238,0.98);
  backdrop-filter:blur(14px);
  z-index:200;
  display:flex;
  align-items:center;
  justify-content:center;
  opacity:0;
  visibility:hidden;
  transform:translateY(-10px);
  transition:opacity 0.25s ease, transform 0.25s ease, visibility 0s linear 0.25s;
}
.mobile-nav nav{
  display:flex;
  flex-direction:column;
  align-items:center;
  gap:6px;
}
.mobile-nav.open{
  opacity:1; visibility:visible; transform:translateY(0);
  transition:opacity 0.25s ease, transform 0.25s ease;
}
.mobile-nav a{
  font-family:'Fraunces', sans-serif;
  font-size:26px;
  font-weight:500;
  color:var(--paper);
  padding:12px 0;
}
.mobile-nav a[aria-current="page"]{ color:var(--teal); }
.mobile-nav .btn-primary{ margin-top:28px; }
body.nav-open{ overflow:hidden; }

@media (max-width: 860px){
  .nav-toggle{ display:flex; }
}

.page-hero{
  position:relative;
  padding:172px 0 96px;
  z-index:1;
  border-bottom:1px solid var(--line);
}
@keyframes fadeInUp{
  from{ opacity:0; transform:translateY(14px); }
  to{ opacity:1; transform:translateY(0); }
}
.page-hero .eyebrow{ justify-content:flex-start; animation:fadeInUp 0.7s ease both; }
.page-hero h1{
  font-size:clamp(32px, 4.6vw, 52px);
  max-width:20ch;
  animation:fadeInUp 0.7s ease 0.08s both;
}
.page-hero p{
  margin-top:22px;
  max-width:60ch;
  font-size:17.5px;
  color:var(--paper-dim);
  animation:fadeInUp 0.7s ease 0.16s both;
}

section{
  padding:120px 0;
  position:relative;
  z-index:1;
}
section.alt{ background:var(--ink-2); border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
section.tight{ padding:88px 0; }

[data-reveal]{
  opacity:0;
  transform:translateY(22px);
  transition:opacity 0.7s ease, transform 0.7s ease;
}
[data-reveal].in-view{ opacity:1; transform:translateY(0); }

.chip{
  font-family:'Inter', sans-serif;
  font-weight:600;
  font-size:12.5px;
  letter-spacing:0.07em;
  text-transform:uppercase;
  padding:10px 18px;
  border:1px solid var(--line-strong);
  border-radius:var(--radius);
}
.chip.past{ border-color:rgba(91,98,112,0.5); color:var(--paper-dim); }
.chip.now{ border-color:rgba(14,58,95,0.5); color:var(--teal); }
.chip.future{ border-color:rgba(156,107,18,0.5); color:var(--gold); }

.final-cta{ text-align:center; padding:150px 0; }
.final-cta h2{ font-size:clamp(30px, 4.6vw, 50px); font-weight:500; max-width:18ch; margin:0 auto 18px; }
.final-cta p{ color:var(--paper-dim); max-width:44ch; margin:0 auto 40px; }

footer{ border-top:1px solid var(--line); padding:56px 0 40px; position:relative; z-index:1; }
.footer-top{
  display:grid;
  grid-template-columns:1.4fr 1fr 1fr 1fr;
  gap:40px;
  padding-bottom:40px;
  margin-bottom:32px;
  border-bottom:1px solid var(--line);
}
.footer-brand .logo{ margin-bottom:14px; }
.footer-brand p{ color:var(--paper-dim); font-size:14px; max-width:32ch; }
.footer-col .label{ color:var(--paper-dim); margin-bottom:16px; display:block; }
.footer-col a{
  display:block;
  color:var(--paper-dim);
  font-size:14px;
  padding:6px 0;
  transition:color 0.2s ease;
}
.footer-col a:hover{ color:var(--teal); }
.footer-legal-links{ display:flex; gap:18px; }
.footer-legal-links a:hover{ color:var(--teal); }
.footer-row{
  display:flex; justify-content:space-between; align-items:center;
  font-family:'Inter', sans-serif; font-size:13px; color:var(--paper-faint); letter-spacing:0.01em;
}
.placeholder{background:var(--gold-dim);color:var(--gold);padding:1px 6px;border-radius:2px;font-size:0.92em}
.footer-company{font-family:'Inter', sans-serif;font-size:12.5px;color:var(--paper-faint);margin-top:18px;line-height:1.7}


.status-indicator{
  display:flex; align-items:center; gap:9px;
  font-family:var(--mono);
  font-size:11px;
  letter-spacing:0.03em;
  color:var(--paper-faint);
  padding-right:22px;
  margin-right:6px;
  border-right:1px solid var(--line-strong);
}
.status-dot{
  width:7px; height:7px;
  border-radius:50%;
  background:var(--secure);
  flex:none;
  box-shadow:0 0 0 0 rgba(46,125,70,0.5);
  animation:statusPulse 2.4s ease-in-out infinite;
}
@keyframes statusPulse{
  0%{ box-shadow:0 0 0 0 rgba(46,125,70,0.45); }
  70%{ box-shadow:0 0 0 6px rgba(46,125,70,0); }
  100%{ box-shadow:0 0 0 0 rgba(46,125,70,0); }
}
@media (max-width: 1080px){ .status-indicator{ display:none; } }

.grain-veil{
  position:fixed; inset:0;
  z-index:0;
  pointer-events:none;
  opacity:0.035;
  mix-blend-mode:overlay;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

.scroll-progress{
  position:fixed; top:0; left:0;
  height:2px; width:0%;
  background:linear-gradient(90deg, var(--teal), var(--gold));
  z-index:400;
  box-shadow:0 0 12px rgba(14,58,95,0.5);
}

.value-card, .stat-cell, .security-card, .kpi-card, .chart-card{ position:relative; }
.value-card::before, .stat-cell::before, .security-card::before{
  content:"";
  position:absolute; top:0; left:0;
  width:12px; height:12px;
  border-top:1.5px solid var(--teal);
  border-left:1.5px solid var(--teal);
  opacity:0.5;
}

.kpi-card, .chart-card{
  transition:transform 0.45s cubic-bezier(.16,1,.3,1), box-shadow 0.45s cubic-bezier(.16,1,.3,1), background 0.3s ease;
}
.kpi-card:hover, .chart-card:hover{
  transform:translateY(-4px);
  box-shadow:0 22px 44px -18px rgba(0,0,0,0.55), 0 0 0 1px rgba(14,58,95,0.16);
  z-index:2;
}

html{ overflow-x:hidden; }
body{ overflow-x:hidden; -webkit-text-size-adjust:100%; }
img, svg{ max-width:100%; }

@media (max-width: 1080px){
  .wrap{ padding:0 28px; }
}
@media (max-width: 860px){
  .wrap{ padding:0 22px; }
  .nav-links{ display:none; }
  .nav-trailing .btn-ghost{ display:none; }
  .logo span{ display:none; }
  .hero{ min-height:auto; padding-top:126px; padding-bottom:64px; }
  .final-cta{ padding:110px 0; }
}
@media (max-width: 640px){
  body{ font-size:16px; }
  section{ padding:72px 0; }
  section.tight{ padding:56px 0; }
  .page-hero{ padding:130px 0 56px; }
  .page-hero h1{ max-width:none; }
  .final-cta{ padding:88px 0; }
}
@media (max-width: 400px){
  .wrap{ padding:0 18px; }
  .btn{ padding:12px 18px; font-size:13px; }
}
"""

EXTRA_CSS = r"""
/* =========================================================
   BACKTEST / ANALISI DI BILANCIO / IMPATTO POTENZIALE — stili aggiuntivi
   (estendono il design system esistente, nessuna variabile ridefinita)
   ========================================================= */
.fin-section-head{ max-width:64ch; margin-bottom:56px; }
.fin-section-head h2{ font-size:clamp(26px, 3.2vw, 36px); font-weight:500; }
.fin-section-head p{ color:var(--paper-dim); margin-top:14px; max-width:58ch; font-size:15.5px; }

.kpi-grid{
  display:grid; grid-template-columns:repeat(4, 1fr); gap:1px;
  background:var(--line); border:1px solid var(--line); margin-top:44px;
}
.kpi-card{ background:var(--ink-2); padding:26px 22px; position:relative; }
.kpi-card .kpi-label{
  font-family:'Inter', sans-serif; font-weight:600; font-size:10.5px;
  letter-spacing:0.08em; text-transform:uppercase; color:var(--paper-dim); margin-bottom:10px;
}
.kpi-card .kpi-num{ font-family:var(--mono); font-weight:500; font-size:24px; color:var(--teal); text-shadow:0 0 22px rgba(14,58,95,0.28); }
.kpi-card .kpi-num.gold{ color:var(--gold); text-shadow:0 0 22px rgba(156,107,18,0.3); }
.kpi-card .kpi-num.rose{ color:#A63D3D; text-shadow:0 0 22px rgba(166,61,61,0.3); }
.kpi-card .kpi-sub{ margin-top:6px; font-size:12px; color:var(--paper-faint); }

.chart-row{ display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--line); border:1px solid var(--line); margin-top:32px; }
.chart-row.wide{ grid-template-columns:1fr 1.35fr; }
.chart-row.featured{ border-color:var(--line-strong); box-shadow:0 0 0 1px rgba(14,58,95,0.18); }
.chart-row.featured .chart-card::before{ border-color:var(--teal); opacity:0.85; width:16px; height:16px; }
.chart-card{ background:var(--ink); padding:32px 30px; position:relative; }
.chart-card::before{
  content:""; position:absolute; top:0; left:0; width:12px; height:12px;
  border-top:1.5px solid var(--teal); border-left:1.5px solid var(--teal); opacity:0.5;
}
.chart-card h3{ font-size:16.5px; font-weight:500; margin-bottom:4px; }
.chart-card .chart-sub{ font-size:13px; color:var(--paper-dim); margin-bottom:18px; }
.ring-card{ display:flex; flex-direction:column; align-items:center; text-align:center; }
.ring-svg{ margin:8px 0 18px; }
.legend-row{ display:flex; flex-wrap:wrap; gap:14px 22px; margin-top:16px; justify-content:center; }
.legend-item{ display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--paper-dim); font-family:'Inter', sans-serif; }
.legend-item b{ color:var(--paper); font-weight:600; font-family:var(--mono); }
.legend-dot{ width:8px; height:8px; border-radius:50%; flex:none; }

.donut-wrap{ display:flex; justify-content:center; }

.summary-list{ margin-top:18px; width:100%; }
.summary-line{ display:flex; justify-content:space-between; padding:11px 0; border-top:1px solid var(--line); font-size:13.5px; }
.summary-line:first-child{ border-top:none; }
.summary-line span:first-child{ color:var(--paper-dim); }
.summary-line span:last-child{ color:var(--paper); font-weight:600; font-family:var(--mono); }

.disclaimer-block{
  margin-top:56px; padding:22px 26px; border:1px solid var(--line-strong); border-left:2px solid var(--gold);
  background:var(--ink-2); font-size:13.5px; color:var(--paper-dim); line-height:1.6;
}
.disclaimer-block b{ color:var(--paper); }
.disclaimer-block.teal{ border-left-color:var(--teal); }
.disclaimer-small{ margin-top:20px; font-size:12px; color:var(--paper-faint); line-height:1.5; }
.databadge-row{ display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-top:28px; }
.databadge-row p{ font-size:13px; color:var(--paper-faint); margin:0; max-width:60ch; }

/* --- controlli interattivi -------------------------------------------- */
.control-bar{
  display:flex; align-items:center; gap:18px; flex-wrap:wrap;
  margin-top:40px; padding:20px 24px; background:var(--ink-2); border:1px solid var(--line-strong);
}
.control-bar .control-field{ display:flex; align-items:center; gap:12px; }
.control-bar label{
  font-family:'Inter', sans-serif; font-weight:600; font-size:11px; letter-spacing:0.08em;
  text-transform:uppercase; color:var(--paper-dim); white-space:nowrap;
}
select.veyron-select, select.veyron-select option, select.veyron-select optgroup{ font-family:'Inter', -apple-system, 'Segoe UI', sans-serif; }
select.veyron-select{
  background:var(--ink); color:var(--paper); border:1px solid var(--line-strong); border-radius:var(--radius);
  padding:10px 14px; font-size:14px; font-weight:500; cursor:pointer; min-width:240px;
}
select.veyron-select:focus{ outline:2px solid var(--teal); outline-offset:2px; }
#companyHint{ font-size:12.5px; color:var(--paper-faint); margin-left:auto; }

.company-summary{
  display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:1px; background:var(--line);
  border:1px solid var(--line); margin-top:1px;
}
.company-summary .cs-item{ background:var(--ink); padding:18px 16px; }
.company-summary .cs-label{ font-size:10px; text-transform:uppercase; letter-spacing:0.07em; color:var(--paper-dim); font-family:'Inter', sans-serif; font-weight:600; }
.company-summary .cs-val{ font-family:var(--mono); font-size:20px; font-weight:600; color:var(--teal-vivid); margin-top:8px; }
.company-summary .cs-val-sub{ font-family:var(--mono); font-size:12px; color:var(--paper-faint); margin-top:4px; }

.chart-canvas-wrap{ position:relative; height:270px; }
.chart-canvas-wrap.tall{ height:310px; }
.chart-canvas-wrap.short{ height:220px; }

.compare-toggle{ display:flex; align-items:center; gap:8px; margin:14px 0 0; font-size:12.5px; color:var(--paper-dim); }
.compare-toggle input{ accent-color:var(--teal); width:14px; height:14px; }

/* --- griglia di 3 grafici (metriche "di livello") ---------------------- */
.chart-row.triple{ grid-template-columns:repeat(3, 1fr); }
.chart-row.triple .chart-card{ padding:26px 22px; }

/* --- badge risultato (reale vs obiettivo) sopra un grafico -------------- */
.gap-badges{ display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; }
.gap-badge{
  font-family:var(--mono); font-size:12.5px; padding:6px 12px; border-radius:var(--radius);
  border:1px solid var(--line-strong); color:var(--paper-dim);
}
.gap-badge b{ color:var(--paper); font-weight:600; }
.gap-badge.teal{ border-color:rgba(14,58,95,0.4); color:var(--teal); }
.gap-badge.gold{ border-color:rgba(156,107,18,0.4); color:var(--gold); }

@media (max-width: 980px){
  .kpi-grid{ grid-template-columns:1fr 1fr; }
  .chart-row, .chart-row.wide, .chart-row.triple{ grid-template-columns:1fr; }
  .company-summary{ grid-template-columns:1fr 1fr; }
}
@media (max-width: 640px){
  .kpi-grid{ grid-template-columns:1fr; }
  .company-summary{ grid-template-columns:1fr; }
  .control-bar{ flex-direction:column; align-items:stretch; }
  .control-bar .control-field{ flex-direction:column; align-items:stretch; }
  #companyHint{ margin-left:0; }
  select.veyron-select{ min-width:0; width:100%; }
}
"""


# =========================================================================
# 7. TEMPLATE HTML
# =========================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Benchmark &amp; Analisi di Bilancio — Veyron</title>
<meta name="description" content="Benchmark su bilanci reali di PMI italiane: confronto tra risultati effettivi e obiettivo di settore, azienda per azienda, con dati AIDA anonimizzati.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Veyron">
<meta property="og:title" content="Benchmark &amp; Analisi di Bilancio — Veyron">
<meta property="og:description" content="Benchmark su bilanci reali di PMI italiane: risultati effettivi vs obiettivo di settore, azienda per azienda.">
<meta name="twitter:card" content="summary">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://www.veyron.it/backtest.html">
<meta name="theme-color" content="#F5F3EE">
<meta property="og:url" content="https://www.veyron.it/backtest.html">
<meta property="og:image" content="https://www.veyron.it/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://www.veyron.it/og-image.png">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E%3Crect width=%2732%27 height=%2732%27 rx=%273%27 fill=%27%23151A21%27/%3E%3Crect x=%271%27 y=%271%27 width=%2730%27 height=%2730%27 rx=%272%27 fill=%27none%27 stroke=%27%232FC6B8%27 stroke-opacity=%270.4%27/%3E%3Ctext x=%2716%27 y=%2722%27 font-family=%27Arial,sans-serif%27 font-size=%2717%27 font-weight=%27700%27 text-anchor=%27middle%27 fill=%27%232FC6B8%27%3EV%3C/text%3E%3C/svg%3E">
<link rel="preload" href="fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/fraunces-latin-opsz-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="fonts/fonts.css">
<style>
___BASE_CSS___
___EXTRA_CSS___

/* ---- Hero con foto su sfondo blu (come le altre pagine) ---- */
.page-hero.photo-hero{ padding:0; border-bottom:none; }
.page-hero.photo-hero .hero-media{
  position:relative; overflow:hidden; isolation:isolate;
  padding:172px 0 92px; background:#151a21;
}
.page-hero.photo-hero .hero-media img{
  position:absolute; inset:0; width:100%; height:100%; object-fit:cover;
  filter:grayscale(100%) contrast(1.08) brightness(.62);
  z-index:0; color:transparent;
}
.page-hero.photo-hero .hero-media::before{
  content:""; position:absolute; inset:0;
  background:linear-gradient(180deg,rgba(10,32,56,.6) 0%,rgba(10,32,56,.75) 55%,rgba(10,32,56,.92) 100%);
  z-index:1;
}
.page-hero.photo-hero .wrap{ position:relative; z-index:2; }
.page-hero.photo-hero .eyebrow{ color:var(--ink-3); }
.page-hero.photo-hero .eyebrow::before{ background:var(--ink-3); }
.page-hero.photo-hero h1{ color:var(--ink); }
.page-hero.photo-hero p{ color:rgba(245,243,238,0.86); }
body.photo-topbar header:not(.scrolled) .nav-links a{ color:rgba(245,243,238,0.86); }
body.photo-topbar header:not(.scrolled) .nav-links a:hover,
body.photo-topbar header:not(.scrolled) .nav-links a[aria-current="page"]{ color:var(--ink); }
body.photo-topbar header:not(.scrolled) .nav-links a::after{ background:var(--ink); }
body.photo-topbar header:not(.scrolled) .logo{ color:var(--ink); }
body.photo-topbar header:not(.scrolled) .logo span{ color:rgba(245,243,238,0.72); }
body.photo-topbar header:not(.scrolled) .btn-ghost{ color:var(--ink); border-color:rgba(245,243,238,0.4); }
body.photo-topbar header:not(.scrolled) .btn-ghost:hover{ border-color:var(--ink); color:var(--ink); background:rgba(245,243,238,0.1); }
body.photo-topbar header:not(.scrolled) .nav-toggle span{ background:var(--ink); }
body.photo-topbar header:not(.scrolled) .nav-toggle{ border-color:rgba(245,243,238,0.4); }
/* filtri e badge dati sotto l'hero */
.bench-tools{ padding:44px 0 72px; border-bottom:1px solid var(--line); }
@media (max-width:860px){
  .page-hero.photo-hero .hero-media{ padding:126px 0 64px; }
  .bench-tools{ padding:32px 0 56px; }
}
</style>
</head>
<body class="photo-topbar">

<div class="scroll-progress" aria-hidden="true"></div>
<div class="grid-veil" aria-hidden="true"></div>
<div class="grain-veil" aria-hidden="true"></div>
<a class="skip-link" href="#main-content">Vai al contenuto</a>

<header id="siteHeader">
  <div class="wrap">
    <nav>
      <a class="logo" href="index.html">VEYRON<span class="dot">.</span> <span>Consulenza Data &amp; AI</span></a>
      <div class="nav-links">
        <a href="chi-siamo.html">Chi Siamo</a>
        <a href="metodo.html">Metodo</a>
        <a href="soluzioni.html">Soluzioni</a>
        <a href="risultati.html">Risultati</a>
        <a href="backtest.html" aria-current="page">Backtest</a>
        <a href="contatti.html">Contatti</a>
      </div>
      <button class="nav-toggle" id="navToggle" type="button" aria-label="Apri il menu" aria-expanded="false" aria-controls="mobileNav"><span></span><span></span><span></span></button>
      <div class="nav-trailing">
        <a href="contatti.html" class="btn btn-ghost">Prenota una call</a>
      </div>
    </nav>
  </div>
</header>

<div class="mobile-nav" id="mobileNav" aria-hidden="true">
  <nav aria-label="Menu mobile">
    <a href="chi-siamo.html">Chi Siamo</a>
      <a href="metodo.html">Metodo</a>
      <a href="soluzioni.html">Soluzioni</a>
      <a href="risultati.html">Risultati</a>
      <a href="backtest.html" aria-current="page">Backtest</a>
      <a href="contatti.html">Contatti</a>
    <a href="contatti.html" class="btn btn-primary">Prenota una call</a>
  </nav>
</div>

<main id="main-content">

  <section class="page-hero photo-hero">
    <div class="hero-media">
      <img src="img/hero-benchmark.jpg" alt="Scrivania con smartphone, calcolatrice e grafici di un report finanziario" loading="eager" width="2000" height="1333">
      <div class="wrap">
      <div class="eyebrow">Benchmark &amp; Analisi di Bilancio</div>
      <h1>30 PMI italiane a confronto con il miglior quartile del loro settore</h1>
      <p>La stessa domanda che ci poniamo per una PMI cliente — su quali voci di bilancio può migliorare, e quanto — qui la testiamo su ___N_MOSTRATE___ PMI italiane reali (dati AIDA/Bureau van Dijk), confrontando ogni azienda con il miglior quartile del proprio settore negli ultimi ___ORIZZONTE___ anni. Nessun nome d’azienda è pubblicato: solo etichette anonime.</p>
      </div>
    </div>
  </section>

  <section class="bench-tools">
    <div class="wrap">
      <div class="databadge-row">
        ___DATA_BADGE___
        <p>___DATA_NOTE___</p>
      </div>

      <div class="control-bar" data-reveal>
        <div class="control-field">
          <label for="companySelect">Esplora azienda</label>
          <select id="companySelect" class="veyron-select" aria-label="Scegli un'azienda anonimizzata da esplorare"></select>
        </div>
        <div class="control-field">
          <label for="sectorSelect">Media per settore</label>
          <select id="sectorSelect" class="veyron-select" aria-label="Scegli un settore per vedere la sua media"></select>
        </div>
        <span id="companyHint">Scegli un'azienda o un settore; lascia "Media di tutte le PMI" per la vista aggregata.</span>
      </div>
      <div class="company-summary" id="companySummary" hidden></div>
    </div>
  </section>

  <!-- ===================== FATTORI CHIAVE ===================== -->
  <section>
    <div class="wrap">
      <div class="fin-section-head" data-reveal>
        <div class="eyebrow">Fattori chiave</div>
        <h2>Cosa misura questo benchmark</h2>
        <p>___N_MOSTRATE___ PMI italiane reali, ___N_SETTORI___ settori, storico di bilancio completo sugli ultimi ___ORIZZONTE___ anni. Per ogni azienda e ogni anno confrontiamo il risultato reale con l’“obiettivo”: il valore del miglior quartile (75°/25° percentile) tra le aziende comparabili dello stesso settore e dello stesso anno relativo — nessun dato futuro, nessun look-ahead.</p>
      </div>
      <div class="kpi-grid" data-reveal>
        <div class="kpi-card"><div class="kpi-label">EBITDA/Vendite — reale</div><div class="kpi-num">___KPI_EBITDA_REALE___</div><div class="kpi-sub">media di tutte le PMI, ultimo anno</div></div>
        <div class="kpi-card"><div class="kpi-label">EBITDA/Vendite — obiettivo</div><div class="kpi-num gold">___KPI_EBITDA_OBIETTIVO___</div><div class="kpi-sub">miglior quartile di settore</div></div>
        <div class="kpi-card"><div class="kpi-label">ROE — reale</div><div class="kpi-num">___KPI_ROE_REALE___</div><div class="kpi-sub">media di tutte le PMI, ultimo anno</div></div>
        <div class="kpi-card"><div class="kpi-label">ROE — obiettivo</div><div class="kpi-num gold">___KPI_ROE_OBIETTIVO___</div><div class="kpi-sub">miglior quartile di settore</div></div>
        <div class="kpi-card"><div class="kpi-label">Rotazione capitale investito</div><div class="kpi-num" style="color:var(--paper-dim); text-shadow:none;">___KPI_ROTAZIONE_REALE___</div><div class="kpi-sub">media di tutte le PMI, ultimo anno</div></div>
        <div class="kpi-card"><div class="kpi-label">Costi riducibili in teoria (media)</div><div class="kpi-num ___KPI_RISPARMIO_CLASS___">___KPI_RISPARMIO___</div><div class="kpi-sub">___KPI_RISPARMIO_SUB___</div></div>
        <div class="kpi-card"><div class="kpi-label">Capitale investito vs obiettivo (media)</div><div class="kpi-num ___KPI_CAPITALE_CLASS___">___KPI_CAPITALE___</div><div class="kpi-sub">___KPI_CAPITALE_SUB___</div></div>
        <div class="kpi-card"><div class="kpi-label">Fonte dati</div><div class="kpi-num" style="font-size:15.5px; color:var(--paper-dim); text-shadow:none;">AIDA · Bureau van Dijk</div><div class="kpi-sub">bilanci ufficiali, PMI anonimizzate</div></div>
      </div>

      <div class="chart-row wide" data-reveal>
        <div class="chart-card">
          <h3>Composizione per settore</h3>
          <div class="chart-sub">PMI con storico di bilancio completo, per settore — passa il mouse per i dettagli</div>
          <div class="donut-wrap"><div class="chart-canvas-wrap tall" style="width:260px;"><canvas id="chartSectorDonut"></canvas></div></div>
          <div class="legend-row" id="legendSector"></div>
        </div>
        <div class="chart-card">
          <h3>Dal perimetro alle PMI mostrate</h3>
          <div class="chart-sub">quante aziende nei 6 settori target hanno uno storico di bilancio completo, e quante vengono mostrate qui</div>
          <div class="chart-canvas-wrap tall"><canvas id="chartFunnel"></canvas></div>
        </div>
      </div>
    </div>
  </section>

  <!-- ===================== ANALISI DI BILANCIO ===================== -->
  <section class="alt">
    <div class="wrap">
      <div class="fin-section-head" data-reveal>
        <div class="eyebrow">Analisi di Bilancio</div>
        <h2>Reale vs obiettivo di settore, anno per anno</h2>
        <p>Il divario tra risultato reale e obiettivo di settore è persistente nel tempo, non un caso isolato di un singolo anno. Qui sotto la media di tutte le PMI analizzate; più in basso puoi esplorare azienda per azienda o settore per settore con il selettore in cima alla pagina.</p>
      </div>
      <div class="chart-row featured" data-reveal>
        <div class="chart-card">
          <h3>EBITDA/Vendite: reale vs obiettivo</h3>
          <div class="chart-sub">media di tutte le PMI analizzate, per anno (obiettivo = miglior quartile del settore)</div>
          <div class="chart-canvas-wrap"><canvas id="chartFeaturedEbitda"></canvas></div>
        </div>
        <div class="chart-card">
          <h3>ROE: reale vs obiettivo</h3>
          <div class="chart-sub">stesso confronto sulla redditività del capitale proprio</div>
          <div class="chart-canvas-wrap"><canvas id="chartFeaturedRoe"></canvas></div>
        </div>
      </div>
      <div class="disclaimer-block teal" data-reveal>
        <b>Perché conta per una PMI.</b> Lo stesso principio — confrontare i bilanci storici con il miglior quartile di aziende comparabili, per capire quali voci hanno più margine di miglioramento — è quello che applichiamo ai dati di una singola azienda cliente: non per confrontarla con l'intero mercato, ma per indicare su quali metriche intervenire per prime.
      </div>
      <div class="disclaimer-block" data-reveal>
        <b>Metodo e limiti.</b> Questo è un benchmark, non una previsione: confrontiamo i bilanci storici di ciascuna azienda con il miglior quartile del suo settore, senza testare modelli predittivi. Il campione è di 30 PMI in 6 settori: indica un ordine di grandezza, non una stima valida per ogni azienda. Le medie sono sensibili ai valori estremi e il miglior quartile è un riferimento ambizioso, non un obiettivo realistico per tutte. Un valore negativo di capitale investito indica che l'azienda usa già meno capitale del livello richiesto dal benchmark. Il risparmio sui costi è un potenziale teorico e non tiene conto di vincoli operativi.
      </div>

      <div class="fin-section-head" data-reveal style="margin-top:56px; margin-bottom:0;">
        <h3 id="detailTitle" style="font-size:20px; font-weight:500;">Le tre metriche di bilancio, azienda per azienda</h3>
        <p id="detailSub" style="margin-top:8px; font-size:14.5px;">Media di tutte le PMI analizzate — usa il selettore in cima alla pagina per vedere una singola azienda o la media di un settore.</p>
      </div>
      <div class="chart-row triple" data-reveal style="margin-top:24px;">
        <div class="chart-card">
          <h3 style="font-size:14.5px;">EBITDA/Vendite</h3>
          <div class="chart-canvas-wrap short"><canvas id="chartDetailEbitda"></canvas></div>
        </div>
        <div class="chart-card">
          <h3 style="font-size:14.5px;">ROE</h3>
          <div class="chart-canvas-wrap short"><canvas id="chartDetailRoe"></canvas></div>
        </div>
        <div class="chart-card">
          <h3 style="font-size:14.5px;">Rotazione capitale investito</h3>
          <div class="chart-canvas-wrap short"><canvas id="chartDetailRotazione"></canvas></div>
        </div>
      </div>
    </div>
  </section>

  <!-- ===================== IMPATTO POTENZIALE ===================== -->
  <section>
    <div class="wrap">
      <div class="fin-section-head" data-reveal>
        <div class="eyebrow">Impatto Potenziale</div>
        <h2 id="impattoTitle">Quanto vale, in euro, colmare il divario</h2>
        <p id="impattoDesc">Le stesse due metriche tradotte in euro: quanto costerebbe operare come il miglior quartile del settore (costi operativi), e quanto capitale investito netto servirebbe per generare lo stesso fatturato con la stessa efficienza. Valori per l'azienda o il settore selezionato in cima alla pagina, o per la media di tutte le PMI.</p>
      </div>
      <div class="chart-row" data-reveal>
        <div class="chart-card">
          <h3>Costi operativi: reale vs ipotetico</h3>
          <div class="chart-sub" id="costiSub">media di tutte le PMI — migliaia di EUR, per anno</div>
          <div class="chart-canvas-wrap"><canvas id="chartCosti"></canvas></div>
        </div>
        <div class="chart-card">
          <h3>Capitale investito netto: reale vs ipotetico</h3>
          <div class="chart-sub" id="capitaleSub">migliaia di EUR, per anno</div>
          <div class="chart-canvas-wrap"><canvas id="chartCapitale"></canvas></div>
        </div>
      </div>

      <div class="chart-row wide" data-reveal style="margin-top:1px;">
        <div class="chart-card ring-card">
          <h3 id="ringTitle">Risparmio potenziale sui costi</h3>
          <div class="chart-sub" id="ringSub">% di riduzione dei costi operativi verso l'obiettivo, ultimo anno</div>
          <svg class="ring-svg" viewBox="0 0 190 190" width="190" height="190" role="img" aria-label="percentuale di risparmio potenziale">
            <circle cx="95" cy="95" r="87" fill="none" stroke="rgba(21,26,33,0.10)" stroke-width="16"/>
            <circle id="ringProgress" cx="95" cy="95" r="87" fill="none" stroke="#2E7D46" stroke-width="16"
              stroke-dasharray="0 1000" stroke-linecap="round" transform="rotate(-90 95 95)"/>
            <text id="ringText" x="95" y="103" text-anchor="middle" font-family="'IBM Plex Mono', monospace" font-weight="600" font-size="34" fill="#2E7D46">0%</text>
          </svg>
          <div class="summary-list" id="summaryList"></div>
        </div>
        <div class="chart-card">
          <h3>Rotazione del capitale investito: reale vs obiettivo</h3>
          <div class="chart-sub">quante volte il capitale investito si "gira" in ricavi — più alto è meglio</div>
          <div class="chart-canvas-wrap"><canvas id="chartRotazioneWide"></canvas></div>
        </div>
      </div>

      <div class="disclaimer-block" data-reveal>
        <b>Nota metodologica.</b> L'obiettivo di settore è calcolato sul miglior quartile (75° percentile per le metriche "più alto è meglio"; 25° percentile sul rapporto costi/ricavi per il costo ipotetico) tra le aziende con storico di bilancio completo dello stesso settore, nello stesso anno relativo — mai un dato futuro rispetto all'anno osservato. I costi e il capitale investito "ipotetici" sono stime, ottenute applicando il rapporto di efficienza del miglior quartile ai ricavi reali dell'azienda: non sono una previsione, ma un termine di paragone. ___SETTORI_ESCLUSI_NOTE___
      </div>

      <p class="disclaimer-small" data-reveal><b>Avvertenza.</b> I rendimenti passati non sono indicativi di quelli futuri.</p>
    </div>
  </section>

  <section class="final-cta">
    <div class="wrap">
      <div class="eyebrow" style="justify-content:center;">Parliamone</div>
      <h2 data-reveal>Vuoi lo stesso rigore sui dati della tua azienda?</h2>
      <p>Una call conoscitiva di 30 minuti, senza impegno, per capire da dove partire.</p>
      <a href="contatti.html" class="btn btn-primary" style="padding:14px 28px; font-size:14px;">Parla con Veyron</a>
    </div>
  </section>

</main>

<footer>
  <div class="wrap">
    <div class="footer-top">
      <div class="footer-brand">
        <a class="logo" href="index.html">VEYRON<span class="dot">.</span></a>
        <p>Consulenza data &amp; AI per piccole e medie imprese. Analizziamo, preveniamo, automatizziamo.</p>
      </div>
      <div class="footer-col">
        <span class="label">Azienda</span>
        <a href="chi-siamo.html">Chi Siamo</a>
        <a href="metodo.html">Metodo</a>
        <a href="risultati.html">Risultati</a>
      </div>
      <div class="footer-col">
        <span class="label">Soluzioni</span>
        <a href="soluzioni.html">Dati &amp; Intelligence</a>
        <a href="soluzioni.html">Intelligenza Artificiale</a>
        <a href="backtest.html">Backtest &amp; Analisi</a>
      </div>
      <div class="footer-col">
        <span class="label">Contatti</span>
        <a href="contatti.html">Prenota una call</a>
        <a href="mailto:info@veyron.it">info@veyron.it</a>
      </div>
    </div>
    <div class="footer-row">
      <span>© 2026 Veyron — Consulenza Data &amp; AI</span>
      <div class="footer-legal-links">
        <a href="privacy.html">Privacy</a>
        <a href="termini.html">Termini</a>
      </div>
      <span>www.veyron.it</span>
    </div>
    <p class="footer-company">Veyron — <span class="placeholder">[[RAGIONE_SOCIALE]]</span> · P.IVA <span class="placeholder">[[PIVA]]</span> · Sede legale: <span class="placeholder">[[SEDE_LEGALE]]</span> · PEC: <span class="placeholder">[[PEC]]</span></p>
  </div>
</footer>

<!-- ==================== CHROME DI PAGINA ====================
     Header/nav/scroll-reveal/progress-bar: NON dipendono dai dati o da
     Chart.js e girano per primi e sempre, cosi' anche se la dashboard piu'
     sotto dovesse fallire per qualche motivo, il resto della pagina (testi,
     KPI, nav mobile) resta comunque visibile e funzionante. -->
<script>
(function(){
  "use strict";
  const header = document.getElementById('siteHeader');
  if (header) {
    window.addEventListener('scroll', () => header.classList.toggle('scrolled', window.scrollY > 20), { passive: true });
  }
  const reveals = document.querySelectorAll('[data-reveal]');
  if (reveals.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in-view'); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    reveals.forEach(el => io.observe(el));
  }
  const scrollProgress = document.querySelector('.scroll-progress');
  if (scrollProgress) {
    const updateProgress = () => {
      const h = document.documentElement;
      const max = h.scrollHeight - h.clientHeight;
      scrollProgress.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
    };
    window.addEventListener('scroll', updateProgress, { passive: true });
    updateProgress();
  }
  const navToggle = document.getElementById('navToggle');
  const mobileNav = document.getElementById('mobileNav');
  if (navToggle && mobileNav) {
    const closeNav = () => {
      navToggle.setAttribute('aria-expanded', 'false'); navToggle.setAttribute('aria-label', 'Apri il menu');
      mobileNav.classList.remove('open'); mobileNav.setAttribute('aria-hidden', 'true'); document.body.classList.remove('nav-open');
    };
    navToggle.addEventListener('click', () => {
      const isOpen = navToggle.getAttribute('aria-expanded') === 'true';
      navToggle.setAttribute('aria-expanded', String(!isOpen)); navToggle.setAttribute('aria-label', isOpen ? 'Apri il menu' : 'Chiudi il menu');
      mobileNav.classList.toggle('open', !isOpen); mobileNav.setAttribute('aria-hidden', String(isOpen)); document.body.classList.toggle('nav-open', !isOpen);
    });
    mobileNav.querySelectorAll('a').forEach(a => a.addEventListener('click', closeNav));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeNav(); });
    window.addEventListener('resize', () => { if (window.innerWidth > 860) closeNav(); });
  }
})();
</script>

<!-- Chart.js e' incorporato qui sotto (non caricato da CDN): la pagina
     funziona anche offline o dietro reti/filtri che bloccano script esterni. -->
<script>
___CHARTJS_SOURCE___
</script>

<script id="veyron-data" type="application/json">___PAYLOAD_JSON___</script>
<script>
___DASHBOARD_JS___
</script>
</body>
</html>
"""


# =========================================================================
# 8. JAVASCRIPT DELLA DASHBOARD INTERATTIVA
# =========================================================================
DASHBOARD_JS = """
(function(){
  "use strict";
  if (typeof Chart === 'undefined') {
    console.error('Veyron backtest: Chart.js non disponibile, la dashboard interattiva resta disabilitata.');
    return;
  }
  try {
  const DATA = JSON.parse(document.getElementById('veyron-data').textContent);

  const COLORS = {
    teal:'#0E3A5F', gold:'#875C0E', secure:'#2E7D46', rose:'#A63D3D',
    paper:'#151A21', paperDim:'#5B6270', paperFaint:'#666C7E', line:'rgba(21,26,33,0.10)'
  };

  Chart.defaults.color = COLORS.paperDim;
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 11.5;
  Chart.defaults.borderColor = COLORS.line;

  const METRICS = {};
  DATA.metrics.forEach(m => { METRICS[m.id] = m; });

  function fmtMetric(v, metricId){
    if (v === null || v === undefined || isNaN(v)) return 'n.d.';
    const m = METRICS[metricId];
    if (!m) return String(v);
    if (m.unita === '%') return v.toFixed(1) + '%';
    if (m.unita === 'volte') return v.toFixed(2) + '×';
    return v.toLocaleString('it-IT', { maximumFractionDigits: 0 }) + ' k€';
  }
  function avg(arr){ const v = (arr||[]).filter(x => x !== null && x !== undefined && !isNaN(x)); return v.length ? v.reduce((a,b)=>a+b,0)/v.length : null; }
  function lastValid(arr){
    for (let i = arr.length - 1; i >= 0; i--) { if (arr[i] !== null && arr[i] !== undefined) return arr[i]; }
    return null;
  }
  function hexToRgba(hex, a){
    const h = hex.replace('#','');
    const r = parseInt(h.substring(0,2),16), g = parseInt(h.substring(2,4),16), b = parseInt(h.substring(4,6),16);
    return `rgba(${r},${g},${b},${a})`;
  }

  const tooltipBase = {
    backgroundColor: '#E6E3D9', borderColor: 'rgba(21,26,33,0.20)', borderWidth: 1,
    titleColor: COLORS.paper, bodyColor: COLORS.paperDim, padding: 10, boxPadding: 4,
    titleFont: { family: "'Fraunces', sans-serif", weight: '500' },
    bodyFont: { family: "'IBM Plex Mono', monospace", size: 11.5 }
  };

  const centerTextPlugin = {
    id: 'centerText',
    afterDraw(chart){
      const cfg = chart.config.options.plugins && chart.config.options.plugins.centerText;
      if (!cfg) return;
      const { ctx, chartArea: { width, height, left, top } } = chart;
      ctx.save();
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = COLORS.paper;
      ctx.font = "600 22px 'IBM Plex Mono', monospace";
      ctx.fillText(cfg.big, left + width/2, top + height/2 - 9);
      ctx.fillStyle = COLORS.paperDim;
      ctx.font = "11.5px 'Inter', sans-serif";
      ctx.fillText(cfg.small, left + width/2, top + height/2 + 14);
      ctx.restore();
    }
  };
  Chart.register(centerTextPlugin);

  // ==================== GRAFICI "REALE VS OBIETTIVO" (generici, per metrica) ==
  const charts = {};

  function metricChartOptions(metricId){
    return {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', align: 'start', labels: { usePointStyle: true, boxWidth: 8, padding: 14 } },
        tooltip: Object.assign({}, tooltipBase, { callbacks: { label: (c)=> `${c.dataset.label}: ${fmtMetric(c.parsed.y, metricId)}` } })
      },
      scales: {
        y: { ticks: { callback: (v)=> fmtMetric(v, metricId) }, grid: { color: COLORS.line } },
        x: { grid: { display: false } }
      }
    };
  }

  function buildMetricChart(canvasId, metricId, initialRec, obiettivoLabel){
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: DATA.tLabels,
        datasets: [
          { label: 'Reale', data: initialRec[metricId].reale, borderColor: COLORS.teal, backgroundColor: hexToRgba(COLORS.teal, 0.12), borderWidth: 3, pointRadius: 4, tension: 0.2, fill: false, spanGaps: true },
          { label: obiettivoLabel || 'Obiettivo (miglior quartile)', data: initialRec[metricId].obiettivo, borderColor: COLORS.gold, borderDash: [5,4], borderWidth: 1.8, pointRadius: 3, tension: 0.2, spanGaps: true }
        ]
      },
      options: metricChartOptions(metricId)
    });
  }

  function updateMetricChart(chart, metricId, rec){
    chart.data.datasets[0].data = rec[metricId].reale;
    chart.data.datasets[1].data = rec[metricId].obiettivo;
    chart.update();
  }

  charts.featuredEbitda = buildMetricChart('chartFeaturedEbitda', 'ebitda_margin', DATA.companies.__ALL__);
  charts.featuredRoe = buildMetricChart('chartFeaturedRoe', 'roe', DATA.companies.__ALL__);

  charts.detailEbitda = buildMetricChart('chartDetailEbitda', 'ebitda_margin', DATA.companies.__ALL__);
  charts.detailRoe = buildMetricChart('chartDetailRoe', 'roe', DATA.companies.__ALL__);
  charts.detailRotazione = buildMetricChart('chartDetailRotazione', 'rotazione_ci', DATA.companies.__ALL__);

  charts.costi = buildMetricChart('chartCosti', 'costi_operativi', DATA.companies.__ALL__, 'Ipotetico (al ritmo del miglior quartile)');
  charts.capitale = buildMetricChart('chartCapitale', 'capitale_investito_netto', DATA.companies.__ALL__, 'Ipotetico (al ritmo del miglior quartile)');
  charts.rotazioneWide = buildMetricChart('chartRotazioneWide', 'rotazione_ci', DATA.companies.__ALL__);

  // ==================== DONUT SETTORI =====================================
  function buildDonut(canvasId, values, centerBig, centerSmall){
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
      type: 'doughnut',
      data: { labels: DATA.sectors, datasets: [{ data: values, backgroundColor: DATA.sectorColors, borderColor: '#F5F3EE', borderWidth: 2, offset: DATA.sectors.map(()=>0) }] },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '66%',
        plugins: {
          legend: { display: false },
          tooltip: Object.assign({}, tooltipBase, { callbacks: { label: (c)=> `${c.label}: ${c.parsed}` } }),
          centerText: { big: centerBig, small: centerSmall }
        }
      }
    });
  }
  function buildLegend(elId, colors){
    const el = document.getElementById(elId);
    el.innerHTML = DATA.sectors.map((s,i)=>
      `<span class="legend-item"><span class="legend-dot" style="background:${colors[i]}"></span>${s} <b id="${elId}-v${i}"></b></span>`
    ).join('');
  }
  function setLegendValues(elId, values){
    values.forEach((v,i)=>{ const n = document.getElementById(`${elId}-v${i}`); if (n) n.textContent = v; });
  }
  charts.sectorDonut = buildDonut('chartSectorDonut', DATA.sectorCounts, String(DATA.meta.storicoCompleto), 'PMI con storico completo');
  buildLegend('legendSector', DATA.sectorColors); setLegendValues('legendSector', DATA.sectorCounts);

  function updateSectorHighlight(sector){
    const ch = charts.sectorDonut;
    if (!ch) return;
    ch.data.datasets[0].backgroundColor = DATA.sectorColors.map((c,i)=> (!sector || DATA.sectors[i] === sector) ? c : hexToRgba(c, 0.16));
    ch.data.datasets[0].offset = DATA.sectors.map(s => s === sector ? 14 : 0);
    ch.update();
  }

  // ==================== FUNNEL ============================================
  charts.funnel = new Chart(document.getElementById('chartFunnel').getContext('2d'), {
    data: {
      labels: DATA.funnel.labels,
      datasets: [
        { type: 'bar', data: DATA.funnel.values, backgroundColor: [COLORS.paperDim, COLORS.gold, COLORS.teal], barThickness: 46 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: tooltipBase },
      scales: { y: { beginAtZero: true, grid: { color: COLORS.line } }, x: { grid: { display: false } } }
    }
  });

  // ==================== RING ==============================================
  const RING_C = 2 * Math.PI * 87;
  function setRing(pct){
    const clamped = Math.max(0, Math.min(1, pct === null ? 0 : pct));
    const color = (pct !== null && pct >= 0) ? COLORS.secure : COLORS.rose;
    const dash = RING_C * clamped;
    const el = document.getElementById('ringProgress');
    el.setAttribute('stroke-dasharray', `${dash.toFixed(2)} ${(RING_C - dash).toFixed(2)}`);
    el.setAttribute('stroke', color);
    el.style.filter = `drop-shadow(0 0 10px ${color}88)`;
    const t = document.getElementById('ringText');
    t.textContent = pct === null ? 'n.d.' : Math.round(pct*100) + '%';
    t.setAttribute('fill', color);
  }

  // ==================== RENDER PER SELEZIONE ==============================
  function renderDetailCharts(rec){
    updateMetricChart(charts.detailEbitda, 'ebitda_margin', rec);
    updateMetricChart(charts.detailRoe, 'roe', rec);
    updateMetricChart(charts.detailRotazione, 'rotazione_ci', rec);
    const isSel = rec !== DATA.companies.__ALL__;
    document.getElementById('detailSub').textContent = isSel
      ? `${rec.displayName}${rec.settore ? ' — ' + rec.settore : ''}`
      : "Media di tutte le PMI analizzate — usa il selettore in cima alla pagina per vedere una singola azienda o la media di un settore.";
  }

  function renderImpatto(rec){
    updateMetricChart(charts.costi, 'costi_operativi', rec);
    updateMetricChart(charts.capitale, 'capitale_investito_netto', rec);
    updateMetricChart(charts.rotazioneWide, 'rotazione_ci', rec);
    const isSel = rec !== DATA.companies.__ALL__;
    const label = isSel ? rec.displayName : 'media di tutte le PMI';
    document.getElementById('costiSub').textContent = `${label} — migliaia di EUR, per anno`;
    document.getElementById('capitaleSub').textContent = `${label} — migliaia di EUR, per anno`;

    const realeT0 = lastValid(rec.costi_operativi.reale);
    const obiettivoT0 = lastValid(rec.costi_operativi.obiettivo);
    let pct = null;
    if (realeT0 !== null && obiettivoT0 !== null && realeT0 !== 0) {
      pct = (realeT0 - obiettivoT0) / Math.abs(realeT0);
    }
    setRing(pct);
    document.getElementById('ringSub').textContent = isSel
      ? `${label} — % di riduzione dei costi operativi verso l'obiettivo, ultimo anno`
      : "% di riduzione dei costi operativi verso l'obiettivo, ultimo anno";

    const capRealeT0 = lastValid(rec.capitale_investito_netto.reale);
    const capObiettivoT0 = lastValid(rec.capitale_investito_netto.obiettivo);
    const risparmioT0 = (realeT0 !== null && obiettivoT0 !== null) ? (realeT0 - obiettivoT0) : null;
    const capitaleDeltaT0 = (capRealeT0 !== null && capObiettivoT0 !== null) ? (capRealeT0 - capObiettivoT0) : null;
    const summary = document.getElementById('summaryList');
    summary.innerHTML = `
      <div class="summary-line"><span>Costi operativi risparmiabili (ultimo anno)</span><span>${risparmioT0 === null ? 'n.d.' : fmtMetric(risparmioT0, 'costi_operativi')}</span></div>
      <div class="summary-line"><span>Capitale investito vs obiettivo (ultimo anno)</span><span>${capitaleDeltaT0 === null ? 'n.d.' : fmtMetric(capitaleDeltaT0, 'capitale_investito_netto')}</span></div>
      <div class="summary-line"><span>Orizzonte analizzato</span><span>${DATA.meta.orizzonteAnni} anni</span></div>
    `;
  }

  function renderCompanySummary(rec, key){
    const box = document.getElementById('companySummary');
    if (key === '__ALL__') { box.hidden = true; return; }
    box.hidden = false;
    const isSector = rec.isAggregate === true;
    box.innerHTML = `
      <div class="cs-item"><div class="cs-label">${isSector ? 'Settore' : 'Azienda'}</div><div class="cs-val" style="color:var(--paper)">${isSector ? rec.settore : rec.displayName}</div></div>
      ${isSector ? '' : `<div class="cs-item"><div class="cs-label">Settore</div><div class="cs-val" style="font-size:13.5px; color:var(--paper-dim); font-family:Inter,sans-serif;">${rec.settore}</div></div>`}
      <div class="cs-item"><div class="cs-label">EBITDA/Vendite (ultimo anno)</div><div class="cs-val">${fmtMetric(lastValid(rec.ebitda_margin.reale), 'ebitda_margin')}<div class="cs-val-sub">obiettivo ${fmtMetric(lastValid(rec.ebitda_margin.obiettivo), 'ebitda_margin')}</div></div></div>
      <div class="cs-item"><div class="cs-label">ROE (ultimo anno)</div><div class="cs-val" style="color:var(--gold-vivid)">${fmtMetric(lastValid(rec.roe.reale), 'roe')}<div class="cs-val-sub">obiettivo ${fmtMetric(lastValid(rec.roe.obiettivo), 'roe')}</div></div></div>
      <div class="cs-item"><div class="cs-label">Rotazione capitale investito</div><div class="cs-val">${fmtMetric(lastValid(rec.rotazione_ci.reale), 'rotazione_ci')}</div></div>
      ${rec.annoUltimo ? `<div class="cs-item"><div class="cs-label">Ultimo bilancio</div><div class="cs-val" style="font-size:14px; color:var(--paper-dim);">${rec.annoUltimo}</div></div>` : ''}
    `;
  }

  // ==================== SELEZIONE AZIENDA/SETTORE =========================
  function selectRecord(key, opts){
    opts = opts || {};
    const rec = DATA.companies[key];
    if (!rec) return;
    const companySel = document.getElementById('companySelect');
    const sectorSel = document.getElementById('sectorSelect');
    const isAggregateChoice = key === '__ALL__' || key.indexOf('SETTORE::') === 0;
    if (isAggregateChoice) {
      if (sectorSel.value !== key) sectorSel.value = key;
      companySel.value = '';
    } else {
      if (companySel.value !== key) companySel.value = key;
      sectorSel.value = '__ALL__';
    }
    if (!opts.skipHash) {
      if (key === '__ALL__') history.replaceState(null, '', location.pathname + location.search);
      else history.replaceState(null, '', '#azienda=' + encodeURIComponent(key));
    }
    renderDetailCharts(rec);
    renderImpatto(rec);
    updateSectorHighlight(rec.settore);
    renderCompanySummary(rec, key);
  }

  // ==================== SELETTORI (dropdown azienda + dropdown settore) ===
  (function initSelect(){
    const companySel = document.getElementById('companySelect');
    const placeholder = document.createElement('option');
    placeholder.value = ''; placeholder.textContent = "— seleziona un'azienda —"; placeholder.disabled = true; placeholder.selected = true;
    companySel.appendChild(placeholder);
    DATA.sectors.forEach(sector=>{
      const grp = document.createElement('optgroup');
      grp.label = sector;
      DATA.companyOrder.filter(k => DATA.companies[k].settore === sector).forEach(k=>{
        const o = document.createElement('option'); o.value = k; o.textContent = DATA.companies[k].displayName; grp.appendChild(o);
      });
      companySel.appendChild(grp);
    });
    companySel.addEventListener('change', (e)=> { if (e.target.value) selectRecord(e.target.value); });

    const sectorSel = document.getElementById('sectorSelect');
    const optAll = document.createElement('option');
    optAll.value = '__ALL__'; optAll.textContent = DATA.companies.__ALL__.displayName;
    sectorSel.appendChild(optAll);
    DATA.sectors.forEach(sector=>{
      const key = 'SETTORE::' + sector;
      const o = document.createElement('option');
      o.value = key; o.textContent = DATA.companies[key].displayName;
      sectorSel.appendChild(o);
    });
    sectorSel.addEventListener('change', (e)=> selectRecord(e.target.value));
  })();

  // ==================== SELEZIONE INIZIALE (da URL hash) ==================
  (function initSelection(){
    const m = location.hash.match(/azienda=([^&]+)/);
    const raw = m ? decodeURIComponent(m[1]) : null;
    const initial = (raw && DATA.companies[raw]) ? raw : '__ALL__';
    selectRecord(initial, { skipHash: true });
  })();
  } catch (err) {
    console.error('Veyron backtest: errore nella dashboard interattiva, il resto della pagina resta comunque visibile:', err);
  }
})();
"""

# =========================================================================
# 9. FORMATTAZIONE VALORI PER I PLACEHOLDER DELLA PAGINA (KPI, note)
# =========================================================================
def fmt_pp(x, sign=True, decimals=1):
    """Formatta un valore gia' espresso in punti percentuali (es. 7.43 -> '7.4%'),
    NON una frazione 0-1: i rapporti AIDA (EBITDA/Vendite, ROE, ...) sono
    esportati gia' in percentuale."""
    if x is None:
        return "n.d."
    s = "+" if (sign and x >= 0) else ""
    return f"{s}{x:.{decimals}f}%"

def fmt_migl(x, decimals=0):
    if x is None:
        return "n.d."
    return f"{x:,.{decimals}f}".replace(",", ".") + " k€"

def fmt_volte(x, decimals=2):
    if x is None:
        return "n.d."
    return f"{x:.{decimals}f}×"

SETTORI_ESCLUSI_NOTE = (
    f"Settori esclusi dall'analisi per numero insufficiente di aziende con storico completo: {', '.join(settori_scartati)}."
    if settori_scartati else
    "Tutti i 6 settori target hanno superato la soglia minima di aziende con storico di bilancio completo."
)

# =========================================================================
# 10. SOSTITUZIONE PLACEHOLDER E SCRITTURA FILE
# =========================================================================
replacements = {
    "___BASE_CSS___": BASE_CSS,
    "___EXTRA_CSS___": EXTRA_CSS,
    "___DATA_BADGE___": DATA_BADGE,
    "___DATA_NOTE___": DATA_NOTE,
    "___N_MOSTRATE___": str(N_MOSTRATE),
    "___N_SETTORI___": str(N_SETTORI),
    "___ORIZZONTE___": str(CONFIG["orizzonte_anni"]),
    "___KPI_EBITDA_REALE___": fmt_pp(meta["ebitdaMarginRealeT0"]),
    "___KPI_EBITDA_OBIETTIVO___": fmt_pp(meta["ebitdaMarginObiettivoT0"]),
    "___KPI_ROE_REALE___": fmt_pp(meta["roeRealeT0"]),
    "___KPI_ROE_OBIETTIVO___": fmt_pp(meta["roeObiettivoT0"]),
    "___KPI_ROTAZIONE_REALE___": fmt_volte(meta["rotazioneRealeT0"]),
    "___KPI_RISPARMIO___": fmt_migl(meta["risparmioMedioT0"]),
    "___KPI_RISPARMIO_CLASS___": "rose" if meta["risparmioMedioT0"] is not None and meta["risparmioMedioT0"] > 0 else "",
    "___KPI_RISPARMIO_SUB___": ("migliaia EUR/anno, verso l'obiettivo" if meta["risparmioMedioT0"] is not None and meta["risparmioMedioT0"] > 0
                                 else "negativo: in media già sotto il livello del benchmark"),
    "___KPI_CAPITALE___": fmt_migl(meta["capitaleLiberabileMedioT0"]),
    "___KPI_CAPITALE_CLASS___": "rose" if meta["capitaleLiberabileMedioT0"] is not None and meta["capitaleLiberabileMedioT0"] > 0 else "",
    "___KPI_CAPITALE_SUB___": ("migliaia EUR, verso l'obiettivo" if meta["capitaleLiberabileMedioT0"] is not None and meta["capitaleLiberabileMedioT0"] > 0
                                else "negativo: in media già sotto il livello del benchmark"),
    "___SETTORI_ESCLUSI_NOTE___": SETTORI_ESCLUSI_NOTE,
    "___PAYLOAD_JSON___": PAYLOAD_JSON,
    "___CHARTJS_SOURCE___": CHARTJS_SOURCE,
    "___DASHBOARD_JS___": DASHBOARD_JS,
}

html_out = HTML_TEMPLATE
for token, value in replacements.items():
    html_out = html_out.replace(token, value)

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(html_out)

print(f"Pagina generata: {OUT_PATH}")
