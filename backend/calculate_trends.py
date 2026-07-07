#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
計算大戶持股趨勢並生成排行榜與個股 JSON
"""

import json
import os
from datetime import datetime


def calculate_recent_change(history):
    """計算近2週比例變化（最新 vs 2週前），反映當下動能"""
    if len(history) < 2:
        return None
    ref = history[2] if len(history) >= 3 else history[1]
    return round(history[0]['big_ratio'] - ref['big_ratio'], 2)


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


def calculate_divergence(history):
    """
    計算籌碼背離分數：大戶比例「連續上升」但股價尚未跟上
    - 需連續 ≥ 2 週上升，過濾單週雜訊
    - 比較基準為連漲起點（動態），非固定 12 週前
    - 分數 = 比例累積變化 × 10 − 股價漲幅 + 連續週數 × 3
    分數越高 = 持續吃貨且股價越落後 → 訊號越可靠
    """
    if len(history) < 3:
        return None

    # 從最新週往回數，計算大戶比例連續上升週數
    consecutive_weeks = 0
    for i in range(len(history) - 1):
        if history[i]['big_ratio'] > history[i + 1]['big_ratio']:
            consecutive_weeks += 1
        else:
            break

    if consecutive_weeks < 2:
        return None

    latest      = history[0]
    streak_start = history[consecutive_weeks]   # 連漲起點那週

    latest_price = latest.get('close_price')
    start_price  = streak_start.get('close_price')

    if not latest_price or not start_price or start_price <= 0:
        return None

    total_ratio_change = latest['big_ratio'] - streak_start['big_ratio']
    price_change_pct   = (latest_price - start_price) / start_price * 100

    # 連續週數加成：每多一週給 +3 分（獎勵持續性）
    divergence_score = round(total_ratio_change * 10 - price_change_pct + consecutive_weeks * 3, 2)

    return {
        'consecutive_weeks': consecutive_weeks,
        'ratio_change':      round(total_ratio_change, 2),
        'price_change_pct':  round(price_change_pct, 2),
        'divergence_score':  divergence_score,
        'latest_price':      latest_price,
    }


def calculate_profit_taking(history):
    """
    偵測獲利了結風險：曾連續吃貨 ≥ 3 週後，大戶比例開始回落
    條件：
      1. 最近 ≥ 1 週比例連續下降
      2. 下降之前曾有 ≥ 3 週連續上升（確認為吃貨後出貨，非隨機波動）
    """
    if len(history) < 5:
        return None

    # 計算最近連續下降週數
    recent_down = 0
    for i in range(len(history) - 1):
        if history[i]['big_ratio'] < history[i + 1]['big_ratio']:
            recent_down += 1
        else:
            break

    if recent_down < 1:
        return None

    # 下降之前找連續上升週數
    prev_streak = 0
    for i in range(recent_down, len(history) - 1):
        if history[i]['big_ratio'] > history[i + 1]['big_ratio']:
            prev_streak += 1
        else:
            break

    if prev_streak < 3:
        return None

    peak_week  = history[recent_down]
    base_week  = history[recent_down + prev_streak]

    latest_price = history[0].get('close_price')
    peak_price   = peak_week.get('close_price')
    base_price   = base_week.get('close_price')

    price_gain_pct = None
    if peak_price and base_price and base_price > 0:
        price_gain_pct = round((peak_price - base_price) / base_price * 100, 2)

    ratio_drop = round(history[0]['big_ratio'] - peak_week['big_ratio'], 2)

    return {
        'recent_down_weeks': recent_down,
        'prev_streak_weeks': prev_streak,
        'ratio_drop':        ratio_drop,
        'price_gain_pct':    price_gain_pct,
        'latest_price':      latest_price,
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
            'close_price': h.get('close_price') or None,
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

    rankings        = []
    divergence_list = []
    pt_list         = []

    for stock in raw_data['stocks']:
        history = stock['history']
        if len(history) < 1:
            continue

        latest = history[0]
        trend         = calculate_trend(history)
        signal        = generate_signal(trend)
        div           = calculate_divergence(history)
        pt            = calculate_profit_taking(history)
        recent_change = calculate_recent_change(history)

        save_stock_json(stock, trend, signal)

        if trend:
            score = round(trend['ratio_change'] * 10 + trend['holder_change_pct'], 2)
            rankings.append({
                'stock_code': stock['stock_code'],
                'stock_name': stock['stock_name'],
                'latest': {
                    'big_holders': latest['big_holders'],
                    'big_ratio':   latest['big_ratio'],
                    'date':        latest['date'],
                    'close_price': latest.get('close_price'),
                },
                'trend':         trend,
                'signal':        signal,
                'score':         score,
                'divergence':    div,
                'recent_change': recent_change,
            })

        if div:
            divergence_list.append({
                'stock_code': stock['stock_code'],
                'stock_name': stock['stock_name'],
                'latest': {
                    'big_holders': latest['big_holders'],
                    'big_ratio':   latest['big_ratio'],
                    'date':        latest['date'],
                    'close_price': latest.get('close_price'),
                },
                'divergence': div,
                'signal':     signal,
            })

        if pt:
            pt_list.append({
                'stock_code':    stock['stock_code'],
                'stock_name':    stock['stock_name'],
                'latest': {
                    'big_holders': latest['big_holders'],
                    'big_ratio':   latest['big_ratio'],
                    'date':        latest['date'],
                    'close_price': latest.get('close_price'),
                },
                'profit_taking': pt,
                'signal':        signal,
            })

    rankings.sort(key=lambda x: x['score'], reverse=True)
    divergence_list.sort(key=lambda x: x['divergence']['divergence_score'], reverse=True)
    # 出貨警示：先看出貨時間長度，再看吃貨期漲幅（漲越多越要小心）
    pt_list.sort(key=lambda x: (
        x['profit_taking']['recent_down_weeks'],
        x['profit_taking']['price_gain_pct'] or 0
    ), reverse=True)

    strong_buy = [r for r in rankings if r['signal']['level'] == 'strong_buy']
    buy        = [r for r in rankings if r['signal']['level'] == 'buy']
    hold       = [r for r in rankings if r['signal']['level'] == 'hold']

    recent_up = sorted(
        [r for r in rankings if r['recent_change'] is not None and r['recent_change'] >= 0.5],
        key=lambda x: x['recent_change'],
        reverse=True
    )

    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': raw_data.get('data_date', ''),
        'summary': {
            'total':          len(rankings),
            'strong_buy':     len(strong_buy),
            'buy':            len(buy),
            'hold':           len(hold),
            'divergence':     len(divergence_list),
            'recent_up':      len(recent_up),
            'profit_taking':  len(pt_list),
        },
        'rankings': {
            'all':            rankings[:30],
            'strong_buy':     strong_buy[:10],
            'buy':            buy[:10],
            'hold':           hold[:10],
            'divergence':     divergence_list[:20],
            'recent_up':      recent_up[:20],
            'profit_taking':  pt_list[:20],
        }
    }

    with open(os.path.join('data', 'ranking.json'), 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'✅ 完成!')
    print(f'🚀 強力集中: {len(strong_buy)} 支')
    print(f'📈 持續增加: {len(buy)} 支')
    print(f'➡️  微幅增加: {len(hold)} 支')
    print(f'📊 籌碼背離: {len(divergence_list)} 支')
    print(f'⚠️  注意出貨: {len(pt_list)} 支')
    print(f'📁 已產生 data/stocks/{"{code}"}.json 個股檔案')
    print(f'📁 已更新 data/ranking.json')

    print('\n🔍 背離前5名:')
    for i, s in enumerate(divergence_list[:5], 1):
        d = s['divergence']
        print(f'{i}. {s["stock_code"]} {s["stock_name"]}  '
              f'大戶比例 {d["ratio_change"]:+.2f}pp  '
              f'股價 {d["price_change_pct"]:+.1f}%  '
              f'背離分 {d["divergence_score"]:+.1f}')

    print('\n🏆 前5名:')
    for i, stock in enumerate(rankings[:5], 1):
        print(f'{i}. {stock["signal"]["icon"]} {stock["stock_code"]} {stock["stock_name"]}')
        if stock['trend']:
            print(f'   大戶 {stock["trend"]["holder_change"]:+d}人 '
                  f'({stock["trend"]["holder_change_pct"]:+.1f}%), '
                  f'比例 {stock["trend"]["ratio_change"]:+.1f}%')


if __name__ == '__main__':
    main()
