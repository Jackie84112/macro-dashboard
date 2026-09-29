# 總經看板

美國總經數據看板，GitHub Pages 靜態網站，GitHub Actions 每個工作日自動從 FRED 抓資料更新。

- `index.html`：就業狀況頁（三張圖＋最下方就業狀況數據表，15 個指標全部由 FRED 自動重算、上色）
- `data/calendar.json`：BLS／Fed 發布日曆（「下次發布」欄用）。**每年底要手動補隔年日期**
- `pipeline/labor.py`：抓 FRED → 計算 → 寫 `data/labor.json`（本機可直接跑）
- `.github/workflows/update-data.yml`：排程（UTC 13:15、15:15，週一至五），也可在 Actions 頁手動觸發
