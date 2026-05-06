#!/usr/bin/env python3
"""
Polymarket 后台监控Daemon
每5分钟扫描一次，发现高赔率机会自动通知
"""

import os
import sys
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# 加载环境变量
load_dotenv(os.path.expanduser("~/.polymarket_env"))

POLY_HOST = os.getenv("POLYMARKET_HOST", "https://clob.polob.market")
API_KEY = os.getenv("POLYMARKET_API_KEY")
API_SECRET = os.getenv("POLYMARKET_API_SECRET")
PASSPHRASE = os.getenv("POLYMARKET_PASSPHRASE")
PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

# 策略参数
MIN_ODDS_HIGH = 3.0      # 高赔率阈值
MIN_ODDS_MED = 2.0       # 中等赔率
SCAN_INTERVAL = 300      # 5分钟扫一次

class PolymarketDaemon:
    def __init__(self):
        self.client = ClobClient(
            host=POLY_HOST,
            key=PRIVATE_KEY,
            chain_id=137
        )
        creds = ApiCreds(
            api_key=API_KEY,
            api_secret=API_SECRET,
            api_passphrase=PASSPHRASE
        )
        self.client.set_api_creds(creds)
        self.round = 0
        self.high_value_signals = []
        
    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")
        sys.stdout.flush()
        
    def scan_markets(self):
        """扫描市场"""
        try:
            markets_data = self.client.get_markets()
            markets = markets_data.get('data', [])
            
            opportunities = []
            for market in markets[:30]:  # 检查前30个市场
                tokens = market.get('tokens', [])
                if len(tokens) >= 2:
                    price_yes = float(tokens[0].get('price', 0))
                    price_no = float(tokens[1].get('price', 0))
                    
                    odds_yes = 1 / price_yes if price_yes > 0 else 0
                    odds_no = 1 / price_no if price_no > 0 else 0
                    
                    question = market.get('question', '')
                    volume = float(market.get('volume', 0))
                    
                    # 高赔率机会
                    if odds_yes >= MIN_ODDS_HIGH and price_yes < 0.4:
                        opportunities.append({
                            'question': question,
                            'side': 'YES',
                            'odds': odds_yes,
                            'price': price_yes,
                            'volume': volume,
                            'level': 'high' if odds_yes > 5 else 'medium'
                        })
                    elif odds_no >= MIN_ODDS_HIGH and price_no < 0.4:
                        opportunities.append({
                            'question': question,
                            'side': 'NO',
                            'odds': odds_no,
                            'price': price_no,
                            'volume': volume,
                            'level': 'high' if odds_no > 5 else 'medium'
                        })
            
            return sorted(opportunities, key=lambda x: x['odds'], reverse=True)
            
        except Exception as e:
            self.log(f"❌ 扫描失败: {e}")
            return []
    
    def run(self):
        self.log("🚀 Polymarket Daemon 启动")
        self.log(f"   扫描间隔: {SCAN_INTERVAL//60}分钟")
        self.log(f"   高赔率阈值: {MIN_ODDS_HIGH}x")
        
        while True:
            self.round += 1
            self.log(f"\n📡 第{self.round}轮扫描开始...")
            
            ops = self.scan_markets()
            
            if ops:
                high_count = sum(1 for o in ops if o['level'] == 'high')
                self.log(f"✅ 发现 {len(ops)} 个机会 (高价值: {high_count})")
                
                # 输出最佳机会
                for i, op in enumerate(ops[:3], 1):
                    emoji = "🔥" if op['level'] == 'high' else "⭐"
                    self.log(f"   {emoji} {op['question'][:50]}...")
                    self.log(f"      {op['side']} | {op['odds']:.1f}x | 成交${op['volume']:,.0f}")
                
                if high_count > 0:
                    self.log(f"\n🎯 **高赔率信号检测到** - 建议关注！")
            else:
                self.log("⚠️ 未发现符合条件的机会")
            
            self.log(f"✅ 第{self.round}轮完成")
            time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    daemon = PolymarketDaemon()
    daemon.run()
