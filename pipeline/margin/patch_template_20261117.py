# 2026-11-17：11 月 IBKR 未出，改用「FINRA MoM ~ 當月 SPX＋SOX 漲跌」回歸暫估 11 月 YoY（紅虛線）
import io, json
p = 'template.html'
s = io.open(p, encoding='utf-8').read()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:50]
    s = s.replace(old, new)

# 對帳表 11 月列
rep('<tr class="act"><td><b>11 月</b></td><td>12/1 公佈</td><td>—</td><td>12 月下旬公佈</td><td>—</td><td>—</td><td>—</td></tr>',
    '<tr class="act"><td><b>11 月</b></td><td>12/1 公佈</td><td class="neg">−2.6%（指數回歸）</td><td>12 月下旬公佈</td><td>16.2%</td><td>—</td><td>—</td></tr>')

# 新增 [註4]：理由
i = s.index('<p class="note lead" style="margin-top:2px">[註3]：10 月 IBKR')
j = s.index('</p>', i) + 4
s = s[:j] + '''
    <p class="note lead" style="margin-top:2px">[註4]：11 月 IBKR 要 12/1 才公佈，先以指數回歸暫估（紅虛線）：以 2017/1–2026/10 共 118 個月擬合 FINRA MoM ≈ 0.03 + 0.43 × SPX 當月漲跌 + 0.17 × SOX 當月漲跌（R² 0.59，樣本外誤差 ±3.0pp，優於用歷史平均的 ±4.2pp）。代入 11 月至 11/16 的 SPX −2.2%、SOX −10.1%，得 MoM −2.6%，YoY = 10 月總額 $1,448,360M × (1 − 2.6%) ÷ 去年 11 月 $1,214,321M − 1 ≈ 16.2%（區間 12.6%–19.8%）。方向較確定：2017 年以來 SOX 單月跌逾 8% 的 12 個月，FINRA MoM 全為負。11 月尚未結束，指數後續漲跌會改變暫估，12/1 IBKR 出爐後改用 IBKR 換算。</p>''' + s[j:]

# tooltip／燈號：暫估來源依 nowcast.src 顯示（無 src 者沿用「IBKR 暫估」）
rep('html+=`<div class="r"><i style="--dc:#E11D48">IBKR 暫估</i><b style="color:#FF9384">${ncHit.yoy.toFixed(1)}%（誤差',
    'html+=`<div class="r"><i style="--dc:#E11D48">${ncHit.src||"IBKR 暫估"}</i><b style="color:#FF9384">${ncHit.yoy.toFixed(1)}%（誤差')
rep('html+=`<div class="r"><i style="--dc:#E11D48">IBKR 暫估</i><b style="color:#FF9384">${ncHit.yoy.toFixed(1)}%</b></div>`;',
    'html+=`<div class="r"><i style="--dc:#E11D48">${ncHit.src||"IBKR 暫估"}</i><b style="color:#FF9384">${ncHit.yoy.toFixed(1)}%</b></div>`;')
rep('${est?" IBKR 暫估":""}', '${est?" "+(NCS.find(o=>o.month===M[i]).src||"IBKR 暫估"):""}')
rep('<h3 class="sub-h">IBKR 暫估 vs. 實際</h3>', '<h3 class="sub-h">暫估 vs. 實際</h3>')
rep('<span class="dot"></span>IBKR 暫估（最新）</button>', '<span class="dot"></span>暫估（最新）</button>')
rep('<span class="dot"></span>IBKR 暫估（歷史）</button>', '<span class="dot"></span>暫估（歷史）</button>')
rep('紅虛線段 = IBKR 暫估）', '紅虛線段 = 暫估，FINRA 未出月份）')
rep('紅色虛線段 = IBKR 暫估路徑，保留供對帳', '紅色虛線段 = 暫估路徑（IBKR 換算；11 月為指數回歸），保留供對帳')
io.open(p, 'w', encoding='utf-8').write(s)

n = json.load(io.open('nowcast.json', encoding='utf-8'))
assert not any(x['month'] == '2026-11' for x in n)
n.append({"month": "2026-11", "yoy": 16.2, "lo": 12.6, "hi": 19.8, "mom": -2.6,
          "src": "指數回歸暫估",
          "label": "指數回歸 11月暫估 16.2%",
          "note": "IBKR 11 月 12/1 才公佈；FINRA MoM ≈ 0.03 + 0.43×SPX + 0.17×SOX（2017–2026/10，R² 0.59，樣本外 ±3.0pp），代入至 11/16 SPX −2.2%、SOX −10.1% → MoM −2.6% → 1,448,360×0.974÷1,214,321−1 ≈ 16.2%（12.6–19.8%）"})
io.open('nowcast.json', 'w', encoding='utf-8').write(json.dumps(n, ensure_ascii=False, indent=2))
print('ok')
