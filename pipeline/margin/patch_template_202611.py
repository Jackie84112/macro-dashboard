import io
p='template.html'
s=io.open(p,encoding='utf-8').read()
def rep(old,new):
    global s
    assert s.count(old)==1,old[:40]
    s=s.replace(old,new)
rep('<tr class="act"><td><b>10 月</b></td><td class="pos">+2%</td><td>+1.1%</td><td>11 月下旬公佈</td><td>26.4%</td><td>—</td><td>—</td></tr>',
 '<tr><td>10 月</td><td class="pos">+2%</td><td>+1.1%</td><td class="neg">−2.1%</td><td>26.4%</td><td>22.4%</td><td>+4.0pp</td></tr>\n      <tr class="act"><td><b>11 月</b></td><td>12/1 公佈</td><td>—</td><td>12 月下旬公佈</td><td>—</td><td>—</td><td>—</td></tr>')
i=s.index('<p class="note lead" style="margin:2px 0 0">[註2]：10 月 YoY')
j=s.index('</p>',s.index('[註3]：IBKR 10 月'))+4
new='''<p class="note lead" style="margin:2px 0 0">[註2]：11 月 YoY = 19.3% + 1.193 × FINRA 11 月 MoM；去年 11 月總額為 $1,214,321M，MoM 持平時 YoY 為 19.3%，要回到 10 月的 22.4% 需 MoM +2.6%。</p>
    <p class="note lead" style="margin-top:2px">[註3]：10 月 IBKR +2% 落在 ±3% 內，不判方向；實際 FINRA 10 月總額 $1,448,360M、MoM −2.1%，與暫估 +1.1% 差 3.2pp、方向相反，YoY 實際 22.4% 恰落在暫估區間下緣（22.3–30.5%）。同月 SOX −15.4%，FINRA 反映去槓桿而 IBKR 未動，屬「IBKR 沒動 ≠ 市場沒動」盲點。</p>'''
s=s[:i]+new+s[j:]
rep('YoY = 9 月總額 × (1 + MoM) ÷ 去年 10 月總額 − 1','YoY = 上月總額 × (1 + MoM) ÷ 去年同月總額 − 1')
io.open(p,'w',encoding='utf-8').write(s)
