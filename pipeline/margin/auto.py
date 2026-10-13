"""GitHub Actions 用：FINRA 出新月份才重建 margin.html（--auto 提示條）。
輸出到 $GITHUB_OUTPUT：new=true|false、month=YYYY/MM。--force 無新月份也重建（測試用）。"""
import json, os, sys, subprocess
from fetch_data import fetch_finra, fetch_yahoo
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
d=json.load(open("data.json",encoding="utf-8"))
have=max(m for m,v in zip(d["months"],d["mar"]) if v is not None)
latest=fetch_finra()
new = latest > have
print("網頁現有 FINRA 至",have,"｜FINRA 最新",latest,"｜新月份" if new else "｜無新資料")
def out(k,v):
    if os.environ.get("GITHUB_OUTPUT"):
        open(os.environ["GITHUB_OUTPUT"],"a").write(f"{k}={v}\n")
if new or "--force" in sys.argv:
    try: fetch_yahoo()
    except Exception as e: print("Yahoo 抓取失敗，沿用上次指數資料：",e)
    subprocess.run([sys.executable,"build.py","--auto"],check=True)
out("new","true" if new else "false"); out("month",latest.replace("-","/"))
