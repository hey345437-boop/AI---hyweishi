# 交易策略审计报告

**审计日期**: 2024-12-16  
**审计范围**: 策略信号逻辑、下单逻辑、所有可能的交易场景

---

## 一、策略概览

| 策略 | 文件 | 描述 | 适用周期 |
|------|------|------|----------|
| 📈 趋势策略 v1 | `strategy_v1.py` | 趋势1.3策略：双MACD + 顶底系统 + SMC订单块 | 30m, 1h |
| 📈 趋势策略 v2 | `strategy_v2.py` | 趋势2.3策略：EMA通道 + 何以为底 + SMC订单块 | 1m, 3m, 5m, 15m, 30m, 1h |

---

## 二、策略 v1 (趋势1.3) 信号逻辑

### 2.1 技术指标

| 指标 | 参数 | 用途 |
|------|------|------|
| Stochastic %K | period=14, smooth=5 | 超买超卖判断 |
| KDJ | ilong=9, isig=3 | 金叉死叉信号 |
| OBV-ADX | len=22, sig=22 | 量能趋势确认 |
| ADX | len=14 | 趋势强度过滤 |
| EMA | 12, 144, 169 | 趋势方向判断 |
| RSI | len=14 | 动量过滤 |
| MACD策略1 | 12, 26, 9 | 主趋势信号 |
| MACD策略2 | 6, 13, 5 | 辅助趋势信号 |
| CCI | 55, 144 | 趋势确认 |

### 2.2 信号类型与条件

#### 主信号：趋势1策略 (MAIN_TREND)
**做多条件** (全部满足):
```
1. trend_filter = ADX > 20 且 ADX斜率 > 0 (趋势确认)
2. trend_up = EMA12 > EMA144 且 EMA12 > EMA169 (上升趋势)
3. RSI 不在 45-55 中性区间
4. MACD策略1金叉 且 CCI55 > 100
   或 MACD策略2金叉 且 CCI144 > 100
```

**做空条件** (全部满足):
```
1. trend_filter = ADX > 20 且 ADX斜率 > 0
2. trend_down = EMA12 < EMA144 且 EMA12 < EMA169 (下降趋势)
3. RSI 不在 45-55 中性区间
4. MACD策略1死叉 且 CCI55 < -100
   或 MACD策略2死叉 且 CCI144 < -100
```

#### 次信号：顶底系统 (SUB_BOTTOM / SUB_TOP)
**抄底条件** (全部满足):
```
1. Stochastic %K < 20 (超卖)
2. KDJ金叉 (pk从下穿越pd)
3. OBV_minus >= 22 且 OBV_ADX >= 22 且 OBV_plus <= 18
```

**逃顶条件** (全部满足):
```
1. Stochastic %K > 80 (超买)
2. KDJ死叉 (pk从上穿越pd)
3. OBV_plus >= 22 且 OBV_ADX >= 22 且 OBV_minus <= 18
```

#### 次信号：订单块 (SUB_ORDER_BLOCK)
**看涨订单块触发**:
```
1. 价格回踩到看涨订单块区间 [ob_low, ob_high]
2. 当前收盘价 > ob_low (订单块未失效)
```

**看跌订单块触发**:
```
1. 价格反弹到看跌订单块区间 [ob_low, ob_high]
2. 当前收盘价 < ob_high (订单块未失效)
```

### 2.3 信号优先级
```
1. 主信号 (MAIN_TREND) - 仓位 5%
2. 次信号 (SUB_BOTTOM/SUB_TOP) - 仓位 2.5%
3. 订单块信号 (SUB_ORDER_BLOCK) - 仓位 2.5%
```

---

## 三、策略 v2 (趋势2.3) 信号逻辑

### 3.1 技术指标

| 指标 | 参数 | 用途 |
|------|------|------|
| Stochastic %K | period=14, smooth=5 | 超买超卖判断 |
| KDJ | ilong=9, isig=3 | 金叉死叉信号 |
| OBV-ADX | len=22, sig=22 | 量能趋势确认 |
| ADX | len=14 | 趋势强度过滤 |
| EMA快通道 | 144, 169 | 快速趋势 |
| EMA慢通道 | 576, 676 | 慢速趋势 |
| EMA12 | 12 | 短期趋势 |
| MACD | 13, 34, 9 | 动量信号 |
| RSI | len=14, os=30, ob=70 | 超买超卖 |

### 3.2 信号类型与条件

#### 主信号：趋势2.3 (MAIN_TREND)
**做多条件** (全部满足):
```
1. bullish_trend = EMA12 > 快通道顶部 且 EMA12 > 慢通道顶部
2. trend_filter = ADX > 20 且 ADX斜率 > 0 (可选)
3. macd_below_rise = MACD柱 < 0 且 MACD柱上升 且 前一根下降
4. RSI > 50 或 RSI从30下方上穿
```

**做空条件** (全部满足):
```
1. bearish_trend = EMA12 < 快通道底部 且 EMA12 < 慢通道底部
2. trend_filter = ADX > 20 且 ADX斜率 > 0 (可选)
3. macd_above_fall = MACD柱 > 0 且 MACD柱下降 且 前一根上升
4. RSI < 50 或 RSI从70上方下穿
```

#### 次信号：何以为底 (SUB_BOTTOM / SUB_TOP)
与策略v1相同的顶底系统逻辑。

#### 次信号：订单块 (SUB_ORDER_BLOCK)
与策略v1相同的订单块逻辑。

### 3.3 信号优先级与周期规则

| 周期 | 主信号 | 顶底信号 | 订单块信号 |
|------|--------|----------|------------|
| 1m | ✅ 开仓 | ⚠️ 仅止盈 | ⚠️ 仅止盈 |
| 3m | ✅ 开仓 | ✅ 开仓 | ⚠️ 仅止盈 |
| 5m | ✅ 开仓 | ✅ 开仓 | ⚠️ 仅止盈 |
| 15m | ❌ | ✅ 开仓 | ⚠️ 仅止盈 |
| 30m | ❌ | ✅ 开仓 | ✅ 开仓 |
| 1h | ❌ | ✅ 开仓 | ✅ 开仓 |

---

## 四、下单逻辑审计

### 4.1 下单流程

```
1. 每分钟59秒触发扫描
2. 检查交易是否启用 (enable_trading=1)
3. 检查交易是否暂停 (pause_trading=0)
4. 获取当前周期的K线数据
5. 调用策略的 check_signals() 方法
6. 根据信号类型和运行模式决定是否下单
```

### 4.2 运行模式与下单行为

| 模式 | 数据来源 | 下单行为 | 持仓管理 |
|------|----------|----------|----------|
| paper (实盘测试) | 真实API | 模拟下单 | 数据库持久化 |
| live (实盘) | 真实API | 真实下单 | 交易所持仓 |

### 4.3 下单条件检查

**实盘模式 (live)**:
```python
blocked_reasons = []
if pause_trading != 0:
    blocked_reasons.append("trading_paused")
if control.get("allow_live", 0) != 1:
    blocked_reasons.append("live_trading_not_allowed")
if "posSide" not in plan_order:
    blocked_reasons.append("missing_pos_side")
if enable_trading != 1:
    blocked_reasons.append("trading_disabled")

can_execute_real_order = len(blocked_reasons) == 0
```

**实盘测试模式 (paper)**:
```python
blocked_reasons = []
if pause_trading != 0:
    blocked_reasons.append("trading_paused")
if "posSide" not in plan_order:
    blocked_reasons.append("missing_pos_side")
if enable_trading != 1:
    blocked_reasons.append("trading_disabled")

can_execute_paper_order = len(blocked_reasons) == 0
```

---

## 五、所有可能的交易场景

### 场景1: 趋势做多 (MAIN_TREND LONG)
```
触发条件: 
- 策略v1: EMA12 > EMA144/169 + MACD金叉 + CCI > 100 + ADX趋势确认
- 策略v2: EMA12 > 快慢通道 + MACD柱上升 + RSI > 50

下单参数:
- side: buy
- posSide: long
- amount: 权益 × 3% (主信号)
- leverage: 50
- order_type: market
```

### 场景2: 趋势做空 (MAIN_TREND SHORT)
```
触发条件:
- 策略v1: EMA12 < EMA144/169 + MACD死叉 + CCI < -100 + ADX趋势确认
- 策略v2: EMA12 < 快慢通道 + MACD柱下降 + RSI < 50

下单参数:
- side: sell
- posSide: short
- amount: 权益 × 3%
- leverage: 50
- order_type: market
```

### 场景3: 抄底做多 (SUB_BOTTOM LONG)
```
触发条件:
- Stochastic %K < 20 (超卖)
- KDJ金叉
- OBV-ADX确认

下单参数:
- side: buy
- posSide: long
- amount: 权益 × 1% (次信号)
- leverage: 50
- order_type: market
```

### 场景4: 逃顶做空 (SUB_TOP SHORT)
```
触发条件:
- Stochastic %K > 80 (超买)
- KDJ死叉
- OBV-ADX确认

下单参数:
- side: sell
- posSide: short
- amount: 权益 × 1%
- leverage: 50
- order_type: market
```

### 场景5: 订单块做多 (SUB_ORDER_BLOCK LONG)
```
触发条件:
- 价格回踩看涨订单块区间
- 订单块未失效

下单参数:
- side: buy
- posSide: long
- amount: 权益 × 1%
- leverage: 50
- order_type: market
```

### 场景6: 订单块做空 (SUB_ORDER_BLOCK SHORT)
```
触发条件:
- 价格反弹看跌订单块区间
- 订单块未失效

下单参数:
- side: sell
- posSide: short
- amount: 权益 × 1%
- leverage: 50
- order_type: market
```

### 场景7: 止盈信号 (TP_BOTTOM / TP_TOP / TP_ORDER_BLOCK)
```
触发条件:
- 1m周期的顶底信号
- 1m/3m/5m/15m周期的订单块信号

行为:
- position_pct = 0 (不开新仓)
- 仅用于平仓/止盈决策
```

### 场景8: 无信号 (HOLD)
```
触发条件:
- 所有信号条件均不满足

行为:
- 不执行任何交易
- 保持当前持仓
```

---

## 六、风控参数

| 参数 | 值 | 说明 |
|------|-----|------|
| leverage | 20 (默认) | 杠杆倍数（可在前端调整，范围1-100） |
| max_total_position_pct | 10% | 最大总仓位占权益比例 |
| main_position_pct | 3% | 主信号仓位比例 |
| sub_position_pct | 1% | 次信号/对冲仓位比例 |
| hard_tp_pct | 2% | 硬止盈比例（仅主仓时） |
| hedge_tp_pct | 0.5% | 对冲止盈比例（有对冲仓时） |

---

## 七、信号示例输出

### 示例1: 趋势做多信号
```json
{
    "action": "LONG",
    "type": "MAIN_TREND",
    "position_pct": 0.03,
    "leverage": 50,
    "reason": "[3m]趋势2.3主做多信号 | EMA12=45123.45 | RSI=62.5"
}
```

### 示例2: 抄底信号
```json
{
    "action": "LONG",
    "type": "SUB_BOTTOM",
    "position_pct": 0.01,
    "leverage": 50,
    "reason": "[5m]何以为底抄底信号 | Stoch=18.5 | OBV_ADX=25.3"
}
```

### 示例3: 订单块信号
```json
{
    "action": "LONG",
    "type": "SUB_ORDER_BLOCK",
    "position_pct": 0.01,
    "leverage": 50,
    "reason": "[30m]SMC看涨订单块触发 | 触发价≈$45000.00"
}
```

### 示例4: 止盈信号
```json
{
    "action": "SHORT",
    "type": "TP_TOP",
    "position_pct": 0,
    "leverage": 0,
    "reason": "[1m]顶底止盈信号（仅平仓）"
}
```

### 示例5: 无信号
```json
{
    "action": "HOLD",
    "type": "NONE",
    "reason": "无有效信号"
}
```

---

## 八、对冲交易系统 (2024-12-16 新增)

### 8.1 对冲逻辑概述

系统支持全仓对冲策略，当持有主仓后遇到反向信号时，会开对冲仓而非直接平仓。

| 功能 | 说明 |
|------|------|
| 差值止盈逃生 | 有对冲仓时，净收益率 ≥ 0.5% 全仓平仓 |
| 硬止盈 | 仅主仓时，本金盈利 ≥ 2% 自动平仓 |
| 顺势解对冲 | 新信号与主仓同向时，平掉所有对冲仓 |
| 对冲转正 | 主仓不存在但有对冲仓时，对冲仓转为主仓 |
| 对冲熔断 | 单币种最多2个对冲仓 |

### 8.2 交易参数配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| leverage | 20 | 杠杆倍数（可在前端调整） |
| main_position_pct | 3% | 主信号仓位比例 |
| sub_position_pct | 1% | 次信号/对冲仓位比例 |
| hard_tp_pct | 2% | 硬止盈比例（仅主仓时） |
| hedge_tp_pct | 0.5% | 对冲止盈比例（有对冲仓时） |

### 8.3 对冲场景示例

#### 场景A: 1分钟做多后遇到3分钟做空信号
```
时间线:
1. 14:00:59 - 1m做多信号 → 开主仓 LONG
2. 14:02:59 - 3m做空信号 → 检测到已有主仓且方向相反
3. 开对冲仓 SHORT（最多2个）
4. 后续监控净收益率，当 Net_ROI ≥ 0.5% 时全仓平仓止盈
```

#### 场景B: 硬止盈触发
```
条件: 仅有主仓，无对冲仓
触发: 本金盈利 ≥ 2%
动作: 自动平仓主仓
```

#### 场景C: 顺势解对冲
```
条件: 持有主仓(LONG) + 对冲仓(SHORT)
触发: 新信号为 LONG（与主仓同向）
动作: 平掉所有对冲仓，保留主仓
```

#### 场景D: 对冲转正
```
条件: 主仓已平仓，但有遗留对冲仓(SHORT)
触发: 新信号为 SHORT（与对冲仓同向）
动作: 将对冲仓标记为新主仓，跳过开新单
```

### 8.4 前端控制

在侧边栏「交易参数」中可调整：
- 杠杆倍数 (1-100x)
- 主信号仓位比例
- 次信号仓位比例
- 硬止盈比例
- 对冲止盈比例

---

*审计报告更新于 2024-12-16*
