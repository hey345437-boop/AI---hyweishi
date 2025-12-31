# -*- coding: utf-8 -*-
# ============================================================================
#
#    _   _  __   __ __        __  _____ ___  ____   _   _  ___ 
#   | | | | \ \ / / \ \      / / | ____||_ _|/ ___| | | | ||_ _|
#   | |_| |  \ V /   \ \ /\ / /  |  _|   | | \___ \ | |_| | | | 
#   |  _  |   | |     \ V  V /   | |___  | |  ___) ||  _  | | | 
#   |_| |_|   |_|      \_/\_/    |_____||___||____/ |_| |_||___|
#
#                         何 以 为 势
#                  Quantitative Trading System
#
#   Copyright (c) 2024-2025 HeWeiShi. All Rights Reserved.
#   License: Apache License 2.0
#
# ============================================================================
"""
强制停止 AI 竞技场

当正常停止无法工作时使用此脚本
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def force_stop():
    """强制停止调度器"""
    print("=" * 50)
    print("强制停止 AI 竞技场")
    print("=" * 50)
    
    try:
        from arena_scheduler import (
            stop_scheduler,
            is_scheduler_running,
            _precision_scheduler
        )
        
        # 检查状态
        running = is_scheduler_running()
        print(f"调度器运行状态: {'运行中' if running else '已停止'}")
        
        if running:
            print("\n正在停止调度器...")
            stop_scheduler()
            print(" 停止命令已发送")
        
        # 清除持久化状态
        try:
            from ai_config_manager import get_ai_config_manager
            config_mgr = get_ai_config_manager()
            config_mgr.clear_scheduler_state()
            print(" 已清除持久化状态")
        except Exception as e:
            print(f"⚠️ 清除持久化状态失败: {e}")
        
        # 再次检查
        running = is_scheduler_running()
        print(f"\n最终状态: {'运行中' if running else '已停止'}")
        
        if running:
            print("\n⚠️ 调度器仍在运行，可能需要重启 Streamlit 应用")
            print("建议: 按 Ctrl+C 停止 Streamlit，然后重新启动")
        
    except Exception as e:
        print(f" 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    force_stop()
