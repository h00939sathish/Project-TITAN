#!/usr/bin/env python3
"""EXP-00025 — trader.dev strategy families ported to FX (resampled to their
native timeframe) tested on real Dukascopy bid/ask.

The 24 trader.dev strategies are all designed on 60m / 240m crypto candles.
Running them on 1-minute FX bars is NOT a fair test (they whip). So we resample
the real FX 1m bid/ask data to 60m and 240m and run the SAME Pine-ported logic
at the timeframe it was authored for. Execution is bar-conservative:
signal on close(i), fill at open(i+1) on the adverse side (buy ask / sell bid),
intrabar SL/TP/trail checks against high/low, real spread + slippage + commission.

THIS IS A RESEARCH/EVIDENCE RUN ONLY — no orders, no capital movement.
Run:  python research/run_traderdev_families.py
"""
from __future__ import annotations
import json
import statistics
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "research" / "dukascopy_1m_ba"
PAIRS = ["EURUSD", "GBPUSD"]
FRAMES = [(60, "1h"), (240, "4h")]
SLIPPAGE_BPS = 0.5
COMMISSION_BPS = 0.2
QTY = 10_000
PIP = 0.0001


# ---------------- data helpers ----------------
def resample(rows, minutes):
    out = []
    cur = None
    for b in rows:
        dt = b["dt"]
        key = int(dt // (minutes * 60))
        if cur is None or cur[0] != key:
            if cur:
                out.append(cur[1])
            cur = [key, {"timestamp": b["ts"], "o_ask": b["o_ask"], "o_bid": b["o_bid"],
                         "h_ask": b["h_ask"], "h_bid": b["h_bid"], "l_ask": b["l_ask"],
                         "l_bid": b["l_bid"], "c_ask": b["c_ask"], "c_bid": b["c_bid"], "n": b["n"]}]
        else:
            d = cur[1]
            d["h_ask"] = max(d["h_ask"], b["h_ask"]); d["h_bid"] = max(d["h_bid"], b["h_bid"])
            d["l_ask"] = min(d["l_ask"], b["l_ask"]); d["l_bid"] = min(d["l_bid"], b["l_bid"])
            d["c_ask"] = b["c_ask"]; d["c_bid"] = b["c_bid"]; d["n"] += b["n"]
    if cur:
        out.append(cur[1])
    return out


def load(rows_raw, minutes):
    from datetime import datetime
    rows = []
    for b in rows_raw:
        dt = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        rows.append({**{k: b[k] for k in ("o_ask","o_bid","h_ask","h_bid","l_ask","l_bid","c_ask","c_bid","n")},
                      "dt": dt.timestamp(), "ts": b["timestamp"]})
    return resample(rows, minutes)


# ---------------- indicators ----------------
def ema(vals, period):
    out=[None]*len(vals); k=2.0/(period+1); e=None
    for i,v in enumerate(vals):
        e = v if e is None else v*k+e*(1-k); out[i]=e
    return out

def sma(vals, period):
    out=[None]*len(vals); acc=0.0
    for i,v in enumerate(vals):
        acc+=v
        if i>=period: acc-=vals[i-period]
        if i>=period-1: out[i]=acc/period
    return out

def tr(rows):
    out=[0.0]*len(rows); pc=rows[0]["c_bid"]
    for i in range(1,len(rows)):
        h,l=rows[i]["h_bid"],rows[i]["l_bid"]
        out[i]=max(h-l,abs(h-pc),abs(l-pc)); pc=rows[i]["c_bid"]
    return out

def atr(rows, period):
    trs=tr(rows); out=[None]*len(rows); acc=0.0
    for i in range(len(rows)):
        acc+=trs[i]
        if i>=period: acc-=trs[i-period]
        if i>=period-1: out[i]=acc/period
    return out

def vwap_daily(rows):
    out=[None]*len(rows); day=None; pv=vol=0.0
    for i,b in enumerate(rows):
        d=b["timestamp"][:10]
        if d!=day: day=d; pv=vol=0.0
        v=max(b["n"],1); pv+=b["c_bid"]*v; vol+=v; out[i]=pv/vol
    return out

def supertrend(rows, period, factor):
    """Canonical Pine ta.supertrend. direction: -1 = uptrend (bull), +1 = downtrend."""
    a = atr(rows, period)
    n = len(rows)
    st = [0.0] * n
    direction = [0] * n
    final_upper = [0.0] * n
    final_lower = [0.0] * n
    for i in range(n):
        if a[i] is None:
            continue
        mid = (rows[i]["h_bid"] + rows[i]["l_bid"]) / 2
        bu = mid + factor * a[i]
        bl = mid - factor * a[i]
        prev_fu = final_upper[i - 1] if i > 0 else bu
        prev_fl = final_lower[i - 1] if i > 0 else bl
        prev_close = rows[i - 1]["c_bid"] if i > 0 else rows[i]["c_bid"]
        final_upper[i] = bu if (bu < prev_fu or prev_close > prev_fu) else prev_fu
        final_lower[i] = bl if (bl > prev_fl or prev_close < prev_fl) else prev_fl
        if i == 0:
            st[i] = bu
            direction[i] = -1
        else:
            prev_st = st[i - 1]
            if prev_close > prev_fu:
                st[i] = final_lower[i]
            elif prev_close < prev_fl:
                st[i] = final_upper[i]
            else:
                st[i] = prev_st
            direction[i] = -1 if rows[i]["c_bid"] > st[i] else 1
    return st, direction

def adx(rows, period):
    n=len(rows); out=[None]*n
    if n<period+2: return out
    pdm=[0.0]*n; mdm=[0.0]*n; trs=tr(rows)
    for i in range(1,n):
        up=rows[i]["h_bid"]-rows[i-1]["h_bid"]; dn=rows[i-1]["l_bid"]-rows[i]["l_bid"]
        pdm[i]=up if (up>dn and up>0) else 0.0
        mdm[i]=dn if (dn>up and dn>0) else 0.0
    ts=sma(trs[1:],period); ps=sma(pdm[1:],period); ms=sma(mdm[1:],period)
    for i in range(period,n):
        if ts[i-1] and ps[i-1] is not None and ms[i-1] is not None and ts[i-1]>0:
            pdi=100*ps[i-1]/ts[i-1]; mdi=100*ms[i-1]/ts[i-1]
            out[i]=abs(pdi-mdi)/(pdi+mdi)*100
    return out

def trend_centroid(vals, win=50):
    n=len(vals)
    es=[ema(vals,p) for p in (4,8,16,32,64,128)]
    bands=[[(es[k][i]-es[k+1][i]) if es[k][i] is not None and es[k+1][i] is not None else 0.0 for i in range(n)] for k in range(5)]
    out=[None]*n
    for i in range(n):
        lo=max(0,i-win+1); ps=[]
        for k in range(5):
            s=sum(x*x for x in bands[k][lo:i+1]); ps.append(max(s/max(i-lo+1,1),1e-12))
        den=sum(ps)
        if den>0: out[i]=sum((8,16,32,64,128)[k]*ps[k] for k in range(5))/den
    return out


# ---------------- family runner ----------------
class FamilyRunner:
    family=""
    def __init__(self, rows): self.rows=rows; self.n=len(rows); self.prep()
    def prep(self): pass
    def signal(self, i): return None, {}
    def trail_mult(self): return 1.0
    def _load_atr(self,p=14): self._atr=atr(self.rows,p)

    def run(self):
        rows=self.rows
        cash=0.0; pos=0; entry=0.0; sl=tp=trail=None
        trades=0; wins=0; peak=0.0; md=0.0
        BASE=100000.0
        exits={"sl":0,"tp":0,"trail":0}
        pnl=[]
        for i in range(self.n):
            b=rows[i]
            h=b["h_bid"]; l=b["l_bid"]; c=b["c_bid"]
            if pos!=0:
                ex=None; reason=None
                if pos>0:
                    if sl is not None and l<=sl: ex,reason=sl,"sl"
                    elif tp is not None and b["h_bid"]>=tp: ex,reason=tp,"tp"
                    elif trail is not None and l<=trail: ex,reason=trail,"trail"
                    if ex is None and trail is not None:
                        nt=c-self._atr[i]*self.trail_mult(); trail=max(trail,nt)
                else:
                    if sl is not None and b["h_bid"]>=sl: ex,reason=sl,"sl"
                    elif tp is not None and b["l_bid"]<=tp: ex,reason=tp,"tp"
                    elif trail is not None and b["h_bid"]>=trail: ex,reason=trail,"trail"
                    if ex is None and trail is not None:
                        nt=c+self._atr[i]*self.trail_mult(); trail=min(trail,nt)
                if ex is not None:
                    fill = ex - (SLIPPAGE_BPS/10000)*ex if pos>0 else ex + (SLIPPAGE_BPS/10000)*ex
                    p = (fill-entry)*QTY*pos if pos>0 else (entry-fill)*QTY*-pos
                    p -= (COMMISSION_BPS/10000)*fill*QTY
                    cash+=p; pnl.append(p); trades+=1
                    if p>0: wins+=1
                    exits[reason]+=1; pos=0; sl=tp=trail=None
            if pos==0 and i<self.n-1:
                side,levels=self.signal(i)
                if side in ("BUY","SELL"):
                    nxt=rows[i+1]
                    fill = nxt["o_ask"]+(SLIPPAGE_BPS/10000)*nxt["o_ask"] if side=="BUY" else nxt["o_bid"]-(SLIPPAGE_BPS/10000)*nxt["o_bid"]
                    entry=fill; pos=1 if side=="BUY" else -1
                    sl,tp=levels.get("sl"),levels.get("tp"); trail=levels.get("trail")
            # mtm equity (normalized so 0 = starting)
            if pos!=0:
                mtm = cash + (c-entry)*QTY if pos>0 else cash + (entry-c)*QTY
                eq = BASE + mtm
                if eq>peak: peak=eq
                if peak>0: md=max(md,(peak-eq)/peak)
        if pos!=0:
            c=rows[-1]
            fill = c["c_bid"]-(SLIPPAGE_BPS/10000)*c["c_bid"] if pos>0 else c["c_ask"]+(SLIPPAGE_BPS/10000)*c["c_ask"]
            p=(fill-entry)*QTY*pos if pos>0 else (entry-fill)*QTY*-pos
            p-=(COMMISSION_BPS/10000)*fill*QTY; cash+=p; pnl.append(p); trades+=1
            if p>0: wins+=1
        return {"family": self.family, "trades":trades,"wins":wins,"win_rate":wins/trades if trades else 0.0,
                "net_pips":cash/(QTY*PIP),"max_dd_pct":md*100,
                "avg_pips":(cash/trades)/(QTY*PIP) if trades else 0.0,"exits":exits,
                "pnl_list":pnl}


# ---------------- families ----------------
class F1_EMA9VWAP(FamilyRunner):
    family="F1_ema9_vwap"
    def prep(self):
        self._load_atr(14)
        self._ema9=ema([b["c_bid"] for b in self.rows],9)
        self._vwap=vwap_daily(self.rows)
    def signal(self,i):
        e9,vw=self._ema9[i],self._vwap[i]
        if e9 is None or vw is None: return None,{}
        pe9=self._ema9[i-1] if i>0 else None; pvw=self._vwap[i-1] if i>0 else None
        a=self._atr[i] or 0.0; c=self.rows[i]["c_bid"]
        if pe9 is not None and pvw is not None:
            if pe9<=pvw and e9>vw: return "BUY",{"trail":c-a*2.0}
            if pe9>=pvw and e9<vw: return "SELL",{"trail":c+a*2.0}
        return None,{}
    def trail_mult(self): return 2.0

class F2_EMA2060(FamilyRunner):
    family="F2_ema20_60"; SL,TP=2.5,11.0
    def prep(self):
        closes=[b["c_bid"] for b in self.rows]
        self._e20=ema(closes,20); self._e60=ema(closes,60)
    def signal(self,i):
        f,s=self._e20[i],self._e60[i]
        if f is None or s is None: return None,{}
        pf=self._e20[i-1] if i>0 else None; ps=self._e60[i-1] if i>0 else None
        c=self.rows[i]["c_bid"]
        if pf is not None and ps is not None:
            if pf<=ps and f>s: return "BUY",{"sl":c*(1-self.SL/100),"tp":c*(1+self.TP/100)}
            if pf>=ps and f<s: return "SELL",{"sl":c*(1+self.SL/100),"tp":c*(1-self.TP/100)}
        return None,{}

class F3_StDouble(FamilyRunner):
    family="F3_st_double"
    def prep(self):
        self._load_atr(13)
        self._stf,self._stfd=supertrend(self.rows,13,3.0)
        self._sts,self._stsd=supertrend(self.rows,65,3.0)
    def signal(self,i):
        fd,sd=self._stfd[i],self._stsd[i]
        if i==0 or fd==0 or sd==0: return None,{}
        pfd=self._stfd[i-1]; psd=self._stsd[i-1]
        bb=fd<0 and sd<0; bs=fd>0 and sd>0
        pbb=pfd<0 and psd<0; pbs=pfd>0 and psd>0
        c=self.rows[i]["c_bid"]
        if bb and not pbb: return "BUY",{"trail":c-(self._atr[i] or 0.0)*2.0}
        if bs and not pbs: return "SELL",{"trail":c+(self._atr[i] or 0.0)*2.0}
        return None,{}

class F4_StVolTrail(FamilyRunner):
    family="F4_st_vol_trail"
    def prep(self):
        self._load_atr(10)
        self._stl,self._std=supertrend(self.rows,10,3.0)
        a=[x if x is not None else 0.0 for x in self._atr]
        self._atravg=sma(a,50)
    def signal(self,i):
        d=self._std[i]
        if i==0 or d==0: return None,{}
        pd=self._std[i-1]; a=self._atr[i] or 0.0; avg=self._atravg[i] or 0.0
        c=self.rows[i]["c_bid"]; st=self._stl[i] or c
        if d<0 and pd>=0 and c>st and a>avg: return "BUY",{"trail":max(st,c-a*2.0)}
        if d>0 and pd<=0 and c<st and a>avg: return "SELL",{"trail":min(st,c+a*2.0)}
        return None,{}

class F5_Spectral(FamilyRunner):
    family="F5_spectral"; SL_PCT,TP_PCT=2.5,7.0
    def prep(self):
        closes=[b["c_bid"] for b in self.rows]
        self._e20=ema(closes,20); self._e60=ema(closes,60)
        self._tc=trend_centroid(closes,50)
    def signal(self,i):
        f,s=self._e20[i],self._e60[i]; tc=self._tc[i]
        if f is None or s is None or tc is None: return None,{}
        pf=self._e20[i-1] if i>0 else None; ps=self._e60[i-1] if i>0 else None
        c=self.rows[i]["c_bid"]
        if pf is not None and ps is not None:
            if pf<=ps and f>s and tc>45.0: return "BUY",{"sl":c*(1-self.SL_PCT/100),"tp":c*(1+self.TP_PCT/100)}
            if pf>=ps and f<s and tc>45.0: return "SELL",{"sl":c*(1+self.SL_PCT/100),"tp":c*(1-self.TP_PCT/100)}
        return None,{}

class F6_ADXVwap(FamilyRunner):
    family="F6_adx_vwap"
    def prep(self):
        self._load_atr(14)
        closes=[b["c_bid"] for b in self.rows]
        self._e9=ema(closes,9); self._vw=vwap_daily(self.rows)
        self._sma200=sma(closes,200); self._adx=adx(self.rows,14)
    def signal(self,i):
        e9,vw,s200,ad=self._e9[i],self._vw[i],self._sma200[i],self._adx[i]
        if None in (e9,vw,s200,ad): return None,{}
        pe9=self._e9[i-1] if i>0 else None; pvw=self._vw[i-1] if i>0 else None
        c=self.rows[i]["c_bid"]; a=self._atr[i] or 0.0
        if pe9 is not None and pvw is not None:
            if pe9<=pvw and e9>vw and c>s200 and ad>=18.0: return "BUY",{"trail":c-a*0.03,"sl":c-a*1.5}
            if pe9>=pvw and e9<vw and c<s200 and ad>=18.0: return "SELL",{"trail":c+a*0.03,"sl":c+a*1.5}
        return None,{}

FAMILIES=[F1_EMA9VWAP,F2_EMA2060,F3_StDouble,F4_StVolTrail,F5_Spectral,F6_ADXVwap]

def main():
    print("=" * 78)
    print("EXP-00025 — trader.dev strategy families on real FX (dukascopy 1m bid/ask resampled)")
    print("  Cost model: real spread (buy ask / sell bid) + slippage 0.5bps + commission 0.2bps")
    print("=" * 78)
    summary = []
    for pair in PAIRS:
        raw = json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8"))
        for mins, tfname in FRAMES:
            rows = load(raw, mins)
            print(f"\n### {pair} {tfname}  ({len(rows):,} bars  {rows[0]['timestamp'][:10]} -> {rows[-1]['timestamp'][:10]})")
            for F in FAMILIES:
                try:
                    runner = F(rows)
                    r = runner.run()
                except Exception as e:
                    print(f"  {F.family:<16} ERROR {e}")
                    continue
                r["pair"] = pair; r["frame"] = tfname
                summary.append(r)
                print(f"  {r['family']:<16} trades={r['trades']:>3} win={r['win_rate']*100:5.1f}% "
                      f"net={r['net_pips']:+8.1f} pips  avg={r['avg_pips']:+6.2f} pip/trade  "
                      f"maxDD={r['max_dd_pct']:5.1f}%  exits={r['exits']}")
    print("\n" + "=" * 78)
    print("AGGREGATE (2 pairs, both timeframes — total net pips, pooled)")
    print("=" * 78)
    by = {}
    for r in summary:
        by.setdefault(r["family"], []).append(r)
    ranked = []
    for fam, rs in by.items():
        tot = sum(x["net_pips"] for x in rs)
        tr = sum(x["trades"] for x in rs)
        wins = sum(x["wins"] for x in rs)
        ranked.append((fam, tot, tr, wins / tr if tr else 0.0))
    ranked.sort(key=lambda x: -x[1])
    for fam, tot, tr, wr in ranked:
        print(f"  {fam:<16} total={tot:+8.1f} pips  trades={tr:>3}  win={wr*100:5.1f}%")
    # JSON dump for evidence bundle
    out = Path(__file__).resolve().parents[1] / "research" / "results" / "EXP-00025_traderdev_families.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()