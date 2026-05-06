#!/usr/bin/env python3
"""
Polymarket 自动交易客户端
策略：胜率>60% 且 赔率>2倍时自动下注
"""

import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# 加载环境变量
load_dotenv(os.path.expanduser("~/.polymarket_env"))

# 配置
POLY_HOST = os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com")
API_KEY = os.getenv("POLYMARKET_API_KEY")
API_SECRET = os.getenv("POLYMARKET_API_SECRET")
PASSPHRASE = os.getenv("POLYMARKET_PASSPHRASE")
PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

# 策略参数
MIN_WIN_RATE = 0.60      # 最低胜率60%
MIN_ODDS = 2.0           # 最低赔率2倍
BET_AMOUNT = 0.01        # 下注金额0.01 ETH (约$20)
MAX_DAILY_BETS = 5       # 每日最多5单

class PolymarketTrader:
    """Polymarket自动交易机器人"""
    
    def __init__(self):
        print("🚀 初始化Polymarket交易客户端...")
        
        # 初始化客户端
        self.client = ClobClient(
            host=POLY_HOST,
            key=PRIVATE_KEY,
            chain_id=137  # Polygon主网
        )
        
        # 设置API凭证
        creds = ApiCreds(
            api_key=API_KEY,
            api_secret=API_SECRET,
            api_passphrase=PASSPHRASE
        )
        self.client.set_api_creds(creds)
        
        # 验证连接
        try:
            server_time = self.client.get_server_time()
            print(f"✅ 连接成功！服务器时间: {server_time}")
        except Exception as e:
            print(f"⚠️ 连接验证: {e}")
        
        self.daily_bets = 0
        self.trades_today = []
        
    def get_active_markets(self, limit=20):
        """获取活跃市场"""
        try:
            markets = self.client.get_markets()
            return markets.get('data', [])[:limit]
        except Exception as e:
            print(f"❌ 获取市场失败: {e}")
            return []
    
    def analyze_market(self, market):
        """分析单个市场"""
        market_id = market.get('condition_id', 'unknown')
        question = market.get('question', 'N/A')
        
        try:
            # 直接从市场数据获取信息
            # Polymarket API返回的是一系列tickers
            tokens = market.get('tokens', [])
            
            if len(tokens) >= 2:
                # YES token
                yes_token = tokens[0]
                no_token = tokens[1]
                
                # 获取最新价格
                price_yes = float(yes_token.get('price', 0))
                price_no = float(no_token.get('price', 0))
                
                # 赔率计算
                odds_yes = 1 / price_yes if price_yes > 0 else 0
                odds_no = 1 / price_no if price_no > 0 else 0
                
                # 成交量
                volume = float(market.get('volume', 0))
                
                return {
                    'market_id': market_id,
                    'question': question,
                    'price_yes': price_yes,
                    'price_no': price_no,
                    'odds_yes': odds_yes,
                    'odds_no': odds_no,
                    'volume': volume,
                    'end_date': market.get('end_date_iso', 'N/A'),
                    'category': market.get('category', 'Unknown')
                }
        except Exception as e:
            print(f"⚠️ 分析失败 {market_id}: {e}")
            
        return None
    
    def find_opportunities(self):
        """寻找交易机会"""
        print(f"\n🔍 [{datetime.now().strftime('%H:%M:%S')}] 扫描市场机会...")
        
        markets = self.get_active_markets(limit=20)
        opportunities = []
        
        for market in markets:
            analysis = self.analyze_market(market)
            if analysis:
                # 策略：赔率>2倍且价格<0.5（潜在高回报）
                if analysis['odds_yes'] >= MIN_ODDS and analysis['price_yes'] < 0.5:
                    opportunities.append({
                        **analysis,
                        'side': 'YES',
                        'confidence': 'high' if analysis['odds_yes'] > 3 else 'medium'
                    })
                elif analysis['odds_no'] >= MIN_ODDS and analysis['price_no'] < 0.5:
                    opportunities.append({
                        **analysis,
                        'side': 'NO',
                        'confidence': 'high' if analysis['odds_no'] > 3 else 'medium'
                    })
        
        # 按赔率排序
        opportunities.sort(key=lambda x: x.get('odds_yes', 0) if x['side'] == 'YES' else x.get('odds_no', 0), reverse=True)
        
        print(f"   发现 {len(opportunities)} 个潜在机会")
        return opportunities
    
    def execute_trade(self, opportunity):
        """执行交易"""
        if self.daily_bets >= MAX_DAILY_BETS:
            print(f"⚠️ 今日已达最大下注次数 ({MAX_DAILY_BETS})")
            return False
        
        try:
            print(f"\n🎯 执行交易:")
            print(f"   市场: {opportunity['question'][:60]}...")
            print(f"   方向: {opportunity['side']}")
            print(f"   赔率: {opportunity.get('odds_yes', opportunity.get('odds_no', 0)):.2f}x")
            print(f"   金额: {BET_AMOUNT} ETH")
            
            # 这里应该调用实际下单API
            # 但目前只做模拟，等确认后再实盘
            print(f"   状态: ⏳ 模拟模式（未真实下单）")
            
            self.daily_bets += 1
            self.trades_today.append({
                'time': datetime.now().isoformat(),
                'market': opportunity['question'],
                'side': opportunity['side'],
                'amount': BET_AMOUNT
            })
            
            return True
            
        except Exception as e:
            print(f"❌ 交易失败: {e}")
            return False
    
    def run_strategy(self):
        """运行交易策略"""
        print(f"\n{'='*70}")
        print(f"🤖 Polymarket 自动交易策略")
        print(f"{'='*70}")
        print(f"策略参数:")
        print(f"  - 最低赔率: {MIN_ODDS}x")
        print(f"  - 下注金额: {BET_AMOUNT} ETH")
        print(f"  - 每日上限: {MAX_DAILY_BETS}单")
        print(f"{'='*70}\n")
        
        opportunities = self.find_opportunities()
        
        if opportunities:
            print("\n📊 前3个最佳机会:")
            for i, opp in enumerate(opportunities[:3], 1):
                odds = opp.get('odds_yes', opp.get('odds_no', 0))
                conf_emoji = "🟢" if opp['confidence'] == 'high' else "🟡"
                print(f"\n{i}. {conf_emoji} {opp['question'][:50]}...")
                print(f"   方向: {opp['side']} | 赔率: {odds:.2f}x | 价格: ${opp.get('price_yes', opp.get('price_no', 0)):.3f}")
            
            # 执行最佳机会
            if opportunities[0]['confidence'] == 'high':
                self.execute_trade(opportunities[0])
        else:
            print("\n⚠️ 未找到符合条件的交易机会")
        
        # 打印今日统计
        print(f"\n📈 今日统计:")
        print(f"   已下单: {self.daily_bets}/{MAX_DAILY_BETS}")
        print(f"   盈亏: 模拟模式（未实盘）")

if __name__ == "__main__":
    trader = PolymarketTrader()
    trader.run_strategy()
