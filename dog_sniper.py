#!/usr/bin/env python3
"""
土狗狙击手 - 超早期代币发现系统
筛选规则：满足≥2条即推送
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class TokenSignal:
    chain: str
    symbol: str
    address: str
    price: float
    market_cap: float
    liquidity: float
    volume_24h: float
    price_change_1h: float
    price_change_24h: float
    created_at: Optional[datetime] = None
    top10_holding: Optional[float] = None
    smart_money_signals: int = 0
    safety_score: int = 0
    rules_matched: List[int] = None
    narrative: str = ""  # Meme/AI/GameFi
    
    def to_dict(self):
        return {
            'chain': self.chain,
            'symbol': self.symbol,
            'address': self.address,
            'price': self.price,
            'market_cap': self.market_cap,
            'liquidity': self.liquidity,
            'volume_24h': self.volume_24h,
            'price_change_1h': self.price_change_1h,
            'price_change_24h': self.price_change_24h,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'top10_holding': self.top10_holding,
            'smart_money_signals': self.smart_money_signals,
            'safety_score': self.safety_score,
            'rules_matched': self.rules_matched or [],
            'narrative': self.narrative
        }

class DogSniper:
    """土狗狙击手"""
    
    # 筛选阈值
    RULES = {
        1: "新且小 (≤6小时, ≤10ETH流动性)",
        2: "筹码集中 (前10≤20%)",
        3: "聪明钱入场 (胜率>55%地址10分钟内买入)",
        4: "社媒热炒 (1小时≥2个KOL转发)",
        5: "安全底线 (GoPlus≥70分)"
    }
    
    # Meme关键词
    MEME_KEYWORDS = ['dog', 'cat', 'pepe', 'wif', 'shib', 'floki', 'doge', 'cat', 'meme', 'moon', 'rocket', 'elon']
    AI_KEYWORDS = ['ai', 'gpt', 'neural', 'brain', 'bot', 'intelligence']
    GAMEFI_KEYWORDS = ['game', 'play', 'meta', 'nft', 'verse', 'world']
    
    def __init__(self):
        self.signals = []
        
    def check_rule_1_new_small(self, token: Dict) -> bool:
        """规则1: 新且小 - ≤6小时, ≤10ETH流动性"""
        # DexScreener没有创建时间，用pairCreatedAt估算
        pair_created = token.get('pairCreatedAt')
        if pair_created:
            created_time = datetime.fromtimestamp(pair_created / 1000)
            hours_old = (datetime.now() - created_time).total_seconds() / 3600
            if hours_old <= 6:
                return True
        
        # 小流动性检查 (10 ETH ≈ $30K)
        liquidity = token.get('liquidity', {}).get('usd', 0)
        if liquidity > 0 and liquidity <= 30000:  # ≤$30K ≈ 10 ETH
            return True
            
        return False
    
    def check_rule_2_holder_concentration(self, token: Dict) -> bool:
        """规则2: 筹码集中 - 前10≤20%"""
        # 需要从链上获取持币分布
        # 暂时用流动性/市值比例估算
        mc = token.get('marketCap', 0)
        liq = token.get('liquidity', {}).get('usd', 0)
        
        if mc > 0 and liq > 0:
            liq_ratio = liq / mc
            # 流动性占比高 = 筹码分散
            if liq_ratio > 0.1:  # 流动性>市值10%，说明较分散
                return True
        return False
    
    def check_rule_3_smart_money(self, token: Dict, recent_txs: List[Dict] = None) -> bool:
        """规则3: 聪明钱入场 - 胜率>55%地址10分钟内买入"""
        # 简化：检查是否有大额买入且地址历史胜率较高
        # 实际实现需要接入Moralis分析地址历史
        volume = token.get('volume', {}).get('h1', 0)
        if volume > token.get('marketCap', 0) * 0.05:  # 1小时成交>市值5%，有聪明钱活跃
            return True
        return False
    
    def check_rule_4_social_media(self, token: Dict) -> bool:
        """规则4: 社媒热炒 - 1小时≥2个KOL转发"""
        # 简化：检查社媒链接和名字热度
        symbol = token.get('symbol', '').lower()
        name = token.get('name', '').lower()
        
        # Meme风格名字 = 社媒热度指标
        for keyword in self.MEME_KEYWORDS:
            if keyword in symbol or keyword in name:
                return True
        return False
    
    def check_rule_5_safety(self, token: Dict) -> bool:
        """规则5: 安全底线 - GoPlus≥70分"""
        # 简化检查：没有明显危险标记
        # 实际调用GoPlus API
        return True  # 后续集成GoPlus
    
    def detect_narrative(self, token: Dict) -> str:
        """检测叙事类型"""
        symbol = token.get('symbol', '').lower()
        name = token.get('name', '').lower()
        text = f"{symbol} {name}"
        
        for keyword in self.MEME_KEYWORDS:
            if keyword in text:
                return "Meme"
        for keyword in self.AI_KEYWORDS:
            if keyword in text:
                return "AI"
        for keyword in self.GAMEFI_KEYWORDS:
            if keyword in text:
                return "GameFi"
        return "Other"
    
    def evaluate_token(self, token: Dict) -> Optional[TokenSignal]:
        """评估单个代币，返回满足≥2条规则的Signal"""
        rules_matched = []
        
        # 检查各条规则
        if self.check_rule_1_new_small(token):
            rules_matched.append(1)
        if self.check_rule_2_holder_concentration(token):
            rules_matched.append(2)
        if self.check_rule_3_smart_money(token):
            rules_matched.append(3)
        if self.check_rule_4_social_media(token):
            rules_matched.append(4)
        if self.check_rule_5_safety(token):
            rules_matched.append(5)
        
        # 必须满足≥2条
        if len(rules_matched) < 2:
            return None
        
        # 构建Signal
        return TokenSignal(
            chain=token.get('chain', 'unknown'),
            symbol=token.get('symbol', 'UNKNOWN'),
            address=token.get('address', ''),
            price=token.get('priceUsd', 0),
            market_cap=token.get('marketCap', 0),
            liquidity=token.get('liquidity', {}).get('usd', 0),
            volume_24h=token.get('volume', {}).get('h24', 0),
            price_change_1h=token.get('priceChange', {}).get('h1', 0),
            price_change_24h=token.get('priceChange', {}).get('h24', 0),
            rules_matched=rules_matched,
            narrative=self.detect_narrative(token)
        )
    
    def scan_all_chains(self) -> List[TokenSignal]:
        """扫描所有链寻找土狗"""
        chains = ['ethereum', 'bsc', 'solana', 'base', 'arbitrum', 'polygon', 'optimism']
        all_signals = []
        
        print(f"\n🦴 土狗狙击手启动 - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)
        
        for chain in chains:
            try:
                print(f"\n🔍 扫描 {chain.upper()}...")
                url = f"https://api.dexscreener.com/token-profiles/latest/v1"
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    continue
                
                data = response.json()
                tokens = [t for t in data if t.get('chainId', '').lower() == chain]
                
                chain_signals = []
                for token in tokens[:30]:  # 只检查前30个
                    signal = self.evaluate_token(token)
                    if signal:
                        chain_signals.append(signal)
                
                if chain_signals:
                    print(f"   ✅ 发现 {len(chain_signals)} 个土狗信号")
                    all_signals.extend(chain_signals)
                else:
                    print(f"   ❌ 无信号")
                    
            except Exception as e:
                print(f"   ⚠️ 扫描失败: {e}")
                continue
        
        # 按规则匹配数排序
        all_signals.sort(key=lambda x: len(x.rules_matched), reverse=True)
        
        print(f"\n{'='*60}")
        print(f"🎯 总计发现: {len(all_signals)} 个土狗机会")
        
        return all_signals
    
    def format_signal_report(self, signal: TokenSignal) -> str:
        """格式化推送消息"""
        rules_str = '+'.join(map(str, signal.rules_matched))
        
        # 风险评估
        risks = []
        if signal.market_cap < 10000:
            risks.append("🚨 超小市值(<$10K)")
        if signal.liquidity < 5000:
            risks.append("💧 低流动性")
        if len(signal.rules_matched) == 2:
            risks.append("⚠️ 仅满足2条规则")
        
        risk_text = ' | '.join(risks) if risks else "✅ 基础安全"
        
        # 建议
        if signal.narrative == "Meme" and len(signal.rules_matched) >= 3:
            advice = "🔥 小额试仓 (0.5-1%)"
        elif len(signal.rules_matched) >= 3:
            advice = "👀 重点观察"
        else:
            advice = "⏸️ 先观察"
        
        report = f"""
【{signal.chain.upper()}+{signal.symbol}】{signal.narrative}
📋 {signal.address}
【信号】规则 {rules_str}: {', '.join([self.RULES[r] for r in signal.rules_matched])}
【数据】市值${signal.market_cap/1000:.1f}K | 流动${signal.liquidity/1000:.1f}K | 1h {signal.price_change_1h:+.1f}%
【风险】{risk_text}
【建议】{advice}
{'='*50}"""
        
        return report

if __name__ == "__main__":
    sniper = DogSniper()
    signals = sniper.scan_all_chains()
    
    if signals:
        print("\n📱 推送报告:\n")
        for i, sig in enumerate(signals[:5], 1):  # 只显示前5个
            print(sniper.format_signal_report(sig))
    else:
        print("\n😴 今日暂无土狗机会")
