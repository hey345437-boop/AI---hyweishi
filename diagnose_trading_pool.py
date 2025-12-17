#!/usr/bin/env python3
"""
交易池币种诊断脚本
检查为什么只扫描BTC而忽略其他币种
"""

import sys
import os
import json

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入主程序的函数
from app import init_db, load_user_state, get_db_connection, USE_POSTGRES

def diagnose_trading_pool(username=None):
    """诊断交易池配置问题"""
    print("🔍 开始诊断交易池币种问题...")
    
    if not username:
        # 获取第一个用户
        conn = get_db_connection()
        try:
            c = conn.cursor()
            if USE_POSTGRES:
                c.execute("SELECT username FROM users LIMIT 1")
            else:
                c.execute("SELECT username FROM users LIMIT 1")
            
            result = c.fetchone()
            if result:
                username = result[0]
            else:
                print("❌ 数据库中没有用户")
                return
        finally:
            conn.close()
    
    print(f"👤 诊断用户: {username}")
    
    # 1. 检查数据库中的用户状态
    print("\n📊 检查数据库中的用户状态:")
    try:
        user_state = load_user_state(username)
        print(f"   交易激活状态: {user_state['trading_active']}")
        print(f"   交易池币种数量: {len(user_state['auto_symbols'])}")
        print(f"   交易池币种列表: {user_state['auto_symbols']}")
        print(f"   持仓数量: {len(user_state['open_positions'])}")
        print(f"   持仓币种: {list(user_state['open_positions'].keys())}")
        print(f"   环境模式: {user_state['env_mode']}")
    except Exception as e:
        print(f"   ❌ 读取用户状态失败: {e}")
        return
    
    # 2. 检查数据库原始数据
    print("\n🔍 检查数据库原始数据:")
    conn = get_db_connection()
    try:
        c = conn.cursor()
        if USE_POSTGRES:
            c.execute("SELECT auto_symbols, open_positions, trading_active FROM user_states WHERE username=%s", (username,))
        else:
            c.execute("SELECT auto_symbols, open_positions, trading_active FROM user_states WHERE username=?", (username,))
        
        result = c.fetchone()
        if result:
            auto_symbols_raw = result[0]
            open_positions_raw = result[1]
            trading_active_raw = result[2]
            
            print(f"   原始交易池数据: {auto_symbols_raw}")
            print(f"   原始持仓数据: {open_positions_raw}")
            print(f"   原始交易状态: {trading_active_raw}")
            
            # 尝试解析JSON
            try:
                auto_symbols_parsed = json.loads(auto_symbols_raw) if auto_symbols_raw else []
                print(f"   解析后交易池: {auto_symbols_parsed}")
            except json.JSONDecodeError as e:
                print(f"   ❌ 交易池JSON解析失败: {e}")
        else:
            print("   ❌ 用户状态表中没有数据")
    except Exception as e:
        print(f"   ❌ 查询数据库失败: {e}")
    finally:
        conn.close()
    
    # 3. 分析可能的问题
    print("\n🧠 问题分析:")
    
    # 检查睁眼模式
    if user_state['open_positions']:
        print(f"   ⚠️ 检测到持仓 {list(user_state['open_positions'].keys())}")
        print(f"   👀 系统可能进入'睁眼模式'，只扫描持仓币种")
        print(f"   💡 建议: 清空持仓或等待睁眼模式完成")
    
    # 检查交易池是否为空
    if not user_state['auto_symbols']:
        print(f"   ❌ 交易池为空")
        print(f"   💡 建议: 在UI中添加币种到交易池")
    
    # 检查交易状态
    if not user_state['trading_active']:
        print(f"   ⚠️ 交易未激活")
        print(f"   💡 建议: 在UI中启动交易")
    
    # 检查币种数量
    if len(user_state['auto_symbols']) > 1:
        print(f"   ✅ 交易池包含 {len(user_state['auto_symbols'])} 个币种，应该扫描多个币种")
        print(f"   🤔 如果只看到BTC扫描，可能是因为:")
        print(f"      - 睁眼模式限制")
        print(f"      - 网络问题导致其他币种API调用失败")
        print(f"      - 交易线程重启后状态未正确加载")
    
    print("\n🔧 建议的解决方案:")
    print("1. 检查终端输出，查看是否有'睁眼模式激活'的消息")
    print("2. 检查是否有'获取行情失败'的错误信息")
    print("3. 重启交易系统")
    print("4. 确认在UI中正确添加了币种")

def check_real_time_sync():
    """检查实时同步问题"""
    print("\n🔄 检查实时同步...")
    
    # 这里可以添加检查交易线程状态的代码
    print("   💡 如果问题持续，可能需要重启交易线程")

if __name__ == "__main__":
    diagnose_trading_pool()
    check_real_time_sync()
    print("\n✅ 诊断完成！")
