#!/usr/bin/env python3
"""
Polymarket CLOB API Key 派生脚本
使用 py-clob-client 库通过钱包签名生成API凭证
"""

import os
from py_clob_client.client import ClobClient

# 配置
POLY_HOST = "https://clob.polymarket.com"
PRIVATE_KEY = "0xa0570ae6e27a7182f1d819d254ffaa3cf4bbb13de82483e95e3b39c092bbe9ea"

def derive_api_key():
    """通过私钥派生Polymarket API Key"""
    
    print("🚀 派生Polymarket API Key...")
    print("="*70)
    
    # 初始化ClobClient
    client = ClobClient(
        host=POLY_HOST,
        key=PRIVATE_KEY,
        chain_id=137  # Polygon主网
    )
    
    try:
        # 创建/派生API Key
        api_creds = client.create_or_derive_api_creds()
        
        print("✅ API Key 派生成功！")
        print("="*70)
        print(f"API Key: {api_creds.api_key}")
        print(f"API Secret: {api_creds.api_secret}")
        print(f"Passphrase: {api_creds.api_passphrase}")
        print("="*70)
        
        # 保存到环境文件
        env_content = f"""# Polymarket API配置
POLYMARKET_API_KEY={api_creds.api_key}
POLYMARKET_API_SECRET={api_creds.api_secret}
POLYMARKET_PASSPHRASE={api_creds.api_passphrase}
POLYMARKET_HOST={POLY_HOST}

# 钱包配置（仅用于API派生）
POLYMARKET_PRIVATE_KEY={PRIVATE_KEY}
"""
        
        env_file = os.path.expanduser("~/.polymarket_env")
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        print(f"✅ 已保存到: {env_file}")
        print("\n🎯 现在可以开始交易Polymarket了！")
        
        return api_creds
        
    except Exception as e:
        print(f"❌ 派生失败: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    derive_api_key()
