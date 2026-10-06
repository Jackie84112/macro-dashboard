"""就業看板資料管線：從 FRED 抓資料 → 計算 → 寫 data/labor.json。

不需要 API key（用 fredgraph.csv）。本機與 GitHub Actions 都用這支。
"""
import io
import json
from decimal import ROUND_HALF_UP, Decimal
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

START = "2018-01-01"
OUT = Path(__file__).resolve().parent.parent / "data" / "labor.json"


def fred(series_id: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={START}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True)
    s = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna()
    return s


def points(s: pd.Series, digits: int) -> list:
    return [[d.strftime("%Y-%m-%d"), round(float(v), digits)] for d, v in s.items()]


def monthly(s: pd.Series) -> pd.Series:
    """把日期對齊到月初，方便各序列用 (年, 月) 對齊。"""
    return s.groupby(s.index.to_period("M")).mean()


# 表格列定義：(群組, 列名, key, 上升代表, 格式, 發布排程)
# 上升代表：good=好轉、bad=惡化、None=不上色
ROWS = [
    ("核心數據", "失業率 U-3", "unrate", "bad", "pct1", "empsit"),
    ("核心數據", "Fed 長期失業率估計 u*", "ustar", None, "pct1", "sep"),
    ("核心數據", "失業率缺口 u−u*", "gap", "bad", "pct1", None),
    ("企業需求端 JOLTS", "職缺數（萬）", "jol", "good", "int", "jolts"),
    ("企業需求端 JOLTS", "僱傭率", "hires", "good", "pct1", "jolts"),
    ("企業需求端 JOLTS", "離職率", "quits", "good", "pct1", "jolts"),
    ("企業需求端 JOLTS", "裁員率", "layoffs", "bad", "pct1", "jolts"),
    ("企業需求端 JOLTS", "V/U（職缺數/失業人數）比", "vu", "good", "pct0", "jolts"),
    ("企業需求端 JOLTS", "平均時薪（年增）", "ahe", "good", "pct1", "empsit"),
    ("勞動力供給端", "非農就業（萬）", "nfp", "good", "signed1", "empsit"),
    ("勞動力供給端", "非農三個月均值（萬）", "nfp3", "good", "signed1", "empsit"),
    ("勞動力供給端", "勞動參與率 LFPR", "lfpr", "good", "pct1", "empsit"),
    ("勞動力供給端", "就業人口比 EPOP（16+）", "epop", "good", "pct1", "empsit"),
    ("勞動力供給端", "長期失業占比", "ltu", "bad", "pct1", "empsit"),
    ("勞動力供給端", "初領四周均值（萬，月均）", "claims", "bad", "dec2", "weekly"),
]


def half_up(v: float, digits: int) -> Decimal:
    """一般四捨五入（Python round 是銀行家捨入，758.5 會變 758）。"""
    q = Decimal(1).scaleb(-digits)
    d = Decimal(repr(round(v, 9))).quantize(q, rounding=ROUND_HALF_UP)
    return d + 0  # 把 -0.0 正規化成 0.0


def fmt(v: float, kind: str) -> str:
    if kind == "pct1":
        return f"{half_up(v, 1)}%"
    if kind == "pct0":
        return f"{half_up(v, 0)}%"
    if kind == "int":
        return f"{half_up(v, 0)}"
    if kind == "signed1":
        d = half_up(v, 1)
        return f"+{d}" if d > 0 else f"{d}"
    return f"{half_up(v, 2)}"


def build_table(src: dict, ustar: pd.Series, years: int = 3) -> dict:
    """產生就業狀況表：每列每年 12 個月的顯示字串，最新一格依規則上色。"""
    unrate = src["unrate"]
    last_year = unrate.index[-1].year
    year_list = list(range(last_year - years + 1, last_year + 1))
    today = pd.Timestamp.now().to_period("M")
    sep_months = {d.to_period("M"): v for d, v in ustar.items()}

    rows = []
    for group, label, key, up, kind, sched in ROWS:
        row = {"group": group, "label": label, "key": key, "schedule": sched, "cells": {}}
        if key == "ustar":
            for y in year_list:
                cells = []
                for m in range(1, 13):
                    per = pd.Period(year=y, month=m, freq="M")
                    if per in sep_months:
                        cells.append({"v": fmt(sep_months[per], kind)})
                    elif per <= today:
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

    latest = unrate.index[-1]
    return {"years": year_list, "latestYear": latest.year, "latestMonth": latest.month, "rows": rows}


def diff_changes(prev: dict, new: dict) -> list:
    """比對上一版與這一版，列出本次新增／修正的數據（給頁尾「本次更新內容」）。"""
    out = []
    # 初領：以週資料比對（月均那列每週都會變動，不另列）
    old_w = {d for d, _ in prev.get("claims4w", [])}
    added = [(d, v) for d, v in new["claims4w"] if d not in old_w]
    if added:
        items = "、".join(f"{int(d[5:7])}/{int(d[8:])} 當週 {v:.2f}" for d, v in added)
        out.append({"label": "初領四周均值（萬）", "items": [f"{items}（新）"]})
    prev_rows = {r["key"]: r for r in prev.get("table", {}).get("rows", [])}
    for row in new["table"]["rows"]:
        if row["key"] in ("claims", "gap"):
            continue
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
        if items:
            out.append({"label": row["label"], "items": items})
    return out


def main() -> None:
    # 1) 初領失業金四周均值（週，萬人）
    claims = fred("IC4WSA") / 1e4

    # 2) 非農就業月增與三個月均值（萬人）
    nfp = fred("PAYEMS").diff() / 10  # PAYEMS 單位千人 → 月增（萬人）
    nfp3 = nfp.rolling(3).mean()
    nfp, nfp3 = nfp.dropna(), nfp3.dropna()

    # 3) 失業率 U-3 與 Fed 長期失業率預估 u*（SEP 中位數，每季一次）
    unrate = fred("UNRATE")
    ustar = fred("UNRATEMDLR")

    # 4) 就業狀況表（全部由 FRED 重算，口徑同 PPT）
    u_m = monthly(unrate)
    ustar_m = ustar.copy()
    ustar_m.index = ustar_m.index.to_period("M")
    ustar_m = ustar_m.groupby(level=0).last()

    def ustar_asof(per: pd.Period) -> float:
        prior = ustar_m[ustar_m.index <= per]
        return float(prior.iloc[-1]) if len(prior) else float("nan")

    unemploy = monthly(fred("UNEMPLOY"))
    jol = monthly(fred("JTSJOL"))
    ahe = monthly(fred("CES0500000003"))
    src = {
        "unrate": u_m,
        "gap": pd.Series({p: v - ustar_asof(p) for p, v in u_m.items()}).dropna(),
        "jol": jol / 10,
        "hires": monthly(fred("JTSHIR")),
        "quits": monthly(fred("JTSQUR")),
        "layoffs": monthly(fred("JTSLDR")),
        "vu": (jol / unemploy * 100).dropna(),
        "ahe": (ahe.pct_change(12) * 100).dropna(),
        "nfp": monthly(nfp),
        "nfp3": monthly(nfp3),
        "lfpr": monthly(fred("CIVPART")),
        "epop": monthly(fred("EMRATIO")),
        "ltu": monthly(fred("LNS13025703")),
        "claims": monthly(claims),
    }

    data = {
        "table": build_table(src, ustar),
        "claims4w": points(claims, 2),
        "nfp": points(nfp, 1),
        "nfp3": points(nfp3, 1),
        "unrate": points(unrate, 1),
        "ustar": points(ustar, 2),
    }
    # 數據沒變就保留原本的更新時間，避免排程每次都產生空的提交
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
    if prev and {k: v for k, v in prev.items() if k not in ("updated", "changes")} == data:
        print("資料無變動")
        return
    changes = diff_changes(prev, data) if prev else []
    data = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "changes": changes, **data}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫入 {OUT}：初領至 {data['claims4w'][-1]}，非農至 {data['nfp'][-1]}，"
          f"失業率至 {data['unrate'][-1]}，u* 至 {data['ustar'][-1]}")


if __name__ == "__main__":
    main()
