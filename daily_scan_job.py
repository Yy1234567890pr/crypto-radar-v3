#!/usr/bin/env python3
"""
Daily Scan Job - Reliable Version
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/crypto-auto-trader')

MIN_LIQUIDITY = 2000
MIN_VOLUME = 10000
SAFETY_MIN_SCORE = 60

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
    report.append("DAILY CRYPTO SCAN REPORT")
    report.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("-" * 40)
    
    opps = results['opportunities']
    
    if not opps:
        report.append("No qualified opportunities today.")
        report.append("Market is quiet.")
        return "\n".join(report)
    
    report.append(f"TOP PICKS ({min(3, len(opps))}):")
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
        
        report.append(f"{i}. [{opp['chain']}] ${opp['symbol']}")
        report.append(f"   MarketCap: {mc_str} | Liquidity: ${opp['liquidity']/1000:.1f}K")
        report.append(f"   Volume24h: ${opp['volume_24h']/1000:.1f}K | Change: {change_str}")
        report.append(f"   Safety: {opp['safety_score']}/100 | Score: {opp['total_score']:.1f}")
        report.append(f"   Address: {opp['address'][:20]}...")
        report.append("")
    
    if len(opps) > 3:
        report.append(f"WATCH LIST ({len(opps)-3}):")
        for opp in opps[3:6]:
            mc = opp.get('market_cap', 0)
            mc_str = f"${mc/1000000:.2f}M" if mc >= 1000000 else f"${mc/1000:.1f}K"
            report.append(f"   - {opp['chain']} ${opp['symbol']} | {mc_str} | Safety:{opp['safety_score']}")
        report.append("")
    
    report.append("RISK REMINDER:")
    report.append("- Meme coins: 0.5-2% position size")
    report.append("- Set stop-loss -30%, take-profit 30-50%")
    report.append("- High volatility = High risk")
    
    return "\n".join(report)

def main():
    try:
        results = run_scan()
        report = format_report(results)
        
        print("\n" + "="*60)
        print(report)
        print("="*60)
        
    except Exception as e:
        print(f"[FATAL] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
