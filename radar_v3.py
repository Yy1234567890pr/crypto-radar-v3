#!/usr/bin/env python3
"""
链上监控雷达 v3 - 极速版
核心优化：并发请求 + 智能重试 + 双数据源 + 连接池
"""

import asyncio
import aiohttp
import sqlite3
import json
import time
import os
import re
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from functools import lru_cache
import logging

# === 配置 ===
DATA_DIR = os.path.expanduser("~/crypto-radar-v3")
DB_FILE = os.path.join(DATA_DIR, "radar_v3.db")
LOG_FILE = os.path.join(DATA_DIR, "radar_v3.log")

os.makedirs(DATA_DIR, exist_ok=True)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === 核心参数 ===
MIN_SMART_DEGEN = 3
MIN_MARKET_CAP = 5000
MIN_LIQUIDITY = 2000
MAX_MARKET_CAP = 10000000
SCAN_INTERVAL = 30

# 并发配置
MAX_CONCURRENT = 4
REQUEST_TIMEOUT = 3  # 3秒超时
MAX_RETRIES = 3
RETRY_DELAYS = [0.5, 1.0, 2.0]  # 指数退避

# GMGN API端点
GMGN_ENDPOINTS = {
    'sol': 'https://gmgn.ai/defi/quotation/v1/tokens/sol/new_tokens',
    'eth': 'https://gmgn.ai/defi/quotation/v1/tokens/eth/new_tokens',
    'bsc': 'https://gmgn.ai/defi/quotation/v1/tokens/bsc/new_tokens',
    'base': 'https://gmgn.ai/defi/quotation/v1/tokens/base/new_tokens',
}

# DexScreener API端点 (更可靠的token和pair端点)
DS_ENDPOINTS = {
    'sol': 'https://api.dexscreener.com/token-pairs/v1/solana',
    'eth': 'https://api.dexscreener.com/latest/dex/tokens',
    'bsc': 'https://api.dexscreener.com/latest/dex/tokens',
    'base': 'https://api.dexscreener.com/latest/dex/tokens',
}

# DexScreener扫描热门pair
DS_TOP_PAIRS = {
    'sol': 'https://api.dexscreener.com/token-profiles/latest/v1',
    'eth': 'https://api.dexscreener.com/token-profiles/latest/v1', 
}

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://gmgn.ai/',
    'Connection': 'keep-alive',
}

# === 数据模型 ===
@dataclass
class Token:
    address: str
    chain: str
    name: str
    symbol: str
    market_cap: float
    liquidity: float
    volume: float
    holders: int
    smart_degen: int
    change_1h: float
    change_24h: float
    age_hours: float
    price: float
    buys_1h: int
    sells_1h: int
    source: str = 'gmgn'  # 数据源标记
    
    @property
    def buy_sell_ratio(self) -> float:
        if self.sells_1h == 0:
            return float('inf')
        return self.buys_1h / self.sells_1h

# === 异步HTTP客户端 ===
class AsyncHttpClient:
    """带连接池和重试的异步HTTP客户端"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.connector: Optional[aiohttp.TCPConnector] = None
        
    async def __aenter__(self):
        # 高性能连接池配置
        self.connector = aiohttp.TCPConnector(
            limit=20,                    # 总连接数
            limit_per_host=10,           # 单主机连接数
            ttl_dns_cache=300,           # DNS缓存5分钟
            use_dns_cache=True,
            enable_cleanup_closed=True,
            force_close=False,
        )
        
        timeout = aiohttp.ClientTimeout(
            total=REQUEST_TIMEOUT,
            connect=2.0,
            sock_read=REQUEST_TIMEOUT
        )
        
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=timeout,
            headers=HEADERS,
            raise_for_status=False,
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()
            
    async def fetch_with_retry(self, url: str, params: Dict = None, 
                                chain: str = None) -> Optional[Dict]:
        """带智能重试的请求"""
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                async with self.session.get(url, params=params, ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and self._is_valid_response(data, chain):
                            return data
                    elif resp.status == 429:  # 限流
                        logger.warning(f"Rate limited on {chain}, waiting {delay}s")
                        await asyncio.sleep(delay * 2)
                        continue
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on {chain} (attempt {attempt+1})")
            except aiohttp.ClientError as e:
                logger.warning(f"Client error on {chain}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error on {chain}: {e}")
                
            if attempt < len(RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)
                
        return None
        
    def _is_valid_response(self, data: Dict, chain: str) -> bool:
        """验证响应数据有效性"""
        if not isinstance(data, dict):
            return False
        if 'data' in data and isinstance(data['data'], dict):
            tokens = data['data'].get('tokens', [])
            return len(tokens) > 0
        return False

# === 数据抓取器 ===
class TokenFetcher:
    """双源数据抓取器"""
    
    def __init__(self, client: AsyncHttpClient):
        self.client = client
        self.stats = {'gmgn_success': 0, 'gmgn_fail': 0, 'ds_success': 0, 'ds_fail': 0}
        
    async def fetch_chain(self, chain: str) -> List[Token]:
        """抓取单链数据（主源失败自动切备用源）"""
        tokens = []
        
        # 尝试主源：GMGN
        gmgn_data = await self._fetch_gmgn(chain)
        if gmgn_data:
            tokens = self._parse_gmgn(gmgn_data, chain)
            self.stats['gmgn_success'] += 1
            logger.info(f"[{chain}] GMGN: {len(tokens)} tokens")
        else:
            self.stats['gmgn_fail'] += 1
            # 尝试备用源：DexScreener
            ds_data = await self._fetch_dexscreener(chain)
            if ds_data:
                tokens = self._parse_dexscreener(ds_data, chain)
                self.stats['ds_success'] += 1
                logger.info(f"[{chain}] DexScreener: {len(tokens)} tokens")
            else:
                self.stats['ds_fail'] += 1
                logger.error(f"[{chain}] Both sources failed")
                
        return tokens
        
    async def _fetch_gmgn(self, chain: str) -> Optional[Dict]:
        """抓取GMGN数据"""
        url = GMGN_ENDPOINTS.get(chain)
        if not url:
            return None
            
        params = {
            'limit': 100,
            'orderby': 'open_timestamp',
            'direction': 'desc',
            'period': '1h'
        }
        
        return await self.client.fetch_with_retry(url, params, chain)
        
    async def _fetch_dexscreener(self, chain: str) -> Optional[Dict]:
        """抓取DexScreener数据（使用token-profiles端点）"""
        url = DS_TOP_PAIRS.get(chain)
        if not url:
            return None
            
        return await self.client.fetch_with_retry(url, None, chain)
        
    def _parse_gmgn(self, data: Dict, chain: str) -> List[Token]:
        """解析GMGN数据"""
        tokens = []
        raw_tokens = data.get('data', {}).get('tokens', [])
        
        now = time.time()
        for t in raw_tokens:
            try:
                addr = t.get('address', '')
                if not addr or len(addr) < 32:
                    continue
                    
                mc = float(t.get('market_cap', 0) or 0)
                liq = float(t.get('liquidity', 0) or 0)
                sm = int(t.get('smart_degen_count', 0) or 0)
                
                # 快速过滤
                if mc < MIN_MARKET_CAP or mc > MAX_MARKET_CAP or liq < MIN_LIQUIDITY:
                    continue
                if sm < MIN_SMART_DEGEN:
                    continue
                    
                age_ts = t.get('open_timestamp', 0)
                age_h = (now - age_ts) / 3600 if age_ts > 0 else 999
                
                token = Token(
                    address=addr,
                    chain=chain,
                    name=t.get('name', '?')[:50],
                    symbol=t.get('symbol', '?')[:20],
                    market_cap=mc,
                    liquidity=liq,
                    volume=float(t.get('volume', 0) or 0),
                    holders=int(t.get('holder_count', 0) or 0),
                    smart_degen=sm,
                    change_1h=float(t.get('price_change_percent1h', 0) or 0),
                    change_24h=float(t.get('price_change_percent', 0) or 0),
                    age_hours=age_h,
                    price=float(t.get('price', 0) or 0),
                    buys_1h=int(t.get('buys', 0) or 0),
                    sells_1h=int(t.get('sells', 0) or 0),
                    source='gmgn'
                )
                tokens.append(token)
                
            except Exception as e:
                continue
                
        return tokens
        
    def _parse_dexscreener(self, data: Dict, chain: str) -> List[Token]:
        """解析DexScreener数据（备用源格式不同）"""
        tokens = []
        # DexScreener返回的是token profiles列表
        profiles = data if isinstance(data, list) else data.get('results', [])
        
        for p in profiles:
            try:
                token_data = p.get('token', {})
                addr = token_data.get('address', '')
                if not addr:
                    continue
                    
                mc = float(p.get('marketCap', 0) or 0)
                liq = float(p.get('liquidity', {}).get('usd', 0) or 0)
                
                if mc < MIN_MARKET_CAP or mc > MAX_MARKET_CAP or liq < MIN_LIQUIDITY:
                    continue
                    
                # DexScreener没有聪明钱数据，给一个默认值
                token = Token(
                    address=addr,
                    chain=chain,
                    name=token_data.get('name', '?')[:50],
                    symbol=token_data.get('symbol', '?')[:20],
                    market_cap=mc,
                    liquidity=liq,
                    volume=float(p.get('volume', {}).get('h24', 0) or 0),
                    holders=0,  # DS不提供
                    smart_degen=3,  # 备用源默认给3
                    change_1h=float(p.get('priceChange', {}).get('h1', 0) or 0),
                    change_24h=float(p.get('priceChange', {}).get('h24', 0) or 0),
                    age_hours=999,  # DS不提供
                    price=float(p.get('priceUsd', 0) or 0),
                    buys_1h=0,
                    sells_1h=0,
                    source='dexscreener'
                )
                tokens.append(token)
                
            except Exception:
                continue
                
        return tokens

# === 数据库管理 ===
class DatabaseManager:
    """SQLite数据库管理"""
    
    def __init__(self):
        self.db_path = DB_FILE
        self._init_db()
        
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            # 代币记录表
            c.execute('''CREATE TABLE IF NOT EXISTS tokens (
                address TEXT PRIMARY KEY,
                chain TEXT,
                name TEXT,
                symbol TEXT,
                market_cap REAL,
                liquidity REAL,
                smart_degen INTEGER,
                first_seen INTEGER,
                last_seen INTEGER,
                seen_count INTEGER DEFAULT 1,
                push_count INTEGER DEFAULT 0
            )''')
            
            # 扫描日志表
            c.execute('''CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                chain TEXT,
                tokens_found INTEGER,
                duration_ms INTEGER,
                source TEXT
            )''')
            
            # 创建索引
            c.execute('CREATE INDEX IF NOT EXISTS idx_chain ON tokens(chain)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_last_seen ON tokens(last_seen)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_mc ON tokens(market_cap)')
            
            conn.commit()
            
    def save_tokens(self, tokens: List[Token]):
        """批量保存代币"""
        now = int(time.time())
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            for t in tokens:
                c.execute('''INSERT OR REPLACE INTO tokens 
                    (address, chain, name, symbol, market_cap, liquidity, smart_degen,
                     first_seen, last_seen, seen_count, push_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 
                        COALESCE((SELECT first_seen FROM tokens WHERE address=?), ?),
                        ?, 
                        COALESCE((SELECT seen_count FROM tokens WHERE address=?), 0) + 1,
                        COALESCE((SELECT push_count FROM tokens WHERE address=?), 0))
                ''', (t.address, t.chain, t.name, t.symbol, t.market_cap, t.liquidity,
                      t.smart_degen, t.address, now, now, t.address, t.address))
                      
            conn.commit()
            
    def log_scan(self, chain: str, count: int, duration_ms: int, source: str):
        """记录扫描日志"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('INSERT INTO scan_logs (timestamp, chain, tokens_found, duration_ms, source) VALUES (?, ?, ?, ?, ?)',
                     (int(time.time()), chain, count, duration_ms, source))
            conn.commit()
            
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            c.execute('SELECT COUNT(*), COUNT(DISTINCT chain) FROM tokens')
            total, chains = c.fetchone()
            
            c.execute('SELECT AVG(duration_ms) FROM scan_logs WHERE timestamp > ?',
                     (int(time.time()) - 3600,))
            avg_duration = c.fetchone()[0] or 0
            
            return {
                'total_tokens': total,
                'chains': chains,
                'avg_scan_duration_ms': round(avg_duration, 2)
            }

# === 推送器 ===
class AlertPusher:
    """告警推送器（Telegram + 微信）"""
    
    def __init__(self):
        self.tg_token = os.getenv('TG_TOKEN', '')
        self.tg_chat = os.getenv('TG_CHAT_ID', '')
        self.wx_webhook = os.getenv('WX_WEBHOOK', '')
        
    async def push_token(self, token: Token, momentum: Dict):
        """推送单个代币"""
        msg = self._format_message(token, momentum)
        
        # 异步并行推送
        tasks = []
        if self.tg_token and self.tg_chat:
            tasks.append(self._send_tg(msg))
        if self.wx_webhook:
            tasks.append(self._send_wx(msg))
            
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    def _format_message(self, t: Token, m: Dict) -> str:
        """格式化消息"""
        star = "🚀" if t.change_1h > 50 else "⭐" if t.change_1h > 20 else "🟡"
        
        mc_str = f"${t.market_cap/1000:.1f}K" if t.market_cap < 1000000 else f"${t.market_cap/1000000:.1f}M"
        liq_str = f"${t.liquidity/1000:.1f}K" if t.liquidity < 1000000 else f"${t.liquidity/1000000:.1f}M"
        
        return f"""
{star} <b>链上雷达 v3</b> | {t.chain.upper()}

<b>{t.name}</b> (${t.symbol})
<code>{t.address}</code>

⚙️ <b>智能评分</b>
• 聪明钱: {t.smart_degen} 人
• 买/卖比: {t.buy_sell_ratio:.1f}
• 数据源: {t.source.upper()}

📈 <b>关键指标</b>
<pre>市值     {mc_str:>10}
流动性   {liq_str:>10}
持仓人   {t.holders:>10,}
币龄     {t.age_hours:.1f}h
</pre>

🔥 <b>动量</b>: 连涨{m['rounds']}轮 +{m['gain']:.1f}%
        """.strip()
        
    async def _send_tg(self, msg: str):
        """发送Telegram"""
        if not self.tg_token:
            return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        payload = {
            'chat_id': self.tg_chat,
            'text': msg,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, timeout=5) as r:
                    return r.status == 200
        except:
            pass
            
    async def _send_wx(self, msg: str):
        """发送微信"""
        if not self.wx_webhook:
            return
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(self.wx_webhook, json={'msg': msg}, timeout=5) as r:
                    return r.status == 200
        except:
            pass

# === 动量追踪器 ===
class MomentumTracker:
    """代币动量追踪"""
    
    def __init__(self):
        self.history: Dict[str, List[Dict]] = {}
        self.pushed: Dict[str, int] = {}
        
    def update(self, tokens: List[Token]) -> List[Tuple[Token, Dict]]:
        """更新并返回触发动量的代币"""
        now = time.time()
        alerts = []
        current_addrs = set()
        
        for t in tokens:
            addr = t.address
            current_addrs.add(addr)
            
            # 更新历史
            if addr not in self.history:
                self.history[addr] = []
                
            self.history[addr].append({
                'price': t.price,
                'mc': t.market_cap,
                'ts': now
            })
            
            # 只保留最近10分钟
            self.history[addr] = [
                h for h in self.history[addr] 
                if now - h['ts'] < 600
            ]
            
            # 检查动量
            momentum = self._check_momentum(addr, t)
            if momentum:
                # 限制推送频率
                last_push = self.pushed.get(addr, 0)
                if now - last_push > 1800:  # 30分钟内不重复推送
                    alerts.append((t, momentum))
                    self.pushed[addr] = now
                    
        # 清理旧数据
        self._cleanup(current_addrs, now)
        
        return alerts
        
    def _check_momentum(self, addr: str, token: Token) -> Optional[Dict]:
        """检查是否触发动量"""
        hist = self.history.get(addr, [])
        if len(hist) < 3:
            return None
            
        # 连续上涨
        prices = [h['price'] for h in hist[-5:]]
        if len(prices) < 3:
            return None
            
        up_count = sum(1 for i in range(1, len(prices)) if prices[i] > prices[i-1])
        
        if up_count >= 3:
            gain = (prices[-1] - prices[0]) / prices[0] * 100 if prices[0] > 0 else 0
            if gain > 5:  # 至少涨5%
                return {
                    'rounds': up_count,
                    'gain': gain,
                    'start_price': prices[0],
                    'current_price': prices[-1]
                }
        
        return None
        
    def _cleanup(self, current_addrs: set, now: float):
        """清理过期数据"""
        expired = [addr for addr in self.history if addr not in current_addrs 
                  and now - self.history[addr][-1]['ts'] > 600]
        for addr in expired:
            del self.history[addr]
            
        # 清理推送记录
        expired_push = [addr for addr, ts in self.pushed.items() if now - ts > 3600]
        for addr in expired_push:
            del self.pushed[addr]

# === 主控 ===
class RadarMaster:
    """雷达主控"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.tracker = MomentumTracker()
        self.pusher = AlertPusher()
        self.scan_count = 0
        self.total_pushed = 0
        
    async def run_scan(self) -> Dict:
        """执行一次完整扫描"""
        start_time = time.time()
        
        async with AsyncHttpClient() as client:
            fetcher = TokenFetcher(client)
            
            # 并发扫描所有链
            chains = ['sol', 'eth', 'bsc', 'base']
            tasks = [fetcher.fetch_chain(c) for c in chains]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        # 合并结果
        all_tokens = []
        scan_duration = int((time.time() - start_time) * 1000)
        
        for chain, result in zip(chains, results):
            if isinstance(result, list):
                all_tokens.extend(result)
                source = result[0].source if result else 'none'
                self.db.log_scan(chain, len(result), scan_duration, source)
            else:
                logger.error(f"[{chain}] Scan failed: {result}")
                self.db.log_scan(chain, 0, scan_duration, 'error')
                
        # 去重（优先保留GMGN源）
        seen = {}
        for t in all_tokens:
            if t.address not in seen or t.source == 'gmgn':
                seen[t.address] = t
        unique_tokens = list(seen.values())
        
        # 保存到数据库
        self.db.save_tokens(unique_tokens)
        
        # 动量检测
        alerts = self.tracker.update(unique_tokens)
        
        # 推送
        push_count = 0
        for token, momentum in alerts[:5]:  # 每轮最多5个
            await self.pusher.push_token(token, momentum)
            push_count += 1
            await asyncio.sleep(0.5)
            
        self.scan_count += 1
        self.total_pushed += push_count
        
        return {
            'total': len(unique_tokens),
            'pushed': push_count,
            'duration_ms': scan_duration,
            'stats': fetcher.stats
        }
        
    async def run_forever(self):
        """持续运行"""
        logger.info("="*60)
        logger.info("🚀 链上雷达 v3 启动")
        logger.info(f"配置: 聪明钱≥{MIN_SMART_DEGEN} | 市值≥${MIN_MARKET_CAP:,} | 并发={MAX_CONCURRENT}")
        logger.info("="*60)
        
        while True:
            try:
                result = await self.run_scan()
                logger.info(f"[第{self.scan_count}次扫描] {result['total']}个币 | {result['duration_ms']}ms | 推送{result['pushed']}")
                
                if self.scan_count % 10 == 0:
                    stats = self.db.get_stats()
                    logger.info(f"[统计] 总记录{stats['total_tokens']} | 均时延{stats['avg_scan_duration_ms']}ms")
                    
            except Exception as e:
                logger.error(f"扫描异常: {e}")
                
            await asyncio.sleep(SCAN_INTERVAL)

# === 入口 ===
if __name__ == '__main__':
    radar = RadarMaster()
    
    # 测试模式：只运行一次
    async def test_once():
        result = await radar.run_scan()
        print(f"\n✅ 测试完成:")
        print(f"   获取币数: {result['total']}")
        print(f"   耗时: {result['duration_ms']}ms")
        print(f"   推送: {result['pushed']}")
        print(f"   数据源统计: {result['stats']}")
        return result
    
    # 生产模式：持续运行
    # asyncio.run(radar.run_forever())
    
    # 默认运行测试
    result = asyncio.run(test_once())
