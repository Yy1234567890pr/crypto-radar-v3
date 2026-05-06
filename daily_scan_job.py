#!/usr/bin/env python3
"""
Daily Scan Job - Reliable Version with WeChat Push
"""

import os
import sys
import json
import subprocess
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/crypto-auto-trader')

MIN_LIQUIDITY = 2000
MIN_VOLUME = 10000
SAFETY_MIN_SCORE = 60

def send_weixin(message):
    """使用hermes CLI发送微信消息"""
    try:
        # 将消息写入临时文件避免命令行截断
        msg_file = "/tmp/scan_report.txt"
        with open(msg_file, 'w', encoding='utf-8') as f:
            f.write(message)
        
        # 使用hermes send_message 命令发送
        result = subprocess.run(
            ["python3", "-c", f"""
import sys
sys.path.insert(0, '/home/ubuntu/crypto-auto-trader')
with open('{msg_file}', 'r', encoding='utf-8') as f:
    msg = f.read()
print(msg)
"""],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(f"[OK] Report prepared for WeChat")
        return True
    except Exception as e:
        print(f"[ERROR] WeChat prep failed: {e}")
        return False

def run_scan():
    from scanners.multi_chain_scanner import MultiChainScanner
    
    scanner = MultiChainScanner()
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'opportunities': [],
        'errors': []
    }
    
    print("="*60)
    print(f"DAILY EARLY-BIRD SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)
    
    try:
        all_tokens = scanner.scan_all_chains(limit_per_chain=15)
        print(f"\n[OK] Found {len(all_tokens)} tokens total")
        
        for token in all_tokens:
            volume = token.get('volume_24h', 0)
            liquidity = token.get('liquidity', 0)
            safety_score = token.get('safety_score', 0)
            
            if volume >= MIN_VOLUME and liquidity >= MIN_LIQUIDITY and safety_score >= SAFETY_MIN_SCORE:
                opp = {
                    'chain': token.get('chain', 'unknown').upper(),
                    'symbol': token.get('symbol', 'N/A'),
                    'name': token.get('name', ''),
                    'address': token.get('address', ''),
                    'price': token.get('price', 0),
                    'market_cap': token.get('market_cap', 0),
                    'liquidity': liquidity,
                    'volume_24h': volume,
                    'price_change_24h': token.get('price_change_24h', 0),
                    'safety_score': safety_score,
                    'total_score': token.get('total_score', 0),
                    'url': token.get('url', '')
                }
                results['opportunities'].append(opp)
        
        results['opportunities'].sort(key=lambda x: x['total_score'], reverse=True)
        print(f"[OK] Qualified opportunities: {len(results['opportunities'])}")
        
    except Exception as e:
        results['errors'].append(str(e))
        print(f"[ERROR] Scan failed: {e}")
    
    output_file = f"/home/ubuntu/crypto-radar-v3/daily_scan_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"[OK] Saved to: {output_file}")
    print("="*60)
    
    return results

def format_report(results):
    report = []
    report.append("🦞 DAILY CRYPTO SCAN REPORT")
    report.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("-" * 40)
    
    opps = results['opportunities']
    
    if not opps:
        report.append("😴 No qualified opportunities today.")
        report.append("Market is quiet.")
        return "\n".join(report)
    
    report.append(f"🔥 TOP PICKS ({min(3, len(opps))}):")
    report.append("")
    
    for i, opp in enumerate(opps[:3], 1):
        mc = opp.get('market_cap', 0)
        if mc >= 1000000:
            mc_str = f"${mc/1000000:.2f}M"
        elif mc >= 1000:
            mc_str = f"${mc/1000:.1f}K"
        else:
            mc_str = f"${mc:.0f}"
        
        change = opp.get('price_change_24h', 0)
        change_str = f"{change:+.1f}%"
        change_emoji = "🟢" if change > 0 else "🔴"
        
        report.append(f"{i}. [{opp['chain']}] ${opp['symbol']}")
        report.append(f"   MarketCap: {mc_str} | Liq: ${opp['liquidity']/1000:.1f}K")
        report.append(f"   Vol24h: ${opp['volume_24h']/1000:.1f}K | {change_emoji} {change_str}")
        report.append(f"   Safety: {opp['safety_score']}/100 | Score: {opp['total_score']:.1f}")
        report.append(f"   📋 {opp['address'][:25]}...")
        report.append("")
    
    if len(opps) > 3:
        report.append(f"👀 WATCH LIST ({len(opps)-3} more):")
        for opp in opps[3:6]:
            mc = opp.get('market_cap', 0)
            mc_str = f"${mc/1000000:.2f}M" if mc >= 1000000 else f"${mc/1000:.1f}K"
            report.append(f"   • {opp['chain']} ${opp['symbol']} | {mc_str} | Safe:{opp['safety_score']}")
        report.append("")
    
    report.append("⚠️ RISK REMINDER:")
    report.append("• Position size: 0.5-2% per coin")
    report.append("• Stop-loss: -30% | Take-profit: 30-50%")
    report.append("• High volatility = High risk")
    
    return "\n".join(report)

def main():
    try:
        results = run_scan()
        report = format_report(results)
        
        print("\n" + "="*60)
        print(report)
        print("="*60)
        
        # 打印到stdout，由hermes系统捕获并发送
        print("\n" + report)
        
    except Exception as e:
        print(f"[FATAL] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
