# -*- coding: utf-8 -*-
"""
风控模块测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.risk_control import (
    OrderValidator,
    DailyLossTracker,
    RiskControlModule,
    RiskControlConfig,
    ValidationResult,
)


class TestOrderValidator:
    """订单验证器测试"""

    def test_valid_order(self):
        """测试有效订单"""
        validator = OrderValidator(max_order_size=1000.0)
        result = validator.validate(500.0, "BTC/USDT")
        
        assert result.is_valid is True
        assert result.error_message is None

    def test_order_exceeds_limit(self):
        """测试超限订单"""
        validator = OrderValidator(max_order_size=1000.0)
        result = validator.validate(1500.0, "BTC/USDT")
        
        assert result.is_valid is False
        assert result.error_code == "ORDER_SIZE_EXCEEDED"
        assert "1500" in result.error_message

    def test_zero_amount(self):
        """测试零金额订单"""
        validator = OrderValidator(max_order_size=1000.0)
        result = validator.validate(0, "BTC/USDT")
        
        assert result.is_valid is False
        assert result.error_code == "INVALID_AMOUNT"

    def test_negative_amount(self):
        """测试负金额订单"""
        validator = OrderValidator(max_order_size=1000.0)
        result = validator.validate(-100.0, "BTC/USDT")
        
        assert result.is_valid is False
        assert result.error_code == "INVALID_AMOUNT"

    def test_boundary_amount(self):
        """测试边界金额"""
        validator = OrderValidator(max_order_size=1000.0)
        
        # 刚好等于限制
        result = validator.validate(1000.0, "BTC/USDT")
        assert result.is_valid is True
        
        # 超过一点点
        result = validator.validate(1000.01, "BTC/USDT")
        assert result.is_valid is False


class TestDailyLossTracker:
    """单日损失追踪器测试"""

    def test_record_loss(self):
        """测试记录亏损"""
        tracker = DailyLossTracker(loss_limit_pct=0.10)
        
        tracker.record_loss(-100.0)
        assert tracker.daily_loss == 100.0
        
        tracker.record_loss(-50.0)
        assert tracker.daily_loss == 150.0

    def test_record_profit_ignored(self):
        """测试盈利不计入损失"""
        tracker = DailyLossTracker(loss_limit_pct=0.10)
        
        tracker.record_loss(100.0)  # 盈利
        assert tracker.daily_loss == 0.0

    def test_loss_limit_exceeded(self):
        """测试损失限制触发"""
        tracker = DailyLossTracker(loss_limit_pct=0.10)
        equity = 1000.0  # 10% = 100
        
        tracker.record_loss(-50.0)
        assert tracker.is_limit_exceeded(equity) is False
        
        tracker.record_loss(-60.0)  # 总计 110 > 100
        assert tracker.is_limit_exceeded(equity) is True

    def test_remaining_allowance(self):
        """测试剩余可亏损额度"""
        tracker = DailyLossTracker(loss_limit_pct=0.10)
        equity = 1000.0
        
        assert tracker.get_remaining_loss_allowance(equity) == 100.0
        
        tracker.record_loss(-30.0)
        assert tracker.get_remaining_loss_allowance(equity) == 70.0


class TestRiskControlModule:
    """风控模块集成测试"""

    def test_default_config(self):
        """测试默认配置"""
        module = RiskControlModule()
        
        assert module.config.max_order_size == 1000.0
        assert module.config.daily_loss_limit_pct == 0.10

    def test_custom_config(self):
        """测试自定义配置"""
        config = RiskControlConfig(
            max_order_size=500.0,
            daily_loss_limit_pct=0.05
        )
        module = RiskControlModule(config)
        
        assert module.config.max_order_size == 500.0
        assert module.config.daily_loss_limit_pct == 0.05

    def test_can_trade(self):
        """测试交易许可检查"""
        module = RiskControlModule()
        
        can_trade, reason = module.can_trade(equity=1000.0)
        assert can_trade is True
        
        # 模拟大额亏损
        module.record_trade_pnl(-150.0)
        can_trade, reason = module.can_trade(equity=1000.0)
        assert can_trade is False
        assert "损失限制" in reason

    def test_validate_order_disabled(self):
        """测试禁用订单验证"""
        config = RiskControlConfig(enable_order_validation=False)
        module = RiskControlModule(config)
        
        result = module.validate_order(99999.0, "BTC/USDT")
        assert result.is_valid is True
