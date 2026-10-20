# 總經看板

美國總經數據看板，GitHub Pages 靜態網站，GitHub Actions 每個工作日自動從 FRED 抓資料更新。

- `index.html`：就業狀況頁（三張圖＋最下方就業狀況數據表，15 個指標全部由 FRED 自動重算、上色）
- `rates.html`：貨幣成本頁（通膨、點陣圖 vs FedWatch、公債殖利率、高收益債、CDS、油價＋數據表）
- `pipeline/rates.py`：抓 FRED → 寫 `data/rates.json`
- `data/rates-manual.json`：**手動資料**——點陣圖（每季 SEP 後）、FedWatch 本週／上週、CDS、各區塊註解文字（每期雙周報更新）
- `data/calendar.json`：BLS／BEA／Fed 發布日曆（「下次發布」欄用）。**每年底要手動補隔年日期**（PCE 目前只到 2026/12）
- `pipeline/labor.py`：抓 FRED → 計算 → 寫 `data/labor.json`（本機可直接跑）
- `.github/workflows/update-data.yml`：排程（台灣時間週一至五 21:15、23:15，加週二、週三 07:00），也可在 Actions 頁手動觸發
