"""抓融資看板原始資料：FINRA 融資餘額 xlsx、Yahoo 四指數月線、IBKR 月報 PDF（僅列印供人工判讀）。
本機手動月更：python fetch_data.py 全抓；GitHub Actions 由 auto.py 呼叫 fetch_finra / fetch_yahoo。"""
import requests, json, io, re, os, sys, time, datetime as dt
import pandas as pd
os.chdir(os.path.dirname(os.path.abspath(__file__)))
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

def fetch_finra():
    """下載 FINRA 歷史檔，回傳最新月份 YYYY-MM；只在內容有效時才覆寫 margin-statistics.xlsx"""
    r=requests.get("https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx",headers=UA,timeout=60)
    r.raise_for_status()
    df=pd.read_excel(io.BytesIO(r.content))
    latest=str(df.iloc[:,0].dropna().astype(str).str[:7].max())
    open("margin-statistics.xlsx","wb").write(r.content)
    print("FINRA",r.status_code,len(r.content),"最新",latest)
    return latest

def fetch_yahoo():
    """抓 ^GSPC/^NDX/^SOX/^W5000 月線寫 yahoo_raw.json（_fetched=抓取日，頁尾月中值註記用）"""
    out={}
    p1=int(dt.datetime(1996,12,1).timestamp()); p2=int(time.time())+86400
    for sym,k in [("^GSPC","spx"),("^NDX","ndx"),("^SOX","sox"),("^W5000","w5000")]:
        u=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1mo"
        rr=requests.get(u,headers=UA,timeout=60); rr.raise_for_status(); j=rr.json()
        res=j["chart"]["result"][0]; ts=res["timestamp"]; cl=res["indicators"]["quote"][0]["close"]
        ser={dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime("%Y-%m"):c for t,c in zip(ts,cl)}
        out[k]=ser; print(k,len(ser),list(ser.items())[-3:])
    out["_fetched"]=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=8)).strftime("%Y-%m-%d")
    json.dump(out,open("yahoo_raw.json","w"))

def fetch_ibkr():
    """IBKR 每月 1 號月報：列印融資段落，人工維護 nowcast.json"""
    today=dt.date.today(); yms=[today.strftime("%Y%m"),(today.replace(day=1)-dt.timedelta(days=1)).strftime("%Y%m")]
    for ym in yms:
        u=f"https://ndcdyn.interactivebrokers.com/mkt/getFileNew.php?file={ym}MetricsPressRelease.pdf"
        rr=requests.get(u,headers=UA,timeout=60); c=rr.content; i=c.find(b"%PDF")
        print("IBKR",ym,rr.status_code,len(c),i)
        if i>=0:
            from pypdf import PdfReader
            t="".join(p.extract_text() for p in PdfReader(io.BytesIO(c[i:])).pages)
            m=re.search(r"margin loan balances of \$([\d.]+) billion,\s*(\d+)% (higher|lower) than prior year and (\d+)% (higher|lower) than|about even with prior month",t)
            print("  ",m.group(0) if m else t[:600])

if __name__=="__main__":
    fetch_finra(); fetch_yahoo(); fetch_ibkr()
