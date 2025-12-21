"""
AI API Key 验证模块

真实调用各 AI 服务的 API 验证 Key 是否有效
每个 AI 有不同的验证方式
"""

import asyncio
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


async def verify_deepseek_key(api_key: str) -> Tuple[bool, str]:
    """
    验证 DeepSeek API Key
    
    通过调用 models 接口验证
    """
    try:
        import httpx
    except ImportError:
        return False, "请安装 httpx: pip install httpx"
    
    if not api_key or not api_key.startswith("sk-"):
        return False, "DeepSeek Key 应以 sk- 开头"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.deepseek.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            
            if response.status_code == 200:
                return True, "DeepSeek API Key 验证成功"
            elif response.status_code == 401:
                return False, "DeepSeek API Key 无效或已过期"
            else:
                return False, f"DeepSeek 验证失败: HTTP {response.status_code}"
    except httpx.TimeoutException:
        return False, "DeepSeek API 连接超时"
    except Exception as e:
        return False, f"DeepSeek 验证异常: {str(e)[:50]}"


async def verify_qwen_key(api_key: str) -> Tuple[bool, str]:
    """
    验证通义千问 (DashScope) API Key
    
    通过调用 models 接口验证
    """
    try:
        import httpx
    except ImportError:
        return False, "请安装 httpx: pip install httpx"
    
    if not api_key or not api_key.startswith("sk-"):
        return False, "Qwen Key 应以 sk- 开头"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # DashScope 使用不同的验证方式
            response = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen-turbo",
                    "input": {"messages": [{"role": "user", "content": "hi"}]},
                    "parameters": {"max_tokens": 1}
                }
            )
            
            data = response.json()
            
            # 检查响应
            if response.status_code == 200 and "output" in data:
                return True, "Qwen API Key 验证成功"
            elif "InvalidApiKey" in str(data) or response.status_code == 401:
                return False, "Qwen API Key 无效"
            elif "Throttling" in str(data):
                # 限流说明 Key 是有效的
                return True, "Qwen API Key 验证成功 (限流中)"
            else:
                error_msg = data.get("message", str(data)[:50])
                return False, f"Qwen 验证失败: {error_msg}"
    except httpx.TimeoutException:
        return False, "Qwen API 连接超时"
    except Exception as e:
        return False, f"Qwen 验证异常: {str(e)[:50]}"


async def verify_openai_key(api_key: str) -> Tuple[bool, str]:
    """
    验证 OpenAI API Key
    
    通过调用 models 接口验证
    """
    try:
        import httpx
    except ImportError:
        return False, "请安装 httpx: pip install httpx"
    
    if not api_key or not api_key.startswith("sk-"):
        return False, "OpenAI Key 应以 sk- 开头"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            
            if response.status_code == 200:
                return True, "OpenAI API Key 验证成功"
            elif response.status_code == 401:
                return False, "OpenAI API Key 无效或已过期"
            else:
                return False, f"OpenAI 验证失败: HTTP {response.status_code}"
    except httpx.TimeoutException:
        return False, "OpenAI API 连接超时"
    except Exception as e:
        return False, f"OpenAI 验证异常: {str(e)[:50]}"


async def verify_claude_key(api_key: str) -> Tuple[bool, str]:
    """
    验证 Anthropic Claude API Key
    
    通过发送最小请求验证
    """
    try:
        import httpx
    except ImportError:
        return False, "请安装 httpx: pip install httpx"
    
    if not api_key or not api_key.startswith("sk-ant-"):
        return False, "Claude Key 应以 sk-ant- 开头"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}]
                }
            )
            
            if response.status_code == 200:
                return True, "Claude API Key 验证成功"
            elif response.status_code == 401:
                return False, "Claude API Key 无效"
            elif response.status_code == 400:
                # 400 可能是请求格式问题，但 Key 是有效的
                data = response.json()
                if "authentication" in str(data).lower():
                    return False, "Claude API Key 无效"
                return True, "Claude API Key 验证成功"
            else:
                return False, f"Claude 验证失败: HTTP {response.status_code}"
    except httpx.TimeoutException:
        return False, "Claude API 连接超时"
    except Exception as e:
        return False, f"Claude 验证异常: {str(e)[:50]}"


async def verify_perplexity_key(api_key: str) -> Tuple[bool, str]:
    """
    验证 Perplexity API Key
    
    通过发送最小请求验证
    """
    try:
        import httpx
    except ImportError:
        return False, "请安装 httpx: pip install httpx"
    
    if not api_key or not api_key.startswith("pplx-"):
        return False, "Perplexity Key 应以 pplx- 开头"
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-sonar-small-128k-online",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                }
            )
            
            if response.status_code == 200:
                return True, "Perplexity API Key 验证成功"
            elif response.status_code == 401:
                return False, "Perplexity API Key 无效"
            else:
                return False, f"Perplexity 验证失败: HTTP {response.status_code}"
    except httpx.TimeoutException:
        return False, "Perplexity API 连接超时"
    except Exception as e:
        return False, f"Perplexity 验证异常: {str(e)[:50]}"


async def verify_spark_lite_key(api_key: str) -> Tuple[bool, str]:
    """
    验证讯飞星火 Spark Lite API Password
    
    通过发送最小请求验证（OpenAI 兼容接口）
    """
    try:
        import httpx
    except ImportError:
        return False, "请安装 httpx: pip install httpx"
    
    if not api_key or len(api_key) < 10:
        return False, "SparkLite API Password 格式不正确"
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://spark-api-open.xf-yun.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "lite",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                }
            )
            
            if response.status_code == 200:
                return True, "SparkLite API Password 验证成功"
            elif response.status_code == 401:
                return False, "SparkLite API Password 无效"
            else:
                error_text = response.text[:100] if response.text else ""
                return False, f"SparkLite 验证失败: HTTP {response.status_code} {error_text}"
    except httpx.TimeoutException:
        return False, "SparkLite API 连接超时"
    except Exception as e:
        return False, f"SparkLite 验证异常: {str(e)[:50]}"


async def verify_hunyuan_key(api_key: str) -> Tuple[bool, str]:
    """
    验证腾讯混元 Hunyuan API Key
    
    通过发送最小请求验证（OpenAI 兼容接口）
    注意：只使用免费模型 hunyuan-lite
    """
    try:
        import httpx
    except ImportError:
        return False, "请安装 httpx: pip install httpx"
    
    if not api_key or len(api_key) < 10:
        return False, "Hunyuan API Key 格式不正确"
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "hunyuan-lite",  # 强制使用免费模型
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                }
            )
            
            if response.status_code == 200:
                return True, "Hunyuan API Key 验证成功 (hunyuan-lite)"
            elif response.status_code == 401:
                return False, "Hunyuan API Key 无效"
            elif response.status_code == 403:
                return False, "Hunyuan API Key 权限不足，请检查是否已开通混元服务"
            else:
                error_text = response.text[:100] if response.text else ""
                # 检查是否是资源包问题
                if "quota" in error_text.lower():
                    return False, "Hunyuan 免费资源包可能已耗尽"
                return False, f"Hunyuan 验证失败: HTTP {response.status_code} {error_text}"
    except httpx.TimeoutException:
        return False, "Hunyuan API 连接超时"
    except Exception as e:
        return False, f"Hunyuan 验证异常: {str(e)[:50]}"


# 验证函数映射
VERIFY_FUNCTIONS = {
    "deepseek": verify_deepseek_key,
    "qwen": verify_qwen_key,
    "openai": verify_openai_key,
    "claude": verify_claude_key,
    "perplexity": verify_perplexity_key,
    "spark_lite": verify_spark_lite_key,
    "hunyuan": verify_hunyuan_key,
}


async def verify_api_key(ai_id: str, api_key: str) -> Tuple[bool, str]:
    """
    验证指定 AI 的 API Key
    
    参数:
        ai_id: AI 标识符 (deepseek, qwen, openai, claude, perplexity)
        api_key: API Key
    
    返回:
        (是否有效, 消息)
    """
    verify_func = VERIFY_FUNCTIONS.get(ai_id.lower())
    if not verify_func:
        return False, f"不支持的 AI: {ai_id}"
    
    return await verify_func(api_key)


def verify_api_key_sync(ai_id: str, api_key: str) -> Tuple[bool, str]:
    """
    同步版本的 API Key 验证
    
    用于 Streamlit 等同步环境
    """
    try:
        # 尝试获取现有的事件循环
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果循环正在运行，创建新线程执行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    verify_api_key(ai_id, api_key)
                )
                return future.result(timeout=15)
        else:
            return loop.run_until_complete(verify_api_key(ai_id, api_key))
    except RuntimeError:
        # 没有事件循环，直接创建
        return asyncio.run(verify_api_key(ai_id, api_key))
    except Exception as e:
        return False, f"验证异常: {str(e)[:50]}"


# API Key 格式预检查（快速检查，不调用 API）
API_KEY_PATTERNS = {
    "deepseek": ("sk-", "DeepSeek Key 应以 sk- 开头"),
    "qwen": ("sk-", "Qwen Key 应以 sk- 开头"),
    "openai": ("sk-", "OpenAI Key 应以 sk- 开头"),
    "claude": ("sk-ant-", "Claude Key 应以 sk-ant- 开头"),
    "perplexity": ("pplx-", "Perplexity Key 应以 pplx- 开头"),
    "spark_lite": ("", "SparkLite 使用 APIPassword，无固定前缀"),
    "hunyuan": ("", "Hunyuan API Key 无固定前缀"),
}


def quick_validate_key_format(ai_id: str, api_key: str) -> Tuple[bool, str]:
    """
    快速验证 API Key 格式（不调用 API）
    
    返回:
        (格式是否正确, 消息)
    """
    if not api_key or len(api_key) < 10:
        return False, "API Key 太短"
    
    pattern_info = API_KEY_PATTERNS.get(ai_id.lower())
    if pattern_info:
        prefix, error_msg = pattern_info
        if not api_key.startswith(prefix):
            return False, error_msg
    
    return True, "格式正确"
