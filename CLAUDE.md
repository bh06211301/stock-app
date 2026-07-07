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
backend/fetch_data.py        → 下載最新一週全市場 CSV + TWSE 收盤價
backend/fetch_history.py     → 一次性歷史回填（手動執行一次即可）
backend/calculate_trends.py  → 計算趨勢、背離分數、生成排行榜與個股 JSON
    ↓
data/stocks/{code}.json      → 66 支個股靜態 JSON（含最多 52 週歷史 + 收盤價）
data/ranking.json            → 趨勢排行榜（含籌碼背離排行）
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
├── index.html              # 主頁：個股大戶查詢 + 圖表
├── ranking.html            # 大戶排行榜（快速集中 / 持續增加 / 籌碼背離）
├── watchlist.html          # 自選股（存在 localStorage）
├── concentration.html      # 持股集中度分析（額外頁面）
├── manifest.json           # PWA 設定
├── service-worker.js       # PWA 離線快取
├── icon-192.png            # App 圖示
├── icon-512.png
│
├── backend/
│   ├── fetch_data.py       # 每週自動：下載最新一週集保 CSV + TWSE 收盤價
│   ├── fetch_history.py    # 一次性：從 norway.twsthr.info 回填最多 52 週歷史
│   ├── calculate_trends.py # 計算趨勢 + 背離分數 + 生成所有 JSON 輸出
│   └── requirements.txt    # Python 依賴
│
├── data/
│   ├── stocks_raw.json     # 後端原始資料（全部 66 支 + 歷史）
│   ├── ranking.json        # 排行榜（前端讀取）
│   └── stocks/
│       ├── 2330.json       # 台積電（前端讀取）
│       ├── 0050.json
│       └── ...（66 個檔案）
│
└── .github/workflows/
    └── update-stocks.yml   # 每週五自動更新
```

---

## 追蹤的股票清單

`backend/fetch_data.py` 與 `backend/fetch_history.py` 的 `STOCK_LIST`（66 支，兩個檔案必須一致）：

```python
STOCK_LIST = [
    # 半導體 / IC 設計
    '2330', '2454', '2303', '2308', '3711', '3034', '2379', '2474',
    '2337', '3037',
    # 電子組裝 / 零組件
    '2317', '2382', '2357', '2353', '3008', '2301', '2395', '3231',
    '2345', '2327', '3443', '2409', '2408', '2356', '4938', '2376',
    # 面板
    '3481',
    # 通訊 / 電信
    '3045', '4904', '2412',
    # 金融
    '2881', '2882', '2891', '2892', '2886', '2884', '2885', '2887',
    '2880', '2883', '2890', '5871', '5876', '5880',
    # 傳產 / 石化 / 食品
    '1301', '1303', '2002', '1326', '2207', '1216', '9910', '2615',
    '6505', '2912', '1101', '1102',
    # 航運
    '2603', '2609',
    # 其他
    '6669', '2347',
    # ETF
    '0050', '0056', '006208', '00878', '00881', '00900',
]
```

新增或刪除股票：修改兩個檔案的清單 → `fetch_history.py` 補歷史 → `calculate_trends.py` → push。

---

## API 說明

### 1. TDCC Opendata CSV（每週批次下載，fetch_data.py 使用）

```
GET https://opendata.tdcc.com.tw/getOD.ashx?id=1-5
```

- 回傳全市場最新一週資料（~68,000 行 CSV）
- **不支援歷史日期查詢**（任何 date 參數都無效）
- 編碼：UTF-8 with BOM，需 `decode('utf-8-sig')`
- CSV 欄位：`資料日期, 股票代號(6碼左補空格), 持股分級(1-17), 人數, 股數, 佔比%`
- Level 15 = 千張以上大戶；Level 17 = 合計

### 2. Norway 歷史資料（fetch_history.py 使用）

```
GET https://norway.twsthr.info/StockHolders.aspx?stock={code}
```

- 一個請求取得約 200 週的持股歷史（目前截取最新 52 週）
- **無 CSRF，速度快**（整個清單約 2-4 分鐘）
- HTML 表格解析：找 16 欄且 col[2] 為 8 位日期的表格
  - `cells[2]` = 日期、`cells[3]` = 集保總張數、`cells[4]` = 總股東人數
  - `cells[12]` = 千張以上人數、`cells[13]` = 千張以上%、`cells[14]` = 收盤價
  - **注意**：HTML 有 2 個隱藏前置欄，所以可見第 N 欄 = `cells[N+2]`

### 3. TWSE 股票名稱與收盤價 API（fetch_data.py 使用）

```
GET https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
```

- 回傳 JSON 陣列，每項含 `Code`、`Name`、`ClosingPrice`
- fetch_data.py 用此取得最新一週的收盤價（TDCC CSV 本身不含股價）

---

## 個股 JSON 格式（data/stocks/{code}.json）

```json
{
  "stock_code": "2330",
  "stock_name": "台積電",
  "last_update": "2026-07-06 12:00:00",
  "history": [
    {
      "date": "20260703",
      "big_holders": 1481,
      "big_ratio": 85.09,
      "total_holders": 2898020,
      "total_shares": 25932119862,
      "big_shares": 22066084295,
      "close_price": 2445.0,
      "distribution": [
        {"level": 1, "level_name": "1-999股", "holders": ..., "shares": ..., "percent": ...},
        ...
        {"level": 15, "level_name": "千張以上", "holders": 1481, "shares": ..., "percent": 85.09}
      ]
    },
    ...
  ],
  "trend": {
    "holder_change": -3,
    "holder_change_pct": -0.2,
    "ratio_change": -0.13,
    "weeks": 12
  },
  "signal": {
    "icon": "➡️",
    "text": "趨勢不明顯",
    "level": "neutral",
    "color": "gray"
  }
}
```

`close_price`：
- 最新一週 → 來自 TWSE API（fetch_data.py）
- 歷史各週 → 來自 norway.twsthr.info（fetch_history.py）
- 幾乎所有股票有 51 週以上的股價歷史

---

## 趨勢判斷邏輯（calculate_trends.py）

### 信號分類（12 週前 vs 最新）

| 條件 | 信號 |
|------|------|
| 大戶人數 +10 且比例 +3% | 🚀 強力集中（strong_buy） |
| 大戶人數 +5 且比例 +2% | 📈 持續增加（buy） |
| 兩者皆正 | ➡️ 微幅增加（hold） |
| 人數 -5 或比例 -2% | 📉 持股減少（sell） |
| 其他 | ➡️ 趨勢不明顯（neutral） |

### 排行分數

```python
score = ratio_change * 10 + holder_change_pct
```

### 籌碼背離分數（calculate_divergence）

```python
# 從最新週往回數連續上升週數（至少 2 週才算）
consecutive_weeks = 0
for i in range(len(history) - 1):
    if history[i]['big_ratio'] > history[i + 1]['big_ratio']:
        consecutive_weeks += 1
    else:
        break

streak_start      = history[consecutive_weeks]          # 連漲起點
total_ratio_change = latest['big_ratio'] - streak_start['big_ratio']
price_change_pct   = (latest_price - start_price) / start_price * 100
divergence_score   = total_ratio_change * 10 - price_change_pct + consecutive_weeks * 3
```

- **意義**：大戶比例「連續」上升（確認持續吃貨）但股價尚未跟漲
- **門檻**：需連續 ≥ 2 週，過濾單週雜訊
- **比較基準**：動態（連漲起點），非固定 12 週前
- **連續週加成**：每多一週 +3 分，獎勵持續性訊號
- 分數越高 = 連續吃貨週數越多、股價越落後 → 訊號越可靠

### 出貨警示（calculate_profit_taking）

```python
# 最近連續下降週數
recent_down = ...  # history[i]['big_ratio'] < history[i+1]['big_ratio'] 連續幾週

# 下降前的連續上升週數
prev_streak = ...  # 從 recent_down 往回數

# 條件：recent_down >= 1 且 prev_streak >= 3
ratio_drop     = history[0]['big_ratio'] - history[recent_down]['big_ratio']
price_gain_pct = (peak_price - base_price) / base_price * 100  # 吃貨期間漲幅
```

- **意義**：曾連續吃貨 ≥ 3 週，但大戶比例已開始回落 → 可能進入獲利了結階段
- **排序**：先按出貨週數降序（出貨越久越優先），再按吃貨期漲幅降序
- **顯示欄位**：吃貨持續週數、已出貨週數、比例回落幅度、吃貨期間股價漲幅

---

## ranking.json 格式

```json
{
  "update_time": "...",
  "data_source": "20260703",
  "summary": {
    "total": 60,
    "strong_buy": 4,
    "buy": 3,
    "hold": 16,
    "divergence": 41
  },
  "rankings": {
    "all":        [...],   // 前 30 名（依 score 排序）
    "strong_buy": [...],   // 前 10 名
    "buy":        [...],   // 前 10 名
    "hold":       [...],   // 前 10 名
    "divergence": [...]    // 前 20 名（依 divergence_score 排序）
  }
}
```

divergence 清單每項格式：
```json
{
  "stock_code": "2603",
  "stock_name": "長榮",
  "latest": { "big_holders": ..., "big_ratio": ..., "date": ..., "close_price": ... },
  "divergence": {
    "ratio_change": 1.81,
    "price_change_pct": -3.7,
    "divergence_score": 21.8,
    "latest_price": 195.0,
    "weeks": 12
  },
  "signal": { ... }
}
```

---

## index.html 主要函數

- `fetchFromLocalJSON(stockCode)` — 讀取個股 JSON，計算 bigHolderChange（週環比）
- `displayData(data)` — 渲染主要資料區塊（2 格統計卡 + 兩個籌碼位置指標）
- `drawDualAxisChart(trendHistory)` — 雙軸圖：
  - **有股價時**（大多數預建股票）：大戶比例折線（左軸）+ 收盤價折線（右軸），標題「大戶比例 vs 股價」
  - **無股價時**（自輸代號）：大戶比例折線（左軸）+ 大戶人數折線（右軸），標題「大戶比例 & 人數趨勢」
  - Y 軸使用 dynRange（±20% padding），不從 0 開始
- `drawPercentileIndicator(trendHistory)` — 52 週籌碼位置指標（紅→綠漸層條）
- `drawChangeChart(trendHistory)` — 週變化柱狀圖
- `drawDistributionChart(distribution)` — 持股分布圖（Chart.js bar）
- URL 參數：`index.html?stock=2330` 可直接帶入股票代號

---

## ranking.html Tab 說明

| Tab | 篩選條件 | 排序 | 顯示欄位 |
|-----|---------|------|---------|
| 全部排行 | 全部有 trend | score 降序 | 大戶人數變化、持股比例、比例變化 |
| 🚀 快速集中 | level == strong_buy | score 降序 | 同上 |
| 📈 持續增加 | level == buy | score 降序 | 同上 |
| 📊 籌碼背離 | 連續 ≥2 週上升且有股價 | divergence_score 降序 | 連續買進週數、比例累積、股價漲跌(N週)、背離分數 |
| ⚡ 近期動能 | 近2週比例 +0.5% 以上 | recent_change 降序 | 大戶人數、12週比例、近2週動向 |
| ⚠️ 注意出貨 | 連續 ≥3 週上升後開始回落 | 出貨週數+漲幅降序 | 吃貨持續週數、已出貨週數、比例回落、吃貨期漲幅 |

---

## 本機開發

```powershell
# 安裝 Python 依賴
pip install -r backend/requirements.txt

# 下載最新一週資料（快，約 30 秒）
python -X utf8 backend/fetch_data.py

# 一次性歷史回填（約 2-4 分鐘，只需跑一次）
python -X utf8 backend/fetch_history.py

# 計算趨勢 + 背離分數 + 生成所有 JSON
python -X utf8 backend/calculate_trends.py
```

Windows 必須加 `-X utf8` 旗標，否則 emoji 輸出會出現 UnicodeEncodeError。

---

## 部署到 GitHub Pages

```powershell
git add data/
git commit -m "更新: 描述"
git push
```

GitHub Pages URL：`https://bh06211301.github.io/stock-app/`
GitHub 倉庫：`https://github.com/bh06211301/stock-app.git`（branch: main）

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

### 調整背離分數公式

修改 `backend/calculate_trends.py` 的 `calculate_divergence()` 函數。目前公式：`divergence_score = total_ratio_change * 10 - price_change_pct + consecutive_weeks * 3`（連續週加成每週 +3）

### 修改前端 UI

直接修改 `index.html`（單一 HTML 檔案，內嵌 CSS 和 JavaScript）。

### 修改排行榜

修改 `ranking.html`，資料來源是 `data/ranking.json`。

---

## 已知限制與注意事項

1. **CORS**：TDCC API 沒有 CORS header，前端不能直接呼叫。解決：用 GitHub Actions 預先生成靜態 JSON。
2. **TDCC opendata 歷史限制**：`getOD.ashx?id=1-5` 不支援歷史日期，歷史回填改用 norway.twsthr.info。
3. **ETF 代號**：`006208`、`00878` 等六碼 ETF 代號在 TDCC CSV 中有空格填充，用 `r[1].strip()` 比對。
4. **歷史資料限制**：目前截斷為最新 52 週（norway 有約 200 週，但只取 52）。
5. **趨勢需要 2+ 週**：第一次執行只有一週資料時，所有股票顯示「❓ 資料不足」是正常的。
6. **背離分數需要股價**：沒有 close_price 的週次不計入背離計算。自輸代號（非預建清單）查詢時無背離分數。
7. **Windows 編碼**：Python 在 Windows 執行時需 `-X utf8` 或在腳本頂部加 `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`。
8. **背離回測限制**：回測期間（2025-2026）為牛市，上漲機率偏高，熊市效果未驗證。

---

## 待改進

- [ ] 支援自選股的趨勢排行（目前自選股頁面只顯示個別資料）
- [ ] 新增推播通知（PWA Web Push，大戶快速集中時主動通知）
- [ ] 增加更多股票到追蹤清單
- [ ] 背離指標加入產業景氣過濾（避免基本面惡化的假訊號）
