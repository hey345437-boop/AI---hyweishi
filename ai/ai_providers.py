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
AI 大模型统一适配器 - 唯一的 AI API 调用层

支持的服务商（2024年12月最新版本）：
- DeepSeek (deepseek-chat, deepseek-reasoner)
- 通义千问 Qwen (qwen-turbo-latest, qwen-plus-latest, qwen-max-latest)
- 讯飞星火 Spark (spark-lite, spark4.0-ultra)
- 腾讯混元 Hunyuan (hunyuan-lite, hunyuan-turbo-latest)
- 火山引擎豆包 Doubao (doubao-1.5-pro-32k, doubao-1.5-lite-32k)
- 智谱 GLM (glm-4-flash, glm-4-plus, glm-4-0520)
- Perplexity (sonar, sonar-pro, sonar-reasoning)
- OpenAI (gpt-4o, gpt-4o-mini, o1, o1-mini)
- Claude (claude-3-5-sonnet, claude-3-5-haiku)
- Grok (grok-2, grok-2-mini)
- Gemini (gemini-2.0-flash, gemini-1.5-pro)

所有其他模块（ai_brain, ai_api_validator, strategy_generator 等）
都应该调用此模块，不要重复实现 API 调用逻辑。
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AIModel:
    """AI 模型定义"""
    id: str                    # 模型 ID（用于 API 调用）
    name: str                  # 显示名称
    is_free: bool = False      # 是否免费
    max_tokens: int = 4096     # 最大输出 tokens
    context_length: int = 8192 # 上下文长度
    description: str = ""      # 描述


@dataclass
class AIProvider:
    """AI 服务商定义"""
    id: str                    # 服务商 ID
    name: str                  # 显示名称
    api_base: str              # API 基础 URL
    api_type: str = "openai"   # API 类型: openai, anthropic, google
    key_prefix: str = ""       # API Key 前缀（用于验证）
    key_env: str = ""          # 环境变量名
    models: List[AIModel] = field(default_factory=list)
    default_model: str = ""    # 默认模型
    headers_builder: str = "bearer"  # 请求头构建方式: bearer, anthropic, google
    description: str = ""      # 描述


# ============================================================================
# AI 服务商和模型定义 - 2025年12月最新版本
# ============================================================================

AI_PROVIDERS: Dict[str, AIProvider] = {
    # DeepSeek - 国产高性能大模型 (V3.1 最新)
    "deepseek": AIProvider(
        id="deepseek",
        name="DeepSeek",
        api_base="https://api.deepseek.com/v1",
        api_type="openai",
        key_prefix="sk-",
        key_env="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        description="深度求索，国产高性能大模型 V3.1",
        models=[
            AIModel("deepseek-chat", "DeepSeek V3.1 Chat", max_tokens=8192, context_length=128000, description="V3.1 非思考模式"),
            AIModel("deepseek-reasoner", "DeepSeek V3.1 Reasoner", max_tokens=8192, context_length=128000, description="V3.1 思考模式/R1"),
        ]
    ),
    
    # 通义千问 - 阿里云 (Qwen 3 系列)
    "qwen": AIProvider(
        id="qwen",
        name="通义千问",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_type="openai",
        key_prefix="sk-",
        key_env="DASHSCOPE_API_KEY",
        default_model="qwen-plus-latest",
        description="阿里云通义千问 Qwen 3 系列",
        models=[
            AIModel("qwen-turbo-latest", "Qwen Turbo", max_tokens=8192, context_length=131072, description="快速响应"),
            AIModel("qwen-plus-latest", "Qwen Plus", max_tokens=8192, context_length=131072, description="性价比之选"),
            AIModel("qwen-max-latest", "Qwen Max", max_tokens=8192, context_length=32000, description="最强模型"),
            AIModel("qwen-long", "Qwen Long", max_tokens=6000, context_length=10000000, description="超长上下文"),
            AIModel("qwq-plus-latest", "QwQ Plus", max_tokens=16384, context_length=131072, description="深度思考模型"),
            AIModel("qwen3-235b-a22b", "Qwen 3 235B", max_tokens=8192, context_length=131072, description="Qwen 3 旗舰"),
        ]
    ),

    # 讯飞星火 - 科大讯飞 (Spark 4.0 Ultra)
    "spark": AIProvider(
        id="spark",
        name="讯飞星火",
        api_base="https://spark-api-open.xf-yun.com/v1",
        api_type="openai",
        key_prefix="",
        key_env="SPARK_API_PASSWORD",
        default_model="4.0Ultra",
        description="科大讯飞星火认知大模型 4.0",
        models=[
            AIModel("lite", "Spark Lite", is_free=True, max_tokens=4096, context_length=4096, description="免费轻量版"),
            AIModel("generalv3", "Spark V3.0", max_tokens=8192, context_length=8192, description="V3.0 基础版"),
            AIModel("generalv3.5", "Spark Max 3.5", max_tokens=8192, context_length=128000, description="Max 3.5 版本"),
            AIModel("pro-128k", "Spark Pro 128K", max_tokens=4096, context_length=128000, description="长上下文专业版"),
            AIModel("max-32k", "Spark Max 32K", max_tokens=8192, context_length=32000, description="Max 32K 版本"),
            AIModel("4.0Ultra", "Spark 4.0 Ultra", max_tokens=8192, context_length=128000, description="最新旗舰 4.0"),
        ]
    ),
    
    # 腾讯混元 (Turbo Latest)
    "hunyuan": AIProvider(
        id="hunyuan",
        name="腾讯混元",
        api_base="https://api.hunyuan.cloud.tencent.com/v1",
        api_type="openai",
        key_prefix="",
        key_env="HUNYUAN_API_KEY",
        default_model="hunyuan-lite",
        description="腾讯混元大模型",
        models=[
            AIModel("hunyuan-lite", "混元 Lite", is_free=True, max_tokens=4096, context_length=256000, description="免费版"),
            AIModel("hunyuan-standard-256K", "混元 Standard 256K", max_tokens=6000, context_length=256000, description="长上下文"),
            AIModel("hunyuan-turbo-latest", "混元 Turbo", max_tokens=4096, context_length=32000, description="最新高性能版"),
            AIModel("hunyuan-pro", "混元 Pro", max_tokens=4096, context_length=32000, description="专业版"),
        ]
    ),
    
    # 火山引擎豆包 - 字节跳动 (Doubao 1.8)
    "doubao": AIProvider(
        id="doubao",
        name="火山豆包",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        api_type="openai",
        key_prefix="",
        key_env="DOUBAO_API_KEY",
        default_model="doubao-1.5-pro-32k",
        description="字节跳动火山引擎豆包大模型 1.8",
        models=[
            AIModel("doubao-1.5-lite-32k", "豆包 1.5 Lite 32K", max_tokens=4096, context_length=32000, description="轻量版"),
            AIModel("doubao-1.5-pro-32k", "豆包 1.5 Pro 32K", max_tokens=4096, context_length=32000, description="专业版"),
            AIModel("doubao-1.5-pro-256k", "豆包 1.5 Pro 256K", max_tokens=4096, context_length=256000, description="超长上下文"),
            AIModel("doubao-seed-1.6", "豆包 Seed 1.6", max_tokens=16384, context_length=256000, description="思考模型"),
        ]
    ),

    # 智谱 GLM (GLM-4.6/4.7)
    "glm": AIProvider(
        id="glm",
        name="智谱 GLM",
        api_base="https://open.bigmodel.cn/api/paas/v4",
        api_type="openai",
        key_prefix="",
        key_env="GLM_API_KEY",
        default_model="glm-4-flash",
        description="智谱AI GLM-4 系列大模型",
        models=[
            AIModel("glm-4-flash", "GLM-4 Flash", is_free=True, max_tokens=4096, context_length=128000, description="免费快速版"),
            AIModel("glm-4-air", "GLM-4 Air", max_tokens=4096, context_length=128000, description="轻量版"),
            AIModel("glm-4-plus", "GLM-4 Plus", max_tokens=4096, context_length=128000, description="增强版"),
            AIModel("glm-4-long", "GLM-4 Long", max_tokens=4096, context_length=1000000, description="超长上下文"),
            AIModel("glm-4.6", "GLM-4.6", max_tokens=16384, context_length=128000, description="最新 4.6 版本"),
        ]
    ),
    
    # Perplexity - 联网搜索
    "perplexity": AIProvider(
        id="perplexity",
        name="Perplexity",
        api_base="https://api.perplexity.ai",
        api_type="openai",
        key_prefix="pplx-",
        key_env="PERPLEXITY_API_KEY",
        default_model="sonar",
        description="Perplexity AI，支持联网搜索",
        models=[
            AIModel("sonar", "Sonar", max_tokens=4096, context_length=128000, description="标准联网模型"),
            AIModel("sonar-pro", "Sonar Pro", max_tokens=8192, context_length=200000, description="高级联网模型"),
            AIModel("sonar-reasoning", "Sonar Reasoning", max_tokens=8192, context_length=128000, description="推理增强"),
        ]
    ),
    
    # OpenAI (GPT-5.2, o3, o4-mini, GPT-4o) - 2025年12月最新
    "openai": AIProvider(
        id="openai",
        name="OpenAI",
        api_base="https://api.openai.com/v1",
        api_type="openai",
        key_prefix="sk-",
        key_env="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
        description="OpenAI GPT/o 系列 (含 GPT-5.2)",
        models=[
            AIModel("gpt-4o-mini", "GPT-4o Mini", max_tokens=16384, context_length=128000, description="轻量高效"),
            AIModel("gpt-4o", "GPT-4o", max_tokens=16384, context_length=128000, description="多模态旗舰"),
            AIModel("gpt-4-turbo", "GPT-4 Turbo", max_tokens=4096, context_length=128000, description="GPT-4 高速版"),
            AIModel("chatgpt-4o-latest", "ChatGPT-4o Latest", max_tokens=16384, context_length=128000, description="ChatGPT 最新"),
            AIModel("o1-mini", "o1 Mini", max_tokens=65536, context_length=128000, description="推理模型轻量版"),
            AIModel("o1", "o1", max_tokens=100000, context_length=200000, description="推理模型"),
            AIModel("o3-mini", "o3 Mini", max_tokens=100000, context_length=200000, description="o3 轻量版"),
            AIModel("o3", "o3", max_tokens=100000, context_length=200000, description="o3 推理旗舰"),
            AIModel("o4-mini", "o4 Mini", max_tokens=100000, context_length=200000, description="o4 轻量版"),
            AIModel("gpt-5", "GPT-5", max_tokens=32768, context_length=256000, description="GPT-5 基础版"),
            AIModel("gpt-5.2", "GPT-5.2", max_tokens=32768, context_length=256000, description="GPT-5.2 最新旗舰"),
        ]
    ),

    # Claude - Anthropic (Claude 4.5 系列)
    "claude": AIProvider(
        id="claude",
        name="Claude",
        api_base="https://api.anthropic.com/v1",
        api_type="anthropic",
        key_prefix="sk-ant-",
        key_env="ANTHROPIC_API_KEY",
        default_model="claude-3-5-haiku-latest",
        headers_builder="anthropic",
        description="Anthropic Claude 4.5 系列",
        models=[
            AIModel("claude-3-5-haiku-latest", "Claude 3.5 Haiku", max_tokens=8192, context_length=200000, description="快速版"),
            AIModel("claude-3-5-sonnet-latest", "Claude 3.5 Sonnet", max_tokens=8192, context_length=200000, description="平衡版"),
            AIModel("claude-3-opus-latest", "Claude 3 Opus", max_tokens=4096, context_length=200000, description="强力版"),
            AIModel("claude-sonnet-4-5-latest", "Claude Sonnet 4.5", max_tokens=16384, context_length=200000, description="最新 Sonnet"),
            AIModel("claude-opus-4-5-latest", "Claude Opus 4.5", max_tokens=16384, context_length=200000, description="最新旗舰"),
        ]
    ),
    
    # Grok - xAI (Grok 4)
    "grok": AIProvider(
        id="grok",
        name="Grok",
        api_base="https://api.x.ai/v1",
        api_type="openai",
        key_prefix="xai-",
        key_env="XAI_API_KEY",
        default_model="grok-2-latest",
        description="xAI Grok 4 系列",
        models=[
            AIModel("grok-2-latest", "Grok 2", max_tokens=131072, context_length=131072, description="Grok 2 稳定版"),
            AIModel("grok-3", "Grok 3", max_tokens=131072, context_length=1000000, description="Grok 3"),
            AIModel("grok-3-mini", "Grok 3 Mini", max_tokens=131072, context_length=131072, description="Grok 3 轻量版"),
            AIModel("grok-4", "Grok 4", max_tokens=131072, context_length=256000, description="最新旗舰"),
            AIModel("grok-4-fast-reasoning", "Grok 4 Fast Reasoning", max_tokens=131072, context_length=2000000, description="快速推理"),
        ]
    ),
    
    # Gemini - Google (Gemini 3 Pro)
    "gemini": AIProvider(
        id="gemini",
        name="Gemini",
        api_base="https://generativelanguage.googleapis.com/v1beta",
        api_type="google",
        key_prefix="",
        key_env="GOOGLE_API_KEY",
        default_model="gemini-2.0-flash",
        headers_builder="google",
        description="Google Gemini 3 系列",
        models=[
            AIModel("gemini-2.0-flash", "Gemini 2.0 Flash", is_free=True, max_tokens=8192, context_length=1048576, description="2.0 快速版"),
            AIModel("gemini-2.5-flash", "Gemini 2.5 Flash", is_free=True, max_tokens=8192, context_length=1048576, description="2.5 快速版"),
            AIModel("gemini-2.5-pro", "Gemini 2.5 Pro", max_tokens=8192, context_length=1048576, description="2.5 专业版"),
            AIModel("gemini-3-pro-preview", "Gemini 3 Pro", max_tokens=65536, context_length=1048576, description="最新 3 Pro"),
        ]
    ),
}

# 兼容旧的 ID 映射
PROVIDER_ALIASES = {
    "spark_lite": "spark",
    "gpt": "openai",
}


# ============================================================================
# 通用 AI 客户端 - 唯一的 API 调用实现
# ============================================================================

def _detect_proxy() -> Optional[str]:
    """自动检测可用的代理"""
    import os
    import socket
    
    # 1. 优先使用环境变量
    for env_var in ['HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy']:
        proxy = os.environ.get(env_var)
        if proxy:
            return proxy
    
    # 2. 检测常用代理端口
    proxy_ports = [
        (49494, 'http'),  # Clash Verge 自定义端口
        (7890, 'http'),   # Clash 默认
        (7897, 'http'),   # Clash Verge 默认
        (1080, 'socks5'), # 通用 SOCKS5
    ]
    
    for port, protocol in proxy_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                if protocol == 'socks5':
                    return f"socks5://127.0.0.1:{port}"
                return f"http://127.0.0.1:{port}"
        except:
            pass
    
    return None


class UniversalAIClient:
    """
    通用 AI 客户端 - 所有 AI API 调用的唯一入口
    
    支持所有已注册的 AI 服务商，统一接口调用
    自动检测并使用代理
    """
    
    def __init__(self, provider_id: str, api_key: str, model_id: str = None):
        """
        初始化 AI 客户端
        
        Args:
            provider_id: 服务商 ID
            api_key: API Key
            model_id: 模型 ID，不指定则使用默认模型
        """
        # 处理别名
        provider_id = PROVIDER_ALIASES.get(provider_id, provider_id)
        
        self.provider = AI_PROVIDERS.get(provider_id)
        if not self.provider:
            raise ValueError(f"不支持的 AI 服务商: {provider_id}")
        
        self.api_key = api_key
        self.model_id = model_id or self.provider.default_model
        self.timeout = 60
        
        # 自动检测代理
        self.proxy = _detect_proxy()
        if self.proxy:
            logger.debug(f"[{self.provider.name}] 使用代理: {self.proxy}")
        
        # 验证模型是否存在
        model_ids = [m.id for m in self.provider.models]
        if self.model_id not in model_ids:
            logger.warning(f"模型 {self.model_id} 不在已知列表中，将尝试使用")
    
    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        if self.provider.headers_builder == "anthropic":
            return {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
        elif self.provider.headers_builder == "google":
            return {
                "Content-Type": "application/json"
            }
        else:
            # 默认 Bearer Token (OpenAI 兼容)
            return {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
    
    def _build_payload(self, messages: List[Dict], max_tokens: int = 4096, temperature: float = 0.3) -> Dict:
        """构建请求体"""
        if self.provider.api_type == "anthropic":
            return {
                "model": self.model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }
        elif self.provider.api_type == "google":
            # Gemini 格式
            contents = []
            for msg in messages:
                role = "user" if msg["role"] in ["user", "system"] else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
            return {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens
                }
            }
        else:
            # OpenAI 兼容格式
            return {
                "model": self.model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }

    def _get_endpoint(self) -> str:
        """获取 API 端点"""
        if self.provider.api_type == "anthropic":
            return f"{self.provider.api_base}/messages"
        elif self.provider.api_type == "google":
            return f"{self.provider.api_base}/models/{self.model_id}:generateContent?key={self.api_key}"
        else:
            return f"{self.provider.api_base}/chat/completions"
    
    def _parse_response(self, data: Dict) -> str:
        """解析响应"""
        if self.provider.api_type == "anthropic":
            content = data.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")
            return ""
        elif self.provider.api_type == "google":
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return ""
        else:
            # OpenAI 兼容格式
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return ""
    
    def _clean_response(self, content: str) -> str:
        """清理响应内容（移除 think 标签等）"""
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return content
    
    def chat(self, prompt: str, system_prompt: str = None, max_tokens: int = 4096, temperature: float = 0.3) -> str:
        """
        发送聊天请求（同步）
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            max_tokens: 最大输出 tokens
            temperature: 温度参数
        
        Returns:
            AI 响应内容
        """
        import httpx
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = self._build_headers()
        payload = self._build_payload(messages, max_tokens, temperature)
        endpoint = self._get_endpoint()
        
        try:
            # 配置代理
            transport = None
            if self.proxy:
                transport = httpx.HTTPTransport(proxy=self.proxy)
            
            with httpx.Client(timeout=self.timeout, transport=transport) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = self._parse_response(data)
                return self._clean_response(content)
        except httpx.HTTPStatusError as e:
            logger.error(f"[{self.provider.name}] HTTP 错误: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"[{self.provider.name}] 请求失败: {e}")
            raise

    async def chat_async(self, prompt: str, system_prompt: str = None, max_tokens: int = 4096, temperature: float = 0.3) -> str:
        """
        发送聊天请求（异步）
        """
        import httpx
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = self._build_headers()
        payload = self._build_payload(messages, max_tokens, temperature)
        endpoint = self._get_endpoint()
        
        try:
            # 配置代理
            transport = None
            if self.proxy:
                transport = httpx.AsyncHTTPTransport(proxy=self.proxy)
            
            async with httpx.AsyncClient(timeout=self.timeout, transport=transport) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = self._parse_response(data)
                return self._clean_response(content)
        except httpx.HTTPStatusError as e:
            logger.error(f"[{self.provider.name}] HTTP 错误: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"[{self.provider.name}] 请求失败: {e}")
            raise
    
    def chat_with_messages(self, messages: List[Dict], max_tokens: int = 4096, temperature: float = 0.3) -> str:
        """
        使用完整消息列表发送请求（同步）
        """
        import httpx
        
        headers = self._build_headers()
        payload = self._build_payload(messages, max_tokens, temperature)
        endpoint = self._get_endpoint()
        
        try:
            # 配置代理
            transport = None
            if self.proxy:
                transport = httpx.HTTPTransport(proxy=self.proxy)
            
            with httpx.Client(timeout=self.timeout, transport=transport) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = self._parse_response(data)
                return self._clean_response(content)
        except Exception as e:
            logger.error(f"[{self.provider.name}] 请求失败: {e}")
            raise
    
    async def chat_with_messages_async(self, messages: List[Dict], max_tokens: int = 4096, temperature: float = 0.3) -> str:
        """
        使用完整消息列表发送请求（异步）
        """
        import httpx
        
        headers = self._build_headers()
        payload = self._build_payload(messages, max_tokens, temperature)
        endpoint = self._get_endpoint()
        
        try:
            # 配置代理
            transport = None
            if self.proxy:
                transport = httpx.AsyncHTTPTransport(proxy=self.proxy)
            
            async with httpx.AsyncClient(timeout=self.timeout, transport=transport) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = self._parse_response(data)
                return self._clean_response(content)
        except Exception as e:
            logger.error(f"[{self.provider.name}] 请求失败: {e}")
            raise


# ============================================================================
# API Key 验证 - 统一验证入口
# ============================================================================

async def verify_api_key(provider_id: str, api_key: str) -> Tuple[bool, str]:
    """
    验证 API Key（异步）
    
    Args:
        provider_id: 服务商 ID
        api_key: API Key
    
    Returns:
        (是否有效, 消息)
    """
    provider_id = PROVIDER_ALIASES.get(provider_id, provider_id)
    provider = AI_PROVIDERS.get(provider_id)
    
    if not provider:
        return False, f"不支持的服务商: {provider_id}"
    
    # 检查 Key 前缀
    if provider.key_prefix and not api_key.startswith(provider.key_prefix):
        return False, f"{provider.name} Key 应以 {provider.key_prefix} 开头"
    
    # 尝试调用 API
    try:
        client = UniversalAIClient(provider_id, api_key)
        client.timeout = 15
        
        # 发送最小请求
        response = await client.chat_async("hi", max_tokens=1)
        
        if response is not None:
            return True, f"{provider.name} API Key 验证成功"
        else:
            return True, f"{provider.name} API Key 验证成功（空响应）"
            
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg.lower():
            return False, f"{provider.name} API Key 无效"
        elif "403" in error_msg:
            return False, f"{provider.name} API Key 权限不足"
        elif "timeout" in error_msg.lower():
            return False, f"{provider.name} API 连接超时"
        elif "400" in error_msg:
            # 400 可能是请求格式问题，但 Key 可能是有效的
            return True, f"{provider.name} API Key 验证成功（格式警告）"
        else:
            return False, f"{provider.name} 验证失败: {error_msg[:50]}"


def verify_api_key_sync(provider_id: str, api_key: str) -> Tuple[bool, str]:
    """验证 API Key（同步版本）"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, verify_api_key(provider_id, api_key))
                return future.result(timeout=20)
        else:
            return loop.run_until_complete(verify_api_key(provider_id, api_key))
    except RuntimeError:
        return asyncio.run(verify_api_key(provider_id, api_key))
    except Exception as e:
        return False, f"验证异常: {str(e)[:50]}"


def quick_validate_key_format(provider_id: str, api_key: str) -> Tuple[bool, str]:
    """快速验证 API Key 格式（不调用 API）"""
    if not api_key or len(api_key) < 10:
        return False, "API Key 太短"
    
    provider_id = PROVIDER_ALIASES.get(provider_id, provider_id)
    provider = AI_PROVIDERS.get(provider_id)
    
    if provider and provider.key_prefix:
        if not api_key.startswith(provider.key_prefix):
            return False, f"{provider.name} Key 应以 {provider.key_prefix} 开头"
    
    return True, "格式正确"


# ============================================================================
# 辅助函数
# ============================================================================

def get_available_providers() -> Dict[str, AIProvider]:
    """获取所有可用的 AI 服务商"""
    return AI_PROVIDERS


def get_provider(provider_id: str) -> Optional[AIProvider]:
    """获取指定服务商"""
    provider_id = PROVIDER_ALIASES.get(provider_id, provider_id)
    return AI_PROVIDERS.get(provider_id)


def get_provider_models(provider_id: str) -> List[AIModel]:
    """获取指定服务商的所有模型"""
    provider = get_provider(provider_id)
    if provider:
        return provider.models
    return []


def get_free_models() -> List[Tuple[str, AIModel]]:
    """获取所有免费模型"""
    free_models = []
    for provider_id, provider in AI_PROVIDERS.items():
        for model in provider.models:
            if model.is_free:
                free_models.append((provider_id, model))
    return free_models


def get_default_model(provider_id: str) -> str:
    """获取服务商的默认模型"""
    provider = get_provider(provider_id)
    if provider:
        return provider.default_model
    return ""


def get_all_provider_ids() -> List[str]:
    """获取所有服务商 ID"""
    return list(AI_PROVIDERS.keys())


def create_client(provider_id: str, api_key: str = None, model_id: str = None) -> UniversalAIClient:
    """
    创建 AI 客户端
    
    Args:
        provider_id: 服务商 ID
        api_key: API Key，如果为 None 则从配置中读取
        model_id: 模型 ID，如果为 None 则使用默认模型
    
    Returns:
        UniversalAIClient 实例
    """
    if api_key is None:
        # 从配置中读取
        try:
            from ai_config_manager import get_ai_config_manager
            config_mgr = get_ai_config_manager()
            config = config_mgr.get_ai_api_config(provider_id)
            if not config or not config.get('api_key'):
                raise ValueError(f"未配置 {provider_id} 的 API Key")
            api_key = config['api_key']
            if not model_id:
                model_id = config.get('model', '')
        except ImportError:
            raise ValueError("未提供 API Key 且无法加载配置管理器")
    
    return UniversalAIClient(provider_id, api_key, model_id)


def get_configured_providers() -> Dict[str, Dict[str, Any]]:
    """
    获取已配置 API Key 的服务商列表
    
    Returns:
        字典，key 为服务商 ID，value 包含 provider、api_key、model、verified 等信息
    """
    try:
        from ai_config_manager import get_ai_config_manager
        config_mgr = get_ai_config_manager()
        all_configs = config_mgr.get_all_ai_api_configs()
        
        configured = {}
        for provider_id, config in all_configs.items():
            if config.get('api_key'):
                provider = get_provider(provider_id)
                if provider:
                    configured[provider_id] = {
                        'provider': provider,
                        'api_key': config.get('api_key'),
                        'model': config.get('model', provider.default_model),
                        'models': provider.models,
                        'verified': config.get('verified', False)
                    }
        
        return configured
    except ImportError:
        return {}


# ============================================================================
# 动态模型列表获取（部分服务商支持）
# ============================================================================

async def fetch_available_models(provider_id: str, api_key: str) -> List[str]:
    """
    从 API 动态获取可用模型列表（仅部分服务商支持）
    
    支持的服务商：OpenAI, DeepSeek, Qwen（OpenAI 兼容接口）
    
    Args:
        provider_id: 服务商 ID
        api_key: API Key
    
    Returns:
        模型 ID 列表
    """
    import httpx
    
    provider_id = PROVIDER_ALIASES.get(provider_id, provider_id)
    provider = AI_PROVIDERS.get(provider_id)
    
    if not provider:
        return []
    
    # 只有 OpenAI 兼容的 API 支持 /models 端点
    if provider.api_type != "openai":
        return []
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{provider.api_base}/models",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                return [m.get("id") for m in models if m.get("id")]
            else:
                logger.warning(f"[{provider.name}] 获取模型列表失败: {response.status_code}")
                return []
    except Exception as e:
        logger.warning(f"[{provider.name}] 获取模型列表异常: {e}")
        return []


def fetch_available_models_sync(provider_id: str, api_key: str) -> List[str]:
    """获取可用模型列表（同步版本）"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, fetch_available_models(provider_id, api_key))
                return future.result(timeout=20)
        else:
            return loop.run_until_complete(fetch_available_models(provider_id, api_key))
    except RuntimeError:
        return asyncio.run(fetch_available_models(provider_id, api_key))
    except Exception as e:
        logger.warning(f"获取模型列表异常: {e}")
        return []


def get_model_version_info() -> Dict[str, str]:
    """
    获取当前配置的模型版本信息
    
    Returns:
        字典，key 为服务商 ID，value 为版本描述
    """
    return {
        "deepseek": "DeepSeek V3.1 (2025.08)",
        "qwen": "Qwen 3 系列 (2025.04)",
        "spark": "Spark 4.0 Ultra",
        "hunyuan": "混元 Turbo Latest",
        "doubao": "豆包 1.8 / Seed 1.6",
        "glm": "GLM-4.6 (2025.09)",
        "perplexity": "Sonar Pro",
        "openai": "o3 / GPT-4o (2025)",
        "claude": "Claude 4.5 系列 (2025.11)",
        "grok": "Grok 4 (2025)",
        "gemini": "Gemini 3 Pro (2025.11)",
    }


# 模型版本更新时间戳（用于前端显示）
MODEL_VERSION_UPDATED = "2025-12-30"
