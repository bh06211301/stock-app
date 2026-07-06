#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從 norway.twsthr.info 抓取個股歷史持股分散資料（約 200 週，3 年以上）
比舊版 TDCC 方案更快（無 CSRF）、歷史更長、支援任意股票代號

執行方式: python -X utf8 backend/fetch_history.py
預估時間: 約 2-4 分鐘（每支股票一個請求）

新增股票步驟:
  1. 在下方 STOCK_LIST 加入代號
  2. 同樣在 fetch_data.py 的 STOCK_LIST 加入
  3. 執行此腳本補歷史
  4. 執行 calculate_trends.py
  5. git push
"""

import sys
import json
import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 追蹤清單（與 fetch_data.py 保持一致）──────────────────────────────
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
# ─────────────────────────────────────────────────────────────────────

NORWAY_URL = 'https://norway.twsthr.info/StockHolders.aspx?stock={code}'
DELAY = 1.2  # 請求間隔（秒），避免造成對方伺服器壓力

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Referer': 'https://norway.twsthr.info/',
}


def parse_int(s):
    try:
        return int(str(s).replace(',', '').strip())
    except (ValueError, AttributeError):
        return 0


def parse_float(s):
    try:
        return float(str(s).replace(',', '').strip())
    except (ValueError, AttributeError):
        return 0.0


def fetch_norway_history(stock_code):
    """
    抓取 norway.twsthr.info 的個股頁面，回傳週歷史資料清單（最新在前）。

    頁面 HTML 結構：週報資料放在 16 欄的表格中
      col[2]=資料日期  col[3]=集保總張數  col[4]=總股東人數
      col[12]=千張以上人數  col[13]=千張以上%  col[14]=收盤價
    """
    url = NORWAY_URL.format(code=stock_code)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f' [連線失敗: {e}]', end='', flush=True)
        return []

    soup = BeautifulSoup(r.text, 'lxml')
    tables = soup.find_all('table')

    # 找週報資料表：找有 16 欄、且 col[2] 是 8 位日期的表格
    weekly_table = None
    for tbl in tables:
        rows = tbl.find_all('tr')
        if len(rows) < 10:
            continue
        for tr in rows:
            cells = tr.find_all(['td', 'th'])
            if len(cells) != 16:
                continue
            val = cells[2].get_text(strip=True)
            if len(val) == 8 and val.isdigit() and val.startswith('20'):
                weekly_table = tbl
                break
        if weekly_table:
            break

    if not weekly_table:
        print(' [找不到週報表格]', end='', flush=True)
        return []

    history = []
    for tr in weekly_table.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if len(cells) != 16:
            continue

        date = cells[2].get_text(strip=True)
        if len(date) != 8 or not date.isdigit() or not date.startswith('20'):
            continue

        try:
            total_lots    = parse_int(cells[3].get_text())   # 集保總張數（張）
            total_holders = parse_int(cells[4].get_text())   # 總股東人數
            big_holders   = parse_int(cells[12].get_text())  # >1000張人數
            big_ratio     = parse_float(cells[13].get_text()) # >1000張持有%
        except IndexError:
            continue

        if total_lots == 0 and big_holders == 0:
            continue

        # 轉換單位：張 → 股（1張 = 1000股）
        total_shares = total_lots * 1000
        big_shares   = round(big_ratio / 100 * total_lots) * 1000

        history.append({
            'date': date,
            'big_holders': big_holders,
            'big_shares': big_shares,
            'big_ratio': big_ratio,
            'total_holders': total_holders,
            'total_shares': total_shares,
            'distribution': [],  # 歷史週無分布細項；最新週由 fetch_data.py 補入
        })

    history.sort(key=lambda h: h['date'], reverse=True)
    return history


def fetch_stock_names():
    """從 TWSE 取得股票名稱"""
    try:
        r = requests.get(
            'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL',
            timeout=15
        )
        data = r.json()
        return {item['Code']: item['Name'] for item in data
                if 'Code' in item and 'Name' in item}
    except Exception as e:
        print(f'  ⚠️  無法取得股票名稱: {e}')
        return {}


def main():
    print('=' * 60)
    print('📚 Norway 歷史資料回填腳本')
    print(f'   資料來源: norway.twsthr.info（約 200 週）')
    print('=' * 60)

    raw_file = os.path.join('data', 'stocks_raw.json')

    # 讀取既有資料
    existing = {}
    if os.path.exists(raw_file):
        with open(raw_file, 'r', encoding='utf-8') as f:
            old = json.load(f)
            for s in old.get('stocks', []):
                existing[s['stock_code']] = s
        print(f'📂 讀取既有資料: {len(existing)} 支')

    # 取得股票名稱
    print('📋 取得股票名稱...')
    name_map = fetch_stock_names()
    print(f'   取得 {len(name_map)} 支')

    all_data = []
    start_time = time.time()

    for si, stock_code in enumerate(STOCK_LIST, 1):
        print(f'\n[{si:02d}/{len(STOCK_LIST)}] {stock_code}', end='', flush=True)

        entry = existing.get(stock_code, {
            'stock_code': stock_code,
            'stock_name': name_map.get(stock_code, stock_code),
            'history': []
        })
        if stock_code in name_map:
            entry['stock_name'] = name_map[stock_code]

        existing_dates = {h['date'] for h in entry['history']}

        time.sleep(DELAY)
        norway_history = fetch_norway_history(stock_code)

        if not norway_history:
            print(f' → 無資料，保留既有 {len(entry["history"])} 週')
            all_data.append(entry)
            continue

        # 只補入不存在的週（保留 fetch_data.py 帶 distribution 的最新週）
        added = 0
        for week in norway_history:
            if week['date'] not in existing_dates:
                entry['history'].append(week)
                existing_dates.add(week['date'])
                added += 1

        entry['history'].sort(key=lambda h: h['date'], reverse=True)
        entry['history'] = entry['history'][:52]  # 保留最多 52 週

        weeks_total = len(entry['history'])
        print(f' → 新增 {added} 週，共 {weeks_total} 週 ({entry["stock_name"]})')
        all_data.append(entry)

        # 每 10 支存一次中間結果
        if si % 10 == 0:
            _save(raw_file, all_data)
            print(f'  💾 中間存檔 ({si} 支)')

    _save(raw_file, all_data)
    elapsed = time.time() - start_time
    print(f'\n{"=" * 60}')
    print(f'✅ 完成！共處理 {len(all_data)} 支股票')
    print(f'⏱️  耗時 {elapsed/60:.1f} 分鐘')
    print(f'📁 已儲存: {raw_file}')
    print(f'\n⚠️  請接著執行: python -X utf8 backend/calculate_trends.py')


def _save(raw_file, all_data):
    os.makedirs('data', exist_ok=True)
    with open(raw_file, 'w', encoding='utf-8') as f:
        json.dump({
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_date': all_data[0]['history'][0]['date'] if all_data and all_data[0]['history'] else '',
            'stocks': all_data,
        }, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
