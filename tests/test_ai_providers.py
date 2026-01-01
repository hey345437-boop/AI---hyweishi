# -*- coding: utf-8 -*-
"""
AI 服务商适配器测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.ai_providers import (
    AI_PROVIDERS,
    get_available_providers,
    get_provider,
    get_provider_models,
    get_free_models,
    get_default_model,
    get_all_provider_ids,
    quick_validate_key_format,
    PROVIDER_ALIASES,
)


class TestAIProviders:
    """AI 服务商测试"""

    def test_providers_defined(self):
        """测试服务商已定义"""
        providers = get_available_providers()
        
        assert len(providers) >= 10
        assert 'deepseek' in providers
        assert 'qwen' in providers
        assert 'spark' in providers
        assert 'openai' in providers
        assert 'claude' in providers

    def test_provider_structure(self):
        """测试服务商结构完整"""
        for provider_id, provider in AI_PROVIDERS.items():
            assert provider.id == provider_id
            assert provider.name
            assert provider.api_base
            assert len(provider.models) > 0
            assert provider.default_model

    def test_get_provider(self):
        """测试获取服务商"""
        provider = get_provider('deepseek')
        assert provider is not None
        assert provider.id == 'deepseek'
        assert provider.name == 'DeepSeek'

    def test_get_provider_with_alias(self):
        """测试别名获取"""
        # spark_lite 应该映射到 spark
        if 'spark_lite' in PROVIDER_ALIASES:
            provider = get_provider('spark_lite')
            assert provider is not None
            assert provider.id == 'spark'

    def test_get_nonexistent_provider(self):
        """测试获取不存在的服务商"""
        provider = get_provider('nonexistent')
        assert provider is None

    def test_get_provider_models(self):
        """测试获取服务商模型"""
        models = get_provider_models('deepseek')
        
        assert len(models) >= 1
        model_ids = [m.id for m in models]
        assert 'deepseek-chat' in model_ids

    def test_get_free_models(self):
        """测试获取免费模型"""
        free_models = get_free_models()
        
        assert len(free_models) >= 3
        
        # 检查格式 (provider_id, AIModel)
        for provider_id, model in free_models:
            assert isinstance(provider_id, str)
            assert model.is_free is True

    def test_get_default_model(self):
        """测试获取默认模型"""
        default = get_default_model('deepseek')
        assert default == 'deepseek-chat'
        
        default = get_default_model('qwen')
        assert 'qwen' in default.lower()

    def test_get_all_provider_ids(self):
        """测试获取所有服务商 ID"""
        ids = get_all_provider_ids()
        
        assert len(ids) >= 10
        assert 'deepseek' in ids
        assert 'qwen' in ids
        assert 'openai' in ids


class TestKeyValidation:
    """API Key 格式验证测试"""

    def test_valid_deepseek_key(self):
        """测试有效的 DeepSeek Key 格式"""
        valid, msg = quick_validate_key_format('deepseek', 'sk-1234567890abcdef')
        assert valid is True

    def test_invalid_deepseek_key_prefix(self):
        """测试无效的 DeepSeek Key 前缀"""
        valid, msg = quick_validate_key_format('deepseek', 'invalid-key-format')
        assert valid is False
        assert 'sk-' in msg

    def test_short_key(self):
        """测试过短的 Key"""
        valid, msg = quick_validate_key_format('deepseek', 'sk-123')
        assert valid is False
        assert '太短' in msg

    def test_empty_key(self):
        """测试空 Key"""
        valid, msg = quick_validate_key_format('deepseek', '')
        assert valid is False

    def test_provider_without_prefix(self):
        """测试无前缀要求的服务商"""
        # spark 没有前缀要求
        valid, msg = quick_validate_key_format('spark', 'any_valid_key_here')
        assert valid is True
