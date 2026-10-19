# ============================================================================
# Backtest rapido "in sample": fattore Quality (ROE) su un universo di
# small/mid-cap USA raggruppate per settore, con statistiche di trade-off
# rischio/rendimento.
#
# Dati fondamentali : pacchetto R "edgarfundamentals" (SEC EDGAR XBRL, gratuito)
# Dati di prezzo     : pacchetto R "tidyquant" (Yahoo Finance, gratuito)
#
# Strategia testata  : ogni anno, long equal-weight sulle N aziende con ROE
#                       più alto nell'universo; confronto con un benchmark
#                       equal-weight su tutte le aziende dell'universo.
# ============================================================================

# --- 1. Installazione pacchetti (una tantum) --------------------------------
if (!requireNamespace("remotes", quietly = TRUE)) install.packages("remotes")
if (!requireNamespace("edgarfundamentals", quietly = TRUE))
  remotes::install_github("robschumaker/edgarfundamentals")   # non ancora su CRAN al momento della prova
if (!requireNamespace("tidyquant", quietly = TRUE)) install.packages("tidyquant")
if (!requireNamespace("dplyr", quietly = TRUE))     install.packages("dplyr")
if (!requireNamespace("tidyr", quietly = TRUE))      install.packages("tidyr")
if (!requireNamespace("ggplot2", quietly = TRUE))    install.packages("ggplot2")
if (!requireNamespace("scales", quietly = TRUE))     install.packages("scales")

library(edgarfundamentals)
library(tidyquant)
library(dplyr)
library(tidyr)
library(ggplot2)

# La SEC richiede che i tool automatici si identifichino con uno User-Agent
# nella forma "Nome Cognome email@dominio.it" -- personalizzalo.
options(edgarfundamentals.user_agent = "Nome Cognome tuo@email.com")

# --- 2. Universo per settore (ticker + CIK forniti direttamente) ------------
# I CIK sono passati esplicitamente (invece di farli risolvere dal ticker via
# get_cik()) perche' per le small/micro-cap la mappa ticker->CIK di
# company_tickers.json puo' essere incompleta o ambigua; usare il CIK diretto
# e' piu' affidabile.
universe <- tribble(
  ~sector,                  ~symbol, ~cik,
  "Trasporti/Logistica",    "CVLG",  "0000928658",
  "Trasporti/Logistica",    "MRTN",  "0000799167",
  "Trasporti/Logistica",    "ULH",   "0001308208",
  "Trasporti/Logistica",    "FWRD",  "0000912728",

  "Alimentare",             "SENEA", "0000088948",
  "Alimentare",             "JJSF",  "0000785956",
  "Alimentare",             "NGVC",  "0001547459",
  "Alimentare",             "UTZ",   "0001739566",

  "Meccanico/Machinery",    "PKOH",  "0000076282",
  "Meccanico/Machinery",    "TNC",   "0000097134",
  "Meccanico/Machinery",    "LNN",   "0000836157",
  "Meccanico/Machinery",    "GHM",   "0000716314",
  "Meccanico/Machinery",    "LXFR",  "0001096056",
  "Meccanico/Machinery",    "GRC",   "0000042682",

  "Packaging",              "KRT",   "0001758021",
  "Packaging",              "MYE",   "0000069488",
  "Packaging",              "PACK",  "0001712463",

  "Edilizia",                "BZH",   "0000915840",
  "Edilizia",                "CCS",   "0001576940",
  "Edilizia",                "TPC",   "0000077543",
  "Edilizia",                "GRBK",  "0001373670",  # mid-cap, fuori dal limite stretto

  "Arredamento",             "LZB",   "0000057131",
  "Arredamento",             "ETD",   "0000896156",
  "Arredamento",             "HOFT",  "0001077688",
  "Arredamento",             "BSET",  "0000010329",
  "Arredamento",             "FLXS",  "0000037472"
)

# --- 3. Date di formazione del portafoglio -----------------------------------
# Uso fine marzo (non fine dicembre) come data di "disponibilita'" dei
# fondamentali: i filer SEC devono depositare il 10-K entro 60-90 giorni dalla
# chiusura dell'esercizio, quindi a fine marzo il 10-K dell'anno precedente e'
# quasi sempre gia' pubblico. Usare direttamente il 31/12 introdurrebbe un
# look-ahead bias (si userebbero dati non ancora disponibili in quella data).
# ATTENZIONE: alcune di queste societa' potrebbero avere un esercizio fiscale
# non allineato all'anno solare -- in quel caso il filtro "periodo <= to_date"
# di get_fundamentals() potrebbe agganciare un esercizio diverso da quello
# atteso: vale la pena un controllo puntuale se un risultato sembra anomalo.
form_dates <- as.character(seq.Date(as.Date("2020-03-31"),
                                     as.Date("2025-03-31"), by = "year"))

# --- 4. Fetch dei fondamentali per CIK esplicito -----------------------------
# get_fundamentals() del pacchetto risolve il ticker in CIK internamente;
# qui replichiamo la stessa logica (stessi tag XBRL con fallback, stesse
# formule per i ratio) ma partendo dal CIK gia' noto, cosi' rispettiamo i CIK
# forniti invece di fidarci di una nuova ricerca per ticker.
get_fundamentals_by_cik <- function(symbol, cik, to_date) {
  cik.pad <- edgarfundamentals:::pad_cik(cik)

  facts <- tryCatch({
    httr::GET(
      paste0("https://data.sec.gov/api/xbrl/companyfacts/CIK", cik.pad, ".json"),
      edgarfundamentals:::edgar_ua()
    ) |>
      httr::content(as = "text", encoding = "UTF-8") |>
      jsonlite::fromJSON()
  }, error = function(e) NULL)

  Sys.sleep(0.5)  # rispetta il rate limit SEC (10 richieste/secondo)

  if (is.null(facts)) {
    return(c(CIK = as.numeric(cik), EPS = NA, NetIncome = NA, Revenue = NA,
             ROE = NA, ROA = NA, DE = NA, CurrentRatio = NA, GrossMargin = NA,
             OperatingMargin = NA, NetMargin = NA))
  }

  lt <- edgarfundamentals:::latest_10k

  net.income <- lt(facts, "NetIncomeLoss",
                    fallback_tags = c("ProfitLoss", "NetIncome"),
                    unit = "USD", to_date = to_date)
  revenue    <- lt(facts, "RevenueFromContractWithCustomerExcludingAssessedTax",
                    fallback_tags = c("Revenues", "SalesRevenueNet",
                                      "SalesRevenueGoodsNet", "SalesRevenueServicesNet"),
                    unit = "USD", to_date = to_date)
  equity     <- lt(facts, "StockholdersEquity",
                    fallback_tags = "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                    unit = "USD", to_date = to_date)
  debt       <- lt(facts, "LongTermDebt",
                    fallback_tags = c("LongTermDebtNoncurrent", "LongTermNotesPayable"),
                    unit = "USD", to_date = to_date)
  assets     <- lt(facts, "Assets", unit = "USD", to_date = to_date)
  cur.assets <- lt(facts, "AssetsCurrent", unit = "USD", to_date = to_date)
  cur.liab   <- lt(facts, "LiabilitiesCurrent", unit = "USD", to_date = to_date)
  gp         <- lt(facts, "GrossProfit", unit = "USD", to_date = to_date)
  op.inc     <- lt(facts, "OperatingIncomeLoss", unit = "USD", to_date = to_date)
  eps        <- lt(facts, "EarningsPerShareDiluted",
                    fallback_tags = "EarningsPerShareBasic",
                    unit = "USD/shares", to_date = to_date)

  roe <- if (!is.na(net.income) && !is.na(equity) && equity != 0) round(net.income / equity * 100, 2) else NA_real_
  roa <- if (!is.na(net.income) && !is.na(assets) && assets != 0) round(net.income / assets * 100, 2) else NA_real_
  de  <- if (!is.na(debt) && !is.na(equity) && equity != 0) round(debt / equity, 2) else NA_real_
  cr  <- if (!is.na(cur.assets) && !is.na(cur.liab) && cur.liab != 0) round(cur.assets / cur.liab, 2) else NA_real_
  gm  <- if (!is.na(gp) && !is.na(revenue) && revenue != 0) round(gp / revenue * 100, 2) else NA_real_
  om  <- if (!is.na(op.inc) && !is.na(revenue) && revenue != 0) round(op.inc / revenue * 100, 2) else NA_real_
  nm  <- if (!is.na(net.income) && !is.na(revenue) && revenue != 0) round(net.income / revenue * 100, 2) else NA_real_

  c(CIK = as.numeric(cik), EPS = round(eps, 2), NetIncome = round(net.income, 0),
    Revenue = round(revenue, 0), ROE = roe, ROA = roa, DE = de,
    CurrentRatio = cr, GrossMargin = gm, OperatingMargin = om, NetMargin = nm)
}

# --- 5. Scarica il pannello di fondamentali per ogni data di formazione -----
panel <- lapply(form_dates, function(d) {
  message("Scarico fondamentali al ", d, " ...")
  rows <- lapply(seq_len(nrow(universe)), function(i) {
    r <- tryCatch(
      get_fundamentals_by_cik(universe$symbol[i], universe$cik[i], d),
      error = function(e) {
        message("  fallito per ", universe$symbol[i], ": ", conditionMessage(e))
        c(CIK = NA, EPS = NA, NetIncome = NA, Revenue = NA, ROE = NA, ROA = NA,
          DE = NA, CurrentRatio = NA, GrossMargin = NA, OperatingMargin = NA, NetMargin = NA)
      }
    )
    as.data.frame(as.list(r))
  }) |> bind_rows()
  rows$symbol <- universe$symbol
  rows$sector <- universe$sector
  rows$asof   <- d
  rows
}) |> bind_rows()

# --- 6. Prezzi storici per calcolare i rendimenti forward -------------------
prices <- tq_get(universe$symbol, from = "2020-01-01", to = Sys.Date()) |>
  select(symbol, date, adjusted)

price_on_or_after <- function(sym, target_date) {
  out <- prices |>
    filter(symbol == sym, date >= as.Date(target_date)) |>
    arrange(date) |>
    slice(1) |>
    pull(adjusted)
  if (length(out) == 0) NA_real_ else out
}

panel <- panel |>
  rowwise() |>
  mutate(
    p0         = price_on_or_after(symbol, asof),
    date_fwd   = as.character(as.Date(asof) + 365),
    p1         = price_on_or_after(symbol, date_fwd),
    fwd_return = p1 / p0 - 1
  ) |>
  ungroup()

# --- 7. Strategia (Top-N ROE) vs benchmark (equal-weight su tutto l'universo)
n_top       <- 8       # ~30% dell'universo: modificabile
risk_free   <- 0.02    # tasso "risk-free" annuo usato per lo Sharpe, modificabile

strategy <- panel |>
  filter(!is.na(ROE), !is.na(fwd_return)) |>
  group_by(asof) |>
  slice_max(order_by = ROE, n = n_top) |>
  summarise(port_return = mean(fwd_return), .groups = "drop")

benchmark <- panel |>
  filter(!is.na(fwd_return)) |>
  group_by(asof) |>
  summarise(bench_return = mean(fwd_return), .groups = "drop")

results <- left_join(strategy, benchmark, by = "asof") |>
  arrange(asof) |>
  mutate(
    equity_strategy = cumprod(1 + port_return),
    equity_bench    = cumprod(1 + bench_return)
  )

print(results)

# --- 8. Statistiche di trade-off rischio/rendimento -------------------------
tradeoff_stats <- function(returns, equity) {
  n_years <- length(returns)
  cagr    <- equity[length(equity)]^(1 / n_years) - 1        # rendimento annuo composto
  vol     <- sd(returns)                                     # volatilita' annua (dev.std. dei rendimenti annui)
  sharpe  <- (cagr - risk_free) / vol                        # rendimento per unita' di rischio
  dd      <- max(1 - equity / cummax(equity))                # massimo drawdown lungo il periodo
  c(CAGR = cagr, Volatilita = vol, Sharpe = sharpe, MaxDrawdown = dd)
}

stats_strategy  <- tradeoff_stats(results$port_return,  results$equity_strategy)
stats_benchmark <- tradeoff_stats(results$bench_return, results$equity_bench)

stats_table <- rbind(
  Strategia_TopROE = stats_strategy,
  Benchmark_EqualWeight = stats_benchmark
) |> round(3)

cat("\n--- Statistiche di trade-off rischio/rendimento ---\n")
print(stats_table)
write.csv(stats_table, "tradeoff_stats.csv", row.names = TRUE)

# --- 9. Grafico 1: equity curve con statistiche annotate --------------------
results_long <- results |>
  select(asof, equity_strategy, equity_bench) |>
  pivot_longer(-asof, names_to = "serie", values_to = "equity")

caption_txt <- sprintf(
  "Strategia Top-%d ROE -> CAGR %.1f%%, Vol %.1f%%, Sharpe %.2f, MaxDD %.1f%% | Benchmark -> CAGR %.1f%%, Vol %.1f%%, Sharpe %.2f, MaxDD %.1f%%",
  n_top,
  stats_strategy["CAGR"] * 100, stats_strategy["Volatilita"] * 100,
  stats_strategy["Sharpe"], stats_strategy["MaxDrawdown"] * 100,
  stats_benchmark["CAGR"] * 100, stats_benchmark["Volatilita"] * 100,
  stats_benchmark["Sharpe"], stats_benchmark["MaxDrawdown"] * 100
)

p1 <- ggplot(results_long, aes(x = as.Date(asof), y = equity, color = serie)) +
  geom_line(linewidth = 1) +
  geom_point(size = 2) +
  labs(title = sprintf("Backtest in-sample: Top-%d ROE vs equal-weight (%d small/mid-cap USA)", n_top, nrow(universe)),
       subtitle = "Ribilancio annuale, rendimento forward a 1 anno, senza costi di transazione",
       caption = caption_txt,
       x = NULL, y = "Crescita di 1$ investito", color = NULL) +
  theme_minimal() +
  theme(plot.caption = element_text(hjust = 0, size = 8))

ggsave("backtest_equity_curve.png", p1, width = 10, height = 6, dpi = 150)
print(p1)

# --- 10. Grafico 2: scatter rischio/rendimento (trade-off) per titolo -------
# Per ogni titolo: rendimento medio e volatilita' dei rendimenti forward
# osservati alle date di formazione -- mostra visivamente il trade-off
# rischio/rendimento nell'universo, con i due portafogli sovrapposti.
per_stock <- panel |>
  filter(!is.na(fwd_return)) |>
  group_by(symbol, sector) |>
  summarise(ret_medio = mean(fwd_return), volatilita = sd(fwd_return), .groups = "drop") |>
  filter(!is.na(volatilita))

portfolios <- data.frame(
  symbol     = c(sprintf("Strategia Top-%d ROE", n_top), "Benchmark (tutto l'universo)"),
  sector     = c("PORTAFOGLIO", "PORTAFOGLIO"),
  ret_medio  = c(mean(results$port_return), mean(results$bench_return)),
  volatilita = c(sd(results$port_return), sd(results$bench_return))
)

p2 <- ggplot(per_stock, aes(x = volatilita, y = ret_medio, color = sector)) +
  geom_point(size = 3, alpha = 0.8) +
  geom_text(aes(label = symbol), size = 3, vjust = -0.8, show.legend = FALSE, check_overlap = TRUE) +
  geom_point(data = portfolios, aes(x = volatilita, y = ret_medio),
             color = "black", shape = 18, size = 5, inherit.aes = FALSE) +
  geom_text(data = portfolios, aes(x = volatilita, y = ret_medio, label = symbol),
             color = "black", size = 3.2, fontface = "bold", hjust = -0.1, vjust = -0.6, inherit.aes = FALSE) +
  labs(title = "Trade-off rischio/rendimento per titolo e per portafoglio",
       subtitle = "Rendimento medio e volatilita' dei rendimenti forward a 1 anno, 2020-2025",
       x = "Volatilita' (deviazione standard dei rendimenti annui)",
       y = "Rendimento medio annuo", color = "Settore") +
  scale_x_continuous(labels = scales::percent, expand = expansion(mult = c(0.08, 0.12))) +
  scale_y_continuous(labels = scales::percent) +
  theme_minimal()

ggsave("backtest_risk_return_tradeoff.png", p2, width = 10, height = 7, dpi = 150)
print(p2)
