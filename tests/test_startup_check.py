# tests/test_startup_check.py
# 启动自检属性测试
#
# 重要说明：本系统只支持两种模式
# - live: 实盘模式，真实下单
# - paper_on_real: 实盘测试模式，用实盘行情但本地模拟下单
#
# 两种模式都必须使用实盘 API Key，绝对禁止 demo/sandbox

import pytest
from hypothesis import given, strategies as st, settings

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from startup_check import StartupSelfCheck, StartupCheckResult, OKXEnvironmentError


class TestStartupCheckProperties:
    """启动自检属性测试 - 新行为：禁止 demo/sandbox"""
    
    @given(
        run_mode=st.sampled_from(['demo', 'sandbox', 'test']),
        api_key=st.text(min_size=10, max_size=50)
    )
    @settings(max_examples=50)
    def test_forbidden_modes_produce_error(self, run_mode, api_key):
        """
        **Feature: trading-bot-v2-fixes, Property 8: Environment Mismatch Warning**
        
        禁止的模式（demo/sandbox/test）应该产生错误，而不是警告
        
        **Validates: Requirements 5.5, 5.6**
        """
        result = StartupSelfCheck.check_okx_environment(
            run_mode=run_mode,
            api_key=api_key,
            is_sandbox=False
        )
        
        # 应该有错误（不是警告）
        assert result.has_errors, \
            f"Expected error for forbidden mode {run_mode}"
        
        # 错误应该提到不允许
        error_text = " ".join(result.errors)
        assert '不允许' in error_text or 'not allowed' in error_text.lower(), \
            f"Error should mention not allowed: {result.errors}"
    
    @given(
        is_sandbox=st.just(True),
        api_key=st.text(min_size=10, max_size=50)
    )
    @settings(max_examples=50)
    def test_sandbox_enabled_produces_error(self, is_sandbox, api_key):
        """
        **Feature: trading-bot-v2-fixes, Property 8: Environment Mismatch Warning**
        
        sandbox=True 应该产生错误，无论什么模式
        
        **Validates: Requirements 5.5, 5.6**
        """
        result = StartupSelfCheck.check_okx_environment(
            run_mode='live',
            api_key=api_key,
            is_sandbox=is_sandbox
        )
        
        # 应该有错误
        assert result.has_errors, \
            f"Expected error for sandbox={is_sandbox}"
        
        # 错误应该提到 sandbox
        error_text = " ".join(result.errors)
        assert 'sandbox' in error_text.lower(), \
            f"Error should mention sandbox: {result.errors}"


class TestStartupCheckEdgeCases:
    """边界情况测试"""
    
    def test_live_mode_no_sandbox_no_error(self):
        """live 模式 + sandbox=false + 实盘key 不应该有错误"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='live',
            api_key='live_key_12345',
            is_sandbox=False
        )
        
        # 不应该有错误
        assert not result.has_errors, f"Unexpected errors: {result.errors}"
    
    def test_paper_on_real_mode_no_sandbox_no_error(self):
        """paper_on_real 模式 + sandbox=false + 实盘key 不应该有错误"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='paper_on_real',
            api_key='live_key_12345',
            is_sandbox=False
        )
        
        # 不应该有错误
        assert not result.has_errors, f"Unexpected errors: {result.errors}"
    
    def test_legacy_sim_mode_mapped_to_paper(self):
        """旧的 sim 模式应该被映射到 paper 并产生警告"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='sim',
            api_key='live_key_12345',
            is_sandbox=False
        )
        
        # 应该有警告（关于模式映射）
        assert result.has_warnings, "Expected warning for legacy mode mapping"
        
        # 模式应该被映射
        assert result.run_mode == 'paper'
        
        # 不应该有错误
        assert not result.has_errors, f"Unexpected errors: {result.errors}"
    
    def test_legacy_paper_on_real_mode_mapped_to_paper(self):
        """旧的 paper_on_real 模式应该被映射到 paper 并产生警告"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='paper_on_real',
            api_key='live_key_12345',
            is_sandbox=False
        )
        
        # 应该有警告（关于模式映射）
        assert result.has_warnings, "Expected warning for legacy mode mapping"
        
        # 模式应该被映射
        assert result.run_mode == 'paper'
    
    def test_no_api_key_error(self):
        """无 API Key 应该报错"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='live',
            api_key='',
            is_sandbox=False
        )
        
        assert result.has_errors
        assert any('API Key' in e for e in result.errors)
    
    def test_demo_key_detected_produces_error(self):
        """检测到 demo key 应该产生错误"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='live',
            api_key='demo_test_key_12345',
            is_sandbox=False
        )
        
        # 应该有错误
        assert result.has_errors, "Expected error for demo key"
        
        # key_type 应该是 demo_key
        assert result.key_type == 'demo_key'
    
    def test_result_properties_live_mode(self):
        """验证 live 模式结果属性"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='live',
            api_key='live_key_12345',
            is_sandbox=False
        )
        
        assert result.run_mode == 'live'
        assert result.env_mode == 'live'  # 兼容旧属性
        assert '实盘' in result.api_domain
        assert result.simulated_trading == 0
        assert result.sandbox_enabled == False
        assert result.key_type == 'live_key'
    
    def test_result_properties_paper_mode(self):
        """验证 paper 模式结果属性"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='paper',
            api_key='live_key_12345',
            is_sandbox=False
        )
        
        assert result.run_mode == 'paper'
        assert '实盘' in result.api_domain
        assert result.simulated_trading == 0
        assert result.sandbox_enabled == False
    
    def test_remediation_steps_for_sandbox(self):
        """验证 sandbox 错误的修复建议"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='live',
            api_key='live_key_12345',
            is_sandbox=True
        )
        
        steps = StartupSelfCheck.get_remediation_steps(result)
        
        assert len(steps) > 0
        assert any('OKX_SANDBOX' in s or 'sandbox' in s.lower() for s in steps)
    
    def test_remediation_steps_for_demo_key(self):
        """验证 demo key 错误的修复建议"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='live',
            api_key='demo_key_12345',
            is_sandbox=False
        )
        
        steps = StartupSelfCheck.get_remediation_steps(result)
        
        assert len(steps) > 0
        assert any('实盘' in s or 'live' in s.lower() or 'Key' in s for s in steps)
    
    def test_validate_and_raise_with_errors(self):
        """验证有错误时 validate_and_raise 抛出异常"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='demo',
            api_key='demo_key_12345',
            is_sandbox=True
        )
        
        with pytest.raises(OKXEnvironmentError):
            StartupSelfCheck.validate_and_raise(result)
    
    def test_validate_and_raise_without_errors(self):
        """验证无错误时 validate_and_raise 不抛出异常"""
        result = StartupSelfCheck.check_okx_environment(
            run_mode='live',
            api_key='live_key_12345',
            is_sandbox=False
        )
        
        # 不应该抛出异常
        StartupSelfCheck.validate_and_raise(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
