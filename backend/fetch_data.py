#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票大戶資料抓取腳本
從台灣集保所 opendata 抓取股權分散表資料
API: https://opendata.tdcc.com.tw/getOD.ashx?id=1-5
CSV 格式: 資料日期, 股票代號, 持股分級, 人數, 股數, 佔集保庫存數比例%
Level 15 = 千張以上大戶, Level 17 = 合計
"""

import sys
import requests
import json
import csv
import io
import os
from datetime import datetime

# Windows 命令列需設定 UTF-8 輸出才能顯示中文和 emoji
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STOCK_LIST = [
    '2330', '2317', '2454', '2881', '2882', '2891', '2892', '2886',
    '2303', '2382', '2308', '3711', '2412', '2207', '3008', '2301',
    '1301', '1303', '2002', '1326', '2912', '2884', '2885', '2887',
    '2357', '2353', '3045', '2408', '2409', '6505', '2880', '5871',
    '5876', '2883', '2890', '1216', '2327', '2345', '2615', '9910',
    '2395', '3231', '3034', '2379', '2474', '6669', '3443', '4904',
    '0050', '0056', '006208', '00878', '00881', '00900'
]

LEVEL_NAMES = {
    '1': '1-999股', '2': '1-5張', '3': '5-10張', '4': '10-15張',
    '5': '15-20張', '6': '20-30張', '7': '30-40張', '8': '40-50張',
    '9': '50-100張', '10': '100-200張', '11': '200-400張',
    '12': '400-600張', '13': '600-800張', '14': '800千-1千張',
    '15': '千張以上'
}


def fetch_opendata_csv():
    """下載集保所 opendata CSV (全市場最新一週資料)"""
    url = 'https://opendata.tdcc.com.tw/getOD.ashx?id=1-5'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    session = requests.Session()
    session.max_redirects = 10
    response = session.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    content = response.content.decode('utf-8-sig')
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    return rows[1:]  # 跳過標題行


def fetch_stock_names():
    """從 TWSE 取得股票名稱對照表"""
    try:
        url = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
        r = requests.get(url, timeout=15)
        data = r.json()
        return {item['Code']: item['Name'] for item in data if 'Code' in item and 'Name' in item}
    except Exception as e:
        print(f'⚠️  無法取得股票名稱: {e}')
        return {}


def parse_stock_week(stock_code, all_rows):
    """從全部 CSV 行中解析指定股票的當週資料"""
    stock_rows = [r for r in all_rows if len(r) >= 6 and r[1].strip() == stock_code]
    if not stock_rows:
        return None

    date = stock_rows[0][0]

    total_row = next((r for r in stock_rows if r[2] == '17'), None)
    if not total_row:
        return None

    total_holders = int(total_row[3])
    total_shares = int(total_row[4])

    big_row = next((r for r in stock_rows if r[2] == '15'), None)
    big_holders = int(big_row[3]) if big_row else 0
    big_shares = int(big_row[4]) if big_row else 0
    big_ratio = float(big_row[5]) if big_row else 0.0

    distribution = []
    for r in stock_rows:
        level = r[2]
        if level in [str(i) for i in range(1, 16)]:
            distribution.append({
                'level': int(level),
                'level_name': LEVEL_NAMES.get(level, level),
                'holders': int(r[3]),
                'shares': int(r[4]),
                'percent': float(r[5])
            })

    return {
        'date': date,
        'big_holders': big_holders,
        'big_shares': big_shares,
        'big_ratio': big_ratio,
        'total_holders': total_holders,
        'total_shares': total_shares,
        'distribution': distribution
    }


def main():
    print('🚀 開始抓取股票資料...')
    print(f'📊 共 {len(STOCK_LIST)} 支股票')

    print('📥 下載集保所 opendata CSV...')
    all_rows = fetch_opendata_csv()
    data_date = all_rows[0][0] if all_rows else 'unknown'
    print(f'✅ 下載完成，共 {len(all_rows)} 筆，資料日期: {data_date}')

    print('📋 取得股票名稱...')
    name_map = fetch_stock_names()
    print(f'   取得 {len(name_map)} 支股票名稱')

    raw_file = os.path.join('data', 'stocks_raw.json')
    existing = {}
    if os.path.exists(raw_file):
        with open(raw_file, 'r', encoding='utf-8') as f:
            old = json.load(f)
            for s in old.get('stocks', []):
                existing[s['stock_code']] = s
        print(f'📂 讀取既有歷史資料: {len(existing)} 支')

    all_data = []
    success_count = 0

    for stock_code in STOCK_LIST:
        week_data = parse_stock_week(stock_code, all_rows)

        if week_data:
            entry = existing.get(stock_code, {
                'stock_code': stock_code,
                'stock_name': name_map.get(stock_code, stock_code),
                'history': []
            })
            if stock_code in name_map:
                entry['stock_name'] = name_map[stock_code]

            if not any(h['date'] == week_data['date'] for h in entry['history']):
                entry['history'].insert(0, week_data)
                entry['history'] = entry['history'][:52]  # 保留一年52週

            all_data.append(entry)
            success_count += 1
            print(f'  ✅ {stock_code} {entry["stock_name"]}: '
                  f'大戶 {week_data["big_holders"]}人 ({week_data["big_ratio"]}%)')
        else:
            if stock_code in existing:
                all_data.append(existing[stock_code])
            print(f'  ⚠️  {stock_code}: 本週集保資料缺失')

    os.makedirs('data', exist_ok=True)
    with open(raw_file, 'w', encoding='utf-8') as f:
        json.dump({
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_date': data_date,
            'stocks': all_data
        }, f, ensure_ascii=False, indent=2)

    print(f'\n✅ 完成! 成功 {success_count}/{len(STOCK_LIST)} 支')
    print(f'📁 儲存至: {raw_file}')


if __name__ == '__main__':
    main()
