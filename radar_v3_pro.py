#!/usr/bin/env python3
"""链上雷达 v3 - 主系统集成版
特点：稳定、快速、高质量
"""

import sys
sys.path.insert(0, '/home/ubuntu/crypto-auto-trader')

import asyncio
import aiohttp
import sqlite3
import json
import time
from datetime import datetime
from typing import List, Dict

# 导入主系统模块
from scanners.multi_chain_scanner import MultiChainScanner
from scanners.safety_checker import SafetyChecker

# 配置
DATA_DIR = "/home/ubuntu/crypto-radar-v3"
DB_FILE = f"{DATA_DIR}/radar_v3.db"

# 筛选参数（土狗早鸟模式 - 简化版，主系统数据结构有限）
MIN_MARKET_CAP = 5000       # $5K（主系统很多币缺少市值数据）
MAX_MARKET_CAP = 5000000    # $5M（排除太大市值）
MIN_LIQUIDITY = 2000        # $2K
MIN_VOLUME_24H = 10000      # $10K
MIN_PRICE_CHANGE_24H = 0    # 24h必须为正（至少不涨）
SAFETY_MIN_SCORE = 60       # 安全分≥60（基础安全）

class RadarV3:
    def __init__(self):
        self.scanner = MultiChainScanner()
        self.safety = SafetyChecker()
        self.init_db()
        
    def init_db(self):
        """初始化数据库"""
        import os
        os.makedirs(DATA_DIR, exist_ok=True)
        
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS radar_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT,
                chain TEXT,
                symbol TEXT,
                name TEXT,
                market_cap REAL,
                liquidity REAL,
                volume_24h REAL,
                holders INTEGER,
                change_1h REAL,
                safety_score INTEGER,
                is_honeypot BOOLEAN,
                buy_tax REAL,
                sell_tax REAL,
                smart_money_count INTEGER,
                signal_type TEXT,
                detected_at INTEGER
            )''')
            conn.commit()
            
    def scan_with_quality_filter(self) -> List[Dict]:
        """扫描并应用高质量筛选"""
        print(f"\n[🔄] 开始扫描 {datetime.now().strftime('%H:%M:%S')}")
        
        tokens = self.scanner.scan_all_chains(limit_per_chain=20)
        print(f"   原始获取: {len(tokens)} 个币")
        
        # 多层过滤（基于主系统数据结构）
        filtered = []
        for t in tokens:
            # 层1: 基础门槛
            mc = t.get('market_cap', 0)
            # 市值=0表示是主链代币（如ETH），这些不是土狗
            if mc == 0 or mc < MIN_MARKET_CAP:
                continue
            if mc > MAX_MARKET_CAP:
                continue
                
            liq = t.get('liquidity', 0)
            if liq < MIN_LIQUIDITY:
                continue
                
            vol = t.get('volume_24h', 0)
            if vol < MIN_VOLUME_24H:
                continue
                
            # 层2: 价格动量
            change = t.get('price_change_24h', -999)
            if change < MIN_PRICE_CHANGE_24H:
                continue
                
            # 层3: 安全检查
            safety = t.get('safety_score', 0)
            if safety < SAFETY_MIN_SCORE:
                continue
                
            # 层4: 排除已知主流代币
            symbol = t.get('symbol', '').upper()
            main_coins = {'ETH', 'BTC', 'SOL', 'BNB', 'ARB', 'OP', 'MATIC', 'AVAX', 'FTM'}
            if symbol in main_coins:
                continue
                
            filtered.append(t)
            
        print(f"   过滤后: {len(filtered)} 个币 (通过率 {len(filtered)/len(tokens)*100:.1f}%)")
        return filtered
        
    def check_safety_batch(self, tokens: List[Dict]) -> List[Dict]:
        """批量安全检测"""
        safe_tokens = []
        
        for t in tokens[:10]:  # 只检查前10个最有希望的
            try:
                safety = self.safety.check_token_safety(t['address'], t['chain'])
                
                # 过滤非常危险的
                if safety.get('is_honeypot', False):
                    continue
                if safety.get('safety_score', 0) < 60:
                    continue
                if safety.get('buy_tax', 0) > 10 or safety.get('sell_tax', 0) > 10:
                    continue
                    
                t['safety'] = safety
                safe_tokens.append(t)
                
            except Exception as e:
                continue
                
        print(f"   安全通过: {len(safe_tokens)} 个币")
        return safe_tokens
        
    def save_signals(self, tokens: List[Dict]):
        """保存信号到数据库"""
        now = int(time.time())
        
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            for t in tokens:
                safety = t.get('safety', {})
                c.execute('''INSERT INTO radar_signals 
                    (address, chain, symbol, name, market_cap, liquidity, volume_24h,
                     holders, change_1h, safety_score, is_honeypot, buy_tax, sell_tax,
                     smart_money_count, signal_type, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (t['address'], t['chain'], t['symbol'], t['name'],
                     t.get('market_cap', 0), t.get('liquidity', 0),
                     t.get('volume_24h', 0), t.get('holder_count', 0),
                     t.get('price_change_1h', 0),
                     safety.get('safety_score', 0),
                     safety.get('is_honeypot', False),
                     safety.get('buy_tax', 0),
                     safety.get('sell_tax', 0),
                     t.get('smart_degen_count', 0),
                     'momentum', now))
            conn.commit()
            
    def generate_report(self, tokens: List[Dict]) -> str:
        """生成报告"""
        if not tokens:
            return "⚠️ 本轮未发现高质量信号"
            
        report = f"""
🚀 **v3雷达报告** | {datetime.now().strftime('%H:%M')}

**筛选条件**:
• 市值 ${MIN_MARKET_CAP/1000:.0f}K-${MAX_MARKET_CAP/1000000:.0f}M | 流动性≥${MIN_LIQUIDITY/1000:.0f}K
• 24h成交≥${MIN_VOLUME_24H/1000:.0f}K | 价格涨幅≥0%
• 安全分≥{SAFETY_MIN_SCORE}

**发现 {len(tokens)} 个高质量信号**:
"""
        for i, t in enumerate(tokens[:5], 1):
            safety = t.get('safety', {})
            score = safety.get('safety_score', 0)
            mc = t.get('market_cap', 0)
            mc_str = f"${mc/1000:.1f}K" if mc < 1000000 else f"${mc/1000000:.2f}M"
            
            report += f"""
{i}. **{t['symbol']}** ({t['chain'].upper()})
   市值: {mc_str} | 安全分: {score}/100
   `
{t['address'][:20]}...`
"""
        return report
        
    def run(self):
        """运行一次扫描"""
        print("="*60)
        print("🚀 链上雷达 v3 - 高质量版")
        print("="*60)
        
        # 1. 扫描+过滤
        tokens = self.scan_with_quality_filter()
        
        if not tokens:
            print("   ⚠️ 没有通过基础筛选的币")
            return []
            
        # 2. 安全检测
        safe_tokens = self.check_safety_batch(tokens)
        
        # 3. 保存
        self.save_signals(safe_tokens)
        
        # 4. 生成报告
        report = self.generate_report(safe_tokens)
        print(f"\n{report}")
        
        return safe_tokens

if __name__ == '__main__':
    radar = RadarV3()
    radar.run()
