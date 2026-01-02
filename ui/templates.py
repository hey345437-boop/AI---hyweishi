# -*- coding: utf-8 -*-
"""
UI 模板文件 - 存放 HTML/CSS 模板常量
"""

# 免责声明页面样式
DISCLAIMER_STYLES = """
<style>
.stApp {
    background: #0a0e17 !important;
    overflow: hidden;
}
header[data-testid="stHeader"] {
    background: rgba(10, 14, 23, 0.95) !important;
    backdrop-filter: blur(10px) !important;
}

/* 标题动画 */
@keyframes textGlow {
    0%, 100% { text-shadow: 0 0 20px rgba(255, 107, 157, 0.5), 0 0 40px rgba(255, 107, 157, 0.3); }
    50% { text-shadow: 0 0 30px rgba(255, 143, 171, 0.8), 0 0 60px rgba(255, 143, 171, 0.5); }
}
@keyframes textShine { 
    0% { background-position: 0% 50%; } 
    100% { background-position: 200% 50%; } 
}
@keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-10px); }
}

.login-title {
    font-size: 48px;
    font-weight: 900;
    background: linear-gradient(90deg, #ff6b9d, #ff8fab, #ff4081, #ff6b9d);
    background-size: 200% auto;
    color: transparent;
    -webkit-background-clip: text;
    background-clip: text;
    animation: textShine 3s linear infinite, textGlow 2s ease-in-out infinite;
    letter-spacing: 8px;
    margin-bottom: 10px;
    text-align: center;
}
.login-subtitle {
    font-size: 14px;
    color: #4a5568;
    letter-spacing: 6px;
    font-family: 'Courier New', monospace;
    margin-bottom: 20px;
    text-align: center;
}
.login-icon {
    font-size: 64px;
    margin-bottom: 20px;
    animation: float 3s ease-in-out infinite;
    filter: drop-shadow(0 0 20px rgba(255, 107, 157, 0.5));
    text-align: center;
}
.login-divider {
    width: 120px;
    height: 2px;
    background: linear-gradient(90deg, transparent, #ff6b9d, #ff8fab, transparent);
    margin: 15px auto;
}
.stButton > button {
    background: linear-gradient(135deg, #ff6b9d 0%, #ff4081 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 15px 30px !important;
    font-size: 16px !important;
    width: 100% !important;
    transition: all 0.3s ease !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 30px rgba(255, 107, 157, 0.4) !important;
}
.disclaimer-card {
    background: linear-gradient(145deg, rgba(26, 26, 46, 0.95), rgba(15, 15, 26, 0.98));
    border: 1px solid rgba(255, 107, 157, 0.3);
    border-radius: 16px;
    padding: 24px;
    margin: 20px 0;
    max-height: 400px;
    overflow-y: auto;
}
.disclaimer-title {
    color: #ff6b9d;
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
    text-align: center;
}
.disclaimer-content {
    color: #a0aec0;
    font-size: 13px;
    line-height: 1.8;
}
.disclaimer-content h4 {
    color: #ff8fab;
    margin-top: 16px;
    margin-bottom: 8px;
}
.disclaimer-content ul {
    padding-left: 20px;
}
.disclaimer-content li {
    margin-bottom: 6px;
}
.warning-box {
    background: rgba(255, 193, 7, 0.1);
    border-left: 3px solid #ffc107;
    padding: 12px;
    margin: 16px 0;
    border-radius: 4px;
}
</style>
"""

# 免责声明内容
DISCLAIMER_CONTENT = """
<div class="disclaimer-card">
    <div class="disclaimer-title">⚠️ 免责声明 / Disclaimer</div>
    <div class="disclaimer-content">
        <h4>1. 风险警示</h4>
        <ul>
            <li>加密货币交易具有<b>极高风险</b>，可能导致全部本金损失</li>
            <li>杠杆交易会放大收益和亏损，请谨慎使用</li>
            <li>历史收益不代表未来表现，策略可能在不同市场环境下失效</li>
        </ul>
        <h4>2. 软件声明</h4>
        <ul>
            <li>本软件为<b>开源项目</b>，仅供学习和研究使用</li>
            <li>作者不对使用本软件造成的任何损失承担责任</li>
            <li>本软件不构成任何投资建议</li>
            <li>使用前请确保了解相关法律法规</li>
        </ul>
        <h4>3. 使用条款</h4>
        <ul>
            <li>用户需自行承担使用本软件的全部风险</li>
            <li>请勿将超出承受能力的资金用于交易</li>
            <li>建议先使用模拟账户熟悉系统</li>
            <li>实盘交易前请充分测试策略</li>
        </ul>
        <div class="warning-box">
            <b>⚠️ 重要提醒</b><br>
            投资有风险，入市需谨慎。请确保您已充分了解加密货币交易的风险，
            并且只使用您能够承受损失的资金进行交易。
        </div>
    </div>
</div>
"""

# 引导页面样式
ONBOARDING_STYLES = """
<style>
.stApp {
    background: #0a0e17 !important;
}
header[data-testid="stHeader"] {
    background: rgba(10, 14, 23, 0.95) !important;
}
.onboarding-card {
    background: linear-gradient(145deg, rgba(26, 26, 46, 0.95), rgba(15, 15, 26, 0.98));
    border: 1px solid rgba(255, 107, 157, 0.3);
    border-radius: 16px;
    padding: 24px;
    margin: 16px 0;
}
.step-title {
    color: #ff6b9d;
    font-size: 20px;
    font-weight: 600;
    margin-bottom: 16px;
}
.step-content {
    color: #e2e8f0;
    font-size: 14px;
    line-height: 1.8;
}
.step-number {
    display: inline-block;
    width: 28px;
    height: 28px;
    background: linear-gradient(135deg, #ff6b9d, #ff4081);
    border-radius: 50%;
    text-align: center;
    line-height: 28px;
    color: white;
    font-weight: bold;
    margin-right: 10px;
}
.stButton > button {
    background: linear-gradient(135deg, #ff6b9d 0%, #ff4081 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    color: white !important;
    font-weight: 600 !important;
}
</style>
"""

# 引导步骤内容
ONBOARDING_STEPS = [
    {
        "number": 1,
        "title": "配置交易所 API",
        "content": "• 前往 OKX 交易所创建 API Key<br>• 建议只开启「交易」权限，不要开启「提币」权限<br>• 将 API Key、Secret、Passphrase 填入系统设置"
    },
    {
        "number": 2,
        "title": "选择运行模式",
        "content": "• <b>测试模式</b>：使用真实行情，但不实际下单（推荐新手）<br>• <b>实盘模式</b>：真实交易，请谨慎使用<br>• 建议先在测试模式下熟悉系统"
    },
    {
        "number": 3,
        "title": "配置交易策略",
        "content": "• 选择内置策略或使用 AI 助手创建自定义策略<br>• 设置交易对、仓位比例、杠杆倍数<br>• 配置止盈止损参数"
    },
    {
        "number": 4,
        "title": "启动交易引擎",
        "content": "• 点击「启动机器人」按钮运行交易引擎<br>• 引擎会自动扫描信号并执行交易<br>• 可在界面实时查看持仓和收益"
    }
]

# 联系方式
CONTACT_INFO = {
    "email": "hey345437@gmail.com",
    "qq": "3269180865"
}

CONTACT_FOOTER_HTML = f"""
<div style="text-align: center; color: #555; font-size: 11px; margin-top: 20px;">
    📧 {CONTACT_INFO['email']} | QQ: {CONTACT_INFO['qq']}<br>
    开源项目 · AGPL-3.0 License
</div>
"""

# 主界面底部签名
MAIN_FOOTER_HTML = f"""
<div style="
    position: fixed;
    bottom: 10px;
    right: 15px;
    font-size: 10px;
    color: rgba(255, 255, 255, 0.4);
    z-index: 1000;
    text-align: right;
    line-height: 1.4;
">
    📧 {CONTACT_INFO['email']} | QQ: {CONTACT_INFO['qq']}<br>
    ⚠️ 投资有风险，入市需谨慎 | AGPL-3.0
</div>
"""


def render_onboarding_step(step: dict) -> str:
    """渲染单个引导步骤"""
    return f"""
    <div class="onboarding-card">
        <div class="step-title"><span class="step-number">{step['number']}</span> {step['title']}</div>
        <div class="step-content">{step['content']}</div>
    </div>
    """
