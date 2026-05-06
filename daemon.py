#!/usr/bin/env python3
"""雷达v3常驻守护进程 - 每30秒扫描一次"""
import sys
import time
import os
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/crypto-radar-v3')

from radar_v3_pro import RadarV3

INTERVAL = 30  # 30秒扫描一次

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 雷达v3守护进程启动")
    print(f"扫描间隔: {INTERVAL}秒")
    print("="*60)
    
    radar = RadarV3()
    scan_count = 0
    
    while True:
        try:
            scan_count += 1
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📡 第{scan_count}轮扫描开始...")
            radar.run()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 第{scan_count}轮扫描完成")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 扫描异常: {e}")
        
        time.sleep(INTERVAL)

if __name__ == '__main__':
    main()
