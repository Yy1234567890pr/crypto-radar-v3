#!/usr/bin/env python3
"""
Daily Scan Job - 终极简化版
直接用 radar_v3_pro 的集成扫描
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/crypto-radar-v3')

def run_scan():
    """运行每日扫描"""
    print("="*60)
    print(f"🦞 DAILY EARLY-BIRD SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)
    
    from radar_v3_pro import RadarV3
    radar = RadarV3()
    
    # 直接用RadarV3的高质量扫描方法
    print("\n📡 开始全链扫描...")
    tokens = radar.scan_with_quality_filter()
    print(f"   找到 {len(tokens)} 个符合条件的币")
    
    # 加安全检测
    from goplus_client import GoPlusClient
    goplus = GoPlusClient()
    opportunities = []
    
    for t in tokens[:15]:  # 只处理前15个
        try:
            chain = t.get('chain', 'ethereum')
            address = t.get('address', '')
            safety_result = goplus.get_token_security(chain, address)
            
            # 计算安全分
            safety_score = 100
            if safety_result.get('is_honeypot'):
                safety_score -= 50
            if safety_result.get('buy_tax', 0) > 5:
                safety_score -= 20
            if safety_result.get('sell_tax', 0) > 5:
                safety_score -= 20
            
            opp = {
                'chain': chain.upper(),
                'symbol': t.get('symbol', 'N/A'),
                'name': t.get('name', ''),
                'address': address,
                'price': t.get('price', 0),
                'market_cap': t.get('market_cap', 0),
                'liquidity': t.get('liquidity', 0),
                'volume_24h': t.get('volume_24h', 0),
                'price_change_24h': t.get('price_change_24h', 0),
                'safety_score': safety_score,
                'total_score': t.get('total_score', 0)
            }
            opportunities.append(opp)
        except:
            continue
    
    # 排序
    opportunities.sort(key=lambda x: x.get('total_score', 0), reverse=True)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'opportunities': opportunities,
        'count': len(opportunities)
    }
    
    # 保存
    output_file = f"/home/ubuntu/crypto-radar-v3/daily_scan_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"[OK] 保存到: {output_file}")
    print("="*60)
    
    return results

def format_report(results):
    """格式化报告"""
    report = []
    report.append("🦞 DAILY CRYPTO SCAN REPORT")
    report.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("-" * 40)
    
    opps = results.get('opportunities', [])
    
    if not opps:
        report.append("😴 今日无合适标的")
        report.append("市场安静或筛选条件严格")
        return "\n".join(report)
    
    report.append(f"🔥 TOP PICKS ({min(3, len(opps))}):")
    report.append("")
    
    for i, opp in enumerate(opps[:3], 1):
        mc = opp['market_cap'] or 0
        if mc >= 1000000:
            mc_str = f"${mc/1000000:.2f}M"
        elif mc >= 1000:
            mc_str = f"${mc/1000:.1f}K"
        else:
            mc_str = f"${mc:.0f}"
        
        change = opp['price_change_24h'] or 0
        change_emoji = "🟢" if change > 0 else "🔴"
        
        report.append(f"{i}. [{opp['chain']}] ${opp['symbol']}")
        report.append(f"   市值: {mc_str} | 流动: ${opp['liquidity']/1000:.1f}K")
        report.append(f"   成交: ${opp['volume_24h']/1000:.1f}K | {change_emoji} {change:+.1f}%")
        report.append(f"   安全: {opp['safety_score']}/100 | 📋 {opp['address'][:25]}...")
        report.append("")
    
    report.append("⚠️ 风险提示: 单币0.5-2% 止损-30% 止盈30-50%")
    
    return "\n".join(report)

def main():
    try:
        results = run_scan()
        report = format_report(results)
        
        # 打印报告，Hermes系统会捕获并发送到微信
        print("\n" + report)
        
    except Exception as e:
        print(f"[FATAL] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
