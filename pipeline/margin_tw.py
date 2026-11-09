# -*- coding: utf-8 -*-
"""台股融資槓桿頁資料管線：大盤融資維持率、融資餘額 × 0050 → data/margin-tw.json。

維持率口徑同大盤監控與凱基：Σ(上市各股融資餘額張 × 收盤價 × 1000) ÷ 融資金額餘額（含 ETF）。
逐日資料累積在 data/margin-tw-history.csv，只補缺的日期。

用法：python pipeline/margin_tw.py                       補近 10 天、重算 JSON（排程用）
      python pipeline/margin_tw.py --no-fetch            不抓證交所，只用現有歷史重算
      python pipeline/margin_tw.py --recalc 起 迄 ...    用現行公式重抓全部歷史＋指定區間，寫到 .new 檔
"""
import bisect
import csv
import datetime as dt
import json
import statistics
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
HIST, OUT = ROOT / "data" / "margin-tw-history.csv", ROOT / "data" / "margin-tw.json"
CLOSES = ROOT / "data" / "margin-tw-closes.json"   # 各股最近收盤價，停牌股沿用
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
TW = dt.timezone(dt.timedelta(hours=8))
TWSE_DELAY = 1.5           # 證交所限流，勿低於 1.4 秒
PEAK_DATE = "2026-10-06"   # 與大盤監控同一個波段高點（換波段時手動改）
P50_START = "2009-03-10"   # Yahoo 0050 在此之前有壞點，見 clean_0050
BREAK, NORMAL = 140, 160   # 股災級修正線、正常水位線（使用者 2026-11-09 定案，同大盤監控維持率說明）
RECENT = 15                # 頁面近期明細的筆數
# 證交所憑證在 Python 3.13 以上的嚴格檢查會驗不過，只有這些版本才略過驗證；讀的是公開資料
VERIFY = sys.version_info < (3, 13)
if not VERIFY:
    requests.packages.urllib3.disable_warnings()


def num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except ValueError:
        return None


def twse(path, **params):
    for attempt in range(3):
        try:
            r = requests.get(f"https://www.twse.com.tw/rwd/zh/{path}", params={**params, "response": "json"},
                             headers=UA, timeout=40, verify=VERIFY)
            time.sleep(TWSE_DELAY)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"證交所 {path} {params.get('date')} 第 {attempt + 1} 次失敗：{str(e)[:100]}", flush=True)
            time.sleep(8)
    raise RuntimeError(f"證交所 {path} {params.get('date')} 連續失敗")


def fetch_day(ymd, last):
    """回傳 (維持率, 融資餘額億)；非交易日或融資還沒公布回 None。先查融資，假日少打一次。
    last＝各股最近一次收盤價，會就地更新：當天停牌或無成交的股票沒有收盤價，要沿用前價，
    否則市值被算成 0（例：2024/8/6 矽統停牌，維持率少算 0.75 點）。"""
    jm = twse("marginTrading/MI_MARGN", date=ymd, selectType="ALL")
    tabs = jm.get("tables") or []
    if jm.get("stat") != "OK" or len(tabs) < 2 or not tabs[1].get("data"):
        return None
    fin = next((num(r[5]) * 1000 for r in tabs[0]["data"] if "融資金額" in r[0]), None)
    fields = tabs[1]["fields"]
    bi = 6 if fields[6] == "今日餘額" else fields.index("今日餘額")
    jp = twse("afterTrading/MI_INDEX", date=ymd, type="ALLBUT0999")
    if jp.get("stat") != "OK" or not fin:
        return None
    close = {}
    for t in jp.get("tables", []):
        f = t.get("fields") or []
        if "收盤價" in f and "證券代號" in f:
            fi, ci = f.index("收盤價"), f.index("證券代號")
            for row in t["data"]:
                c = num(row[fi])
                if c:
                    close[row[ci].strip()] = c
    if not close:
        return None
    last.update(close)
    mv = sum((num(r[bi]) or 0) * 1000 * last.get(r[0].strip(), 0) for r in tabs[1]["data"])
    return round(mv / fin * 100, 2), round(fin / 1e8, 1)


def load_hist():
    if not HIST.exists():
        return {}
    with HIST.open(encoding="utf-8", newline="") as f:
        return {r["date"]: (float(r["ratio"]), float(r["fin"])) for r in csv.DictReader(f)}


def save_hist(hist, path=HIST):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", "ratio", "fin"])
        for d in sorted(hist):
            w.writerow([d, *hist[d]])


def load_closes(path=CLOSES):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_closes(last, path=CLOSES):
    path.write_text(json.dumps(last, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def fill(hist, start, end):
    """補 start–end 間缺的平日；回傳新增筆數。"""
    added, d, last = 0, start, load_closes()
    while d <= end:
        iso = d.isoformat()
        if d.weekday() < 5 and iso not in hist:
            v = fetch_day(d.strftime("%Y%m%d"), last)
            if v:
                hist[iso] = v
                added += 1
        d += dt.timedelta(days=1)
    save_hist(hist)
    if added:
        save_closes(last)
    return added


def recalc(windows):
    """用目前公式由舊到新重抓全部歷史＋指定區間，寫到 .new 檔，比對無誤再手動換掉正式檔。
    沿用前價需要依日期順序處理；每 20 筆存一次，中斷後從最後一天接著跑。"""
    old = load_hist()
    new_hist, new_close = HIST.with_suffix(".new.csv"), CLOSES.with_suffix(".new.json")
    done = {}
    if new_hist.exists():
        with new_hist.open(encoding="utf-8", newline="") as f:
            done = {r["date"]: (float(r["ratio"]), float(r["fin"])) for r in csv.DictReader(f)}
    last = load_closes(new_close)
    days = set(old)
    for s, e in windows:
        d, stop = dt.date.fromisoformat(s), dt.date.fromisoformat(e)
        while d <= stop:
            if d.weekday() < 5:
                days.add(d.isoformat())
            d += dt.timedelta(days=1)
    resume = max(done, default="")
    todo = [d for d in sorted(days) if d > resume]
    print(f"重算 {len(todo)} 個日期（已完成 {len(done)} 筆）", flush=True)
    for n, iso in enumerate(todo, 1):
        v = fetch_day(iso.replace("-", ""), last)
        if v:
            done[iso] = v
        elif iso in old:      # 舊資料有、這次抓不到：保留舊值並提示
            done[iso] = old[iso]
            print(f"{iso} 抓不到，保留舊值", flush=True)
        if n % 20 == 0:
            save_hist(done, new_hist)
            save_closes(last, new_close)
            print(f"進度 {n}/{len(todo)}，到 {iso}", flush=True)
    save_hist(done, new_hist)
    save_closes(last, new_close)
    print("重算完成", len(done), "筆", flush=True)


def yahoo_0050():
    """0050 日線還原權息價（與大盤監控相同）。range=max 只回月線，要用 period1 才是日線。"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/0050.TW?period1=0&period2={int(time.time()) + 86400}&interval=1d"
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    j = r.json()["chart"]["result"][0]
    off = j["meta"].get("gmtoffset", 0)
    adj = j["indicators"]["adjclose"][0]["adjclose"]
    out = {}
    for t, a in zip(j["timestamp"], adj):
        day = dt.datetime.fromtimestamp(t + off, dt.timezone.utc)
        if a is not None and day.weekday() < 5:    # Yahoo 偶有週末佔位資料
            out[day.strftime("%Y-%m-%d")] = a
    return dict(sorted(out.items()))


def clean_0050(px):
    """Yahoo 的 0050 有兩個問題（2026-11-09 與加權指數逐日比對確認）：
    1. 2025/6 一拆四只還原到 2014-01-02，再往前仍是原價，當天出現假的 −75%，要把斷點前除以 4。
    2. 2009-03-10 以前逐日跳動超過當時 7% 漲跌幅限制，是壞點，整段不用。"""
    days = sorted(px)
    breaks = [days[i] for i in range(1, len(days)) if px[days[i - 1]] / px[days[i]] > 2.5]
    cut = breaks[-1] if breaks else None
    return {d: (px[d] / 4 if cut and d < cut else px[d]) for d in days if d >= P50_START}


class Px:
    def __init__(self, px):
        self.days, self.vals = list(px), list(px.values())

    def at(self, iso):
        """該日或之前最近一個交易日的價格。"""
        i = bisect.bisect_right(self.days, iso) - 1
        return self.vals[i] if i >= 0 else None

    def shift(self, iso, months):
        target = (dt.date.fromisoformat(iso) + dt.timedelta(days=round(months * 30.44))).isoformat()
        return None if target > self.days[-1] else target

    def fwd(self, iso, months):
        target = self.shift(iso, months)
        base = self.at(iso)
        return round((self.at(target) / base - 1) * 100, 1) if target and base else None

    def maxdd(self, iso, months):
        """iso 收盤起 months 個月內最低收盤的跌幅；未滿期就算到最新。回傳 (跌幅, 是否未滿期)。"""
        target = self.shift(iso, months)
        i0, i1 = bisect.bisect_left(self.days, iso), bisect.bisect_right(self.days, target or self.days[-1])
        if i0 >= i1:
            return None, target is None
        return round((min(self.vals[i0:i1]) / self.vals[i0] - 1) * 100, 1), target is None

    def from_high(self, iso, days=250):
        """iso 相對近 days 個交易日最高收盤的跌幅。"""
        i = bisect.bisect_right(self.days, iso)
        return round((self.vals[i - 1] / max(self.vals[max(0, i - days):i]) - 1) * 100, 1) if i else None


def month_ends(hist, today):
    """每月最後一筆樣本（當月未完不算），統計用，避免事件日與近年逐日資料過度取樣。"""
    last = {}
    for d in sorted(hist):
        last[d[:7]] = d
    return [v for k, v in sorted(last.items()) if k < today[:7]]


def zones(hist, px, today):
    ends = [d for d in month_ends(hist, today) if d >= px.days[0]]
    defs = [(f"≥ {NORMAL}%　正常水位", lambda v: v >= NORMAL), (f"{BREAK}–{NORMAL}%　中型修正", lambda v: BREAK <= v < NORMAL), (f"< {BREAK}%　股災級修正", lambda v: v < BREAK)]
    out = []
    for name, f in defs:
        sub = [d for d in ends if f(hist[d][0])]
        row = {"name": name, "n": len(sub), "share": round(len(sub) / len(ends) * 100, 1) if ends else None}
        for m in (3, 6, 12):
            rets = [x for x in (px.fwd(d, m) for d in sub) if x is not None]
            row[f"r{m}"] = round(statistics.mean(rets), 1) if rets else None
            row[f"w{m}"] = round(sum(x > 0 for x in rets) / len(rets) * 100) if rets else None
        out.append(row)
    return out, (ends[0] if ends else None), (ends[-1] if ends else None)


def events(hist, px):
    """跌破 BREAK 事件：回到 NORMAL 正常水位才算結束，之後再破才是新事件。0050 開始有資料前的事件不列。"""
    out, cur = [], None
    days = sorted(hist)
    for d in days:
        r = hist[d][0]
        if cur is None and r < BREAK:
            cur = {"start": d, "low": r, "lowDate": d}
        elif cur is not None:
            if r < cur["low"]:
                cur["low"], cur["lowDate"] = r, d
            if r >= NORMAL:
                cur["end"] = d
                out.append(cur)
                cur = None
    if cur is not None:
        cur["end"] = None
        out.append(cur)
    res = []
    for e in out:
        s = e["start"]
        if s < px.days[0]:
            continue
        dd, open_dd = px.maxdd(s, 12)
        # 融資減幅：首破前 6 個月內高點 → 首破後 6 個月內低點
        d0 = (dt.date.fromisoformat(s) - dt.timedelta(days=183)).isoformat()
        d1 = (dt.date.fromisoformat(s) + dt.timedelta(days=183)).isoformat()
        before = [hist[x][1] for x in days if d0 <= x <= s]
        after = [hist[x][1] for x in days if s <= x <= d1]
        res.append({"start": s, "end": e["end"], "low": e["low"], "lowDate": e["lowDate"], "ratio": hist[s][0],
                    "fromHigh": px.from_high(s), "r3": px.fwd(s, 3), "r6": px.fwd(s, 6), "r12": px.fwd(s, 12),
                    "dd": dd, "ddOpen": open_dd, "finCut": round((min(after) / max(before) - 1) * 100, 1)})
    return res


def sensitivity(hist, px):
    """近三年逐日樣本：維持率單日變動 vs 0050 單日漲跌的斜率與相關係數，融資餘額同理。"""
    start = (dt.date.fromisoformat(max(hist)) - dt.timedelta(days=1096)).isoformat()
    days = [d for d in sorted(hist) if d >= start]
    pairs = []
    for a, b in zip(days, days[1:]):
        if (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days <= 5 and px.at(a) and px.at(b):
            pairs.append(((px.at(b) / px.at(a) - 1) * 100, hist[b][0] - hist[a][0], (hist[b][1] / hist[a][1] - 1) * 100))
    if len(pairs) < 30:
        return None
    x, y, z = zip(*pairs)
    slope = statistics.linear_regression(x, y).slope
    down = [p for p in pairs if p[0] <= -2]
    return {"n": len(pairs), "start": days[0], "slope": round(slope, 2), "corr": round(statistics.correlation(x, y), 2),
            "corrFin": round(statistics.correlation(x, z), 2),
            "downN": len(down), "downRatio": round(statistics.mean(p[1] for p in down), 1) if down else None,
            "downFin": round(statistics.mean(p[2] for p in down), 1) if down else None}


def build(hist):
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    try:
        px = clean_0050(yahoo_0050())
    except Exception as e:
        print(f"Yahoo 0050 失敗，沿用上次：{e}")
        if not old:
            raise
        px = {d: v for d, v in zip(old["dates"], old["p50"]) if v is not None}
    p = Px(px)
    now = dt.datetime.now(TW)
    today = now.strftime("%Y-%m-%d")
    dates = sorted(set(hist) | set(px))
    zs, z0, z1 = zones(hist, p, today)
    hd = sorted(hist)
    recent = []
    for d in hd[-RECENT:]:
        i = hd.index(d)
        prev = hd[i - 1] if i else None
        a, b = p.at(d), p.at(prev) if prev else None
        recent.append({"d": d, "p": round(a, 2), "pc": round((a / b - 1) * 100, 2) if a and b else None, "r": hist[d][0],
                       "rc": round(hist[d][0] - hist[prev][0], 2) if prev else None, "f": hist[d][1],
                       "fc": round(hist[d][1] - hist[prev][1], 1) if prev else None})
    peak = [d for d in p.days if d <= PEAK_DATE][-1]
    ld = p.days[-1]
    ld_fin = hd[-1]
    fin_year = [hist[d][1] for d in hd if d >= (dt.date.fromisoformat(ld_fin) - dt.timedelta(days=365)).isoformat()]
    r_low = min((d for d in hd if d >= peak), key=lambda d: hist[d][0])
    res = {"updated": now.strftime("%Y/%m/%d %H:%M"), "peakDate": peak,
           "dates": dates,
           "p50": [round(px[d], 2) if d in px else None for d in dates],
           "ratio": [hist[d][0] if d in hist else None for d in dates],
           "fin": [hist[d][1] if d in hist else None for d in dates],
           "zones": zs, "zoneStart": z0, "zoneEnd": z1, "events": events(hist, p), "sens": sensitivity(hist, p), "recent": recent,
           "latest": {"p": round(px[ld], 2), "pDate": ld, "pPeak": round(px[peak], 2), "pFromPeak": round((px[ld] / px[peak] - 1) * 100, 1),
                      "pLow": round(min(v for d, v in px.items() if d >= peak), 2),
                      "r": hist[ld_fin][0], "f": hist[ld_fin][1], "fDate": ld_fin, "rLow": hist[r_low][0], "rLowDate": r_low,
                      "pFromHigh": p.from_high(ld_fin), "pAtFin": round(p.at(ld_fin), 2),
                      "f5": round(hist[ld_fin][1] - hist[hd[-6]][1], 1), "fHigh": max(fin_year),
                      "fFromHigh": round((hist[ld_fin][1] / max(fin_year) - 1) * 100, 1)}}
    OUT.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫入 {OUT.name}：{len(dates)} 日，維持率最新 {ld_fin} {hist[ld_fin][0]}，0050 最新 {ld} {px[ld]:.2f}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    hist = load_hist()
    if "--recalc" in sys.argv:
        a = sys.argv[sys.argv.index("--recalc") + 1:]
        recalc(list(zip(a[::2], a[1::2])))
        return
    today = dt.datetime.now(TW).date()
    if "--no-fetch" not in sys.argv:
        try:
            print("補了", fill(hist, today - dt.timedelta(days=10), today), "筆")
        except Exception as e:      # 證交所暫時抓不到就用現有資料重算，下次排程會再補
            print(f"證交所失敗：{e}")
    build(hist)


if __name__ == "__main__":
    main()
