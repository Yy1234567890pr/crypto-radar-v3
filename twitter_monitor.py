#!/usr/bin/env python3
"""
Twitter KOL 监控系统
监控20个指定账号，检测"新币"/"金狗"等关键词
结合链上雷达验证
"""

import os
import re
import time
import json
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode

# 监控配置
TARGET_ACCOUNTS = [
    "VitalikButerin", "cz_binance", "aantonop", "saylor", "RaoulGMI",
    "100trillionUSD", "awasunyin", "Capybara_BTC", "Bitcoin", "MicroStrategy",
    "ethereum", "solana", "BNBCHAIN", "OpenAI", "GoogleDeepmind",
    "a16zcrypto", "Filecoin", "Helium", "unisat_wallet", "L1Fxyz",
    "Lookonchain", "ArkhamIntel"
]

KEYWORDS = [
    # 核心金狗词
    "新币", "金狗", "老狗", "土狗", "龙头", "搞了", "梭哈", "冲了",
    "大金狗", "金狗王", "狗王", "神狗", "天狗", "妖币", "妖狗",
    
    # 倍数空间词 - 十倍百倍目标！
    "十倍", "十倍币", "10x", "10倍",
    "百倍", "百倍币", "100x", "100倍", 
    "千倍", "千倍币", "1000x", "1000倍",
    "万倍", "万倍币", "10000x",
    "to the moon", "moonshot", "rocket", "pump",
    
    # 英文核心词
    "new token", "new coin", "gem", "shitcoin", "memecoin", 
    "alpha", "launching", "fair launch", "stealth launch",
    "just launched", "early", "presale", "whitelist",
    
    # 中文操作词
    "上币", "发币", "开盘", "开盘即冲", "新盘", "打新",
    "上车", "下车", "抄底", "逃顶", "埋伏", "重仓",
    
    # 合约/技术信号
    "CA:", "contract address", "0x...", 
    "buy now", "aped", "degen", "ape in", 
    "liquidity locked", "ownership renounced", "audit"
]

# 排除词（降低误报）
EXCLUDE_WORDS = [
    "bitcoin at $", "btc at $", "price $", "$btc", "$eth",  # 价格讨论
    "gpt-", "gemini", "google io", "main stage",             # AI活动
    "model", "closed", "february", "week",                  # 普通词汇
    "carrier", "packets", "edition", "trading campaign"     # Helium等
]

MONITOR_INTERVAL = 300  # 5分钟检查一次

class TwitterMonitor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.known_tweets = set()
        self.signals_log = []
        
    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")
        
    def fetch_nitter_feed(self, username):
        """通过Nitter获取推文 (Twitter镜像站)"""
        nitter_instances = [
            "https://nitter.net",
            "https://nitter.it", 
            "https://nitter.cz"
        ]
        
        for instance in nitter_instances:
            try:
                url = f"{instance}/{username}/rss"
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200:
                    return self.parse_rss(resp.text, username)
            except Exception as e:
                continue
        return []
    
    def parse_rss(self, xml_content, username):
        """解析RSS获取推文"""
        import xml.etree.ElementTree as ET
        
        tweets = []
        try:
            root = ET.fromstring(xml_content)
            items = root.findall('.//item')
            
            for item in items[:5]:  # 只省最近5条
                title = item.find('title')
                pub_date = item.find('pubDate')
                link = item.find('link')
                
                if title is not None:
                    tweet_text = title.text or ""
                    tweet_time = pub_date.text if pub_date is not None else ""
                    tweet_link = link.text if link is not None else ""
                    
                    tweets.append({
                        'username': username,
                        'text': tweet_text,
                        'time': tweet_time,
                        'link': tweet_link
                    })
        except Exception as e:
            pass
            
        return tweets
    
    def check_keywords(self, text):
        """检测关键词"""
        text_lower = text.lower()
        found_keywords = []
        
        # 先检查排除词
        for exclude in EXCLUDE_WORDS:
            if exclude.lower() in text_lower:
                return {'is_signal': False, 'reason': 'excluded'}
        
        # 检测关键词
        for kw in KEYWORDS:
            if kw.lower() in text_lower or kw in text:
                found_keywords.append(kw)
                
        # 检测代币符号 $XXX (排除单纯价格如$67k)
        ticker_pattern = r'\$([A-Za-z]{2,10})'
        tickers = re.findall(ticker_pattern, text)
        # 过滤掉纯数字/价格类的符号
        tickers = [t for t in tickers if not t.replace('k','').replace('m','').isdigit()]
        
        # 检测合约地址 0x...
        contract_pattern = r'0x[a-fA-F0-9]{40}'
        contracts = re.findall(contract_pattern, text)
        
        return {
            'keywords': found_keywords,
            'tickers': tickers,
            'contracts': contracts,
            'is_signal': len(found_keywords) > 0 or len(tickers) > 0 or len(contracts) > 0
        }
    
    def scan_accounts(self):
        """扫描所有账号"""
        self.log(f"\n📡 开始扫描 {len(TARGET_ACCOUNTS)} 个KOL账号...")
        
        all_signals = []
        
        for username in TARGET_ACCOUNTS:
            try:
                tweets = self.fetch_nitter_feed(username)
                
                for tweet in tweets:
                    tweet_id = f"{username}:{tweet['text'][:50]}"
                    
                    if tweet_id in self.known_tweets:
                        continue
                    self.known_tweets.add(tweet_id)
                    
                    analysis = self.check_keywords(tweet['text'])
                    
                    if analysis['is_signal']:
                        signal = {
                            'time': datetime.now().isoformat(),
                            'username': username,
                            'text': tweet['text'][:200],
                            'keywords': analysis['keywords'],
                            'tickers': analysis['tickers'],
                            'contracts': analysis['contracts'],
                            'link': tweet['link']
                        }
                        all_signals.append(signal)
                        
            except Exception as e:
                self.log(f"  ⚠️ {username}: 获取失败")
                continue
                
        return all_signals
    
    def print_signals(self, signals):
        """输出信号"""
        if not signals:
            self.log("未发现新信号")
            return
            
        self.log(f"\n🚨 发现 {len(signals)} 个潜在信号!")
        
        for i, sig in enumerate(signals, 1):
            emoji = "🔥" if sig['contracts'] else "⭐"
            self.log(f"\n{i}. {emoji} @{sig['username']}")
            self.log(f"   内容: {sig['text'][:80]}...")
            if sig['keywords']:
                self.log(f"   关键词: {', '.join(sig['keywords'])}")
            if sig['tickers']:
                self.log(f"   代币: {', '.join(['$'+t for t in sig['tickers']])}")
            if sig['contracts']:
                self.log(f"   ⚠️ 合约: {sig['contracts'][0][:20]}...")
            self.log(f"   链接: {sig['link']}")
            
    def run(self):
        """主循环"""
        self.log("🚀 Twitter KOL监控启动")
        self.log(f"   监控账号: {len(TARGET_ACCOUNTS)}个")
        self.log(f"   关键词: {', '.join(KEYWORDS[:5])}...")
        self.log(f"   检查间隔: {MONITOR_INTERVAL//60}分钟")
        
        # 首次运行，先获取现有推文不触发
        self.log("\n🔄 初始化: 获取现有推文...")
        for username in TARGET_ACCOUNTS[:5]:  # 先初始化前5个
            try:
                tweets = self.fetch_nitter_feed(username)
                for tweet in tweets:
                    tweet_id = f"{username}:{tweet['text'][:50]}"
                    self.known_tweets.add(tweet_id)
            except:
                pass
        self.log(f"   已缓存 {len(self.known_tweets)} 条历史推文")
        
        # 主循环
        while True:
            signals = self.scan_accounts()
            self.print_signals(signals)
            
            if signals:
                self.signals_log.extend(signals)
                # 保存到文件
                with open('/home/ubuntu/crypto-radar-v3/twitter_signals.json', 'w') as f:
                    json.dump(self.signals_log[-50:], f, indent=2)  # 只保存最近50条
                    
            self.log(f"\n✅ 本轮完成，{MONITOR_INTERVAL//60}分钟后下一轮...")
            time.sleep(MONITOR_INTERVAL)

if __name__ == "__main__":
    monitor = TwitterMonitor()
    monitor.run()
