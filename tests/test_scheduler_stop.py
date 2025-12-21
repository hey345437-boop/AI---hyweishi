"""
测试调度器停止功能

验证：
1. 调度器能正确启动
2. 调度器能正确停止
3. 停止后不再发送请求
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock


class TestSchedulerStop:
    """测试调度器停止功能"""
    
    def test_wait_until_next_candle_interruptible(self):
        """测试 wait_until_next_candle 可以被中断"""
        from arena_scheduler import wait_until_next_candle
        
        stop_event = threading.Event()
        
        # 启动一个线程来等待
        result = {'wait_time': None}
        
        def wait_thread():
            result['wait_time'] = wait_until_next_candle('5m', stop_event)
        
        t = threading.Thread(target=wait_thread)
        t.start()
        
        # 等待 2 秒后发送停止信号
        time.sleep(2)
        stop_event.set()
        
        # 等待线程结束
        t.join(timeout=5)
        
        # 验证被中断（返回 -1）
        assert result['wait_time'] == -1, f"期望返回 -1（被中断），实际返回 {result['wait_time']}"
        assert not t.is_alive(), "线程应该已经结束"
    
    def test_precision_scheduler_stop(self):
        """测试 PrecisionScheduler 能正确停止"""
        from arena_scheduler import PrecisionScheduler, is_scheduler_running, stop_scheduler
        
        # Mock API keys 和其他依赖
        with patch('arena_scheduler.ArenaScheduler') as mock_arena:
            mock_arena.return_value.run_batch_battle_cycle = MagicMock(return_value=[])
            
            # 创建调度器
            scheduler = PrecisionScheduler(
                symbols=['BTC/USDT:USDT'],
                timeframes=['1m'],
                agents=['deepseek'],
                api_keys={'deepseek': 'test_key'}
            )
            
            # 启动
            scheduler.start()
            time.sleep(1)
            
            # 验证正在运行
            assert scheduler.is_running(), "调度器应该正在运行"
            
            # 停止
            scheduler.stop()
            
            # 验证已停止
            assert not scheduler.is_running(), "调度器应该已停止"
    
    def test_global_scheduler_stop(self):
        """测试全局调度器停止功能"""
        from arena_scheduler import (
            start_background_scheduler, 
            stop_scheduler, 
            is_scheduler_running
        )
        
        with patch('arena_scheduler.ArenaScheduler') as mock_arena:
            mock_arena.return_value.run_batch_battle_cycle = MagicMock(return_value=[])
            
            # 启动全局调度器
            start_background_scheduler(
                symbols=['BTC/USDT:USDT'],
                timeframes=['1m'],
                agents=['deepseek'],
                api_keys={'deepseek': 'test_key'}
            )
            
            time.sleep(1)
            
            # 验证正在运行
            assert is_scheduler_running(), "全局调度器应该正在运行"
            
            # 停止
            stop_scheduler()
            
            # 等待停止完成
            time.sleep(2)
            
            # 验证已停止
            assert not is_scheduler_running(), "全局调度器应该已停止"
    
    def test_stop_during_wait(self):
        """测试在等待期间停止"""
        from arena_scheduler import PrecisionScheduler
        
        with patch('arena_scheduler.ArenaScheduler') as mock_arena:
            # 模拟一个慢的分析过程
            async def slow_analysis(*args, **kwargs):
                return []
            
            mock_arena.return_value.run_batch_battle_cycle = slow_analysis
            
            scheduler = PrecisionScheduler(
                symbols=['BTC/USDT:USDT'],
                timeframes=['5m'],  # 5 分钟周期，等待时间较长
                agents=['deepseek'],
                api_keys={'deepseek': 'test_key'}
            )
            
            # 启动
            scheduler.start()
            
            # 等待进入等待状态
            time.sleep(3)
            
            # 记录停止前的时间
            stop_start = time.time()
            
            # 停止
            scheduler.stop()
            
            # 记录停止后的时间
            stop_end = time.time()
            
            # 验证停止时间应该很短（< 5 秒），而不是等待整个周期
            stop_duration = stop_end - stop_start
            assert stop_duration < 5, f"停止耗时 {stop_duration:.1f}s，应该 < 5s"
            
            # 验证已停止
            assert not scheduler.is_running(), "调度器应该已停止"


class TestSchedulerNoRequestAfterStop:
    """测试停止后不再发送请求"""
    
    def test_no_api_calls_after_stop(self):
        """测试停止后不再调用 API"""
        from arena_scheduler import PrecisionScheduler
        
        api_call_count = {'count': 0}
        
        async def mock_analysis(*args, **kwargs):
            api_call_count['count'] += 1
            return []
        
        with patch('arena_scheduler.ArenaScheduler') as mock_arena:
            mock_arena.return_value.run_batch_battle_cycle = mock_analysis
            
            scheduler = PrecisionScheduler(
                symbols=['BTC/USDT:USDT'],
                timeframes=['1m'],
                agents=['deepseek'],
                api_keys={'deepseek': 'test_key'}
            )
            
            # 启动
            scheduler.start()
            
            # 等待首次执行
            time.sleep(2)
            initial_count = api_call_count['count']
            
            # 停止
            scheduler.stop()
            
            # 等待一段时间
            time.sleep(3)
            
            # 验证停止后没有新的 API 调用
            final_count = api_call_count['count']
            assert final_count == initial_count, \
                f"停止后不应有新的 API 调用，初始 {initial_count}，最终 {final_count}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
