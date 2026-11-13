"""GitHub Actions 用：每天抓 Yahoo 刷新指數月線；FINRA 出新月份另掛 --auto 提示條。
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
try: fetch_yahoo(); yahoo_ok=True
except Exception as e: yahoo_ok=False; print("Yahoo 抓取失敗，沿用上次指數資料：",e)
if new or "--force" in sys.argv:
    subprocess.run([sys.executable,"build.py","--auto"],check=True)   # FINRA 新月份：掛提示條
elif yahoo_ok:
    subprocess.run([sys.executable,"build.py","--keep-note"],check=True)   # 每日只刷新指數月線，提示條沿用
out("new","true" if new else "false"); out("month",latest.replace("-","/"))
