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
#   Copyright (c) 2024-2025 HyWeiShi. All Rights Reserved.
#   License: AGPL-3.0
#
# ============================================================================
# ============================================================================
"""
AI 策略编写助手 UI 模块

提供独立页面，支持：
1. 自然语言描述生成策略
2. Pine Script 转换
3. Python 代码验证
4. AI 策略评估
"""
import streamlit as st
from typing import Dict, Any, List, Optional


STRATEGY_BUILDER_STYLES = """
<style>
/* 策略助手页面整体样式 */
.strategy-builder-header {
    background: linear-gradient(135deg, #ff6b9d 0%, #c44569 100%);
    padding: 20px 30px;
    border-radius: 16px;
    margin-bottom: 24px;
    box-shadow: 0 8px 32px rgba(255, 107, 157, 0.3);
}

.strategy-builder-header h2 {
    color: white;
    margin: 0;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: 2px;
}

.strategy-builder-header p {
    color: rgba(255,255,255,0.8);
    margin: 8px 0 0 0;
    font-size: 14px;
}

/* AI 选择器卡片 */
.ai-selector-card {
    background: linear-gradient(145deg, rgba(26, 26, 46, 0.9), rgba(15, 15, 26, 0.95));
    border: 1px solid rgba(255, 107, 157, 0.3);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
}

.ai-selector-title {
    color: #a0aec0;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}

/* 代码预览区 */
.code-preview-container {
    background: linear-gradient(145deg, #1a1a2e, #16213e);
    border: 1px solid rgba(255, 107, 157, 0.2);
    border-radius: 12px;
    padding: 20px;
    margin: 16px 0;
}

.code-preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}

.code-preview-title {
    color: #e2e8f0;
    font-size: 16px;
    font-weight: 600;
}

/* 操作按钮组 - 居中显示 */
.action-buttons {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin: 20px 0;
}

/* 策略卡片 */
.strategy-card {
    background: linear-gradient(145deg, rgba(26, 26, 46, 0.8), rgba(15, 15, 26, 0.9));
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0;
    transition: all 0.3s ease;
}

.strategy-card:hover {
    border-color: rgba(255, 107, 157, 0.5);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

/* AI 评估区域 */
.ai-evaluation-card {
    background: linear-gradient(135deg, rgba(255, 107, 157, 0.1), rgba(196, 69, 105, 0.05));
    border: 1px solid rgba(255, 107, 157, 0.3);
    border-radius: 12px;
    padding: 20px;
    margin: 16px 0;
}

.ai-evaluation-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}

.ai-evaluation-title {
    color: #ff6b9d;
    font-size: 16px;
    font-weight: 600;
}

/* 输入区域美化 */
.stTextArea textarea {
    background: rgba(26, 26, 46, 0.6) !important;
    border: 1px solid rgba(255, 107, 157, 0.3) !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-family: 'Fira Code', 'Consolas', monospace !important;
}

.stTextArea textarea:focus {
    border-color: #ff6b9d !important;
    box-shadow: 0 0 0 2px rgba(255, 107, 157, 0.2) !important;
}

/* Tab 样式 - 居中 + 拉长 + 统一圆角 */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: transparent;
    justify-content: center;
}

.stTabs [data-baseweb="tab"] {
    background: rgba(26, 26, 46, 0.6);
    border-radius: 0 !important;
    padding: 14px 80px;
    color: #a0aec0;
    border: 1px solid rgba(255, 255, 255, 0.1);
    min-width: 220px;
    justify-content: center;
}

.stTabs [data-baseweb="tab"]:first-child {
    border-radius: 8px 0 0 8px !important;
}

.stTabs [data-baseweb="tab"]:last-child {
    border-radius: 0 8px 8px 0 !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #ff6b9d, #c44569) !important;
    color: white !important;
    border-color: transparent !important;
    border-radius: 0 !important;
}

.stTabs [aria-selected="true"]:first-child {
    border-radius: 8px 0 0 8px !important;
}

.stTabs [aria-selected="true"]:last-child {
    border-radius: 0 8px 8px 0 !important;
}

/* 成功/错误提示 */
.validation-success {
    background: rgba(0, 212, 170, 0.15);
    border: 1px solid rgba(0, 212, 170, 0.3);
    border-radius: 8px;
    padding: 12px 16px;
    color: #00d4aa;
}

.validation-error {
    background: rgba(255, 107, 107, 0.15);
    border: 1px solid rgba(255, 107, 107, 0.3);
    border-radius: 8px;
    padding: 12px 16px;
    color: #ff6b6b;
}

/* 按钮居中容器 */
.centered-buttons {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin: 20px 0;
}

/* Streamlit 按钮样式覆盖 */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(255, 107, 157, 0.3);
}

/* 主要按钮使用粉色 */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #ff6b9d, #c44569) !important;
    border: none !important;
}
</style>
"""


def render_strategy_builder(view_model: Dict[str, Any], actions: Dict[str, Any]):
    """渲染 AI 策略编写助手独立页面"""
    
    # 注入 CSS 样式
    st.markdown(STRATEGY_BUILDER_STYLES, unsafe_allow_html=True)
    
    # 侧边栏 - 返回按钮
    with st.sidebar:
        st.markdown("""
        <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px 8px;
            margin-bottom: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        ">
            <div style="font-size: 18px; font-weight: 600; color: #ff6b9d;">◈ 策略助手</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("← 返回主界面", key="sidebar_exit_builder", use_container_width=True, type="primary"):
            st.session_state.strategy_builder_mode = False
            st.session_state.arena_mode = False  # 确保也退出 arena 模式
            st.rerun()
        
        st.divider()
        st.caption("(・ω・) 在这里创建和管理你的交易策略")
    
    # 页面标题
    st.markdown("""
    <div class="strategy-builder-header">
        <h2>◈ AI 策略编写助手</h2>
        <p>使用自然语言、Pine Script 或 Python 创建交易策略</p>
    </div>
    """, unsafe_allow_html=True)
    
    # AI 选择器
    _render_ai_selector()
    
    # 信号类型说明（实时信号 vs 收盘信号）
    _render_signal_type_explanation()
    
    st.markdown("---")
    
    # 四种输入模式 Tab（添加回测）
    tab1, tab2, tab3, tab4 = st.tabs([
        "(｡･ω･｡) 自然语言描述", 
        "(◕‿◕) Pine Script 转换", 
        "(≧▽≦) Python 代码",
        "(◕ᴗ◕✿) 策略回测"
    ])
    
    with tab1:
        _render_natural_language_tab()
    with tab2:
        _render_pine_script_tab()
    with tab3:
        _render_python_tab()
    with tab4:
        _render_backtest_tab()
    
    # 代码预览和操作区
    _render_code_preview()
    _render_action_buttons(actions)
    
    # AI 策略评估区域
    _render_ai_evaluation()
    
    # 策略管理区域
    _render_strategy_manager()


def _get_available_ais() -> List[Dict[str, Any]]:
    """获取已配置的 AI 列表（使用新的 ai_providers 模块）"""
    try:
        # 优先使用新的 ai_providers 模块
        try:
            from ai.ai_providers import get_configured_providers, AI_PROVIDERS
            
            configured = get_configured_providers()
            available = []
            
            for provider_id, config in configured.items():
                provider = config.get('provider')
                if provider:
                    available.append({
                        "id": provider_id,
                        "name": provider.name,
                        "api_key": config.get('api_key'),
                        "models": config.get('models', []),
                        "default_model": provider.default_model,
                        "verified": config.get('verified', False)
                    })
            
            return available
        except ImportError:
            pass
        
        # 回退到旧方法
        from ai.ai_config_manager import get_ai_config_manager
        config_mgr = get_ai_config_manager()
        configs = config_mgr.get_all_ai_api_configs()
        
        available = []
        ai_names = {
            "deepseek": "DeepSeek",
            "qwen": "通义千问",
            "openai": "GPT",
            "claude": "Claude",
            "perplexity": "Perplexity",
            "spark_lite": "讯飞星火",
            "spark": "讯飞星火",
            "hunyuan": "腾讯混元",
            "glm": "智谱 GLM",
            "doubao": "火山豆包"
        }
        
        # 默认模型映射
        default_models = {
            "deepseek": "deepseek-chat",
            "qwen": "qwen-max",
            "spark": "lite",
            "spark_lite": "lite",
            "hunyuan": "hunyuan-lite",
            "glm": "glm-4-flash",
            "doubao": "doubao-pro-4k",
            "perplexity": "llama-3.1-sonar-small-128k-online",
            "openai": "gpt-4o-mini",
            "claude": "claude-3-haiku-20240307",
        }
        
        for ai_id, config in configs.items():
            if config.get('api_key'):
                # 使用用户配置的模型，如果没有则使用默认模型
                user_model = config.get('model', '') or default_models.get(ai_id, '')
                available.append({
                    "id": ai_id,
                    "name": ai_names.get(ai_id, ai_id),
                    "api_key": config.get('api_key'),
                    "model": user_model,  # 用户配置的模型
                    "verified": config.get('verified', False)
                })
        return available
    except:
        return []


def _render_ai_selector():
    """渲染 AI 选择器（使用统一配置的 API Key 和模型）"""
    available_ais = _get_available_ais()
    
    st.markdown("""
    <div class="ai-selector-card">
        <div style="font-size: 18px; font-weight: 600; color: #e2e8f0; margin-bottom: 8px;">(◕ᴗ◕✿) 选择 AI 助手</div>
        <div style="font-size: 13px; color: #718096;">选择用于生成策略代码的 AI，可前往「AI 交易系统」配置更多 AI API</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        if available_ais:
            # 服务商选择（显示服务商名称和配置的模型）
            options = ["规则匹配（无需 AI）"] + [f"{ai['name']} ({ai.get('model', '默认')})" for ai in available_ais]
            selected_idx = st.selectbox(
                "AI 服务商",
                range(len(options)),
                format_func=lambda x: options[x],
                key="selected_ai_provider",
                label_visibility="collapsed"
            )
            
            # 保存选择的 AI
            if selected_idx == 0:
                st.session_state.strategy_ai_id = None
                st.session_state.strategy_ai_key = None
                st.session_state.strategy_ai_model = None
            else:
                ai = available_ais[selected_idx - 1]
                st.session_state.strategy_ai_id = ai['id']
                st.session_state.strategy_ai_key = ai['api_key']
                # 使用用户在 AI 配置面板中选择的模型
                st.session_state.strategy_ai_model = ai.get('model', '')
        else:
            st.info("(´・ω・`) 未配置 AI，将使用规则匹配生成策略。")
            st.session_state.strategy_ai_id = None
            st.session_state.strategy_ai_key = None
            st.session_state.strategy_ai_model = None
    
    with col2:
        # 显示当前使用的模型（只读，在 AI 配置面板修改）
        ai_id = st.session_state.get('strategy_ai_id')
        if ai_id and available_ais:
            current_ai = None
            for ai in available_ais:
                if ai['id'] == ai_id:
                    current_ai = ai
                    break
            
            if current_ai:
                model_name = current_ai.get('model', '默认模型')
                st.caption(f"模型: {model_name}")
                st.caption("(在 AI 配置面板修改)")
        else:
            st.caption("")
    
    with col3:
        if available_ais and st.session_state.get('strategy_ai_id'):
            # 找到是否已验证
            verified = False
            for ai in available_ais:
                if ai['id'] == st.session_state.get('strategy_ai_id'):
                    verified = ai.get('verified', False)
                    break
            
            if verified:
                st.success("✓ 已验证")
            else:
                st.caption("未验证")


def _render_signal_type_explanation():
    """渲染信号类型说明（实时信号 vs 收盘信号）"""
    with st.expander("(・ω・) 信号类型说明：实时信号 vs 收盘信号", expanded=False):
        st.markdown("""
        <div style="
            background: linear-gradient(145deg, rgba(26, 26, 46, 0.9), rgba(15, 15, 26, 0.95));
            border: 1px solid rgba(255, 107, 157, 0.3);
            border-radius: 12px;
            padding: 16px;
        ">
        
        **策略信号分为两种类型，需要配合不同的数据源模式使用：**
        
        ---
        
        **📊 收盘信号策略（推荐新手）**
        
        | 特点 | 说明 |
        |------|------|
        | 触发时机 | K线收盘后（如每分钟00秒） |
        | 数据源 | REST 轮询模式 |
        | 适用策略 | 均线交叉、MACD、RSI 等趋势策略 |
        | 优点 | 信号稳定，不会因价格波动反复触发 |
        | 缺点 | 有一定延迟（最多1根K线时间） |
        
        **示例**：EMA12 上穿 EMA26 → 等K线收盘确认后再开仓
        
        ---
        
        **⚡ 实时信号策略（进阶用户）**
        
        | 特点 | 说明 |
        |------|------|
        | 触发时机 | 价格变动时立即触发 |
        | 数据源 | WebSocket 实时推送 |
        | 适用策略 | 突破策略、动量策略、网格策略 |
        | 优点 | 毫秒级响应，抓住瞬间机会 |
        | 缺点 | 可能出现假突破，需要更严格的过滤条件 |
        
        **示例**：价格突破布林带上轨 → 立即开仓
        
        ---
        
        **🔧 如何配置？**
        
        1. 在主界面侧边栏找到「数据源」选项
        2. 收盘信号策略 → 选择 **REST 轮询**
        3. 实时信号策略 → 选择 **WebSocket**
        
        **💡 提示**：系统会根据策略类型自动推荐数据源模式
        
        </div>
        """, unsafe_allow_html=True)


def _render_natural_language_tab():
    """自然语言描述 Tab"""
    st.markdown("### 用自然语言描述你的策略")
    st.caption("支持中英文，描述越详细生成的代码越准确。点击下方按钮展开更大的输入区域。")
    
    # 展开/收起状态
    if 'expand_description' not in st.session_state:
        st.session_state.expand_description = False
    
    # 展开按钮
    col_expand, col_spacer = st.columns([1, 4])
    with col_expand:
        if st.button("📝 展开大输入框" if not st.session_state.expand_description else "📝 收起输入框", 
                     key="toggle_expand"):
            st.session_state.expand_description = not st.session_state.expand_description
            st.rerun()
    
    # 根据状态显示不同大小的输入框
    if st.session_state.expand_description:
        description = st.text_area(
            "策略描述（展开模式）",
            placeholder="""详细描述你的策略，例如：

1. 入场条件：
   - 当 EMA12 上穿 EMA26 时做多
   - 当 EMA12 下穿 EMA26 时做空
   - RSI 需要在 30-70 区间内确认

2. 过滤条件：
   - 只在 EMA200 上方做多，下方做空
   - 成交量需要大于 20 日均量

3. 其他要求：
   - 使用 ATR 动态止损
   - 分批止盈""",
            height=350,
            key="nl_description",
            label_visibility="collapsed"
        )
    else:
        description = st.text_area(
            "策略描述",
            placeholder="例如：当 EMA12 上穿 EMA26 时做多，下穿时做空。RSI 过滤超买超卖。",
            height=120,
            key="nl_description",
            label_visibility="collapsed"
        )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("ヾ(≧▽≦*)o 生成策略", key="generate_from_nl", type="primary"):
            if description:
                _generate_from_natural_language(description)
            else:
                st.warning("请先输入策略描述")
    
    # 示例提示
    with st.expander("(・∀・) 示例描述", expanded=False):
        st.markdown("""
        **简单均线策略：**
        > 当 5 日均线上穿 20 日均线时做多，下穿时做空
        
        **RSI 策略：**
        > RSI(14) 低于 30 时做多，高于 70 时做空
        
        **MACD 策略：**
        > MACD 金叉做多，死叉做空
        """)


def _render_pine_script_tab():
    """Pine Script 转换 Tab"""
    st.markdown("### 转换 TradingView 策略")
    
    # 添加重要提示
    st.info("""
    **💡 推荐工作流程：**
    1. 先把 TradingView 的 Pine Script 代码复制到 [DeepSeek](https://chat.deepseek.com)、[豆包](https://www.doubao.com)、[Kimi](https://kimi.moonshot.cn) 等免费 AI 网站
    2. 让 AI 帮你转换成 Python 代码（节省 API 费用，转换更准确）
    3. 把转换好的 Python 代码粘贴到「Python 代码」标签页进行验证
    4. 验证通过后保存即可使用
    
    **本页面的简单转换器**只支持基础函数，复杂策略建议用上述方法~
    """)
    
    st.markdown("---")
    st.markdown("##### 简单转换器（仅支持基础函数）")
    
    pine_code = st.text_area(
        "Pine Script",
        placeholder="""//@version=5
strategy("My Strategy", overlay=true)
ema12 = ta.ema(close, 12)
ema26 = ta.ema(close, 26)
longCondition = ta.crossover(ema12, ema26)
if (longCondition)
    strategy.entry("Long", strategy.long)""",
        height=150,
        key="pine_code"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("(ﾉ◕ヮ◕)ﾉ 转换", key="convert_pine", type="primary"):
            if pine_code:
                _convert_pine_script(pine_code)
            else:
                st.warning("请先粘贴 Pine Script 代码")
    
    # AI 转换提示词模板
    with st.expander("(◕‿◕) 给 AI 的提示词模板", expanded=False):
        prompt_template = '''请将以下 TradingView Pine Script 代码转换为 Python 策略代码：

```pinescript
[在这里粘贴你的 Pine Script 代码]
```

要求：
1. 生成一个 Python 类，类名自定义
2. 必须实现 __init__(self, config=None) 方法，包含 self.position_pct = 2.0 和 self.leverage = 50
3. 必须实现 analyze(self, ohlcv, symbol, timeframe='5m') 方法
4. analyze 返回格式：{"action": "LONG/SHORT/HOLD", "type": "CUSTOM", "position_pct": self.position_pct, "leverage": self.leverage, "reason": "..."}
5. action 值只能是: LONG（做多）, SHORT（做空）, HOLD（等待）, CLOSE_LONG（平多）, CLOSE_SHORT（平空）
6. type 固定为 "CUSTOM"
7. 使用 pandas_ta 库计算指标（import pandas_ta as ta）
8. ohlcv 是 pandas DataFrame，包含 open, high, low, close, volume 列
9. 添加中文注释说明策略逻辑'''
        
        st.code(prompt_template, language="text")
        st.caption("复制上面的提示词，把 Pine Script 代码粘贴进去，发给 AI 即可")
    
    with st.expander("(｀・ω・´) 支持的函数", expanded=False):
        st.markdown("""
        **趋势指标:**
        | Pine Script | Python | 说明 |
        |-------------|--------|------|
        | `ta.ema()` | `ta.ema()` / `calc_ema()` | 指数移动平均 |
        | `ta.sma()` | `ta.sma()` / `calc_ma()` | 简单移动平均 |
        | `ta.wma()` | `ta.wma()` | 加权移动平均 |
        | `ta.vwma()` | `ta.vwma()` | 成交量加权均线 |
        
        **动量指标:**
        | Pine Script | Python | 说明 |
        |-------------|--------|------|
        | `ta.rsi()` | `ta.rsi()` / `calc_rsi()` | 相对强弱指数 |
        | `ta.macd()` | `ta.macd()` / `calc_macd()` | MACD 指标 |
        | `ta.stoch()` | `ta.stoch()` / `calc_kdj()` | 随机指标 KDJ |
        | `ta.cci()` | `ta.cci()` | 商品通道指数 |
        | `ta.mfi()` | `ta.mfi()` | 资金流量指数 |
        | `ta.willr()` | `ta.willr()` | 威廉指标 |
        
        **波动指标:**
        | Pine Script | Python | 说明 |
        |-------------|--------|------|
        | `ta.bbands()` | `ta.bbands()` / `calc_boll()` | 布林带 |
        | `ta.atr()` | `ta.atr()` / `calc_atr()` | 平均真实波幅 |
        | `ta.kc()` | `ta.kc()` | 肯特纳通道 |
        | `ta.donchian()` | `ta.donchian()` | 唐奇安通道 |
        
        **趋势强度:**
        | Pine Script | Python | 说明 |
        |-------------|--------|------|
        | `ta.adx()` | `ta.adx()` | 平均趋向指数 |
        | `ta.dmi()` | `ta.dm()` | 动向指标 |
        | `ta.aroon()` | `ta.aroon()` | 阿隆指标 |
        
        **成交量:**
        | Pine Script | Python | 说明 |
        |-------------|--------|------|
        | `ta.obv()` | `ta.obv()` / `calc_obv()` | 能量潮 |
        | `ta.vwap()` | `ta.vwap()` / `calc_vwap()` | 成交量加权均价 |
        | `ta.ad()` | `ta.ad()` | 累积/派发线 |
        | `ta.cmf()` | `ta.cmf()` | 蔡金资金流 |
        
        **信号函数:**
        | Pine Script | Python | 说明 |
        |-------------|--------|------|
        | `ta.crossover()` | `_crossover()` | 上穿判断 |
        | `ta.crossunder()` | `_crossunder()` | 下穿判断 |
        | `ta.highest()` | `rolling().max()` | N周期最高 |
        | `ta.lowest()` | `rolling().min()` | N周期最低 |
        
        ---
        ** 加速计算提示:**
        - 带 `calc_xxx()` 的函数来自 `ai_indicators.py`，使用 NumPy 向量化加速
        - 复杂策略建议使用「自然语言描述」+ AI 生成，会自动使用加速函数
        """)


def _render_python_tab():
    """Python 代码 Tab"""
    st.markdown("### 粘贴或编辑 Python 策略代码")
    st.caption("代码必须符合系统策略模板格式")
    
    python_code = st.text_area(
        "Python 代码",
        value=st.session_state.get('generated_code', ''),
        placeholder=_get_strategy_template_simple(),
        height=300,
        key="python_code"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("(•̀ᴗ•́)و 验证代码", key="validate_python", type="primary"):
            if python_code:
                _validate_python_code(python_code)
            else:
                st.warning("请先输入 Python 代码")
    
    with st.expander("(◕‿◕) 策略模板说明", expanded=False):
        st.markdown("""
        **策略只需要做一件事：返回交易信号**
        
        ```python
        {
            "action": "LONG",       # LONG=做多 / SHORT=做空 / HOLD=等待
            "type": "CUSTOM",       # 固定写 CUSTOM
            "reason": "EMA金叉"     # 信号原因（可选）
        }
        ```
        
        | 信号 | 含义 |
        |------|------|
        | `LONG` | 开多仓 |
        | `SHORT` | 开空仓 |
        | `HOLD` | 不操作 |
        | `CLOSE_LONG` | 平多仓 |
        | `CLOSE_SHORT` | 平空仓 |
        
        ---
        
        **💡 仓位、杠杆、止盈止损 → 在主界面配置**
        
        - 策略代码中的 `self.position_pct`、`self.leverage` 只是推荐值
        - 实际交易时使用主界面「交易参数」中的配置，可以随时调整
        - 止盈止损在主界面「风控设置」中配置，策略无需处理
        """)



def _render_code_preview():
    """代码预览区"""
    if 'generated_code' in st.session_state and st.session_state.generated_code:
        st.markdown("""
        <div class="code-preview-container">
            <div class="code-preview-header">
                <span class="code-preview-title">(◕ᴗ◕✿) 生成的代码</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.code(st.session_state.generated_code, language="python")
        
        # 显示验证结果
        if 'validation_result' in st.session_state:
            result = st.session_state.validation_result
            if result.get('valid'):
                st.markdown('<div class="validation-success">(≧◡≦) 代码验证通过，可以保存啦~</div>', unsafe_allow_html=True)
                # 显示策略信息
                if result.get('info'):
                    for info_msg in result.get('info', []):
                        st.info(f"ℹ️ {info_msg}")
                
                # 检测是否是高级策略，显示参数配置面板
                code = st.session_state.generated_code
                if 'AdvancedStrategyBase' in code or 'get_config_schema' in code:
                    _render_strategy_config_panel(code)
            else:
                for error in result.get('errors', []):
                    st.markdown(f'<div class="validation-error"> {error}</div>', unsafe_allow_html=True)
            
            # 显示警告
            for warning in result.get('warnings', []):
                st.warning(f"⚠️ {warning}")
            
            # 自动转换按钮（当 can_convert=True 时显示）
            if result.get('can_convert'):
                st.markdown("---")
                if result.get('valid'):
                    st.info("(◕ᴗ◕✿) 代码已验证通过，但可以进一步优化为标准引擎格式")
                else:
                    st.info("(◕ᴗ◕✿) 检测到代码可以自动转换为传统引擎格式")
                if st.button("✨ 自动转换为引擎格式", key="auto_convert", type="primary"):
                    _auto_convert_code()


def _render_strategy_config_panel(code: str):
    """渲染高级策略参数配置面板"""
    st.markdown("---")
    st.markdown("### (◕‿◕) 策略参数配置")
    st.caption("以下参数可在运行时通过前端调整，无需修改代码")
    
    # 尝试从代码中提取 config schema
    schema = _extract_config_schema(code)
    
    # 获取默认 schema
    default_schema = _get_default_advanced_schema()
    
    if not schema:
        # 使用默认的高级策略 schema
        schema = default_schema
    else:
        # 合并默认 schema 中缺失的参数（确保时间过滤等参数存在）
        for key, value in default_schema.items():
            if key not in schema:
                schema[key] = value
    
    # 初始化配置存储
    if 'strategy_config' not in st.session_state:
        st.session_state.strategy_config = {}
    
    # 分组显示参数
    risk_params = {}
    signal_params = {}
    time_params = {}
    other_params = {}
    
    for key, param in schema.items():
        if key in ['risk_per_trade', 'max_leverage', 'high_volatility_leverage', 
                   'atr_sl_multiplier', 'min_sl_pct', 'max_sl_pct']:
            risk_params[key] = param
        elif key in ['tp1_r_multiple', 'tp1_close_pct', 'tp2_r_multiple', 
                     'tp2_close_pct', 'tp3_trailing_atr']:
            signal_params[key] = param
        elif key in ['enable_time_filter', 'trading_start_hour_1', 'trading_end_hour_1',
                     'trading_start_hour_2', 'trading_end_hour_2']:
            time_params[key] = param
        else:
            other_params[key] = param
    
    # 风控参数
    if risk_params:
        with st.expander("🛡️ 风控参数", expanded=True):
            cols = st.columns(3)
            col_idx = 0
            for key, param in risk_params.items():
                with cols[col_idx % 3]:
                    _render_param_input(key, param)
                col_idx += 1
    
    # 止盈止损参数
    if signal_params:
        with st.expander("📊 止盈止损参数", expanded=True):
            cols = st.columns(3)
            col_idx = 0
            for key, param in signal_params.items():
                with cols[col_idx % 3]:
                    _render_param_input(key, param)
                col_idx += 1
    
    # 时间过滤参数
    if time_params:
        with st.expander("🕐 时间过滤", expanded=True):
            # 先显示启用开关
            if 'enable_time_filter' in time_params:
                _render_param_input('enable_time_filter', time_params['enable_time_filter'])
                st.caption("UTC 时间，北京时间 = UTC + 8 小时")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**时段 1**")
                if 'trading_start_hour_1' in time_params:
                    _render_param_input('trading_start_hour_1', time_params['trading_start_hour_1'])
                if 'trading_end_hour_1' in time_params:
                    _render_param_input('trading_end_hour_1', time_params['trading_end_hour_1'])
            with col2:
                st.markdown("**时段 2**")
                if 'trading_start_hour_2' in time_params:
                    _render_param_input('trading_start_hour_2', time_params['trading_start_hour_2'])
                if 'trading_end_hour_2' in time_params:
                    _render_param_input('trading_end_hour_2', time_params['trading_end_hour_2'])
    
    # 其他参数（冷却期等）
    if other_params:
        with st.expander("⚙️ 策略参数", expanded=True):
            cols = st.columns(3)
            col_idx = 0
            for key, param in other_params.items():
                with cols[col_idx % 3]:
                    _render_param_input(key, param)
                col_idx += 1
    
    # 显示当前配置
    if st.session_state.strategy_config:
        with st.expander("📋 当前配置 JSON", expanded=False):
            import json
            st.code(json.dumps(st.session_state.strategy_config, indent=2, ensure_ascii=False), language="json")


def _render_param_input(key: str, param: Dict[str, Any]):
    """渲染单个参数输入控件"""
    param_type = param.get('type', 'float')
    label = param.get('label', key)
    default = param.get('default', 0)
    description = param.get('description', '')
    
    # 从 session_state 获取当前值
    current_value = st.session_state.strategy_config.get(key, default)
    
    if param_type == 'int':
        value = st.number_input(
            label,
            min_value=param.get('min', 0),
            max_value=param.get('max', 100),
            value=int(current_value),
            step=param.get('step', 1),
            help=description,
            key=f"param_{key}"
        )
    elif param_type == 'float':
        value = st.number_input(
            label,
            min_value=float(param.get('min', 0)),
            max_value=float(param.get('max', 100)),
            value=float(current_value),
            step=float(param.get('step', 0.01)),
            format="%.3f" if param.get('step', 0.01) < 0.01 else "%.2f",
            help=description,
            key=f"param_{key}"
        )
    elif param_type == 'bool':
        value = st.checkbox(
            label,
            value=bool(current_value),
            help=description,
            key=f"param_{key}"
        )
    elif param_type == 'select':
        options = param.get('options', [])
        value = st.selectbox(
            label,
            options=options,
            index=options.index(current_value) if current_value in options else 0,
            help=description,
            key=f"param_{key}"
        )
    else:
        value = st.text_input(
            label,
            value=str(current_value),
            help=description,
            key=f"param_{key}"
        )
    
    # 保存到 session_state
    st.session_state.strategy_config[key] = value


def _extract_config_schema(code: str) -> Optional[Dict[str, Any]]:
    """从代码中提取 config schema"""
    try:
        # 尝试执行代码并获取 schema
        import ast
        import sys
        from io import StringIO
        
        # 解析代码找到类名
        tree = ast.parse(code)
        class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        
        if not class_names:
            return None
        
        # 创建临时模块执行代码
        temp_globals = {
            '__builtins__': __builtins__,
            'np': __import__('numpy'),
        }
        
        # 添加必要的导入
        try:
            from strategies.advanced_strategy_template import AdvancedStrategyBase, PositionSide, RiskConfig
            temp_globals['AdvancedStrategyBase'] = AdvancedStrategyBase
            temp_globals['PositionSide'] = PositionSide
            temp_globals['RiskConfig'] = RiskConfig
        except ImportError:
            pass
        
        try:
            exec(code, temp_globals)
        except Exception:
            return None
        
        # 查找有 get_config_schema 方法的类
        for class_name in class_names:
            if class_name in temp_globals:
                cls = temp_globals[class_name]
                if hasattr(cls, 'get_config_schema'):
                    try:
                        instance = cls()
                        return instance.get_config_schema()
                    except Exception:
                        pass
        
        return None
    except Exception:
        return None


def _get_default_advanced_schema() -> Dict[str, Any]:
    """获取默认的高级策略参数 schema"""
    return {
        "risk_per_trade": {
            "type": "float",
            "label": "单笔风险比例",
            "default": 0.008,
            "min": 0.001,
            "max": 0.05,
            "step": 0.001,
            "description": "每笔交易最大风险占账户权益的比例"
        },
        "max_leverage": {
            "type": "int",
            "label": "最大杠杆",
            "default": 5,
            "min": 1,
            "max": 20,
            "description": "正常情况下的最大杠杆倍数"
        },
        "high_volatility_leverage": {
            "type": "int",
            "label": "高波动杠杆",
            "default": 2,
            "min": 1,
            "max": 10,
            "description": "高波动时自动降低到此杠杆"
        },
        "atr_sl_multiplier": {
            "type": "float",
            "label": "ATR止损倍数",
            "default": 2.2,
            "min": 1.0,
            "max": 5.0,
            "step": 0.1,
            "description": "止损距离 = ATR × 此倍数"
        },
        "min_sl_pct": {
            "type": "float",
            "label": "最小止损%",
            "default": 0.3,
            "min": 0.1,
            "max": 1.0,
            "step": 0.1,
            "description": "止损距离最小百分比"
        },
        "max_sl_pct": {
            "type": "float",
            "label": "最大止损%",
            "default": 2.0,
            "min": 0.5,
            "max": 5.0,
            "step": 0.1,
            "description": "止损距离最大百分比"
        },
        "tp1_r_multiple": {
            "type": "float",
            "label": "TP1 R倍数",
            "default": 1.0,
            "min": 0.5,
            "max": 3.0,
            "step": 0.1,
            "description": "第一止盈目标的R倍数"
        },
        "tp1_close_pct": {
            "type": "float",
            "label": "TP1 平仓比例",
            "default": 0.30,
            "min": 0.1,
            "max": 0.5,
            "step": 0.05,
            "description": "TP1触发时平仓的比例"
        },
        "tp2_r_multiple": {
            "type": "float",
            "label": "TP2 R倍数",
            "default": 2.0,
            "min": 1.0,
            "max": 5.0,
            "step": 0.1,
            "description": "第二止盈目标的R倍数"
        },
        "tp2_close_pct": {
            "type": "float",
            "label": "TP2 平仓比例",
            "default": 0.30,
            "min": 0.1,
            "max": 0.5,
            "step": 0.05,
            "description": "TP2触发时平仓的比例"
        },
        "tp3_trailing_atr": {
            "type": "float",
            "label": "追踪止损ATR倍数",
            "default": 2.0,
            "min": 1.0,
            "max": 4.0,
            "step": 0.1,
            "description": "TP2后追踪止损距离 = ATR × 此倍数"
        },
        "cooldown_bars": {
            "type": "int",
            "label": "入场冷却K线数",
            "default": 3,
            "min": 1,
            "max": 10,
            "description": "入场后禁止加仓的K线数"
        },
        "post_sl_cooldown": {
            "type": "int",
            "label": "止损后冷却K线数",
            "default": 10,
            "min": 5,
            "max": 20,
            "description": "止损后需要更强信号的K线数"
        },
        "enable_time_filter": {
            "type": "bool",
            "label": "启用时间过滤",
            "default": True,
            "description": "是否启用交易时段过滤"
        },
        "trading_start_hour_1": {
            "type": "int",
            "label": "时段1开始(UTC)",
            "default": 0,
            "min": 0,
            "max": 23,
            "description": "第一个交易时段开始小时"
        },
        "trading_end_hour_1": {
            "type": "int",
            "label": "时段1结束(UTC)",
            "default": 8,
            "min": 0,
            "max": 24,
            "description": "第一个交易时段结束小时"
        },
        "trading_start_hour_2": {
            "type": "int",
            "label": "时段2开始(UTC)",
            "default": 12,
            "min": 0,
            "max": 23,
            "description": "第二个交易时段开始小时"
        },
        "trading_end_hour_2": {
            "type": "int",
            "label": "时段2结束(UTC)",
            "default": 20,
            "min": 0,
            "max": 24,
            "description": "第二个交易时段结束小时"
        },
    }


def _render_action_buttons(actions: Dict[str, Any]):
    """操作按钮区 - 居中显示"""
    has_code = bool(st.session_state.get('generated_code'))
    is_valid = st.session_state.get('validation_result', {}).get('valid', False)
    
    # 使用空列实现居中
    spacer1, col1, col2, col3, spacer2 = st.columns([1, 1, 1, 1, 1])
    
    with col1:
        if st.button("(｡♥‿♥｡) 保存", key="save_strategy", disabled=not is_valid, type="primary" if is_valid else "secondary", use_container_width=True):
            # 打开保存对话框
            st.session_state.show_save_dialog = True
            st.rerun()
    
    with col2:
        if st.button("(◕‿◕) AI评估", key="ai_evaluate", disabled=not has_code, use_container_width=True):
            _evaluate_strategy()
    
    with col3:
        if st.button("(╯°□°)╯ 清空", key="clear_all", use_container_width=True):
            st.session_state.generated_code = ""
            st.session_state.validation_result = {}
            st.session_state.evaluation_result = ""
            st.session_state.show_save_dialog = False
            st.rerun()
    
    # 显示保存对话框（在按钮下方）
    if st.session_state.get('show_save_dialog', False):
        _show_save_dialog()


def _render_ai_evaluation():
    """AI 策略评估区域"""
    if 'evaluation_result' in st.session_state and st.session_state.evaluation_result:
        st.markdown("""
        <div class="ai-evaluation-card">
            <div class="ai-evaluation-header">
                <span class="ai-evaluation-title">(◕ᴗ◕✿) AI 策略评估</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(st.session_state.evaluation_result)


def _evaluate_strategy():
    """使用 AI 评估策略"""
    code = st.session_state.get('generated_code', '')
    if not code:
        st.warning("请先生成策略代码")
        return
    
    ai_id = st.session_state.get('strategy_ai_id')
    ai_key = st.session_state.get('strategy_ai_key')
    ai_model = st.session_state.get('strategy_ai_model')
    
    if not ai_id or not ai_key:
        # 无 AI，使用简单评估
        st.session_state.evaluation_result = _simple_evaluate(code)
        st.rerun()
        return
    
    with st.spinner(f"正在使用 {ai_id} 评估策略..."):
        try:
            from ai.ai_providers import UniversalAIClient, get_provider
            
            # 检测是否是高级策略
            is_advanced = 'AdvancedStrategyBase' in code
            
            if is_advanced:
                prompt = f"""请评估以下交易策略代码，从以下几个方面给出建议：

**重要背景**：这是一个继承 AdvancedStrategyBase 的高级策略。基类已内置以下功能：
- 动态 ATR 止损（根据波动率自动调整）
- 分批止盈（TP1/TP2/TP3 三档止盈）
- 追踪止损（TP2 后启动）
- 时间过滤（可配置交易时段）
- 防抖机制（止损后冷却期）
- 动态杠杆（高波动自动降杠杆）

子类只需实现 check_entry_signal() 返回入场信号，止盈止损由基类自动管理。

请评估：
1. **入场逻辑**：check_entry_signal() 中的入场条件是否合理？
2. **指标选择**：使用的技术指标是否适合该策略类型？
3. **适用场景**：适合什么市场环境？
4. **改进建议**：入场逻辑有哪些可以优化的地方？

策略代码：
```python
{code}
```

请用中文回答，简洁明了。注意：止盈止损已由基类实现，无需在子类中重复实现。"""
            else:
                prompt = f"""请评估以下交易策略代码，从以下几个方面给出建议：

1. **策略逻辑**：策略的核心逻辑是否合理？
2. **风险控制**：是否有止损/止盈机制？
3. **适用场景**：适合什么市场环境？
4. **改进建议**：有哪些可以优化的地方？

策略代码：
```python
{code}
```

请用中文回答，简洁明了。"""
            
            client = UniversalAIClient(ai_id, ai_key, ai_model)
            response = client.chat(prompt, max_tokens=2000)
            
            if response:
                st.session_state.evaluation_result = response
            else:
                st.session_state.evaluation_result = _simple_evaluate(code)
            
            st.rerun()
        except Exception as e:
            st.session_state.evaluation_result = f"AI 评估失败: {str(e)}\n\n" + _simple_evaluate(code)
            st.rerun()


def _simple_evaluate(code: str) -> str:
    """简单策略评估（无 AI 时使用）"""
    evaluation = "### (◕ᴗ◕✿) 策略分析\n\n"
    
    # 检测使用的指标
    indicators = []
    if 'ema' in code.lower():
        indicators.append("EMA 均线")
    if 'sma' in code.lower():
        indicators.append("SMA 均线")
    if 'rsi' in code.lower():
        indicators.append("RSI 相对强弱")
    if 'macd' in code.lower():
        indicators.append("MACD")
    if 'boll' in code.lower() or 'bbands' in code.lower():
        indicators.append("布林带")
    
    if indicators:
        evaluation += f"**使用的指标**: {', '.join(indicators)}\n\n"
    
    # 检测信号类型
    signals = []
    if 'open_long' in code:
        signals.append("做多")
    if 'open_short' in code:
        signals.append("做空")
    if 'close_long' in code or 'close_short' in code:
        signals.append("平仓")
    
    if signals:
        evaluation += f"**信号类型**: {', '.join(signals)}\n\n"
    
    # 简单建议
    evaluation += "**建议**:\n"
    evaluation += "- 建议添加止损逻辑以控制风险\n"
    evaluation += "- 可以考虑结合多个指标提高准确率\n"
    evaluation += "- 建议在不同市场环境下回测验证\n"
    
    return evaluation


# ============ 辅助函数 ============

def _auto_validate(code: str) -> dict:
    """自动验证代码（生成/转换后调用）"""
    try:
        from strategies.strategy_validator import StrategyValidator
        validator = StrategyValidator()
        return validator.validate(code)
    except ImportError:
        return _simple_validate(code)
    except Exception:
        return _simple_validate(code)


def _get_strategy_template_simple() -> str:
    """获取简化的策略模板（兼容传统引擎）"""
    return '''class MyStrategy:
    def __init__(self, config=None):
        self.config = config or {}
        self.position_pct = 2.0  # 仓位比例 %
        self.leverage = 50  # 杠杆
    
    def analyze(self, ohlcv, symbol, timeframe='5m'):
        import pandas_ta as ta
        # 计算指标
        # 生成信号
        return {
            "action": "HOLD",  # LONG/SHORT/HOLD
            "type": "CUSTOM",
            "position_pct": self.position_pct,
            "leverage": self.leverage,
            "reason": ""
        }
'''


def _generate_from_natural_language(description: str):
    """从自然语言生成策略代码"""
    ai_id = st.session_state.get('strategy_ai_id')
    ai_key = st.session_state.get('strategy_ai_key')
    ai_model = st.session_state.get('strategy_ai_model')  # 获取选择的模型
    
    with st.spinner("正在生成策略代码..."):
        try:
            from strategies.strategy_generator import StrategyGenerator
            generator = StrategyGenerator()
            
            # 如果有选择的 AI，使用该 AI
            if ai_id and ai_key:
                generator.ai_config = {
                    "ai_id": ai_id,
                    "api_key": ai_key,
                    "model_id": ai_model,  # 传递模型 ID
                    "enabled": True
                }
            
            result = generator.generate_from_description(description)
            
            if result.get('success'):
                code = result.get('code', '')
                st.session_state.generated_code = code
                # 自动验证生成的代码
                st.session_state.validation_result = _auto_validate(code)
                st.success("(≧▽≦) 策略代码生成成功！")
                st.rerun()
            else:
                st.error(f"生成失败: {result.get('error', '未知错误')}")
        except ImportError:
            st.error(" strategy_generator 模块未找到")
        except Exception as e:
            st.error(f"生成失败: {str(e)}")


def _convert_pine_script(pine_code: str):
    """转换 Pine Script 为 Python"""
    with st.spinner("正在转换..."):
        try:
            from strategies.pine_converter import PineConverter
            converter = PineConverter()
            result = converter.convert(pine_code)
            
            if result.get('code'):
                code = result.get('code', '')
                st.session_state.generated_code = code
                # 自动验证转换的代码
                st.session_state.validation_result = _auto_validate(code)
                if result.get('unsupported'):
                    st.warning(f"部分函数不支持: {', '.join(result['unsupported'])}")
                else:
                    st.success("(≧▽≦) 转换成功！")
                st.rerun()
            else:
                st.error("转换失败")
        except ImportError:
            st.error(" pine_converter 模块未找到")
        except Exception as e:
            st.error(f"转换失败: {str(e)}")


def _validate_python_code(code: str):
    """验证 Python 代码"""
    with st.spinner("正在验证..."):
        try:
            from strategies.strategy_validator import StrategyValidator
            validator = StrategyValidator()
            result = validator.validate(code)
            
            st.session_state.validation_result = result
            st.session_state.generated_code = code
            st.rerun()
        except ImportError:
            result = _simple_validate(code)
            st.session_state.validation_result = result
            st.session_state.generated_code = code
            st.rerun()
        except Exception as e:
            st.error(f"验证失败: {str(e)}")


def _auto_convert_code():
    """自动转换代码为传统引擎格式"""
    code = st.session_state.get('generated_code', '')
    if not code:
        st.warning("没有可转换的代码")
        return
    
    with st.spinner("正在转换..."):
        try:
            from strategies.strategy_validator import StrategyValidator
            validator = StrategyValidator()
            result = validator.convert_to_engine_format(code)
            
            if result.get('success'):
                converted_code = result.get('code', '')
                changes = result.get('changes', [])
                
                # 更新代码
                st.session_state.generated_code = converted_code
                
                # 重新验证转换后的代码
                new_validation = validator.validate(converted_code)
                st.session_state.validation_result = new_validation
                
                # 显示转换结果
                if changes:
                    st.success(f"(≧▽≦) 转换成功！修改了 {len(changes)} 处")
                    for change in changes:
                        st.caption(f"  • {change}")
                else:
                    st.success("(≧▽≦) 代码已是标准格式")
                
                st.rerun()
            else:
                st.error(f"转换失败: {result.get('error', '未知错误')}")
        except ImportError:
            st.error(" strategy_validator 模块未找到")
        except Exception as e:
            st.error(f"转换失败: {str(e)}")


def _simple_validate(code: str) -> dict:
    """简单代码验证"""
    import ast
    errors = []
    warnings = []
    
    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append(f"语法错误 (行 {e.lineno}): {e.msg}")
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    if "def analyze" not in code:
        errors.append("缺少 analyze() 方法")
    
    if "signal" not in code:
        warnings.append("代码中未找到 'signal' 关键字")
    
    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def _show_save_dialog():
    """显示保存策略对话框"""
    st.markdown("---")
    st.markdown("### (｡♥‿♥｡) 保存策略")
    
    # 使用 session_state 存储输入值
    if 'save_strategy_id' not in st.session_state:
        st.session_state.save_strategy_id = ""
    if 'save_display_name' not in st.session_state:
        st.session_state.save_display_name = ""
    if 'save_description' not in st.session_state:
        st.session_state.save_description = ""
    
    strategy_id = st.text_input(
        "策略 ID",
        value=st.session_state.save_strategy_id,
        placeholder="my_ema_cross",
        help="小写字母、数字和下划线，必须以小写字母开头",
        key="input_strategy_id"
    )
    display_name = st.text_input(
        "显示名称",
        value=st.session_state.save_display_name,
        placeholder="EMA 交叉策略",
        key="input_display_name"
    )
    description = st.text_area(
        "策略描述",
        value=st.session_state.save_description,
        placeholder="基于 EMA 交叉的趋势策略",
        height=80,
        key="input_description"
    )
    
    # 更新 session_state
    st.session_state.save_strategy_id = strategy_id
    st.session_state.save_display_name = display_name
    st.session_state.save_description = description
    
    col_save, col_cancel = st.columns(2)
    
    with col_save:
        if st.button("💾 确认保存", type="primary", key="confirm_save_btn", use_container_width=True):
            if not strategy_id or not display_name:
                st.error("请填写策略 ID 和显示名称")
            elif not strategy_id.replace('_', '').isalnum() or not strategy_id[0].islower() or not strategy_id.islower():
                st.error("策略 ID 必须以小写字母开头，只能包含小写字母、数字和下划线")
            else:
                _save_strategy(strategy_id, display_name, description)
                # 清空输入并关闭对话框
                st.session_state.save_strategy_id = ""
                st.session_state.save_display_name = ""
                st.session_state.save_description = ""
                st.session_state.show_save_dialog = False
    
    with col_cancel:
        if st.button("❌ 取消", key="cancel_save_btn", use_container_width=True):
            st.session_state.show_save_dialog = False
            st.rerun()


def _save_strategy(strategy_id: str, display_name: str, description: str):
    """保存策略"""
    code = st.session_state.get('generated_code', '')
    if not code:
        st.error("没有可保存的代码")
        return
    
    try:
        from strategies.strategy_registry import save_new_strategy
        
        # 获取策略配置（如果有）
        strategy_config = st.session_state.get('strategy_config', {})
        
        # 检测是否是高级策略
        is_advanced = 'AdvancedStrategyBase' in code or 'get_config_schema' in code
        
        result = save_new_strategy(
            strategy_id, 
            display_name, 
            code, 
            description,
            config=strategy_config if is_advanced else None,
            is_advanced=is_advanced
        )
        
        if result.get('success'):
            st.success(f"(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧ 策略 '{display_name}' 保存成功！")
            if is_advanced:
                st.info("这是一个高级策略，支持动态止盈止损和分批平仓")
            st.info("刷新页面后可在策略下拉列表中看到")
            # 清空状态
            st.session_state.generated_code = ""
            st.session_state.validation_result = {}
            st.session_state.strategy_config = {}
            st.session_state.show_save_dialog = False
            # 延迟刷新让用户看到成功消息
            import time
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"保存失败: {result.get('error')}")
    except Exception as e:
        import traceback
        st.error(f"保存失败: {str(e)}")
        st.code(traceback.format_exc(), language="text")


# ============ 策略管理 ============

def _render_strategy_manager():
    """渲染策略管理区域"""
    st.markdown("---")
    st.markdown("### (◕‿◕) 已保存的自定义策略")
    
    try:
        from strategies.strategy_registry import list_user_strategies, delete_strategy
        import os
        
        user_strategies = list_user_strategies()
        
        if not user_strategies:
            st.info("(´・ω・`) 暂无自定义策略，快去创建一个吧~")
            return
        
        for strategy in user_strategies:
            strategy_id = strategy['strategy_id']
            
            # 使用 expander 显示策略详情
            with st.expander(f"**{strategy['display_name']}** `{strategy_id}`", expanded=False):
                # 策略信息
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.caption(f"版本: {strategy.get('version', '1.0.0')}")
                with col_info2:
                    if strategy.get('created_at'):
                        st.caption(f"创建: {strategy['created_at'][:10]}")
                
                if strategy.get('description'):
                    st.markdown(f"*{strategy['description']}*")
                
                # 显示策略代码
                st.markdown("**策略代码:**")
                code = _load_strategy_code(strategy_id)
                if code:
                    st.code(code, language="python")
                else:
                    st.warning("无法加载策略代码")
                
                # 操作按钮
                col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                
                with col_btn1:
                    if st.button("(◕‿◕) 加载编辑", key=f"load_{strategy_id}", use_container_width=True):
                        if code:
                            st.session_state.generated_code = code
                            st.session_state.validation_result = _auto_validate(code)
                            st.success("已加载到编辑区")
                            st.rerun()
                
                with col_btn2:
                    # 使用确认机制的删除按钮
                    delete_key = f"confirm_del_{strategy_id}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False
                    
                    if not st.session_state[delete_key]:
                        if st.button("(╯°□°)╯ 删除", key=f"del_{strategy_id}", type="secondary", use_container_width=True):
                            st.session_state[delete_key] = True
                            st.rerun()
                    else:
                        # 确认删除
                        st.warning("确定要删除吗？")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("确定", key=f"yes_{strategy_id}", type="primary"):
                                result = delete_strategy(strategy_id)
                                if result.get('success'):
                                    st.success("(≧▽≦) 已删除")
                                    st.session_state[delete_key] = False
                                    st.rerun()
                                else:
                                    st.error(result.get('error'))
                        with col_no:
                            if st.button("取消", key=f"no_{strategy_id}"):
                                st.session_state[delete_key] = False
                                st.rerun()
    
    except ImportError:
        st.error("策略管理模块未加载")


def _load_strategy_code(strategy_id: str) -> str:
    """加载策略代码"""
    import os
    strategies_dir = os.path.join(os.path.dirname(__file__), 'strategies')
    init_path = os.path.join(strategies_dir, strategy_id, '__init__.py')
    
    if os.path.isfile(init_path):
        try:
            with open(init_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            pass
    return None


# ============ 回测功能 ============

def _render_backtest_tab():
    """渲染策略回测 Tab"""
    st.markdown("### (◕ᴗ◕✿) 策略回测")
    st.caption("选择策略、币种、时间周期和回测时间段，验证策略在历史数据上的表现")
    
    # 回测配置区域
    col1, col2 = st.columns(2)
    
    with col1:
        # 策略选择
        st.markdown("**(◕‿◕) 选择策略**")
        
        # 获取可用策略列表
        strategy_options = _get_backtest_strategy_options()
        
        selected_strategy = st.selectbox(
            "策略",
            options=list(strategy_options.keys()),
            key="backtest_strategy_select",
            label_visibility="collapsed"
        )
        
        # 或者使用当前生成的代码
        use_current_code = st.checkbox(
            "使用当前生成的代码",
            value=False,
            key="backtest_use_current",
            help="勾选后将使用上方生成/粘贴的策略代码进行回测"
        )
        
        # 币种选择（从交易池读取）
        st.markdown("**(｡･ω･｡) 交易对**")
        
        # 从 session_state 获取交易池
        trading_pool = st.session_state.get('auto_symbols', ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT'])
        
        if not trading_pool:
            trading_pool = ['BTC/USDT:USDT']
            st.caption("(・_・) 交易池为空，请先在主页面配置")
        
        # 生成显示名称（简化显示）
        def get_display_name(symbol: str) -> str:
            """BTC/USDT:USDT -> BTC"""
            if '/' in symbol:
                return symbol.split('/')[0]
            return symbol
        
        # 下拉选择框
        symbol_input = st.selectbox(
            "交易对",
            options=trading_pool,
            format_func=get_display_name,
            key="backtest_symbol",
            label_visibility="collapsed"
        )
    
    with col2:
        # 时间周期
        st.markdown("**(≧▽≦) 时间周期**")
        timeframe_options = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d']
        selected_tf = st.selectbox(
            "周期",
            options=timeframe_options,
            index=3,  # 默认 15m
            key="backtest_timeframe",
            label_visibility="collapsed"
        )
        
        # 回测时间段
        st.markdown("**(•̀ᴗ•́)و 回测时间段**")
        
        from datetime import datetime, timedelta
        
        # 默认日期：最近30天
        default_end = datetime.now().date()
        default_start = default_end - timedelta(days=30)
        
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input(
                "开始日期",
                value=default_start,
                key="backtest_start_date"
            )
        with col_end:
            end_date = st.date_input(
                "结束日期",
                value=default_end,
                key="backtest_end_date"
            )
    
    st.markdown("---")
    
    # 高级配置（可折叠）
    with st.expander("(◕‿◕) 高级配置", expanded=False):
        # 配置说明
        st.info("""
        **(｡･ω･｡) 配置说明**
        - 高级策略（如趋势跟踪）会使用内置风控配置（动态止损、分批止盈等）
        - 简单策略使用下方的仓位比例和杠杆设置
        - 初始资金、手续费、滑点对所有策略生效
        """)
        
        col_adv1, col_adv2 = st.columns(2)
        
        with col_adv1:
            initial_capital = st.number_input(
                "初始资金 (USDT)",
                min_value=100.0,
                max_value=1000000.0,
                value=10000.0,
                step=1000.0,
                key="backtest_capital"
            )
        
        with col_adv2:
            commission_rate = st.number_input(
                "手续费率 (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.06,
                step=0.01,
                format="%.2f",
                key="backtest_commission",
                help="单边手续费率，OKX 默认 0.06%"
            )
        
        col_adv3, col_adv4 = st.columns(2)
        
        with col_adv3:
            slippage_rate = st.number_input(
                "滑点 (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.01,
                step=0.01,
                format="%.2f",
                key="backtest_slippage",
                help="模拟滑点损耗"
            )
        
        with col_adv4:
            position_pct = st.number_input(
                "仓位比例 (%)",
                min_value=0.5,
                max_value=100.0,
                value=2.0,
                step=0.5,
                key="backtest_position_pct",
                help="简单策略使用，高级策略会忽略"
            )
        
        col_adv5, col_adv6 = st.columns(2)
        
        with col_adv5:
            leverage = st.number_input(
                "杠杆倍数",
                min_value=1,
                max_value=125,
                value=5,
                step=1,
                key="backtest_leverage",
                help="简单策略使用，高级策略有内置杠杆配置"
            )
        
        with col_adv6:
            st.caption("")  # 占位
    
    # 运行回测按钮
    st.markdown("")
    col_run, col_spacer = st.columns([1, 3])
    with col_run:
        run_backtest = st.button(
            "(ﾉ◕ヮ◕)ﾉ 运行回测",
            type="primary",
            use_container_width=True,
            key="run_backtest_btn"
        )
    
    if run_backtest:
        _run_backtest(
            strategy_options.get(selected_strategy),
            use_current_code,
            symbol_input,
            selected_tf,
            start_date,
            end_date,
            initial_capital,
            position_pct,
            leverage,
            commission_rate / 100,
            slippage_rate / 100
        )
    
    # 显示回测结果
    _render_backtest_results()


def _get_backtest_strategy_options() -> Dict[str, str]:
    """获取可用于回测的策略列表"""
    options = {}
    
    try:
        from strategies.strategy_registry import list_all_strategies, get_strategy_registry
        
        strategies = list_all_strategies()
        registry = get_strategy_registry()
        
        for display_name, strategy_id in strategies:
            # 获取策略代码
            meta = registry.get_strategy_meta(strategy_id)
            if meta:
                file_path = meta.get('file_path')
                if file_path:
                    import os
                    if os.path.isdir(file_path):
                        init_path = os.path.join(file_path, '__init__.py')
                        if os.path.isfile(init_path):
                            try:
                                with open(init_path, 'r', encoding='utf-8') as f:
                                    code = f.read()
                                    options[display_name] = code
                            except:
                                pass
                    elif os.path.isfile(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                code = f.read()
                                options[display_name] = code
                        except:
                            pass
    except Exception as e:
        print(f"获取策略列表失败: {e}")
    
    if not options:
        options["(无可用策略)"] = ""
    
    return options


def _run_backtest(
    strategy_code: str,
    use_current_code: bool,
    symbol: str,
    timeframe: str,
    start_date,
    end_date,
    initial_capital: float,
    position_pct: float,
    leverage: int,
    commission_rate: float,
    slippage_rate: float
):
    """运行回测"""
    from datetime import datetime
    
    # 确定使用的策略代码
    if use_current_code:
        code = st.session_state.get('generated_code', '')
        if not code:
            st.error("请先生成或粘贴策略代码")
            return
    else:
        code = strategy_code
        if not code:
            st.error("请选择一个策略")
            return
    
    # 转换日期
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # 验证日期
    if start_datetime >= end_datetime:
        st.error("开始日期必须早于结束日期")
        return
    
    # 创建进度条
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def progress_callback(current, total, message):
        progress_bar.progress(current / total)
        status_text.text(message)
    
    try:
        from core.backtest_engine import get_backtest_engine, BacktestConfig
        
        # 重新创建引擎实例（确保代理配置最新）
        import backtest_engine
        backtest_engine._backtest_engine = None
        engine = get_backtest_engine()
        
        if not engine.exchange:
            progress_bar.empty()
            status_text.empty()
            st.error("❌ 无法连接交易所，请检查网络和代理配置")
            st.info("""
            **可能的解决方案：**
            1. 确保 `.env` 文件中配置了正确的代理：
               ```
               HTTP_PROXY=http://127.0.0.1:49494
               HTTPS_PROXY=http://127.0.0.1:49494
               ```
            2. 确保代理软件（如 Clash Verge）正在运行
            3. 检查代理端口是否正确
            """)
            return
        
        config = BacktestConfig(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_datetime,
            end_date=end_datetime,
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
            leverage=leverage,
            position_pct=position_pct,
        )
        
        result = engine.run_backtest(code, config, progress_callback)
        
        # 保存结果到 session_state
        st.session_state.backtest_result = result
        
        progress_bar.empty()
        status_text.empty()
        
        if result.error:
            st.error(f"回测失败: {result.error}")
            if "数据不足" in result.error or "0 根" in result.error:
                st.info("""
                **数据获取失败的可能原因：**
                1. 网络无法连接 OKX（需要代理）
                2. 代理配置不正确或代理软件未运行
                3. 交易对不存在（请使用正确的格式，如 BTC/USDT:USDT）
                4. 时间范围内没有数据
                """)
        else:
            st.success("(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧ 回测完成！")
            st.rerun()
        
    except Exception as e:
        import traceback
        progress_bar.empty()
        status_text.empty()
        st.error(f"回测出错: {str(e)}")
        st.code(traceback.format_exc(), language="text")


def _render_backtest_results():
    """渲染回测结果"""
    result = st.session_state.get('backtest_result')
    
    if not result:
        return
    
    if result.error:
        return
    
    st.markdown("---")
    st.markdown("### (◕ᴗ◕✿) 回测结果")
    
    # 风险提示
    st.warning("""
    **(｡•́︿•̀｡) 风险提示**：回测结果仅供参考，不代表未来收益。
    历史表现不能保证未来结果，回测可能存在过度拟合风险。
    """)
    
    # 基本信息表格
    st.markdown("#### (◕‿◕) 基本信息")
    info_data = {
        "项目": ["交易对", "时间周期", "K线数量", "交易次数", "回测时间"],
        "数值": [
            result.symbol.split('/')[0] if '/' in result.symbol else result.symbol,
            result.timeframe,
            f"{result.total_bars:,}",
            str(result.total_trades),
            f"{result.start_date} ~ {result.end_date}"
        ]
    }
    st.dataframe(
        info_data,
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    
    # 核心指标表格（三列布局）
    col_left, col_mid, col_right = st.columns(3)
    
    with col_left:
        st.markdown("#### (≧▽≦) 收益指标")
        
        # 收益状态
        profit_status = "(◕ᴗ◕✿) 盈利" if result.total_return >= 0 else "(╥﹏╥) 亏损"
        
        profit_data = [
            ["总收益", f"${result.total_return:,.2f}", f"{result.total_return_pct:+.2f}%"],
            ["最终资金", f"${result.final_capital:,.2f}", f"初始 ${result.initial_capital:,.0f}"],
            ["年化收益率", f"{result.annualized_return:+.2f}%", profit_status],
            ["盈亏比", f"{result.profit_factor:.2f}" if result.profit_factor > 0 else "N/A", ""],
        ]
        
        import pandas as pd
        df_profit = pd.DataFrame(profit_data, columns=["指标", "数值", "备注"])
        st.dataframe(df_profit, use_container_width=True, hide_index=True)
    
    with col_mid:
        st.markdown("#### (•̀ᴗ•́)و 风险指标")
        
        # 夏普评级
        if result.sharpe_ratio >= 2:
            sharpe_rating = "(◕ᴗ◕✿) 优秀"
        elif result.sharpe_ratio >= 1:
            sharpe_rating = "(◕‿◕) 良好"
        elif result.sharpe_ratio >= 0:
            sharpe_rating = "(・_・) 一般"
        else:
            sharpe_rating = "(╥﹏╥) 较差"
        
        risk_data = [
            ["最大回撤", f"${result.max_drawdown:,.2f}", f"-{result.max_drawdown_pct:.2f}%"],
            ["夏普比率", f"{result.sharpe_ratio:.2f}", sharpe_rating],
            ["Sortino比率", f"{result.sortino_ratio:.2f}" if result.sortino_ratio else "N/A", ""],
            ["Calmar比率", f"{result.calmar_ratio:.2f}" if result.calmar_ratio else "N/A", ""],
        ]
        
        df_risk = pd.DataFrame(risk_data, columns=["指标", "数值", "评级"])
        st.dataframe(df_risk, use_container_width=True, hide_index=True)
    
    with col_right:
        st.markdown("#### (｡･ω･｡) 交易统计")
        
        # 胜率评级
        if result.win_rate >= 60:
            win_rating = "(◕ᴗ◕✿) 优秀"
        elif result.win_rate >= 50:
            win_rating = "(◕‿◕) 良好"
        else:
            win_rating = "(・_・) 待优化"
        
        trade_data = [
            ["胜率", f"{result.win_rate:.1f}%", f"{result.winning_trades}胜/{result.losing_trades}负"],
            ["平均盈利", f"${result.avg_win:.2f}" if result.avg_win else "N/A", ""],
            ["平均亏损", f"${result.avg_loss:.2f}" if result.avg_loss else "N/A", ""],
            ["平均持仓", f"{result.avg_trade_duration:.1f}h" if result.avg_trade_duration else "N/A", ""],
            ["连续盈利", f"{result.max_consecutive_wins}次", ""],
            ["连续亏损", f"{result.max_consecutive_losses}次", ""],
        ]
        
        df_trade = pd.DataFrame(trade_data, columns=["指标", "数值", "备注"])
        st.dataframe(df_trade, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # 权益曲线图
    if result.equity_curve:
        st.markdown("#### (◕ᴗ◕✿) 收益率曲线")
        _render_equity_chart(result.equity_curve, result.initial_capital)
    
    # 交易记录表
    if result.trades:
        st.markdown("#### (≧▽≦) 交易记录")
        _render_trades_table(result.trades)


def _render_equity_chart(equity_curve: List[Dict], initial_capital: float = 10000.0):
    """渲染权益曲线图（简洁风格）"""
    import pandas as pd
    import numpy as np
    import plotly.graph_objects as go
    
    df = pd.DataFrame(equity_curve)
    
    if len(df) == 0:
        st.info("暂无权益数据")
        return
    
    # 计算收益率百分比（相对于初始资金）
    df['return_pct'] = (df['equity'] - initial_capital) / initial_capital * 100
    
    # 采样：如果数据点太多，进行采样以提高渲染速度
    max_points = 500
    if len(df) > max_points:
        step = len(df) // max_points
        indices = list(range(0, len(df), step))
        if indices[-1] != len(df) - 1:
            indices.append(len(df) - 1)
        max_idx = df['return_pct'].idxmax()
        min_idx = df['return_pct'].idxmin()
        if max_idx not in indices:
            indices.append(max_idx)
        if min_idx not in indices:
            indices.append(min_idx)
        indices = sorted(set(indices))
        df = df.iloc[indices].reset_index(drop=True)
    
    # 计算关键统计
    final_return = df['return_pct'].iloc[-1]
    max_return = df['return_pct'].max()
    min_return = df['return_pct'].min()
    
    # 显示关键统计
    col1, col2, col3 = st.columns(3)
    with col1:
        color = "normal" if final_return >= 0 else "inverse"
        st.metric(
            "最终收益率", 
            f"{final_return:+.2f}%",
            delta=f"${final_return * initial_capital / 100:,.2f}",
            delta_color=color
        )
    with col2:
        st.metric("最高收益率", f"{max_return:+.2f}%")
    with col3:
        st.metric("最低收益率", f"{min_return:+.2f}%")
    
    # 创建 Plotly 图表
    fig = go.Figure()
    
    # 根据最终收益决定颜色
    line_color = '#26a69a' if final_return >= 0 else '#ef5350'
    fill_color = 'rgba(38, 166, 154, 0.2)' if final_return >= 0 else 'rgba(239, 83, 80, 0.2)'
    
    # 添加主曲线
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['return_pct'],
        mode='lines',
        name='收益率',
        line=dict(color=line_color, width=1.5),
        fill='tozeroy',
        fillcolor=fill_color,
        hovertemplate='%{x|%Y-%m-%d %H:%M}<br>收益率: %{y:.2f}%<extra></extra>'
    ))
    
    # 添加零线
    fig.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.4)", line_width=1)
    
    # 计算 Y 轴范围（确保能看到波动）
    y_range = max_return - min_return
    if y_range < 1:  # 如果波动小于1%，扩大显示范围
        y_padding = 0.5
    else:
        y_padding = y_range * 0.1
    
    y_min = min(min_return - y_padding, -0.5)
    y_max = max(max_return + y_padding, 0.5)
    
    # 设置图表布局
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(17,17,17,1)',
        height=300,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.05)',
            tickformat='%m/%d',
            tickfont=dict(size=10, color='rgba(255,255,255,0.6)'),
            showline=False,
            fixedrange=True,  # 禁用 X 轴缩放
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.05)',
            ticksuffix='%',
            tickfont=dict(size=10, color='rgba(255,255,255,0.6)'),
            showline=False,
            zeroline=False,
            range=[y_min, y_max],
            fixedrange=True,  # 禁用 Y 轴缩放
        ),
        hovermode='x unified',
        showlegend=False,
        dragmode=False,  # 禁用拖动
    )
    
    # 渲染图表
    st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': False,  # 隐藏工具栏
    })


def _render_trades_table(trades: List):
    """渲染交易记录表"""
    import pandas as pd
    
    # 转换为 DataFrame（用于显示）
    trade_data = []
    for i, t in enumerate(trades, 1):
        # 使用颜文字表示方向
        direction = "(◕ᴗ◕) 多" if t.side == 'LONG' else "(•̀ᴗ•́) 空"
        
        # 盈亏状态
        if t.pnl > 0:
            pnl_str = f"+${t.pnl:.2f}"
        else:
            pnl_str = f"${t.pnl:.2f}"
        
        trade_data.append({
            '#': i,
            '方向': direction,
            '入场时间': t.entry_time.strftime('%m-%d %H:%M') if t.entry_time else '',
            '出场时间': t.exit_time.strftime('%m-%d %H:%M') if t.exit_time else '',
            '入场价': f"{t.entry_price:.4f}",
            '出场价': f"{t.exit_price:.4f}",
            '盈亏': pnl_str,
            '盈亏%': f"{t.pnl_pct:+.2f}%",
            '手续费': f"${t.commission:.2f}",
            '出场原因': t.exit_reason[:15] + "..." if t.exit_reason and len(t.exit_reason) > 15 else (t.exit_reason or ''),
        })
    
    df = pd.DataFrame(trade_data)
    
    # 显示表格
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    # 创建导出用的数据（完整格式）
    export_data = []
    for i, t in enumerate(trades, 1):
        export_data.append({
            '序号': i,
            '方向': 'LONG' if t.side == 'LONG' else 'SHORT',
            '入场时间': t.entry_time.strftime('%Y-%m-%d %H:%M:%S') if t.entry_time else '',
            '出场时间': t.exit_time.strftime('%Y-%m-%d %H:%M:%S') if t.exit_time else '',
            '入场价': t.entry_price,
            '出场价': t.exit_price,
            '数量': t.quantity,
            '盈亏(USDT)': round(t.pnl, 4),
            '盈亏(%)': round(t.pnl_pct, 4),
            '手续费(USDT)': round(t.commission, 4),
            '入场原因': t.reason or '',
            '出场原因': t.exit_reason or '',
        })
    
    export_df = pd.DataFrame(export_data)
    
    # 导出按钮
    csv = export_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="(◕‿◕) 导出交易记录 (CSV)",
        data=csv,
        file_name="backtest_trades.csv",
        mime="text/csv",
        key="download_trades"
    )

