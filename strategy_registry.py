"""策略注册与发现机制

提供稳定的策略 ID、元数据管理与扫描，避免策略混淆。
每个策略通过 manifest.json 或策略类属性定义唯一 strategy_id、display_name、version 等。
UI 使用稳定 strategy_id 而非下拉索引，确保跨刷新一致性。
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
        
        🔥 重要：加载失败时直接抛出异常，禁止静默回退到默认策略
        """
        if strategy_id in self._loaded_strategies:
            return self._loaded_strategies[strategy_id]
        
        meta = self.get_strategy_meta(strategy_id)
        if not meta:
            raise ValueError(f"❌ Strategy '{strategy_id}' not found in registry! 请检查 strategy_registry.py 中的 BUILTIN_STRATEGIES 配置")
        
        file_path = meta.get('file_path')
        class_name = meta.get('class_name')
        
        if not file_path or not class_name:
            raise ValueError(f"❌ Invalid strategy metadata for '{strategy_id}': file_path={file_path}, class_name={class_name}")
        
        # 🔥 检查文件是否存在
        if os.path.isdir(file_path):
            init_path = os.path.join(file_path, '__init__.py')
            if not os.path.isfile(init_path):
                raise FileNotFoundError(f"❌ Missing __init__.py in {file_path}")
            actual_path = init_path
        else:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"❌ Strategy file not found: {file_path}")
            actual_path = file_path
        
        # 动态导入模块
        try:
            spec = importlib.util.spec_from_file_location(strategy_id, actual_path)
            if not spec or not spec.loader:
                raise ImportError(f"❌ Cannot create module spec for: {actual_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            raise ImportError(f"❌ Failed to import strategy module '{strategy_id}' from {actual_path}: {e}")
        
        # 获取策略类
        strategy_class = getattr(module, class_name, None)
        if not strategy_class:
            available_attrs = [attr for attr in dir(module) if not attr.startswith('_')]
            raise AttributeError(f"❌ Class '{class_name}' not found in {actual_path}. Available: {available_attrs[:10]}")
        
        # 🔥 首次加载时打印（后续从缓存读取不会再打印）
        # 使用 logger.debug 避免刷屏
        import logging
        logging.getLogger(__name__).debug(f"[REGISTRY] 策略加载: {strategy_id} -> {class_name}")
        
        self._loaded_strategies[strategy_id] = strategy_class
        return strategy_class
    
    def instantiate_strategy(self, strategy_id: str):
        """实例化指定策略"""
        strategy_class = self.get_strategy_class(strategy_id)
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


def validate_and_fallback_strategy(strategy_id: Optional[str]) -> str:
    """验证 strategy_id，无效或无则返回默认值
    
    返回：有效的 strategy_id
    """
    registry = get_strategy_registry()
    # 如果未选择策略（None/空），返回默认策略
    if not strategy_id:
        return registry.get_default_strategy_id()

    # 如果用户显式选择了一个策略但无效，直接抛出错误，禁止静默回退
    if registry.validate_strategy_id(strategy_id):
        return strategy_id
    raise ValueError(f"Selected strategy_id '{strategy_id}' is invalid or not found in registry")


if __name__ == '__main__':
    # 测试
    registry = get_strategy_registry()
    print("Available strategies:")
    for s in registry.list_strategies():
        print(f"  - {s['display_name']} ({s['strategy_id']}): {s['description']}")
    
    print("\nUI selectbox options:")
    for display_name, strategy_id in list_all_strategies():
        print(f"  - {display_name}: {strategy_id}")
