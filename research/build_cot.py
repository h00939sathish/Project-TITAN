"""Build FX COT positioning series from CFTC fut_fin_txt history files.

Net managed-money positioning per FX contract, weekly (report date), 2010-2026.
Writes research/cot/fx_cot.json: {contract: [{date, oi, mm_long, mm_short, net, net_pct_oi}]}

Run:  python research/build_cot.py
"""
import csv
import io
import json
import zipfile
from pathlib import Path

COT = Path(__file__).resolve().parents[1] / "research" / "cot"
FX_MARKETS = {
    "EURO FX": "EUR",
    "BRITISH POUND": "GBP",
    "JAPANESE YEN": "JPY",
    "SWISS FRANC": "CHF",
    "CANADIAN DOLLAR": "CAD",
    "AUSTRALIAN DOLLAR": "AUD",
    "NZ DOLLAR": "NZD",
    "MEXICAN PESO": "MXN",
    "SWEDISH KRONA": "SEK",
    "NORWEGIAN KRONE": "NOK",
}


def main():
    series: dict[str, list[dict]] = {ccy: [] for ccy in FX_MARKETS.values()}
    for year in range(2010, 2027):
        zpath = COT / f"fut_fin_{year}.zip"
        if not zpath.exists():
            continue
        with zipfile.ZipFile(zpath) as z:
            name = z.namelist()[0]
            raw = z.read(name).decode("latin-1", errors="replace")
        for row in csv.DictReader(io.StringIO(raw)):
            # exact contract name (before the " - EXCHANGE" suffix) to avoid
            # false substring matches (e.g. EURO FX vs EURO FX/BRITISH POUND XRATE)
            contract = row.get("Market_and_Exchange_Names", "").split(" - ")[0].strip().upper()
            ccy = FX_MARKETS.get(contract)
            if ccy is None:
                continue
            try:
                d = row["Report_Date_as_YYYY-MM-DD"]
                oi = float(row["Open_Interest_All"])
                ml = float(row["Lev_Money_Positions_Long_All"])
                ms = float(row["Lev_Money_Positions_Short_All"])
            except (KeyError, ValueError):
                continue
            net = ml - ms
            series[ccy].append({
                "date": d, "oi": oi, "mm_long": ml, "mm_short": ms,
                "net": net, "net_pct_oi": net / oi if oi else 0.0,
            })
    out = {ccy: sorted(v, key=lambda r: r["date"]) for ccy, v in series.items()}
    (COT / "fx_cot.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for ccy, rows in out.items():
        if rows:
            print(f"{ccy}: {len(rows)} weeks ({rows[0]['date']} -> {rows[-1]['date']})")


if __name__ == "__main__":
    main()
