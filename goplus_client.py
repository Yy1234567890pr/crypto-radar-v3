#!/usr/bin/env python3
"""GoPlus API 客户端 - 增强版安全检测"""

import requests
import json
from typing import Dict, Optional
from datetime import datetime

# GoPlus API配置
# 公开API不需要Key，但频率有限制
# 如需要高频率，需购买付费计划
GOPLUS_API_KEY = None  # 公开版不需要
GOPLUS_SECRET = None

class GoPlusClient:
    """GoPlus安全检测客户端 - 使用公开API"""
    
    # 链ID映射
    CHAIN_IDS = {
        'ethereum': '1',
        'bsc': '56',
        'solana': 'solana',
        'base': '8453',
        'arbitrum': '42161',
        'polygon': '137',
        'optimism': '10'
    }
    
    def __init__(self):
        self.api_key = GOPLUS_API_KEY
        self.secret = GOPLUS_SECRET
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json'
        })
    
    def get_token_security(self, chain: str, contract_address: str) -> Dict:
        """
        获取代币安全信息
        返回包含17项安全检测的详细报告
        """
        chain_id = self.CHAIN_IDS.get(chain.lower(), '1')
        
        url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={contract_address.lower()}"
        
        try:
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            
            if resp.status_code != 200:
                return {
                    'success': False,
                    'error': f'API Error: {resp.status_code}',
                    'data': None
                }
            
            result = data.get('result', {})
            if not result:
                return {
                    'success': False,
                    'error': 'No data returned',
                    'data': None
                }
            
            # 解析第一个合约数据
            contract_data = list(result.values())[0]
            
            return {
                'success': True,
                'data': self._parse_security_data(contract_data)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def _parse_security_data(self, data: Dict) -> Dict:
        """解析安全检测报告"""
        
        # 关键风险指标
        risks = []
        
        # 1. 貔貅检测 (Honeypot)
        is_honeypot = data.get('is_honeypot', '0') == '1'
        if is_honeypot:
            risks.append('🚨 貔貅合约 - 无法卖出')
        
        # 2. 交易税检测
        buy_tax = data.get('buy_tax', '0')
        sell_tax = data.get('sell_tax', '0')
        if buy_tax and float(buy_tax) > 5:
            risks.append(f'⚠️ 买入税 {buy_tax}%')
        if sell_tax and float(sell_tax) > 5:
            risks.append(f'⚠️ 卖出税 {sell_tax}%')
        
        # 3. 隐藏铸币检测
        hidden_owner = data.get('hidden_owner', '0') == '1'
        if hidden_owner:
            risks.append('🔒 隐藏所有者权限')
        
        can_take_back = data.get('can_take_back_ownership', '0') == '1'
        if can_take_back:
            risks.append('⚠️ 可取回所有权')
        
        # 4. 冻结检测
        is_blacklisted = data.get('is_blacklisted', '0') == '1'
        if is_blacklisted:
            risks.append('🚫 可冻结黑名单')
        
        # 5. 白名单检测
        is_whitelisted = data.get('is_whitelisted', '0') == '1'
        if is_whitelisted:
            risks.append('📋 限制白名单交易')
        
        # 6. 自毁/代理检测
        is_proxy = data.get('is_proxy', '0') == '1'
        if is_proxy:
            risks.append('🔧 代理合约（可升级）')
        
        # 7. 开源检测
        is_open_source = data.get('is_open_source', '0') == '1'
        if not is_open_source:
            risks.append('📕 合约未开源')
        
        # 8. 持有者分布检测
        holder_count = data.get('holder_count', '0')
        holders = int(holder_count) if holder_count else 0
        
        # 计算安全分 (0-100)
        score = 100
        if is_honeypot: score -= 50
        if hidden_owner: score -= 20
        if not is_open_source: score -= 10
        if can_take_back: score -= 15
        if is_blacklisted: score -= 10
        if is_whitelisted: score -= 5
        if is_proxy: score -= 5
        
        # 交易税扣分
        if buy_tax and float(buy_tax) > 0:
            score -= min(float(buy_tax) * 2, 10)
        if sell_tax and float(sell_tax) > 0:
            score -= min(float(sell_tax) * 2, 10)
        
        score = max(0, min(100, score))
        
        return {
            'safety_score': int(score),
            'is_honeypot': is_honeypot,
            'buy_tax': float(buy_tax) if buy_tax else 0,
            'sell_tax': float(sell_tax) if sell_tax else 0,
            'hidden_owner': hidden_owner,
            'can_take_back': can_take_back,
            'is_blacklisted': is_blacklisted,
            'is_whitelisted': is_whitelisted,
            'is_proxy': is_proxy,
            'is_open_source': is_open_source,
            'holder_count': holders,
            'risks': risks,
            'checked_at': datetime.now().isoformat()
        }
    
    def quick_scan(self, chain: str, address: str) -> str:
        """快速扫描并返回结果摘要"""
        result = self.get_token_security(chain, address)
        
        if not result['success']:
            return f"❌ 扫描失败: {result.get('error', 'Unknown')}"
        
        data = result['data']
        score = data['safety_score']
        
        # 表情评级
        if score >= 90:
            rating = "🟢 优秀"
        elif score >= 70:
            rating = "🟡 良好"
        elif score >= 50:
            rating = "🟠 风险"
        else:
            rating = "🔴 高危"
        
        report = f"{rating} | 安全分: {score}/100\n"
        
        if data['buy_tax'] > 0 or data['sell_tax'] > 0:
            report += f"  交易税: 买{data['buy_tax']}% / 卖{data['sell_tax']}%\n"
        
        if data['holder_count'] > 0:
            report += f"  持有者: {data['holder_count']}人\n"
        
        if data['risks']:
            report += f"  风险项: {len(data['risks'])}个\n"
            for risk in data['risks'][:3]:  # 只显示前3个
                report += f"    - {risk}\n"
        
        return report


# 测试
def test_goplus():
    """测试GoPlus客户端"""
    client = GoPlusClient()
    
    print("🧪 测试GoPlus安全扫描")
    print("="*60)
    
    # 测试1: USDT (应通过)
    print("\n[测试1] USDT (以太坊)")
    result = client.quick_scan('ethereum', '0xdAC17F958D2ee523a2206206994597C13D831ec7')
    print(result)
    
    # 测试2: 一个随机BSC币
    print("\n[测试2] 随机BSC币")
    result = client.quick_scan('bsc', '0x6331BF8D601f0D7F0d2101772af5137c418c4444')
    print(result)

if __name__ == '__main__':
    test_goplus()
