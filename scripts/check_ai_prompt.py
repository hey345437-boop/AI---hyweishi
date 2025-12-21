#!/usr/bin/env python3
"""
检查 AI 实际使用的提示词

诊断为什么不同 AI 行为差异大
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_config_manager import get_ai_config_manager, PROMPT_PRESETS

def main():
    print("=" * 60)
    print("AI 提示词诊断")
    print("=" * 60)
    
    # 1. 检查数据库中保存的提示词
    config_mgr = get_ai_config_manager()
    
    print("\n【1. 数据库中的自定义提示词】")
    custom_prompt = config_mgr.get_custom_prompt()
    if custom_prompt:
        print(f"长度: {len(custom_prompt)} 字符")
        print(f"前 200 字符:\n{custom_prompt[:200]}...")
    else:
        print("无自定义提示词")
    
    print("\n【2. 可用的预设提示词】")
    for preset_id, preset in PROMPT_PRESETS.items():
        print(f"  - {preset_id}: {preset.name}")
    
    print("\n【3. 冲浪型提示词内容】")
    surf_preset = PROMPT_PRESETS.get('trend_following')
    if surf_preset:
        print(f"名称: {surf_preset.name}")
        print(f"描述: {surf_preset.description}")
        print(f"提示词长度: {len(surf_preset.prompt)} 字符")
        print(f"\n提示词内容:\n{'-' * 40}")
        print(surf_preset.prompt)
        print(f"{'-' * 40}")
    
    print("\n【4. 检查提示词是否包含关键词】")
    if custom_prompt:
        check_prompt = custom_prompt
        print("检查对象: 自定义提示词")
    else:
        check_prompt = surf_preset.prompt if surf_preset else ""
        print("检查对象: 冲浪型预设")
    
    keywords = ["铁律", "【决策步骤】", "Trader）", "RR", "置信度", "风险回报比"]
    for kw in keywords:
        found = kw in check_prompt
        print(f"  - '{kw}': {'✓ 存在' if found else '✗ 不存在'}")
    
    print("\n【5. 检查 BATCH_SYSTEM_PROMPT_TEMPLATE 如何处理提示词】")
    from ai_brain import BATCH_SYSTEM_PROMPT_TEMPLATE
    
    # 模拟构建系统提示词
    if check_prompt and ("铁律" in check_prompt or "【决策步骤】" in check_prompt or "Trader）" in check_prompt):
        user_style = check_prompt
        print("判断结果: 使用完整的用户提示词作为风格")
    else:
        user_style = check_prompt if check_prompt else "均衡策略，追求稳定收益，风险回报比 >= 2.0"
        print("判断结果: 使用默认风格或简短提示词")
    
    final_prompt = BATCH_SYSTEM_PROMPT_TEMPLATE.format(user_style_prompt=user_style)
    print(f"\n最终系统提示词长度: {len(final_prompt)} 字符")
    print(f"\n最终系统提示词:\n{'=' * 40}")
    print(final_prompt)
    print(f"{'=' * 40}")

if __name__ == "__main__":
    main()
