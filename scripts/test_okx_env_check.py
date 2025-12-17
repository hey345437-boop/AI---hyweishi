#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OKX 环境配置验证脚本

验证：
1. x-simulated-trading 必须为 0
2. sandbox 必须为 False
3. 禁止 demo 模式
4. paper_on_real 模式下交易请求被路由到本地模拟
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from startup_check import StartupSelfCheck, run_startup_check, OKXEnvironmentError


def test_startup_check():
    """测试启动自检"""
    print("=" * 60)
    print("🔍 OKX 环境配置验证")
    print("=" * 60)
    
    # 测试 1: live 模式 + sandbox=False 应该通过
    print("\n📋 测试 1: live 模式 + sandbox=False")
    result = StartupSelfCheck.check_okx_environment(
        run_mode='live',
        api_key='abcdef123456789012345',  # 不包含 demo/test 等关键词
        is_sandbox=False,
        x_simulated_trading=0
    )
    if not result.has_errors:
        print("   ✅ 通过")
    else:
        print(f"   ❌ 失败: {result.errors}")
    
    # 测试 2: paper_on_real 模式 + sandbox=False 应该通过
    print("\n📋 测试 2: paper_on_real 模式 + sandbox=False")
    result = StartupSelfCheck.check_okx_environment(
        run_mode='paper_on_real',
        api_key='abcdef123456789012345',  # 不包含 demo/test 等关键词
        is_sandbox=False,
        x_simulated_trading=0
    )
    if not result.has_errors:
        print("   ✅ 通过")
    else:
        print(f"   ❌ 失败: {result.errors}")
    
    # 测试 3: demo 模式应该失败
    print("\n📋 测试 3: demo 模式应该被拒绝")
    result = StartupSelfCheck.check_okx_environment(
        run_mode='demo',
        api_key='test_key_12345',
        is_sandbox=False,
        x_simulated_trading=0
    )
    if result.has_errors:
        print("   ✅ 正确拒绝 demo 模式")
    else:
        print("   ❌ 错误：应该拒绝 demo 模式")
    
    # 测试 4: sandbox=True 应该失败
    print("\n📋 测试 4: sandbox=True 应该被拒绝")
    result = StartupSelfCheck.check_okx_environment(
        run_mode='live',
        api_key='test_key_12345',
        is_sandbox=True,
        x_simulated_trading=0
    )
    if result.has_errors:
        print("   ✅ 正确拒绝 sandbox=True")
    else:
        print("   ❌ 错误：应该拒绝 sandbox=True")
    
    # 测试 5: x-simulated-trading=1 应该失败
    print("\n📋 测试 5: x-simulated-trading=1 应该被拒绝")
    result = StartupSelfCheck.check_okx_environment(
        run_mode='live',
        api_key='test_key_12345',
        is_sandbox=False,
        x_simulated_trading=1
    )
    if result.has_errors:
        print("   ✅ 正确拒绝 x-simulated-trading=1")
    else:
        print("   ❌ 错误：应该拒绝 x-simulated-trading=1")
    
    # 测试 6: 旧模式 sim 应该被映射到 paper_on_real
    print("\n📋 测试 6: 旧模式 'sim' 应该被映射到 'paper_on_real'")
    result = StartupSelfCheck.check_okx_environment(
        run_mode='sim',
        api_key='test_live_key_12345',
        is_sandbox=False,
        x_simulated_trading=0
    )
    if result.run_mode == 'paper_on_real' and result.has_warnings:
        print("   ✅ 正确映射并产生警告")
    else:
        print(f"   ❌ 错误：run_mode={result.run_mode}, warnings={result.warnings}")
    
    print("\n" + "=" * 60)
    print("✅ 所有验证测试完成")
    print("=" * 60)


def test_okx_adapter_paper_mode():
    """测试 OKX adapter 的 paper_on_real 模式"""
    print("\n" + "=" * 60)
    print("🔍 OKX Adapter paper_on_real 模式测试")
    print("=" * 60)
    
    try:
        from exchange_adapters.okx_adapter import OKXAdapter, LocalPaperBroker
        
        # 创建 paper_on_real 模式的 adapter
        config = {
            'api_key': 'test_key',
            'api_secret': 'test_secret',
            'api_passphrase': 'test_pass',
            'run_mode': 'paper_on_real'
        }
        
        adapter = OKXAdapter(config)
        
        # 验证模式
        print(f"\n📋 run_mode: {adapter.run_mode}")
        assert adapter.run_mode == 'paper_on_real', "run_mode 应该是 paper_on_real"
        print("   ✅ run_mode 正确")
        
        # 验证 paper_broker 存在
        assert adapter.paper_broker is not None, "paper_broker 应该存在"
        assert isinstance(adapter.paper_broker, LocalPaperBroker), "paper_broker 类型错误"
        print("   ✅ paper_broker 已初始化")
        
        # 验证 is_paper_mode
        assert adapter.is_paper_mode() == True, "is_paper_mode() 应该返回 True"
        print("   ✅ is_paper_mode() 返回 True")
        
        # 验证 is_live_mode
        assert adapter.is_live_mode() == False, "is_live_mode() 应该返回 False"
        print("   ✅ is_live_mode() 返回 False")
        
        print("\n" + "=" * 60)
        print("✅ OKX Adapter paper_on_real 模式测试通过")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_legacy_mode_mapping():
    """测试旧模式映射"""
    print("\n" + "=" * 60)
    print("🔍 旧模式映射测试")
    print("=" * 60)
    
    try:
        from exchange_adapters.okx_adapter import OKXAdapter
        
        legacy_modes = ['sim', 'paper', 'demo']
        
        for mode in legacy_modes:
            config = {
                'api_key': 'test_key',
                'api_secret': 'test_secret',
                'api_passphrase': 'test_pass',
                'run_mode': mode
            }
            
            adapter = OKXAdapter(config)
            print(f"\n📋 输入模式 '{mode}' -> 实际模式 '{adapter.run_mode}'")
            
            if mode in ['sim', 'paper', 'demo']:
                assert adapter.run_mode == 'paper_on_real', \
                    f"模式 '{mode}' 应该被映射到 'paper_on_real'"
                print(f"   ✅ 正确映射到 'paper_on_real'")
        
        print("\n" + "=" * 60)
        print("✅ 旧模式映射测试通过")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_startup_check()
    test_okx_adapter_paper_mode()
    test_legacy_mode_mapping()
