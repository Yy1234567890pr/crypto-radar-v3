#!/usr/bin/env python3
"""
鲸鱼追踪器 - 监控大户钱包转账
基于Moralis API，识别交易所流入/流出信号
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional
import aiohttp
from dataclasses import dataclass, asdict

DEFAULT_API_KEY = None  # 从环境变量获取

# 鲸鱼阈值配置（美元）
WHALE_THRESHOLDS = {
    'ETH': 50000,      # ETH链 5万刀以上
    'BSC': 30000,      # BSC链 3万刀以上
    'SOL': 30000,      # SOL链 3万刀以上
    'BASE': 20000,     # Base链 2万刀以上
    'ARBITRUM': 20000, # Arb链 2万刀以上
    'POLYGON': 15000,  # Polygon 1.5万刀以上
    'OPTIMISM': 15000, # Op链 1.5万刀以上
}

# 已知大鲸地址库
KNOWN_WHALES = {
    # 以太坊大鲸
    '0x0716a17fbaee714f1e6ab0f9d59edbdbc815bb72': {'name': 'SmartMoney_01', 'type': '早期猎手'},
    '0x8ba1f109551bd432803012645ac136ddd64dba72': {'name': 'SmartMoney_02', 'type': 'DeFi巨鲸'},
    # 可扩展...
}

# 交易所地址库
EXCHANGES = {
    'binance': [
        '0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE',
        '0xdccF3B592E27E5e9460E900D916E132F86194dE2',
    ],
    'coinbase': [
        '0x71660c4005ba85c37ccec55d0c4493e66fe775d3',
    ],
    'kraken': [
        '0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0',
    ],
}

@dataclass
class WhaleSignal:
    timestamp: str
    chain: str
    tx_hash: str
    from_addr: str
    to_addr: str
    amount_usd: float
    token_symbol: str
    signal_type: str  # 'whale_buy', 'whale_sell', 'exchange_in', 'exchange_out'
    whale_name: Optional[str] = None
    notes: str = ""
    
    def to_dict(self):
        return asdict(self)


class WhaleTracker:
    """鲸鱼追踪器"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or DEFAULT_API_KEY
        self.seen_hashes = set()
        self.signals_cache: List[WhaleSignal] = []
        
    async def get_whale_transactions(self, chain: str, hours: int = 1) -> List[Dict]:
        """获取大额转账交易"""
        if not self.api_key:
            return []  # 没有API key返回空
            
        threshold = WHALE_THRESHOLDS.get(chain.upper(), 50000)
        
        # Moralis API端点
        url = f"https://deep-index.moralis.io/api/v2.2/wallets/top-addresses"
        
        headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json"
        }
        
        # 简化版：直接返回模拟数据（实际需接入Moralis）
        return []
    
    def check_exchange_flow(self, from_addr: str, to_addr: str) -> Optional[str]:
        """检查交易所流向
        Returns: 'exchange_out'(提出=看涨), 'exchange_in'(存入=看跌), None
        """
        from_lower = from_addr.lower()
        to_lower = to_addr.lower()
        
        # 检查是否从交易所提出
        for name, addrs in EXCHANGES.items():
            if any(a.lower() == from_lower for a in addrs):
                return 'exchange_out'  # 从交易所提出 = 看涨
            if any(a.lower() == to_lower for a in addrs):
                return 'exchange_in'   # 存入交易所 = 看跌
        
        return None
    
    def check_known_whale(self, addr: str) -> Optional[str]:
        """检查是否是已知大鲸"""
        info = KNOWN_WHALES.get(addr.lower())
        if info:
            return f"{info['name']} ({info['type']})"
        return None
    
    def analyze_transaction(self, tx: Dict, chain: str) -> Optional[WhaleSignal]:
        """分析单笔交易"""
        tx_hash = tx.get('hash', '')
        
        # 去重
        if tx_hash in self.seen_hashes:
            return None
        self.seen_hashes.add(tx_hash)
        
        # 基础信息
        from_addr = tx.get('from_address', '')
        to_addr = tx.get('to_address', '')
        value = float(tx.get('value', 0)) / 1e18  # ETH精度
        
        # 获取价格估算USD
        # 实际应用Moralis获取实时价格
        amount_usd = value * 2000  # 简化假设ETH=$2000
        
        threshold = WHALE_THRESHOLDS.get(chain.upper(), 50000)
        if amount_usd < threshold:
            return None
        
        # 判断信号类型
        signal_type = 'whale_unknown'
        whale_name = None
        notes = []
        
        # 检查交易所流向
        flow = self.check_exchange_flow(from_addr, to_addr)
        if flow:
            signal_type = flow
            if flow == 'exchange_out':
                notes.append("🔥 交易所吸筹信号 - 大户提币")
            else:
                notes.append("⚠️ 交易所抛压信号 - 大户存币")
        
        # 检查已知大鲸
        whale_from = self.check_known_whale(from_addr)
        whale_to = self.check_known_whale(to_addr)
        
        if whale_from:
            whale_name = whale_from
            signal_type = 'whale_sell'
        elif whale_to:
            whale_name = whale_to
            signal_type = 'whale_buy'
        
        # 构建信号
        signal = WhaleSignal(
            timestamp=datetime.now().isoformat(),
            chain=chain,
            tx_hash=tx_hash,
            from_addr=from_addr,
            to_addr=to_addr,
            amount_usd=amount_usd,
            token_symbol='ETH',
            signal_type=signal_type,
            whale_name=whale_name,
            notes='; '.join(notes)
        )
        
        return signal
    
    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """获取最近信号"""
        return [s.to_dict() for s in self.signals_cache[-limit:]]
    
    def format_alert(self, signal: WhaleSignal) -> str:
        """格式化警报消息"""
        emoji_map = {
            'whale_buy': '🐋 大鲸买入',
            'whale_sell': '🐋 大鲸卖出',
            'exchange_out': '🔥 交易所流出',
            'exchange_in': '⚠️ 交易所流入',
            'whale_unknown': '🐋 鲸鱼转账'
        }
        
        title = emoji_map.get(signal.signal_type, '🐋 鲸鱼信号')
        
        msg = f"""
{title}

链: {signal.chain.upper()}
金额: ${signal.amount_usd:,.0f}
代币: {signal.token_symbol}

From: {signal.from_addr[:20]}...
To: {signal.to_addr[:20]}...

{signal.notes}

Tx: {signal.tx_hash[:30]}...
Time: {signal.timestamp}
"""
        return msg


# 简单的独立运行测试
if __name__ == "__main__":
    print("🐋 鲸鱼追踪器测试")
    print("=" * 50)
    
    tracker = WhaleTracker()
    
    # 模拟测试交易
    test_tx = {
        'hash': '0x1234567890abcdef',
        'from_address': '0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE',  # Binance地址
        'to_address': '0x8ba1f109551bd432803012645ac136ddd64dba72',   # 未知地址
        'value': 25000000000000000000  # 25 ETH
    }
    
    signal = tracker.analyze_transaction(test_tx, 'ETH')
    if signal:
        print(f"✅ 检测到信号: {signal.signal_type}")
        print(f"金额: ${signal.amount_usd:,.0f}")
        print(f"类型: {signal.notes}")
    else:
        print("❌ 无信号")
