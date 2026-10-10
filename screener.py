#!/usr/bin/env python3
"""
Cribado semanal de acciones españolas y europeas (IBEX 35, Euro Stoxx 50, Mercado Continuo).

Fuente de datos: Yahoo Finance a través de la librería yfinance (datos no oficiales,
uso personal/educativo). Cada cifra queda guardada con su ticker, fecha de descarga y
enlace a la ficha de Yahoo para poder comprobarla.

Uso:
    python screener.py            # descarga real (necesita acceso a Yahoo)
    python screener.py --demo     # datos sintéticos para probar el dashboard

Salida (carpeta docs/data, servida por GitHub Pages):
    latest.json                   # foto de la semana que lee el dashboard
    history/AAAA-MM-DD.csv        # histórico semanal
    history/index.json            # lista de semanas disponibles
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TICKERS_FILE = ROOT / "tickers.csv"
OUT_DIR = ROOT / "docs" / "data"
HIST_DIR = OUT_DIR / "history"

# --- Umbrales de las alertas (editables) -----------------------------------
UMBRALES = {
    "rdp_alta": 7.0,            # % rentabilidad por dividendo considerada "alta"
    "payout_max": 90.0,         # % payout por encima del cual el dividendo no está cubierto
    "cobertura_min": 0.8,       # FCL/DPA mínimo para considerar el dividendo cubierto con caja
    "deuda_ebitda_max": 4.0,    # veces; apalancamiento elevado (no aplica a financieras)
    "cerca_minimo_52s": 5.0,    # % por encima del mínimo de 52 semanas
    "caida_semanal": -5.0,      # % variación semanal para marcar "abaratamiento"
    "min_pares_sector": 4,      # mínimo de comparables para puntuar dentro del sector
}

SECTORES_FINANCIEROS = {"Financial Services", "Real Estate"}  # EBITDA/deuda neta poco significativos

# Métricas que entran en la puntuación relativa: (campo, True si "más alto es mejor")
METRICAS_SCORE = [
    ("per", False),
    ("pvc", False),
    ("rdp", True),
    ("roe", True),
    ("deuda_neta_ebitda", False),
]


def leer_tickers() -> list[dict]:
    """Lee tickers.csv. Un valor puede estar en varios índices (p. ej. SAN en IBEX y ES50)."""
    filas: dict[str, dict] = {}
    with TICKERS_FILE.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["ticker"].strip()
            if not t:
                continue
            if t in filas:
                filas[t]["indices"].append(r["indice"].strip())
            else:
                filas[t] = {"ticker": t, "nombre": r["nombre"].strip(), "indices": [r["indice"].strip()]}
    # Los valores españoles del Euro Stoxx 50 también están en el IBEX
    for t in ("SAN.MC", "BBVA.MC", "IBE.MC", "ITX.MC"):
        if t in filas and "ES50" not in filas[t]["indices"]:
            filas[t]["indices"].append("ES50")
    return list(filas.values())


def _num(x):
    try:
        if x is None:
            return None
        v = float(x)
        return None if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


def _div(a, b):
    a, b = _num(a), _num(b)
    if a is None or b in (None, 0):
        return None
    return a / b


def metricas_de_precio(closes: list[float]) -> dict:
    """Indicadores técnicos a partir de cierres diarios (último año)."""
    out = {k: None for k in ("var_semana", "var_4s", "volatilidad", "max_52s", "min_52s",
                             "dist_max_52s", "dist_min_52s", "media_200", "dist_media_200")}
    closes = [c for c in closes if _num(c)]
    if len(closes) < 30:
        return out
    p = closes[-1]
    if len(closes) > 5:
        out["var_semana"] = (p / closes[-6] - 1) * 100
    if len(closes) > 20:
        out["var_4s"] = (p / closes[-21] - 1) * 100
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    out["volatilidad"] = statistics.stdev(rets) * math.sqrt(252) * 100
    out["max_52s"], out["min_52s"] = max(closes), min(closes)
    out["dist_max_52s"] = (p / out["max_52s"] - 1) * 100
    out["dist_min_52s"] = (p / out["min_52s"] - 1) * 100
    if len(closes) >= 200:
        out["media_200"] = sum(closes[-200:]) / 200
        out["dist_media_200"] = (p / out["media_200"] - 1) * 100
    return out


# Partidas de las cuentas anuales que se guardan: (clave, etiqueta, [nombres posibles en Yahoo])
PARTIDAS = {
    "pyg": [
        ("ingresos", "Importe neto cifra de negocios", ["Total Revenue", "Operating Revenue"]),
        ("margen_bruto", "Margen bruto", ["Gross Profit"]),
        ("ebitda", "EBITDA", ["EBITDA", "Normalized EBITDA"]),
        ("ebit", "Resultado de explotación (EBIT)", ["Operating Income", "EBIT"]),
        ("gastos_financieros", "Gastos financieros", ["Interest Expense", "Interest Expense Non Operating"]),
        ("rdo_antes_imp", "Resultado antes de impuestos", ["Pretax Income"]),
        ("impuesto", "Impuesto sobre beneficios", ["Tax Provision"]),
        ("rdo_neto", "Resultado neto atribuido", ["Net Income Common Stockholders", "Net Income"]),
        ("bpa", "BPA diluido", ["Diluted EPS", "Basic EPS"]),
    ],
    "balance": [
        ("activo_total", "Activo total", ["Total Assets"]),
        ("activo_no_corriente", "Activo no corriente", ["Total Non Current Assets"]),
        ("activo_corriente", "Activo corriente", ["Current Assets"]),
        ("existencias", "Existencias", ["Inventory"]),
        ("deudores", "Deudores comerciales", ["Accounts Receivable", "Receivables"]),
        ("efectivo", "Efectivo y equivalentes", ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
        ("patrimonio_neto", "Patrimonio neto atribuido", ["Stockholders Equity", "Common Stock Equity"]),
        ("pasivo_total", "Pasivo total", ["Total Liabilities Net Minority Interest"]),
        ("pasivo_no_corriente", "Pasivo no corriente", ["Total Non Current Liabilities Net Minority Interest"]),
        ("pasivo_corriente", "Pasivo corriente", ["Current Liabilities"]),
        ("deuda_financiera", "Deuda financiera", ["Total Debt"]),
        ("deuda_neta", "Deuda neta", ["Net Debt"]),
    ],
    "flujos": [
        ("fco", "Flujo de explotación", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
        ("capex", "Inversiones en inmovilizado (capex)", ["Capital Expenditure"]),
        ("fcl", "Flujo de caja libre", ["Free Cash Flow"]),
        ("dividendos_pagados", "Dividendos pagados", ["Cash Dividends Paid", "Common Stock Dividend Paid"]),
        ("recompras", "Recompra de acciones", ["Repurchase Of Capital Stock", "Common Stock Payments"]),
    ],
}


def extraer_cuentas(estados: dict) -> dict | None:
    """estados = {"pyg": DataFrame, "balance": DataFrame, "flujos": DataFrame} (formato yfinance:
    filas = partidas, columnas = fechas de cierre, la más reciente primero).
    Devuelve los dos últimos ejercicios cerrados."""
    fechas = None
    out = {"periodos": [], "pyg": {}, "balance": {}, "flujos": {}}
    for bloque, df in estados.items():
        if df is None or getattr(df, "empty", True):
            continue
        cols = sorted(df.columns, reverse=True)[:2]
        if fechas is None or bloque == "pyg":
            fechas = cols
        for clave, _, nombres in PARTIDAS[bloque]:
            fila = next((n for n in nombres if n in df.index), None)
            if fila is None:
                continue
            vals = [_num(df.at[fila, c]) for c in cols]
            if any(v is not None for v in vals):
                out[bloque][clave] = vals
    if not fechas or not any(out[b] for b in ("pyg", "balance", "flujos")):
        return None
    out["periodos"] = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c) for c in fechas]
    return out


def descargar(ticker: str) -> tuple[dict, list[float], dict | None]:
    import yfinance as yf  # import aquí para que --demo funcione sin la librería

    tk = yf.Ticker(ticker)
    info = tk.info or {}
    hist = tk.history(period="1y", interval="1d", auto_adjust=False)
    closes = hist["Close"].dropna().tolist() if hist is not None and not hist.empty else []
    cuentas = None
    try:
        cuentas = extraer_cuentas({"pyg": tk.income_stmt, "balance": tk.balance_sheet, "flujos": tk.cashflow})
    except Exception as e:  # noqa: BLE001  — las cuentas son un extra: si fallan, seguimos
        print(f"{ticker}: sin cuentas anuales ({e})", file=sys.stderr)
    return info, closes, cuentas


def construir_fila(base: dict, info: dict, closes: list[float], cuentas: dict | None = None) -> dict:
    precio = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice")) or (closes[-1] if closes else None)
    acciones = _num(info.get("sharesOutstanding"))
    sector = info.get("sector") or "Sin sector"
    financiera = sector in SECTORES_FINANCIEROS

    dpa = _num(info.get("dividendRate")) or _num(info.get("trailingAnnualDividendRate"))
    ebitda = _num(info.get("ebitda"))
    deuda, caja = _num(info.get("totalDebt")), _num(info.get("totalCash"))
    deuda_neta = (deuda - caja) if deuda is not None and caja is not None else None

    fila = {
        "ticker": base["ticker"],
        "nombre": base["nombre"],
        "indices": base["indices"],
        "sector": sector,
        "industria": info.get("industry"),
        "moneda": info.get("currency"),
        "moneda_contable": info.get("financialCurrency"),
        "precio": precio,
        "capitalizacion": _num(info.get("marketCap")),
        # --- Fundamentales (lista Cajaviva) ---
        "ingresos": _num(info.get("totalRevenue")),
        "bpa": _num(info.get("trailingEps")),
        "dpa": dpa,
        "roa": _pct(info.get("returnOnAssets")),
        "pvc": _num(info.get("priceToBook")),
        "rdp": (_div(dpa, precio) * 100) if _div(dpa, precio) is not None else None,
        "ebitda": None if financiera else ebitda,
        "fcl_accion": _div(info.get("freeCashflow"), acciones),
        "fco_accion": _div(info.get("operatingCashflow"), acciones),
        "roe": _pct(info.get("returnOnEquity")),
        # --- Añadidos ---
        "per": _num(info.get("trailingPE")),
        "per_futuro": _num(info.get("forwardPE")),
        "payout": _pct(info.get("payoutRatio")),
        "deuda_neta_ebitda": None if financiera else _div(deuda_neta, ebitda),
        "financiera": financiera,
        "cuentas": cuentas,
        "url_fuente": f"https://finance.yahoo.com/quote/{base['ticker']}",
        "descargado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    fila.update(metricas_de_precio(closes))
    return fila


def _pct(x):
    v = _num(x)
    return v * 100 if v is not None else None


def percentil(valor, poblacion, mayor_mejor):
    pob = [p for p in poblacion if p is not None]
    if valor is None or len(pob) < 2:
        return None
    menores = sum(1 for p in pob if p < valor)
    iguales = sum(1 for p in pob if p == valor)
    r = (menores + 0.5 * iguales) / len(pob)
    return r if mayor_mejor else 1 - r


def puntuar(filas: list[dict]) -> None:
    """Puntuación 0-100 relativa al sector (o al universo si hay pocos comparables).
    PER y P/VC negativos se excluyen (pérdidas o patrimonio negativo no son 'baratos')."""
    por_sector: dict[str, list[dict]] = {}
    for f in filas:
        por_sector.setdefault(f["sector"], []).append(f)

    def valido(campo, v):
        if v is None:
            return None
        if campo in ("per", "pvc", "deuda_neta_ebitda") and v <= 0:
            return None if campo != "deuda_neta_ebitda" else v  # caja neta (negativo) sí es bueno
        return v

    for f in filas:
        pares = por_sector[f["sector"]]
        grupo = pares if len(pares) >= UMBRALES["min_pares_sector"] else filas
        f["comparado_con"] = f["sector"] if grupo is pares else "universo"
        partes = {}
        for campo, mayor_mejor in METRICAS_SCORE:
            v = valido(campo, f.get(campo))
            pob = [valido(campo, g.get(campo)) for g in grupo]
            p = percentil(v, pob, mayor_mejor)
            if p is not None:
                partes[campo] = round(p * 100)
        f["score_detalle"] = partes
        f["score"] = round(sum(partes.values()) / len(partes)) if len(partes) >= 3 else None


def alertas(f: dict) -> list[str]:
    a = []
    u = UMBRALES
    if f.get("rdp") and f["rdp"] >= u["rdp_alta"]:
        cobertura = _div(f.get("fcl_accion"), f.get("dpa")) if not f.get("financiera") else None
        if (f.get("payout") is not None and (f["payout"] > u["payout_max"] or f["payout"] < 0)) or \
           (cobertura is not None and cobertura < u["cobertura_min"]) or \
           (f.get("deuda_neta_ebitda") and f["deuda_neta_ebitda"] > u["deuda_ebitda_max"]):
            a.append("posible_trampa_dividendo")
        else:
            a.append("rdp_alta")
    if f.get("deuda_neta_ebitda") and f["deuda_neta_ebitda"] > u["deuda_ebitda_max"]:
        a.append("apalancamiento_alto")
    if f.get("dist_min_52s") is not None and f["dist_min_52s"] <= u["cerca_minimo_52s"]:
        a.append("cerca_minimo_52s")
    if f.get("var_semana") is not None and f["var_semana"] <= u["caida_semanal"]:
        a.append("caida_semanal")
    if f.get("dist_media_200") is not None:
        a.append("sobre_media_200" if f["dist_media_200"] > 0 else "bajo_media_200")
    if f.get("bpa") is not None and f["bpa"] < 0:
        a.append("perdidas")
    if f.get("moneda") and f.get("moneda_contable") and f["moneda"] != f["moneda_contable"]:
        a.append("revisar_moneda")  # cotiza en una divisa y reporta en otra: ratios de Yahoo pueden fallar
    return a


def comparar_con_semana_anterior(filas: list[dict]) -> str | None:
    previos = sorted(HIST_DIR.glob("*.csv")) if HIST_DIR.exists() else []
    hoy = datetime.now().strftime("%Y-%m-%d")
    previos = [p for p in previos if p.stem != hoy]
    if not previos:
        return None
    ult = previos[-1]
    ant = {}
    with ult.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            ant[r["ticker"]] = r
    for f in filas:
        r = ant.get(f["ticker"])
        if r and r.get("score") not in (None, ""):
            try:
                f["score_anterior"] = int(float(r["score"]))
            except ValueError:
                pass
    return ult.stem


def datos_demo(base: dict) -> tuple[dict, list[float]]:
    rnd = random.Random(base["ticker"])
    sectores = ["Financial Services", "Utilities", "Industrials", "Consumer Cyclical", "Energy",
                "Technology", "Healthcare", "Real Estate", "Communication Services", "Basic Materials"]
    precio0 = rnd.uniform(2, 300)
    closes, p = [], precio0
    vol = rnd.uniform(0.01, 0.03)
    for _ in range(252):
        p *= math.exp(rnd.gauss(0.0002, vol))
        closes.append(p)
    acciones = rnd.uniform(1e8, 6e9)
    ebitda = rnd.uniform(5e7, 2e10)
    info = {
        "sector": rnd.choice(sectores), "industry": "Demo", "currency": "EUR",
        "financialCurrency": "EUR" if rnd.random() > 0.08 else "USD",
        "currentPrice": closes[-1], "sharesOutstanding": acciones, "marketCap": closes[-1] * acciones,
        "totalRevenue": ebitda * rnd.uniform(2, 8), "trailingEps": rnd.uniform(-1, 12),
        "dividendRate": closes[-1] * rnd.uniform(0, 0.09), "returnOnAssets": rnd.uniform(-0.02, 0.12),
        "priceToBook": rnd.uniform(0.3, 6), "ebitda": ebitda, "freeCashflow": ebitda * rnd.uniform(-0.2, 0.6),
        "operatingCashflow": ebitda * rnd.uniform(0.4, 0.9), "returnOnEquity": rnd.uniform(-0.05, 0.3),
        "trailingPE": rnd.uniform(4, 40), "forwardPE": rnd.uniform(4, 35), "payoutRatio": rnd.uniform(0, 1.4),
        "totalDebt": ebitda * rnd.uniform(0, 6), "totalCash": ebitda * rnd.uniform(0, 1.5),
    }
    import datetime as _dt
    cierre = [_dt.date(2025, 12, 31), _dt.date(2024, 12, 31)]
    g = rnd.uniform(0.9, 1.15)
    rev = info["totalRevenue"]
    cuentas = {
        "periodos": [c.isoformat() for c in cierre],
        "pyg": {"ingresos": [rev, rev / g], "ebitda": [ebitda, ebitda / g], "ebit": [ebitda * .7, ebitda * .7 / g],
                "rdo_neto": [ebitda * .4, ebitda * .4 / g], "bpa": [ebitda * .4 / acciones, ebitda * .4 / g / acciones]},
        "balance": {"activo_total": [rev * 1.6, rev * 1.5], "patrimonio_neto": [rev * .6, rev * .55],
                    "pasivo_total": [rev, rev * .95], "activo_corriente": [rev * .5, rev * .45],
                    "pasivo_corriente": [rev * .4, rev * .42], "deuda_neta": [ebitda * 1.2, ebitda * 1.5]},
        "flujos": {"fco": [ebitda * .8, ebitda * .7], "capex": [-ebitda * .3, -ebitda * .35],
                   "fcl": [ebitda * .5, ebitda * .35], "dividendos_pagados": [-ebitda * .2, -ebitda * .18]},
    }
    return info, closes, cuentas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="usar datos sintéticos (sin red)")
    ap.add_argument("--pausa", type=float, default=0.6, help="segundos entre tickers")
    args = ap.parse_args()

    universo = leer_tickers()
    filas, errores = [], []
    for i, base in enumerate(universo, 1):
        t = base["ticker"]
        for intento in range(3):
            try:
                info, closes, cuentas = datos_demo(base) if args.demo else descargar(t)
                if not closes and not info.get("regularMarketPrice") and not info.get("currentPrice"):
                    raise ValueError("sin datos de precio (¿ticker erróneo o excluido de bolsa?)")
                filas.append(construir_fila(base, info, closes, cuentas))
                break
            except Exception as e:  # noqa: BLE001
                if intento == 2:
                    errores.append({"ticker": t, "nombre": base["nombre"], "error": str(e)[:200]})
                    print(f"[{i}/{len(universo)}] {t}: ERROR {e}", file=sys.stderr)
                else:
                    time.sleep(2 * (intento + 1))
        if not args.demo:
            time.sleep(args.pausa)

    puntuar(filas)
    for f in filas:
        f["alertas"] = alertas(f)
    semana_previa = None if args.demo else comparar_con_semana_anterior(filas)

    ahora = datetime.now(timezone.utc)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    salida = {
        "generado": ahora.isoformat(timespec="seconds"),
        "fuente": "Yahoo Finance vía yfinance (datos no oficiales; retraso posible)",
        "demo": args.demo,
        "semana_previa": semana_previa,
        "umbrales": UMBRALES,
        "n_universo": len(universo),
        "n_ok": len(filas),
        "errores": errores,
        "valores": filas,
    }
    (OUT_DIR / "latest.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.demo:  # los datos sintéticos no entran en el histórico
        print(f"DEMO: {len(filas)} valores sintéticos en {OUT_DIR / 'latest.json'}")
        return

    # Histórico semanal en CSV (columnas planas)
    campos = ["ticker", "nombre", "indices", "sector", "precio", "capitalizacion", "ingresos", "bpa", "dpa",
              "roa", "pvc", "rdp", "ebitda", "fcl_accion", "fco_accion", "roe", "per", "per_futuro", "payout",
              "deuda_neta_ebitda", "volatilidad", "var_semana", "var_4s", "dist_max_52s", "dist_min_52s",
              "dist_media_200", "score", "alertas", "descargado"]
    fecha = ahora.strftime("%Y-%m-%d")
    with (HIST_DIR / f"{fecha}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for f in filas:
            r = dict(f)
            r["indices"] = "|".join(f["indices"])
            r["alertas"] = "|".join(f["alertas"])
            w.writerow(r)
    semanas = sorted(p.stem for p in HIST_DIR.glob("*.csv"))
    (HIST_DIR / "index.json").write_text(json.dumps(semanas), encoding="utf-8")

    print(f"OK: {len(filas)}/{len(universo)} valores; {len(errores)} errores. Salida en {OUT_DIR}")
    if not args.demo and len(filas) < 0.5 * len(universo):
        sys.exit("Menos de la mitad de los valores descargados: revisa el acceso a Yahoo.")


if __name__ == "__main__":
    main()
