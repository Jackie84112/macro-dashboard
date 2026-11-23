# -*- coding: utf-8 -*-
"""Put/Call 長期走勢頁（putcall.html）資料：data/putcall.json。

- P/C：Cboe 每日 total / equity / index。2016/12 起的歷史已存在 putcall.json 的 pc 欄（初始來自 Cboe 舊 CSV＋cdn 每日檔），
  每次執行只補 cdn 上缺的日期（https://cdn.cboe.com/data/us/options/market_statistics/daily/<日期>_daily_options）。
- SMH P/C（2026-11-23 使用者要求加「SMH」鈕）：OCC Volume Query 依標的 SMH 的每日成交量，全部交易所、全部帳戶類別加總後
  賣權÷買權（含 1SMH/2SMH 調整後合約）。OCC 只保留最近 2 年，最早抓得到 2024-11-22；之後靠每天執行累積在 putcall.json 的 smh 欄，勿刪。
- 費城半導體 SOX：Yahoo ^SOX 日線，每次重抓（2026-11-20 使用者要求由標普改 SOX）。
- 暴跌區間：SOX 收盤 zigzag，跌幅與反彈幅都 ≥15% 才算一段（高點→低點）；最後一段若還沒反彈 7%，低點暫定為目前最低。
  規則與回測腳本 專案\\總經\\宏觀因果驗證\\putcall\\crash\\events.py 相同。
"""
import csv
import datetime as dt
import io
import json
import time
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "putcall.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
START, ZZ = "2017-01-01", 0.15
# 使用者指定合併的期間（同一件事算一次）：區間內的 zigzag 事件併成「第一個高點 → 區間內最低收盤」
# 2026-11-20：2022 升息空頭 #4–#6（2021/12/27 高點 → 2022/10/14 低點）合併；2023 美債殖利率那次另計
MERGE = [("2021-12-27", "2022-10-14")]


def cboe(iso):
    r = requests.get(f"https://cdn.cboe.com/data/us/options/market_statistics/daily/{iso}_daily_options", headers=UA, timeout=30)
    if r.status_code != 200:
        return None
    try:
        rs = {x["name"]: float(str(x["value"]).replace(",", "")) for x in r.json().get("ratios", [])}
    except ValueError:
        return None
    t = rs.get("TOTAL PUT/CALL RATIO")
    return [t, rs.get("EQUITY PUT/CALL RATIO"), rs.get("INDEX PUT/CALL RATIO")] if t else None


def occ(iso, sym="SMH"):
    r = requests.get("https://marketdata.theocc.com/volume-query", headers=UA, timeout=30, params={
        "reportDate": iso.replace("-", ""), "format": "csv", "volumeQueryType": "O", "symbolType": "U", "symbol": sym,
        "reportType": "D", "accountType": "ALL", "productKind": "ALL", "porc": "BOTH"})
    if r.status_code != 200 or not r.text.startswith("quantity"):
        return None
    c = p = 0
    for row in csv.DictReader(io.StringIO(r.text)):
        q = int(row["quantity"] or 0)
        if row["porc"] == "C": c += q
        elif row["porc"] == "P": p += q
    return round(p / c, 3) if c and p else None


def sox():
    j = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/%5ESOX?period1=1451606400&period2={int(time.time())}&interval=1d",
                     headers=UA, timeout=60).json()["chart"]["result"][0]
    off = j["meta"].get("gmtoffset", 0)
    day = lambda t: dt.datetime.fromtimestamp(t + off, dt.timezone.utc).strftime("%Y-%m-%d")
    out = {day(t): c for t, c in zip(j["timestamp"], j["indicators"]["quote"][0]["close"]) if c}
    m = j["meta"]   # Yahoo 最新一根收盤偶爾整批 null，用 regularMarketPrice 補
    if m.get("regularMarketPrice") and m.get("regularMarketTime"):
        out.setdefault(day(m["regularMarketTime"]), m["regularMarketPrice"])
    return dict(sorted(out.items()))


def zigzag(px, r):
    ds, vs = list(px), list(px.values())
    piv, trend, hi, lo = [], 0, 0, 0
    for i in range(1, len(vs)):
        if vs[i] > vs[hi]: hi = i
        if vs[i] < vs[lo]: lo = i
        if trend >= 0 and vs[i] <= vs[hi] * (1 - r):
            piv.append(("H", hi)); trend = -1; lo = i
        elif trend <= 0 and vs[i] >= vs[lo] * (1 + r):
            if trend == -1: piv.append(("L", lo))
            trend = 1; hi = i
    if trend == -1:
        piv.append(("L", lo))
    pairs = list(zip(piv, piv[1:]))
    return [[ds[i], ds[j], round(vs[j] / vs[i] - 1, 6), k == len(pairs) - 1 and trend == -1]
            for k, ((a, i), (b, j)) in enumerate(pairs) if a == "H" and b == "L"]


def main():
    old = json.loads(OUT.read_text(encoding="utf-8"))
    pc = old["pc"]
    d = dt.date.fromisoformat(max(pc)) + dt.timedelta(days=1)
    today = dt.datetime.now(dt.timezone.utc).date()
    while d <= today:
        if d.weekday() < 5:
            v = cboe(d.isoformat())
            if v:
                pc[d.isoformat()] = v
        d += dt.timedelta(days=1)
    pc = dict(sorted(pc.items()))
    smh = old.get("smh", {})
    d = max(dt.date.fromisoformat(max(smh)) + dt.timedelta(days=1) if smh else dt.date(2024, 11, 22), today - dt.timedelta(days=729))
    while d <= today:
        if d.weekday() < 5 and d.isoformat() in pc:   # 只抓 Cboe 有資料的交易日
            try:
                v = occ(d.isoformat())
            except requests.RequestException:
                v = None
            if v:
                smh[d.isoformat()] = v
        d += dt.timedelta(days=1)
    smh = dict(sorted(smh.items()))
    px = sox()
    ds = [x for x in pc if x >= "2016-12-01"]
    s, last = [], None
    for x in ds:
        last = px.get(x, last)
        s.append(round(last, 2) if last else None)
    ev = [e for e in zigzag(px, ZZ) if e[1] >= START]
    for m0, m1 in MERGE:
        grp = [e for e in ev if m0 <= e[0] and e[1] <= m1]
        if len(grp) > 1:
            hi = grp[0][0]; lo = min((d for d in px if hi <= d <= m1), key=lambda d: px[d])
            ev = [e for e in ev if e not in grp] + [[hi, lo, round(px[lo] / px[hi] - 1, 6), grp[-1][3]]]
    ev.sort()
    out = {"updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y/%m/%d %H:%M"),
           "start": START, "idx": {"name": "SOX", "d": ds, "v": s}, "ev": ev, "pc": pc, "smh": smh}
    if all(old.get(k) == out[k] for k in ("idx", "ev", "pc", "smh")):   # 資料沒變就不動檔案，Actions 才不會每天空提交
        print("putcall 無變動", max(pc)); return
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print("putcall", len(pc), max(pc), "events", len(ev), "smh", len(smh), max(smh) if smh else "-")


if __name__ == "__main__":
    main()
