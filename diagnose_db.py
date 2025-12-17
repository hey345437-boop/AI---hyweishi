#!/usr/bin/env python3
"""诊断数据库配置问题"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from db_bridge import get_bot_config, load_decrypted_credentials, get_paper_balance, init_db

def main():
    print("=" * 60)
    print("数据库配置诊断")
    print("=" * 60)
    
    # 初始化数据库
    init_db()
    
    # 获取bot_config
    print("\n1. bot_config 表内容:")
    bot_config = get_bot_config()
    if bot_config:
        print(f"   run_mode: {bot_config.get('run_mode', 'N/A')}")
        print(f"   symbols: '{bot_config.get('symbols', '')}' (长度: {len(bot_config.get('symbols', ''))})")
        print(f"   enable_trading: {bot_config.get('enable_trading', 'N/A')}")
        print(f"   position_size: {bot_config.get('position_size', 'N/A')}")
        print(f"   okx_api_key: {'已配置' if bot_config.get('okx_api_key') else '未配置'}")
        print(f"   okx_api_secret_ciphertext: {'已配置' if bot_config.get('okx_api_secret_ciphertext') else '未配置'}")
        print(f"   okx_api_passphrase_ciphertext: {'已配置' if bot_config.get('okx_api_passphrase_ciphertext') else '未配置'}")
    else:
        print("   ❌ bot_config 表为空!")
    
    # 获取解密后的凭证
    print("\n2. 解密后的凭证:")
    creds = load_decrypted_credentials()
    print(f"   okx_api_key: {'已配置 (' + creds.get('okx_api_key', '')[-4:] + ')' if creds.get('okx_api_key') else '未配置'}")
    print(f"   okx_api_secret: {'已配置' if creds.get('okx_api_secret') else '未配置'}")
    print(f"   okx_api_passphrase: {'已配置' if creds.get('okx_api_passphrase') else '未配置'}")
    
    # 获取模拟账户余额
    print("\n3. paper_balance 表内容:")
    paper_balance = get_paper_balance()
    if paper_balance:
        print(f"   equity: {paper_balance.get('equity', 'N/A')}")
        print(f"   available: {paper_balance.get('available', 'N/A')}")
    else:
        print("   ❌ paper_balance 表为空!")
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
    
    # 建议
    print("\n建议:")
    if not bot_config.get('symbols'):
        print("   ⚠️ 交易池为空，请在前端UI中添加交易对")
    if not creds.get('okx_api_key') or not creds.get('okx_api_secret') or not creds.get('okx_api_passphrase'):
        print("   ⚠️ API密钥未完全配置，请在前端UI中配置API密钥")

if __name__ == "__main__":
    main()
