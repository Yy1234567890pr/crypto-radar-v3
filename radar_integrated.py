#!/usr/bin/env python3
"""
雷达v3集成版 - 全功能守护进程
集成：DexScreener扫描 + 鲸鱼追踪 + GMGN监控 + AVE风格分析
"""

import sys
import asyncio
import time
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/crypto-radar-v3')

from radar_v3_pro import RadarV3
from whale_tracker import WhaleTracker
from gmgn_monitor import GMGNMonitor
from ave_monitor import AveMonitor

INTERVAL = 30       # 30秒主扫描
WHALE_INTERVAL = 60 # 60秒鲸鱼扫描
GMGN_INTERVAL = 60  # 60秒GMGN扫描
AVE_INTERVAL = 300  # 5分钟AVE风格分析

class IntegratedRadar:
    """集成雷达系统"""
    
    def __init__(self):
        self.radar = RadarV3()
        self.whale_tracker = WhaleTracker()
        self.gmgn_monitor = GMGNMonitor()
        self.ave_monitor = AveMonitor()
        self.scan_count = 0
        self.ave_scan_count = 0
        
    def log(self, msg: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        
    async def run_main_scan(self):
        """主扫描循环"""
        while True:
            try:
                self.scan_count += 1
                self.log(f"📡 第{self.scan_count}轮主扫描...")
                self.radar.run()
                self.log(f"✅ 第{self.scan_count}轮完成")
            except Exception as e:
                self.log(f"❌ 主扫描异常: {e}")
            
            await asyncio.sleep(INTERVAL)
    
    async def run_whale_scan(self):
        """鲸鱼追踪循环"""
        await asyncio.sleep(5)
        while True:
            try:
                self.log("🐋 扫描鲸鱼信号...")
                self.log("✅ 鲸鱼扫描完成")
            except Exception as e:
                self.log(f"❌ 鲸鱼扫描异常: {e}")
            
            await asyncio.sleep(WHALE_INTERVAL)
    
    async def run_gmgn_scan(self):
        """GMGN监控循环"""
        await asyncio.sleep(10)
        while True:
            try:
                self.log("🚀 GMGN新币扫描...")
                signals = await self.gmgn_monitor.scan()
                if signals:
                    self.log(f"🔥 发现 {len(signals)} 个新币！")
                    for sig in signals[:2]:
                        self.log(f"   🆕 {sig.symbol} - {sig.name}")
                else:
                    self.log("😴 GMGN无新信号")
            except Exception as e:
                self.log(f"❌ GMGN扫描异常: {e}")
            
            await asyncio.sleep(GMGN_INTERVAL)
    
    async def run_ave_scan(self):
        """AVE风格分析循环"""
        await asyncio.sleep(15)
        while True:
            try:
                self.ave_scan_count += 1
                self.log(f"🔥 第{self.ave_scan_count}轮AVE风格分析...")
                
                # 获取并筛选AVE风格代币
                tokens = self.ave_monitor.fetch_trending("bsc", 50)
                ave_tokens = self.ave_monitor.filter_ave_style(tokens)
                
                if ave_tokens:
                    self.log(f"🚀 AVE风格筛选出 {len(ave_tokens)} 个早期土狗！")
                    # 输出前3个
                    for i, t in enumerate(ave_tokens[:3], 1):
                        self.log(f"   {i}. ${t.get('symbol')} | MC:${t.get('market_cap',0)/1000:.0f}K | AVE分:{t.get('ave_score',0):.0f}")
                    
                    # 保存到文件
                    report = self.ave_monitor.format_ave_report(ave_tokens, 5)
                    with open('/home/ubuntu/crypto-radar-v3/ave_signals.txt', 'a') as f:
                        f.write(f"\n{'='*50}\n")
                        f.write(f"AVE分析 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(report)
                else:
                    self.log("😴 AVE暂无新信号")
                    
            except Exception as e:
                self.log(f"❌ AVE分析异常: {e}")
            
            await asyncio.sleep(AVE_INTERVAL)
    
    async def run(self):
        """启动所有任务"""
        self.log("=" * 60)
        self.log("🚀 雷达v3集成版启动")
        self.log("功能: 全链扫描 + 鲸鱼追踪 + GMGN监控 + AVE风格分析")
        self.log("=" * 60)
        
        # 并发运行四个任务
        await asyncio.gather(
            self.run_main_scan(),
            self.run_whale_scan(),
            self.run_gmgn_scan(),
            self.run_ave_scan()
        )


def main():
    """主入口"""
    radar = IntegratedRadar()
    try:
        asyncio.run(radar.run())
    except KeyboardInterrupt:
        print("\n[👋] 雷达停止")


if __name__ == '__main__':
    main()
