# 📊 大戶持股趨勢分析 APP

專為投資人設計的股票大戶持股追蹤工具,自動每週更新排行榜,完全免費!

## ✨ 主要功能

### 1. 個股趨勢分析
- 📈 大戶持股歷史趨勢圖
- 🎯 智能判斷信號(快速集中/持續增加/減少)
- 📊 持股級距分布
- 📅 1個月/3個月/6個月/1年切換

### 2. 大戶集中排行榜 🔥
- 自動掃描50+支熱門股票
- 每週五自動更新
- 按大戶增加幅度排序
- 一鍵查看詳細分析

## 🚀 完整部署步驟

### 步驟1: Fork 或 Upload 到 GitHub

#### 方法A: 上傳檔案 (推薦新手)

1. 到 GitHub 建立新 Repository
   - 名稱: `stock-app`
   - 公開 (Public)
   - ✅ 勾選 "Add a README file"

2. 上傳所有檔案
   - 點擊 "Add file" → "Upload files"
   - 把整個資料夾的檔案都拖進去
   - Commit changes

#### 方法B: 使用 Git (進階)

```bash
git clone <你的repo網址>
cd stock-app
# 複製所有檔案到這裡
git add .
git commit -m "初始版本"
git push
```

### 步驟2: 啟用 GitHub Pages

1. 到 Repository 設定
2. 左側選單 → **Pages**
3. Source 選擇 **main** branch
4. Folder 選擇 **/ (root)**
5. 點擊 **Save**
6. 等1-2分鐘,會顯示網址: `https://你的用戶名.github.io/stock-app/`

### 步驟3: 啟用 GitHub Actions

1. 到 Repository 的 **Actions** 頁籤
2. 如果看到提示,點擊 **I understand my workflows, go ahead and enable them**
3. 完成!之後每週五晚上11點會自動執行

### 步驟4: 手動執行第一次 (測試)

1. 到 **Actions** 頁籤
2. 左側選擇 "更新股票大戶排行榜"
3. 點擊右側 **Run workflow** 按鈕
4. 選擇 branch: main
5. 點擊綠色的 **Run workflow**
6. 等待5-10分鐘執行完成
7. 檢查 `data/ranking.json` 是否有更新

### 步驟5: 在 iPhone 安裝

1. 用 **Safari** 開啟你的網址
2. 點擊下方分享按鈕
3. 選擇「加入主畫面」
4. 完成!

## 📁 專案結構

```
stock-app/
├── .github/workflows/
│   └── update-stocks.yml      # 自動執行腳本 (每週五23:00)
├── backend/
│   ├── fetch_data.py          # 抓取集保所資料
│   ├── calculate_trends.py    # 計算趨勢排行
│   └── requirements.txt       # Python套件
├── data/
│   ├── stocks_raw.json        # 原始資料 (自動生成)
│   └── ranking.json           # 排行榜 (自動生成)
├── index.html                 # 個股分析頁面
├── ranking.html               # 排行榜頁面
├── manifest.json              # PWA設定
├── service-worker.js          # 離線功能
├── icon-192.png               # APP圖標
├── icon-512.png               # APP圖標
└── README.md                  # 說明文件
```

## 🔧 自訂設定

### 修改股票清單

編輯 `backend/fetch_data.py`:

```python
STOCK_LIST = [
    '2330', '2317', '2454',  # 加入你想追蹤的股票代碼
    # ...
]
```

### 修改執行時間

編輯 `.github/workflows/update-stocks.yml`:

```yaml
schedule:
  - cron: '0 15 * * 5'  # 每週五 23:00 (UTC+8)
  # 改成 '0 15 * * *' 就變成每天執行
```

### 修改APP名稱

編輯 `manifest.json`:

```json
{
  "name": "你的APP名稱",
  "short_name": "簡稱"
}
```

## ⚠️ 常見問題

### Q: Actions執行失敗?
A: 檢查:
1. Repository 是否為 Public
2. Actions 是否已啟用
3. 檔案路徑是否正確

### Q: 排行榜沒資料?
A: 
1. 先手動執行一次 Actions
2. 等待5-10分鐘
3. 檢查 `data/ranking.json` 是否生成

### Q: 圖標不顯示?
A: 
1. 確認 icon-192.png 和 icon-512.png 已上傳
2. 重新加入主畫面

### Q: 想改成每天更新?
A: 把 cron 改成 `'0 15 * * *'`
   但集保所資料每週才更新,每天執行會抓到重複資料

## 💰 成本

- GitHub: **$0**
- 運算: **$0** (免費額度)
- 流量: **$0** (免費額度)
- 總計: **$0/月**

每週執行一次,只用2%的免費額度,永久免費!

## 📊 資料來源

- 台灣集中保管結算所 (TDCC)
- 每週五更新
- 官方權威資料

## 🔒 隱私

- 所有資料公開透明
- 不收集個人資訊
- 純前端APP,無追蹤

## 📝 授權

MIT License - 自由使用和修改

---

## 🎉 享受你的投資分析工具!

有問題可以開 Issue 討論 😊
