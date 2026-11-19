"""CDS 追蹤 Excel → data/cds.json（overlay.html「CDS 利差」卡片用，手動更新）。

用法：python pipeline/export_cds.py "C:\\Users\\green\\OneDrive\\Desktop\\CDS追蹤_2026-11-19.xlsx"
讀 CSP、晶片兩個工作表：第 12 列表頭、13 列起 CDS 利差（bps），直到空列；
「隱含5年累積違約機率」區塊另抓（表頭在 CDS 區塊後的下一個「日期」列）。整欄空白的公司（查無報價）不輸出。
"""
import json
import sys
from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parent.parent / "data" / "cds.json"


def block(rows, start):
    """從表頭列 start 讀到空列，回傳 (公司清單, [(日期, [值...])])。"""
    head = [c for c in rows[start][1:] if c]
    data = []
    for r in rows[start + 1:]:
        if not r[0]:
            break
        d = r[0] if isinstance(r[0], str) else r[0].strftime("%Y-%m-%d")
        data.append((d, list(r[1:1 + len(head)])))
    return head, data


def sheet(ws):
    rows = list(ws.iter_rows(values_only=True))
    hdr = [i for i, r in enumerate(rows) if r[0] == "日期"]
    names, cds = block(rows, hdr[0])
    _, pd = block(rows, hdr[1])
    pdm = {d: v for d, v in pd}
    rec = ws["C3"].value
    out = {"dates": [d for d, _ in cds], "recovery": rec, "series": []}
    for j, n in enumerate(names):
        v = [None if x is None else round(float(x), 1) for _, x in [(d, r[j]) for d, r in cds]]
        if all(x is None for x in v):
            continue
        p = [None if pdm.get(d, [None] * len(names))[j] is None else round(float(pdm[d][j]) * 100, 2) for d, _ in cds]
        out["series"].append({"t": n, "bp": v, "pd": p})
    return out


def main(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    j = {"src": Path(path).name, "csp": sheet(wb["CSP"]), "chip": sheet(wb["晶片"])}
    OUT.write_text(json.dumps(j, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for k in ("csp", "chip"):
        s = j[k]
        print(k, s["dates"][0], "→", s["dates"][-1], len(s["dates"]), "天", [x["t"] for x in s["series"]])


if __name__ == "__main__":
    main(sys.argv[1])
