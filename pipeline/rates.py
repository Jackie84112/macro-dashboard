"""貨幣成本看板資料管線：從 FRED 抓資料 → 計算 → 寫 data/rates.json。

FRED 的公債殖利率晚 1–2 個交易日、WTI 現貨（EIA）晚約一週，所以：
- 2 年／10 年殖利率：FRED 歷史 + 美國財政部每日殖利率補最近幾天（FRED DGS 即源自財政部）
- WTI：改用 Yahoo Finance NYMEX WTI 近月期貨 CL=F（同 PPT 的財經M平方圖）
點陣圖、FedWatch、CDS 沒有免費資料源，放在 data/rates-manual.json 手動維護，網頁直接讀。
沿用 labor.py 的 FRED 抓取與四捨五入工具。
"""
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from labor import START, fred, half_up, monthly, points

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}


def yahoo(symbol: str) -> pd.Series:
    """Yahoo Finance 日收盤（交易所當地日期）。當天盤中為最新成交價。"""
    p1 = int(pd.Timestamp(START).timestamp())
    p2 = int(time.time()) + 86400
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1d"
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    tz = res["meta"]["exchangeTimezoneName"]
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(tz).tz_localize(None).normalize()
    s = pd.Series(res["indicators"]["quote"][0]["close"], index=idx, dtype="float64").dropna()
    return s.groupby(level=0).last()


def treasury_recent() -> pd.DataFrame:
    """財政部每日殖利率曲線（今年；1 月初再加去年），欄位 2 Yr、10 Yr。"""
    year = pd.Timestamp.now().year
    frames = []
    for y in ([year - 1] if pd.Timestamp.now().month == 1 else []) + [year]:
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
               f"daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
        r = requests.get(url, headers=UA, timeout=60)
        r.raise_for_status()
        frames.append(pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True)[["2 Yr", "10 Yr"]])
    return pd.concat(frames).sort_index()


def with_recent(hist: pd.Series, recent: pd.Series) -> pd.Series:
    """FRED 歷史接上較新的來源；重疊日期以較新來源為準。"""
    return pd.concat([hist[hist.index < recent.index.min()], recent.dropna()]).sort_index()

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "rates.json"
CAL = ROOT / "data" / "calendar.json"

# 表格列定義：(群組, 列名, key, 上升代表, 格式, 發布排程)
# 通膨類上升都是惡化；聯準利率不上色
ROWS = [
    ("政策利率", "聯準利率上限（FFR）", "ffr", None, "pct2", "fomc"),
    ("物價年增", "PPI", "ppi", "bad", "pct1", "ppi"),
    ("物價年增", "Core PPI", "core_ppi", "bad", "pct1", "ppi"),
    ("物價年增", "CPI", "cpi", "bad", "pct1", "cpi"),
    ("物價年增", "Core CPI", "core_cpi", "bad", "pct1", "cpi"),
    ("物價年增", "PCE", "pce", "bad", "pct1", "pce"),
    ("物價年增", "Core PCE", "core_pce", "bad", "pct1", "pce"),
    ("物價年增", "Trimmed Mean PCE", "trim", "bad", "pct1", "pce"),
    ("Fed 觀察", "PCE（6 個月年化，Warsh）", "pce6", "bad", "pct1", "pce"),
    ("Fed 觀察", "Core PCE（3 個月年化，Waller）", "core_pce3", "bad", "pct1", "pce"),
    ("Fed 觀察", "Core CPI（月增）", "core_cpi_mom", "bad", "signed_pct1", "cpi"),
]

# 市場快照表：(列名, key, 格式, 排程)；前值取一週前
SNAP = [
    ("2 年期公債殖利率", "dgs2", "pct2", "daily"),
    ("10 年期公債殖利率", "dgs10", "pct2", "daily"),
    ("10 年減 2 年利差", "t10y2y", "pct2", "daily"),
    ("高收益債殖利率（BB 級）", "hy_bb", "pct2", "daily"),
    ("高收益債殖利率（B 級）", "hy_b", "pct2", "daily"),
    ("高收益債殖利率（CCC 級以下）", "hy_ccc", "pct2", "daily"),
    ("WTI 原油（美元／桶）", "wti", "dec2", "daily"),
]


def fmt(v: float, kind: str) -> str:
    if kind == "pct1":
        return f"{half_up(v, 1)}%"
    if kind == "pct2":
        return f"{half_up(v, 2)}%"
    if kind == "signed_pct1":
        d = half_up(v, 1)
        return f"+{d}%" if d > 0 else f"{d}%"
    return f"{half_up(v, 2)}"


def annualized(s: pd.Series, months: int) -> pd.Series:
    return ((s / s.shift(months)) ** (12 / months) - 1) * 100


def changes_only(s: pd.Series) -> pd.Series:
    """聯準利率是階梯，只留變動日（再補最後一天）縮小檔案。"""
    keep = s[s.diff() != 0]
    return pd.concat([keep, s.iloc[[-1]]]).groupby(level=0).last()


def fomc_months(cal: dict) -> dict:
    """FOMC 決議日（美東）→ 該月份 Period。"""
    return {pd.Period(d[:7], freq="M"): pd.Timestamp(d[:10]) for d in cal.get("fomc", [])}


def build_table(src: dict, ffr_upper: pd.Series, cal: dict, years: int = 3) -> dict:
    latest = src["cpi"].index[-1]
    year_list = list(range(latest.year - years + 1, latest.year + 1))
    meetings = fomc_months(cal)
    today = pd.Timestamp.now().normalize()

    rows = []
    for group, label, key, up, kind, sched in ROWS:
        row = {"group": group, "label": label, "key": key, "schedule": sched, "cells": {}}
        if key == "ffr":
            # 只在有 FOMC 會議的月份顯示決議後利率，沒開會的月份顯示「–」
            for y in year_list:
                cells = []
                for m in range(1, 13):
                    per = pd.Period(year=y, month=m, freq="M")
                    day = meetings.get(per)
                    if day is not None and day < today:
                        after = ffr_upper[ffr_upper.index > day]
                        v = float(after.iloc[0] if len(after) else ffr_upper.iloc[-1])
                        cells.append({"v": fmt(v, kind)})
                    elif per.end_time < today:
                        cells.append({"v": "–"})
                    else:
                        cells.append(None)
                row["cells"][str(y)] = cells
            rows.append(row)
            continue

        s = src[key].dropna()
        shown = {p: fmt(v, kind) for p, v in s.items()}
        last_p = s.index[-1]
        cls = None
        if up and len(s) >= 2:
            cur, prev = shown[last_p], shown[s.index[-2]]
            if cur == prev:
                cls = "flat"
            else:
                rising = s.iloc[-1] > s.iloc[-2]
                cls = "good" if rising == (up == "good") else "bad"
        for y in year_list:
            cells = []
            for m in range(1, 13):
                per = pd.Period(year=y, month=m, freq="M")
                if per in shown:
                    cell = {"v": shown[per]}
                    if per == last_p and cls:
                        cell["c"] = cls
                    cells.append(cell)
                else:
                    cells.append(None)
            row["cells"][str(y)] = cells
        rows.append(row)

    return {"years": year_list, "latestYear": latest.year, "latestMonth": latest.month, "rows": rows}


def build_snapshot(daily: dict) -> list:
    # 前值＝本次更新日（台灣時間）往前 7 天（或之前最近一個交易日），與網頁圖上的一週前虛線同一天
    week_ago = pd.Timestamp.now(tz="Asia/Taipei").tz_localize(None).normalize() - pd.Timedelta(days=7)
    out = []
    for label, key, kind, sched in SNAP:
        s = daily[key].dropna()
        d, v = s.index[-1], float(s.iloc[-1])
        prior = s[s.index <= week_ago]
        pd_, pv = prior.index[-1], float(prior.iloc[-1])
        out.append({"label": label, "key": key, "schedule": sched,
                    "prev": fmt(pv, kind), "prevDate": pd_.strftime("%Y-%m-%d"),
                    "cur": fmt(v, kind), "date": d.strftime("%Y-%m-%d"),
                    "delta": round(v - pv, 4), "unit": "usd" if kind == "dec2" else "pct"})
    return out


def diff_changes(prev: dict, new: dict) -> tuple[list, dict]:
    """同 labor.py：列出數據表本次新增／修正的格子。"""
    out, marks = [], {}
    prev_rows = {r["key"]: r for r in prev.get("table", {}).get("rows", [])}
    for row in new["table"]["rows"]:
        old = prev_rows.get(row["key"], {}).get("cells", {})
        items = []
        for y, cells in row["cells"].items():
            ocells = old.get(y, [None] * 12)
            for m, (c, o) in enumerate(zip(cells, ocells), start=1):
                v = c["v"] if c else None
                ov = o["v"] if o else None
                if v in (None, "–") or v == ov:
                    continue
                tag = f"{y}/{m}" if y != str(new["table"]["latestYear"]) else f"{m}月"
                items.append(f"{tag} {v}（新）" if ov in (None, "–") else f"{tag} {ov} → {v}（修正）")
                marks.setdefault(row["key"], []).append(f"{y}-{m}")
        if items:
            out.append({"label": row["label"], "items": items})
    return out, marks


def main() -> None:
    cal = json.loads(CAL.read_text(encoding="utf-8"))

    # 1) 物價指數（月）→ 年增率、年化
    # CPI／PPI 年增用未季調（BLS 新聞稿口徑，CUUR0000SA0）；月增用季調
    cpi, core_cpi = monthly(fred("CPIAUCNS")), monthly(fred("CPILFENS"))
    core_cpi_sa = monthly(fred("CPILFESL"))
    pce, core_pce = monthly(fred("PCEPI")), monthly(fred("PCEPILFE"))
    ppi, core_ppi = monthly(fred("PPIFID")), monthly(fred("PPIFES"))
    yoy = lambda s: (s.pct_change(12) * 100).dropna()
    src = {
        "ppi": yoy(ppi), "core_ppi": yoy(core_ppi),
        "cpi": yoy(cpi), "core_cpi": yoy(core_cpi),
        "pce": yoy(pce), "core_pce": yoy(core_pce),
        "trim": monthly(fred("PCETRIM12M159SFRBDAL")),
        "pce6": annualized(pce, 6).dropna(),
        "core_pce3": annualized(core_pce, 3).dropna(),
        "core_cpi_mom": (core_cpi_sa.pct_change() * 100).dropna(),
    }

    # 2) 日資料：政策利率、公債、高收益債、油價、那斯達克
    ffr_u, ffr_l = fred("DFEDTARU"), fred("DFEDTARL")
    ust = treasury_recent()
    dgs2, dgs10 = with_recent(fred("DGS2"), ust["2 Yr"]), with_recent(fred("DGS10"), ust["10 Yr"])
    daily = {
        "dgs2": dgs2, "dgs10": dgs10, "t10y2y": (dgs10 - dgs2).dropna().round(2),
        "hy_bb": fred("BAMLH0A1HYBBEY"), "hy_b": fred("BAMLH0A2HYBEY"), "hy_ccc": fred("BAMLH0A3HYCEY"),
        "wti": yahoo("CL=F"),
    }
    # 那斯達克只畫趨勢，改週資料（週五收盤）縮小檔案
    nasdaq = fred("NASDAQCOM").resample("W-FRI").last().dropna()

    def pts(s: pd.Series, digits: int) -> list:
        # 月資料的 PeriodIndex 轉回月初日期
        if isinstance(s.index, pd.PeriodIndex):
            s = s.copy()
            s.index = s.index.to_timestamp()
        return points(s, digits)

    data = {
        "table": build_table(src, ffr_u, cal),
        "snapshot": build_snapshot(daily),
        "infl": {k: pts(src[k], 2) for k in ("cpi", "core_cpi", "pce", "core_pce", "trim", "ppi", "core_ppi")},
        "pce6": pts(src["pce6"], 2),
        "core_pce3": pts(src["core_pce3"], 2),
        "ffr_upper": points(changes_only(ffr_u), 2),
        "ffr_lower": points(changes_only(ffr_l), 2),
        "dot_median": points(fred("FEDTARMD"), 2),
        "dot_median_lr": points(fred("FEDTARMDLR"), 2),
        **{k: points(v, 2) for k, v in daily.items()},
        "nasdaq": points(nasdaq, 0),
    }
    # 數據沒變就保留原本的更新時間，避免排程每次都產生空的提交
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
    if prev and {k: v for k, v in prev.items() if k not in ("updated", "changes", "changedCells")} == data:
        print("資料無變動")
        return
    changes, marks = diff_changes(prev, data) if prev else ([], {})
    data = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "changes": changes, "changedCells": marks, **data}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫入 {OUT}：CPI 至 {data['infl']['cpi'][-1]}，PCE 至 {data['infl']['pce'][-1]}，"
          f"10Y 至 {data['dgs10'][-1]}，CCC 至 {data['hy_ccc'][-1]}")


if __name__ == "__main__":
    main()
