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
#
"""
策略注册与发现机制

提供稳定的策略 ID、元数据管理与扫描，避免策略混淆。
"""
import json
import os
import importlib.util
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path


STRATEGIES_DIR = os.path.join(os.path.dirname(__file__), 'strategies')
DEFAULT_STRATEGY_ID = 'strategy_v2'
BUILTIN_STRATEGIES = {
    'strategy_v1': {
        'strategy_id': 'strategy_v1',
        'display_name': '📈 趋势策略 v1',
        'version': '1.0',
        'description': '趋势1.3策略引擎：包含双MACD策略 + 顶底系统 + SMC摆动订单块',
        'class_name': 'TradingStrategyV1',
        'file_path': os.path.join(os.path.dirname(__file__), 'strategy_v1.py'),
        'order': 0
    },
    'strategy_v2': {
        'strategy_id': 'strategy_v2',
        'display_name': '📈 趋势策略 v2',
        'version': '2.0',
        'description': '综合策略引擎：趋势2.3 + 何以为底 + SMC',
        'class_name': 'TradingStrategy',
        'file_path': os.path.join(os.path.dirname(__file__), 'strategy_v2.py'),
        'order': 1
    }
}


class StrategyRegistry:
    """策略注册表：维护所有可用策略的元数据与实例化方法"""
    
    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._loaded_strategies: Dict[str, Any] = {}
        self._scan_and_register()
    
    def _scan_and_register(self):
        """扫描并注册所有策略（内置 + 扩展）"""
        # 注册内置策略
        for strategy_id, meta in BUILTIN_STRATEGIES.items():
            self._registry[strategy_id] = meta.copy()
        
        # 扫描 strategies/ 目录中的扩展策略（如果存在）
        if os.path.isdir(STRATEGIES_DIR):
            self._scan_strategies_dir()
    
    def _scan_strategies_dir(self):
        """扫描 strategies/ 目录"""
        for item in os.listdir(STRATEGIES_DIR):
            item_path = os.path.join(STRATEGIES_DIR, item)
            if os.path.isdir(item_path):
                # 跳过模板策略
                if 'template' in item.lower():
                    continue
                manifest_path = os.path.join(item_path, 'manifest.json')
                if os.path.isfile(manifest_path):
                    try:
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)
                            strategy_id = manifest.get('strategy_id', item)
                            # 跳过模板策略
                            if 'template' in strategy_id.lower():
                                continue
                            manifest['file_path'] = item_path
                            self._registry[strategy_id] = manifest
                    except Exception as e:
                        # 跳过错误的 manifest 文件
                        pass
    
    def list_strategies(self) -> List[Dict[str, Any]]:
        """列出所有可用策略，按 order 字段排序"""
        strategies = list(self._registry.values())
        strategies.sort(key=lambda x: x.get('order', 999))
        return strategies
    
    def get_strategy_meta(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """获取指定策略的元数据"""
        return self._registry.get(strategy_id)
    
    def get_strategy_class(self, strategy_id: str):
        """动态加载并返回指定策略的类
        
         重要：加载失败时直接抛出异常，禁止静默回退到默认策略
        """
        if strategy_id in self._loaded_strategies:
            return self._loaded_strategies[strategy_id]
        
        meta = self.get_strategy_meta(strategy_id)
        if not meta:
            raise ValueError(f" Strategy '{strategy_id}' not found in registry! 请检查 strategy_registry.py 中的 BUILTIN_STRATEGIES 配置")
        
        file_path = meta.get('file_path')
        class_name = meta.get('class_name')
        
        if not file_path or not class_name:
            raise ValueError(f" Invalid strategy metadata for '{strategy_id}': file_path={file_path}, class_name={class_name}")
        
        # 检查文件是否存在
        if os.path.isdir(file_path):
            init_path = os.path.join(file_path, '__init__.py')
            if not os.path.isfile(init_path):
                raise FileNotFoundError(f" Missing __init__.py in {file_path}")
            actual_path = init_path
        else:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f" Strategy file not found: {file_path}")
            actual_path = file_path
        
        # 动态导入模块
        try:
            spec = importlib.util.spec_from_file_location(strategy_id, actual_path)
            if not spec or not spec.loader:
                raise ImportError(f" Cannot create module spec for: {actual_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            raise ImportError(f" Failed to import strategy module '{strategy_id}' from {actual_path}: {e}")
        
        # 获取策略类
        strategy_class = getattr(module, class_name, None)
        if not strategy_class:
            available_attrs = [attr for attr in dir(module) if not attr.startswith('_')]
            raise AttributeError(f" Class '{class_name}' not found in {actual_path}. Available: {available_attrs[:10]}")
        
        # 首次加载时打印（后续从缓存读取不会再打印）
        import logging
        logging.getLogger(__name__).debug(f"[REGISTRY] 策略加载: {strategy_id} -> {class_name}")
        
        self._loaded_strategies[strategy_id] = strategy_class
        return strategy_class
    
    def instantiate_strategy(self, strategy_id: str, config: Dict[str, Any] = None):
        """实例化指定策略
        
        Args:
            strategy_id: 策略 ID
            config: 策略配置参数（可选，会与 manifest 中的 risk_config 合并）
        """
        strategy_class = self.get_strategy_class(strategy_id)
        
        # 获取 manifest 中保存的风控配置
        meta = self.get_strategy_meta(strategy_id)
        saved_config = {}
        if meta:
            saved_config = meta.get('risk_config', {}) or {}
        
        # 合并配置：传入的 config 优先级更高
        final_config = {**saved_config}
        if config:
            final_config.update(config)
        
        # 实例化策略
        if final_config:
            return strategy_class(final_config)
        return strategy_class()
    
    def validate_strategy_id(self, strategy_id: str) -> bool:
        """验证 strategy_id 是否有效"""
        return strategy_id in self._registry
    
    def get_default_strategy_id(self) -> str:
        """获取默认策略 ID"""
        return DEFAULT_STRATEGY_ID


# 全局单例
_registry_instance: Optional[StrategyRegistry] = None


def get_strategy_registry() -> StrategyRegistry:
    """获取全局策略注册表单例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = StrategyRegistry()
    return _registry_instance


def list_all_strategies() -> List[Tuple[str, str]]:
    """获取所有策略的 (display_name, strategy_id) 元组列表，供 UI selectbox 使用"""
    registry = get_strategy_registry()
    strategies = registry.list_strategies()
    return [(s.get('display_name', s['strategy_id']), s['strategy_id']) for s in strategies]


def get_strategy_display_name(strategy_id: str) -> str:
    """获取指定策略的显示名称"""
    registry = get_strategy_registry()
    meta = registry.get_strategy_meta(strategy_id)
    if not meta:
        return strategy_id
    return meta.get('display_name', strategy_id)


def is_custom_strategy(strategy_id: str) -> bool:
    """
    判断是否是用户自定义策略（非内置策略）
    
    Returns:
        True: 用户自定义策略
        False: 内置策略（v1/v2）
    """
    return strategy_id not in BUILTIN_STRATEGIES


def get_strategy_type(strategy_id: str) -> str:
    """
    获取策略类型
    
    Returns:
        'builtin': 内置策略（有主次信号）
        'custom': 用户自定义策略（简单多空信号）
    """
    if strategy_id in BUILTIN_STRATEGIES:
        return 'builtin'
    return 'custom'


def get_strategy_default_params(strategy_id: str) -> Dict[str, Any]:
    """
    获取策略的默认交易参数
    
    Args:
        strategy_id: 策略 ID
    
    Returns:
        默认参数字典
    """
    # 内置策略的默认参数
    builtin_defaults = {
        'strategy_v1': {
            'position_pct': 3.0,
            'leverage': 20,
            'stop_loss_pct': 2.0,
            'take_profit_pct': 0
        },
        'strategy_v2': {
            'position_pct': 3.0,
            'leverage': 20,
            'stop_loss_pct': 2.0,
            'take_profit_pct': 0
        }
    }
    
    if strategy_id in builtin_defaults:
        return builtin_defaults[strategy_id]
    
    # 用户自定义策略：从 manifest.json 读取
    registry = get_strategy_registry()
    meta = registry.get_strategy_meta(strategy_id)
    
    if meta and 'default_params' in meta:
        return meta['default_params']
    
    return {
        'position_pct': 2.0,
        'leverage': 50,
        'stop_loss_pct': 2.0,
        'take_profit_pct': 0
    }


def validate_and_fallback_strategy(strategy_id: Optional[str]) -> str:
    """验证 strategy_id，无效或无则返回默认值"""
    registry = get_strategy_registry()
    if not strategy_id:
        return registry.get_default_strategy_id()

    if registry.validate_strategy_id(strategy_id):
        return strategy_id
    raise ValueError(f"Selected strategy_id '{strategy_id}' is invalid or not found in registry")



def save_new_strategy(strategy_id: str, display_name: str, code: str, description: str = "", 
                      config: Dict[str, Any] = None, is_advanced: bool = False) -> Dict[str, Any]:
    """
    保存新策略到 strategies/ 目录
    
    Args:
        strategy_id: 策略唯一标识（小写字母、数字、下划线）
        display_name: 显示名称
        code: Python 策略代码
        description: 策略描述
        config: 高级策略的风控配置参数（可选）
        is_advanced: 是否是高级策略（支持动态止盈止损）
    
    Returns:
        {"success": True/False, "error": "..."}
    """
    import re
    from datetime import datetime
    
    # 1. 验证 strategy_id 格式
    if not re.match(r'^[a-z][a-z0-9_]*$', strategy_id):
        return {"success": False, "error": "策略 ID 必须以小写字母开头，只能包含小写字母、数字和下划线"}
    
    # 2. 检查 strategy_id 唯一性
    registry = get_strategy_registry()
    if registry.validate_strategy_id(strategy_id):
        return {"success": False, "error": f"策略 ID '{strategy_id}' 已存在"}
    
    # 3. 从代码中提取类名
    class_name = _extract_class_name(code)
    if not class_name:
        return {"success": False, "error": "未能从代码中找到策略类定义"}
    
    # 3.1 从代码中提取默认参数
    default_params = _extract_default_params(code)
    
    # 4. 创建策略目录
    strategy_dir = os.path.join(STRATEGIES_DIR, strategy_id)
    try:
        os.makedirs(strategy_dir, exist_ok=True)
    except Exception as e:
        return {"success": False, "error": f"创建目录失败: {str(e)}"}
    
    # 5. 写入 __init__.py
    init_path = os.path.join(strategy_dir, '__init__.py')
    try:
        with open(init_path, 'w', encoding='utf-8') as f:
            f.write(code)
    except Exception as e:
        return {"success": False, "error": f"写入代码文件失败: {str(e)}"}
    
    # 6. 写入 manifest.json
    manifest = {
        "strategy_id": strategy_id,
        "display_name": f"🔧 {display_name}",
        "class_name": class_name,
        "description": description,
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "order": 100,
        "is_advanced": is_advanced,
        "default_params": {
            "position_pct": default_params.get('position_pct', 2.0),
            "leverage": default_params.get('leverage', 50 if not is_advanced else 5),
            "stop_loss_pct": default_params.get('stop_loss_pct', 2.0),
            "take_profit_pct": default_params.get('take_profit_pct', 0)
        }
    }
    
    # 高级策略：保存风控配置
    if is_advanced and config:
        manifest["risk_config"] = config
    
    manifest_path = os.path.join(strategy_dir, 'manifest.json')
    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return {"success": False, "error": f"写入 manifest 失败: {str(e)}"}
    
    # 7. 刷新注册表
    _refresh_registry()
    
    return {"success": True, "strategy_id": strategy_id, "is_advanced": is_advanced}


def _extract_class_name(code: str) -> Optional[str]:
    """从代码中提取策略类名（优先返回 Wrapper 类）"""
    import ast
    try:
        tree = ast.parse(code)
        class_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_names.append(node.name)
        
        # 优先返回 Wrapper 类（交易引擎需要实例化 Wrapper）
        for name in class_names:
            if 'Wrapper' in name:
                return name
        
        # 其次返回第一个类
        if class_names:
            return class_names[0]
    except:
        pass
    return None


def _extract_default_params(code: str) -> Dict[str, Any]:
    """从策略代码中提取默认参数"""
    import ast
    import re
    
    params = {}
    
    # 方法1：使用 AST 解析
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id == 'self':
                            attr_name = target.attr
                            if isinstance(node.value, ast.Constant):
                                if attr_name in ['position_pct', 'leverage', 'stop_loss_pct', 'take_profit_pct']:
                                    params[attr_name] = node.value.value
                            elif isinstance(node.value, ast.Num):
                                if attr_name in ['position_pct', 'leverage', 'stop_loss_pct', 'take_profit_pct']:
                                    params[attr_name] = node.value.n
    except:
        pass
    
    # 方法2：正则表达式兜底
    if not params:
        patterns = [
            (r'self\.position_pct\s*=\s*([\d.]+)', 'position_pct'),
            (r'self\.leverage\s*=\s*(\d+)', 'leverage'),
            (r'self\.stop_loss_pct\s*=\s*([\d.]+)', 'stop_loss_pct'),
            (r'self\.take_profit_pct\s*=\s*([\d.]+)', 'take_profit_pct'),
        ]
        for pattern, key in patterns:
            match = re.search(pattern, code)
            if match:
                value = match.group(1)
                params[key] = float(value) if '.' in value else int(value)
    
    return params


def _refresh_registry():
    """刷新策略注册表"""
    global _registry_instance
    _registry_instance = None
    get_strategy_registry()


def delete_strategy(strategy_id: str) -> Dict[str, Any]:
    """删除用户创建的策略"""
    import shutil
    
    if strategy_id in BUILTIN_STRATEGIES:
        return {"success": False, "error": "不能删除内置策略"}
    
    registry = get_strategy_registry()
    if not registry.validate_strategy_id(strategy_id):
        return {"success": False, "error": f"策略 '{strategy_id}' 不存在"}
    
    strategy_dir = os.path.join(STRATEGIES_DIR, strategy_id)
    if not os.path.isdir(strategy_dir):
        return {"success": False, "error": f"策略目录不存在: {strategy_dir}"}
    
    try:
        shutil.rmtree(strategy_dir)
    except Exception as e:
        return {"success": False, "error": f"删除失败: {str(e)}"}
    
    _refresh_registry()
    
    return {"success": True, "strategy_id": strategy_id}


def list_user_strategies() -> List[Dict[str, Any]]:
    """列出用户创建的策略"""
    registry = get_strategy_registry()
    all_strategies = registry.list_strategies()
    
    user_strategies = []
    for s in all_strategies:
        if s['strategy_id'] not in BUILTIN_STRATEGIES:
            user_strategies.append({
                "strategy_id": s['strategy_id'],
                "display_name": s.get('display_name', s['strategy_id']),
                "description": s.get('description', ''),
                "created_at": s.get('created_at', ''),
                "version": s.get('version', '1.0.0'),
                "is_advanced": s.get('is_advanced', False)
            })
    
    return user_strategies


def is_advanced_strategy(strategy_id: str) -> bool:
    """判断是否是高级策略（支持动态止盈止损）"""
    registry = get_strategy_registry()
    meta = registry.get_strategy_meta(strategy_id)
    if meta:
        return meta.get('is_advanced', False)
    return False


def get_strategy_risk_config(strategy_id: str) -> Optional[Dict[str, Any]]:
    """获取高级策略的风控配置"""
    registry = get_strategy_registry()
    meta = registry.get_strategy_meta(strategy_id)
    if meta:
        return meta.get('risk_config')
    return None


if __name__ == '__main__':
    # 测试
    registry = get_strategy_registry()
    print("Available strategies:")
    for s in registry.list_strategies():
        print(f"  - {s['display_name']} ({s['strategy_id']}): {s['description']}")
    
    print("\nUI selectbox options:")
    for display_name, strategy_id in list_all_strategies():
        print(f"  - {display_name}: {strategy_id}")
