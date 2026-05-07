#!/usr/bin/env python3
"""
AVE.ai 监控模块
扫链时同时获取AVE热门数据
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Optional

class AveMonitor:
    def __init__(self):
        self.base_url = "https://api.ave.ai"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
    def fetch_trending(self, chain: str = "bsc", limit: int = 20) -> List[Dict]:
        """获取AVE热门榜单"""
        try:
            # AVE Trending API (通过他们的公开接口)
            url = f"https://api.dexscreener.com/latest/dex/tokens/{chain}"
            # 实际用DexScreener数据，按AVE标准筛选
            
            resp = requests.get(url, headers=self.headers, timeout=10)
            data = resp.json()
            
            tokens = []
            for pair in data.get('pairs', [])[:limit]:
                token = {
                    'symbol': pair.get('baseToken', {}).get('symbol'),
                    'name': pair.get('baseToken', {}).get('name'),
                    'contract': pair.get('baseToken', {}).get('address'),
                    'chain': chain,
                    'price': float(pair.get('priceUsd', 0)),
                    'market_cap': pair.get('marketCap', 0),
                    'liquidity': pair.get('liquidity', {}).get('usd', 0),
                    'volume_24h': pair.get('volume', {}).get('h24', 0),
                    'change_24h': pair.get('priceChange', {}).get('h24', 0),
                    'change_1h': pair.get('priceChange', {}).get('h1', 0),
                    'holders': pair.get('txns', {}).get('h24', {}).get('buys', 0) + pair.get('txns', {}).get('h24', {}).get('sells', 0),
                    'is_ave_verified': False  # 需要额外验证
                }
                tokens.append(token)
            
            return tokens
        except Exception as e:
            print(f"❌ AVE fetch failed: {e}")
            return []
    
    def filter_ave_style(self, tokens: List[Dict]) -> List[Dict]:
        """按AVE标准筛选：新币+热门"""
        filtered = []
        
        for t in tokens:
            # AVE风格筛选
            mc = t.get('market_cap', 0) or 0
            liq = t.get('liquidity', 0) or 0
            vol = t.get('volume_24h', 0) or 0
            change_1h = t.get('change_1h', 0) or 0
            
            # AVE早期土狗标准
            if mc < 500000 and liq > 5000 and vol > 10000 and change_1h > 5:
                t['ave_score'] = self.calc_ave_score(t)
                filtered.append(t)
        
        # 按AVE分数排序
        return sorted(filtered, key=lambda x: x.get('ave_score', 0), reverse=True)
    
    def calc_ave_score(self, token: Dict) -> float:
        """计算AVE综合评分"""
        mc = token.get('market_cap', 1)
        liq = token.get('liquidity', 1)
        vol = token.get('volume_24h', 1)
        change_1h = token.get('change_1h', 0)
        change_24h = token.get('change_24h', 0)
        
        # AVE评分公式（早期币权重更高）
        score = 0
        
        # 市值越小分数越高（早期优势）
        if mc < 100000:
            score += 40
        elif mc < 500000:
            score += 25
        
        # 流动性/市值比（健康度）
        liq_ratio = liq / mc if mc > 0 else 0
        if liq_ratio > 0.1:
            score += 20
        elif liq_ratio > 0.05:
            score += 10
        
        # 成交量/市值比（活跃度）
        vol_ratio = vol / mc if mc > 0 else 0
        if vol_ratio > 0.5:
            score += 20
        elif vol_ratio > 0.2:
            score += 10
        
        # 涨幅
        if change_1h > 50:
            score += 15
        elif change_1h > 20:
            score += 10
        elif change_1h > 5:
            score += 5
        
        # 24h趋势确认
        if change_24h > 100:
            score += 5
        
        return min(score, 100)
    
    def format_ave_report(self, tokens: List[Dict], top_n: int = 5) -> str:
        """格式化AVE风格报告"""
        if not tokens:
            return "暂无AVE风格信号"
        
        report = "🔥 AVE风格热门榜单\n"
        report += "=" * 50 + "\n\n"
        
        for i, t in enumerate(tokens[:top_n], 1):
            emoji = "🚀" if t.get('ave_score', 0) > 80 else "🔥" if t.get('ave_score', 0) > 60 else "⭐"
            report += f"{i}. {emoji} ${t.get('symbol', 'N/A')}\n"
            report += f"   价格: ${t.get('price', 0):.6f}\n"
            report += f"   市值: ${t.get('market_cap', 0)/1000:.1f}K\n"
            report += f"   流动: ${t.get('liquidity', 0)/1000:.1f}K\n"
            report += f"   1h/24h: {t.get('change_1h', 0):+.1f}% / {t.get('change_24h', 0):+.1f}%\n"
            report += f"   AVE分: {t.get('ave_score', 0):.0f}/100\n"
            report += f"   合约: {t.get('contract', 'N/A')[:20]}...\n\n"
        
        return report

if __name__ == "__main__":
    monitor = AveMonitor()
    print("🚀 AVE监控模块测试\n")
    
    # 测试获取BSC链数据
    tokens = monitor.fetch_trending("bsc", 30)
    print(f"获取到 {len(tokens)} 个Token\n")
    
    # 按AVE风格筛选
    ave_tokens = monitor.filter_ave_style(tokens)
    print(f"AVE风格筛选后: {len(ave_tokens)} 个\n")
    
    # 输出报告
    report = monitor.format_ave_report(ave_tokens, 5)
    print(report)
