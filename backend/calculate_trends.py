#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
計算大戶持股趨勢並生成排行榜與個股 JSON
"""

import json
import os
from datetime import datetime


def calculate_trend(history):
    """比較最新一週 vs 12週前的變化"""
    if len(history) < 2:
        return None

    latest = history[0]
    weeks_ago = min(12, len(history) - 1)
    previous = history[weeks_ago]

    holder_change = latest['big_holders'] - previous['big_holders']
    ratio_change = latest['big_ratio'] - previous['big_ratio']

    if previous['big_holders'] > 0:
        holder_change_pct = (holder_change / previous['big_holders']) * 100
    else:
        holder_change_pct = 0

    return {
        'holder_change': holder_change,
        'holder_change_pct': round(holder_change_pct, 2),
        'ratio_change': round(ratio_change, 2),
        'weeks': weeks_ago
    }


def generate_signal(trend):
    """生成趨勢判斷信號"""
    if not trend:
        return {'icon': '❓', 'text': '資料不足', 'level': 'unknown', 'color': 'gray'}

    holder_change = trend['holder_change']
    ratio_change = trend['ratio_change']

    if holder_change > 10 and ratio_change > 3:
        return {'icon': '🚀', 'text': '大戶快速集中', 'level': 'strong_buy', 'color': 'green'}
    elif holder_change > 5 and ratio_change > 2:
        return {'icon': '📈', 'text': '大戶持續增加', 'level': 'buy', 'color': 'green'}
    elif holder_change > 0 and ratio_change > 0:
        return {'icon': '➡️', 'text': '大戶微幅增加', 'level': 'hold', 'color': 'gray'}
    elif holder_change < -5 or ratio_change < -2:
        return {'icon': '📉', 'text': '大戶持股減少', 'level': 'sell', 'color': 'red'}
    else:
        return {'icon': '➡️', 'text': '趨勢不明顯', 'level': 'neutral', 'color': 'gray'}


def save_stock_json(stock, trend, signal):
    """儲存個股 JSON 供前端直接讀取"""
    os.makedirs(os.path.join('data', 'stocks'), exist_ok=True)
    code = stock['stock_code']

    # 只保留前端需要的欄位，縮小檔案
    history_lite = []
    for h in stock['history']:
        history_lite.append({
            'date': h['date'],
            'big_holders': h['big_holders'],
            'big_shares': h.get('big_shares', 0),
            'big_ratio': h['big_ratio'],
            'total_holders': h['total_holders'],
            'total_shares': h['total_shares'],
            'distribution': h.get('distribution', [])
        })

    output = {
        'stock_code': code,
        'stock_name': stock['stock_name'],
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'history': history_lite,
        'trend': trend,
        'signal': signal
    }

    path = os.path.join('data', 'stocks', f'{code}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def main():
    print('📊 開始計算大戶趨勢排行...')

    try:
        with open(os.path.join('data', 'stocks_raw.json'), 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print('❌ 找不到 data/stocks_raw.json，請先執行 fetch_data.py')
        return

    rankings = []

    for stock in raw_data['stocks']:
        history = stock['history']
        if len(history) < 1:
            continue

        latest = history[0]
        trend = calculate_trend(history)
        signal = generate_signal(trend)

        save_stock_json(stock, trend, signal)

        if trend:
            score = round(trend['ratio_change'] * 10 + trend['holder_change_pct'], 2)
            rankings.append({
                'stock_code': stock['stock_code'],
                'stock_name': stock['stock_name'],
                'latest': {
                    'big_holders': latest['big_holders'],
                    'big_ratio': latest['big_ratio'],
                    'date': latest['date']
                },
                'trend': trend,
                'signal': signal,
                'score': score
            })

    rankings.sort(key=lambda x: x['score'], reverse=True)

    strong_buy = [r for r in rankings if r['signal']['level'] == 'strong_buy']
    buy = [r for r in rankings if r['signal']['level'] == 'buy']
    hold = [r for r in rankings if r['signal']['level'] == 'hold']

    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': raw_data.get('data_date', ''),
        'summary': {
            'total': len(rankings),
            'strong_buy': len(strong_buy),
            'buy': len(buy),
            'hold': len(hold)
        },
        'rankings': {
            'all': rankings[:30],
            'strong_buy': strong_buy[:10],
            'buy': buy[:10],
            'hold': hold[:10]
        }
    }

    with open(os.path.join('data', 'ranking.json'), 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'✅ 完成!')
    print(f'🚀 強力集中: {len(strong_buy)} 支')
    print(f'📈 持續增加: {len(buy)} 支')
    print(f'➡️  微幅增加: {len(hold)} 支')
    print(f'📁 已產生 data/stocks/{"{code}"}.json 個股檔案')
    print(f'📁 已更新 data/ranking.json')

    print('\n🏆 前5名:')
    for i, stock in enumerate(rankings[:5], 1):
        print(f'{i}. {stock["signal"]["icon"]} {stock["stock_code"]} {stock["stock_name"]}')
        if stock['trend']:
            print(f'   大戶 {stock["trend"]["holder_change"]:+d}人 '
                  f'({stock["trend"]["holder_change_pct"]:+.1f}%), '
                  f'比例 {stock["trend"]["ratio_change"]:+.1f}%')


if __name__ == '__main__':
    main()
