"""就業看板資料管線：從 FRED 抓資料 → 計算 → 寫 data/labor.json。

不需要 API key（用 fredgraph.csv）。本機與 GitHub Actions 都用這支。
"""
import io
import json
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

    data = {
        "claims4w": points(claims, 2),
        "nfp": points(nfp, 1),
        "nfp3": points(nfp3, 1),
        "unrate": points(unrate, 1),
        "ustar": points(ustar, 2),
    }
    # 數據沒變就保留原本的更新時間，避免排程每次都產生空的提交
    if OUT.exists():
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        if {k: v for k, v in prev.items() if k != "updated"} == data:
            print("資料無變動")
            return
    data = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), **data}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫入 {OUT}：初領至 {data['claims4w'][-1]}，非農至 {data['nfp'][-1]}，"
          f"失業率至 {data['unrate'][-1]}，u* 至 {data['ustar'][-1]}")


if __name__ == "__main__":
    main()
