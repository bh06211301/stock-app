# 老爸股票神器 — 開發說明

給 Claude 看的專案說明文件，幫助快速接手開發。

---

## 專案目的

協助使用者父親看台灣股市「**千張大戶持股動態**」：
- 大戶（持股 1000 張以上）的人數、佔比是否增加 → 可能是買進信號
- 大戶持股減少 → 可能是賣出信號
- 資料來源：台灣集中保管結算所（TDCC）集保戶股權分散表

**目標裝置**：iPhone Safari「加入主畫面」作為 PWA 使用。

---

## 架構總覽

```
TDCC 集保網站
    ↓ (每週五晚上 11pm 台灣時間，GitHub Actions 自動執行)
backend/fetch_data.py        → 下載最新一週全市場 CSV
backend/fetch_history.py     → 一次性歷史回填（手動執行一次即可）
backend/calculate_trends.py  → 計算趨勢、生成排行榜、生成個股 JSON
    ↓
data/stocks/{code}.json      → 54 支個股靜態 JSON（含 51 週歷史）
data/ranking.json            → 趨勢排行榜
    ↓ (git push 到 GitHub Pages)
https://bh06211301.github.io/stock-app/
    ↓ (iPhone Safari 讀取靜態檔)
index.html（個股查詢）/ ranking.html（排行榜）/ watchlist.html（自選股）
```

**重要**：前端讀的是預先生成的靜態 JSON，不是即時 API。用戶查詢股票時只是下載對應的 JSON 檔案。

---

## 檔案結構

```
stock-app-complete/
├── index.html              # 主頁：個股大戶查詢 + 持股分布圖
├── ranking.html            # 大戶排行榜（強力集中 / 持續增加）
├── watchlist.html          # 自選股（存在 localStorage）
├── concentration.html      # 持股集中度分析（額外頁面）
├── manifest.json           # PWA 設定
├── service-worker.js       # PWA 離線快取
├── icon-192.png            # App 圖示
├── icon-512.png
│
├── backend/
│   ├── fetch_data.py       # 每週自動：下載最新一週集保 CSV
│   ├── fetch_history.py    # 一次性：回填最多 51 週歷史（手動）
│   ├── calculate_trends.py # 計算趨勢 + 生成所有 JSON 輸出
│   ├── requirements.txt    # Python 依賴
│   └── test_*.py           # 測試腳本（可刪除）
│
├── data/
│   ├── stocks_raw.json     # 後端原始資料（全部 54 支 + 歷史）
│   ├── ranking.json        # 排行榜（前端讀取）
│   └── stocks/
│       ├── 2330.json       # 台積電（前端讀取）
│       ├── 0050.json
│       └── ...（54 個檔案）
│
└── .github/workflows/
    └── update-stocks.yml   # 每週五自動更新
```

---

## 追蹤的股票清單

`backend/fetch_data.py` 的 `STOCK_LIST`（54 支）：

```python
STOCK_LIST = [
    '2330', '2317', '2454', '2881', '2882', '2891', '2892', '2886',
    '2303', '2382', '2308', '3711', '2412', '2207', '3008', '2301',
    '1301', '1303', '2002', '1326', '2912', '2884', '2885', '2887',
    '2357', '2353', '3045', '2408', '2409', '6505', '2880', '5871',
    '5876', '2883', '2890', '1216', '2327', '2345', '2615', '9910',
    '2395', '3231', '3034', '2379', '2474', '6669', '3443', '4904',
    '0050', '0056', '006208', '00878', '00881', '00900'
]
```

新增或刪除股票：只需修改 `fetch_data.py` 和 `fetch_history.py` 中的這個清單（兩個檔案都要改），然後重新執行。

---

## API 說明

### 1. TDCC Opendata CSV（每週批次下載）

```
GET https://opendata.tdcc.com.tw/getOD.ashx?id=1-5
```

- 回傳全市場最新一週資料（~68,000 行 CSV）
- **不支援歷史日期查詢**（任何 date 參數都無效）
- 編碼：UTF-8 with BOM，需 `decode('utf-8-sig')`
- CSV 欄位：`資料日期, 股票代號(6碼左補空格), 持股分級(1-17), 人數, 股數, 佔比%`
- Level 15 = 千張以上大戶；Level 17 = 合計

### 2. TDCC 網頁表單（歷史資料查詢）

用於 `fetch_history.py` 一次性回填：

```
GET  https://www.tdcc.com.tw/portal/zh/investor/smWeb/qryStock
POST https://www.tdcc.com.tw/portal/zh/smWeb/qryStock
```

**必要參數**（POST body）：
```
SYNCHRONIZER_TOKEN  從 GET 頁面 HTML 解析（CSRF token，每次請求後更新）
SYNCHRONIZER_URI    固定值: /portal/zh/smWeb/qryStock
method              固定值: submit
firDate             最新日期（從頁面 hidden input 取得，e.g. 20260703）
scaDate             目標歷史日期（e.g. 20260626）
stockNo             股票代號（e.g. 2330）
sqlMethod           固定值: StockNo
```

**可用歷史日期**：從 GET 頁面的 `<select name="scaDate">` 解析，目前有 51 週（約一年）。

**注意**：每次 POST 後必須從回應 HTML 提取新的 `SYNCHRONIZER_TOKEN` 給下次使用。

### 3. TWSE 股票名稱 API

```
GET https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
```

回傳 JSON 陣列，每項含 `Code`、`Name`。

---

## 個股 JSON 格式（data/stocks/{code}.json）

```json
{
  "stock_code": "2330",
  "stock_name": "台積電",
  "last_update": "2026-07-05 12:00:00",
  "history": [
    {
      "date": "20260703",
      "big_holders": 1481,
      "big_ratio": 85.09,
      "total_holders": 2898020,
      "total_shares": 25932119862,
      "big_shares": 22066084295,
      "distribution": [
        {"level": 1, "level_name": "1-999股", "holders": ..., "shares": ..., "percent": ...},
        ...
        {"level": 15, "level_name": "千張以上", "holders": 1481, "shares": ..., "percent": 85.09}
      ]
    },
    ...  // 最多 52 週，最新在前
  ],
  "trend": {
    "holder_change": -3,         // 與 12 週前相比的大戶人數變化
    "holder_change_pct": -0.2,
    "ratio_change": -0.13,       // 與 12 週前相比的比例變化
    "weeks": 12
  },
  "signal": {
    "icon": "➡️",
    "text": "趨勢不明顯",
    "level": "neutral",          // strong_buy / buy / hold / neutral / sell / unknown
    "color": "gray"
  }
}
```

---

## 趨勢判斷邏輯（calculate_trends.py）

12 週前 vs 最新：

| 條件 | 信號 |
|------|------|
| 大戶人數 +10 且比例 +3% | 🚀 強力集中（strong_buy） |
| 大戶人數 +5 且比例 +2% | 📈 持續增加（buy） |
| 兩者皆正 | ➡️ 微幅增加（hold） |
| 人數 -5 或比例 -2% | 📉 持股減少（sell） |
| 其他 | ➡️ 趨勢不明顯（neutral） |

排行分數：`score = holder_change + ratio_change × 2`

---

## 本機開發

```powershell
# 安裝 Python 依賴
pip install -r backend/requirements.txt

# 下載最新一週資料（快，約 30 秒）
python -X utf8 backend/fetch_data.py

# 一次性歷史回填（慢，約 30-45 分鐘，只需跑一次）
python -X utf8 backend/fetch_history.py

# 計算趨勢 + 生成所有 JSON
python -X utf8 backend/calculate_trends.py
```

Windows 必須加 `-X utf8` 旗標，否則 emoji 輸出會出現 UnicodeEncodeError。

前端用 VS Code Live Server 開啟 `index.html` 即可本機測試。

---

## 部署到 GitHub Pages

```powershell
git add data/
git commit -m "更新: 描述"
git push
```

GitHub Pages URL：`https://bh06211301.github.io/stock-app/`
GitHub 倉庫：`https://github.com/bh06211301/stock-app.git`（branch: main）

GitHub Pages 設定：倉庫 Settings → Pages → Source: main branch / root。

---

## 自動更新（GitHub Actions）

`.github/workflows/update-stocks.yml`：

- **排程**：每週五 UTC 15:00 = 台灣時間週五晚上 11:00
- **執行流程**：`fetch_data.py` → `calculate_trends.py` → `git push`
- **也可手動觸發**：GitHub 倉庫 → Actions → 手動執行

---

## 常見任務

### 新增追蹤股票

1. 在 `backend/fetch_data.py` 的 `STOCK_LIST` 加入代號
2. 在 `backend/fetch_history.py` 的 `STOCK_LIST` 加入同一代號
3. 執行 `fetch_history.py` 補充歷史
4. 執行 `calculate_trends.py`
5. push 到 GitHub

### 調整趨勢判斷門檻

修改 `backend/calculate_trends.py` 的 `generate_signal()` 函數。

### 修改前端 UI

直接修改 `index.html`（單一 HTML 檔案，內嵌 CSS 和 JavaScript）。
主要函數：
- `fetchFromLocalJSON(stockCode)` — 讀取個股 JSON
- `displayData(data)` — 渲染主要資料區塊
- `drawDistributionChart(distribution)` — 畫持股分布圖（Chart.js）
- `drawTrendChart(trendHistory)` — 畫大戶比例趨勢圖

### 修改排行榜

修改 `ranking.html`，資料來源是 `data/ranking.json`。

---

## 已知限制與注意事項

1. **CORS**：TDCC API 沒有 CORS header，前端不能直接呼叫。解決：用 GitHub Actions 預先生成靜態 JSON。
2. **TDCC opendata 歷史限制**：`getOD.ashx?id=1-5` 不支援歷史日期，`fetch_history.py` 改用網頁表單爬蟲。
3. **SYNCHRONIZER_TOKEN**：TDCC 網頁用 Grails 框架的 CSRF token，每次 POST 後必須從回應提取新 token。
4. **ETF 代號**：`006208`、`00878` 等六碼 ETF 代號在 TDCC CSV 中有空格填充，用 `r[1].strip()` 比對。
5. **歷史資料限制**：TDCC 僅保存約一年（51 週）歷史，`fetch_history.py` 最多能抓到此範圍。
6. **趨勢需要 2+ 週**：第一次執行只有一週資料時，所有股票顯示「❓ 資料不足」是正常的。
7. **Windows 編碼**：Python 在 Windows 執行時需 `-X utf8` 或在腳本頂部加 `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`。

---

## 未來可能的改進

- [ ] 新增個股股價走勢對比（需另找股價 API，例如 TWSE STOCK_DAY_ALL）
- [ ] 支援自選股的趨勢排行（目前自選股頁面只顯示個別資料）
- [ ] 新增推播通知（PWA Web Push，大戶快速集中時主動通知）
- [ ] 增加更多股票到追蹤清單
- [ ] 歷史資料超過 52 週時的處理（目前截斷為最新 52 週）
