# 信号系统审计报告

## 审计日期: 2024-12-16

---

## 📋 设计说明

### 激进模式（59秒抢跑）- 设计意图

**说明**: 系统使用未收盘的K线（`df.iloc[-1]`）在59秒计算信号，这是**设计意图**而非bug。

**原因**:
1. 在59秒时，K线即将收盘，数据已经基本稳定
2. 使用未收盘K线可以比TradingView提前约1秒下单（抢跑优势）
3. 这是用户明确要求的激进模式

**与TradingView的差异**:
- TradingView 使用已收盘的K线计算信号
- 本系统使用未收盘的K线（59秒时）计算信号
- 因此可能出现 "TV没信号但机器人有信号" 的情况，这是正常的

---

## ✅ 已修复的问题

### 问题1: candle_time 与信号计算K线不一致 - ✅ 已修复

**严重程度**: 🔴 高 → ✅ 已修复

**问题描述**:
原本 `candle_time` 使用 `df.iloc[-2]`（上一根K线），但信号计算使用 `df.iloc[-1]`（当前K线），导致去重逻辑失效。

**修复内容**:
```python
# strategy_v2.py - run_analysis_with_data()
# 修复前:
candle_time = df_with_indicators.iloc[-2]['timestamp']  # 上一根K线

# 修复后:
candle_time = df_with_indicators.iloc[-1]['timestamp']  # 当前K线（与信号计算一致）
```

**修复效果**:
1. ✅ 信号去重使用的 `candle_time` 与信号计算的K线一致
2. ✅ 同一根K线的同一信号只会触发一次
3. ✅ 重复下单风险已消除

---

### 问题2: K线缓存可能导致旧数据

**严重程度**: 🟡 中

**问题描述**:
`_ohlcv_cache` 的 TTL 是 30 秒，但在 59 秒扫描时，缓存中的数据可能是 30 秒前的旧数据。

**代码位置**:
```python
# separated_system/trade_engine.py 第130-132行
_ohlcv_cache: Dict[str, Any] = {}
_OHLCV_CACHE_TTL = 30  # 缓存有效期（秒）
```

**后果**:
- 如果在 29 秒时缓存了数据，59 秒时仍然有效，但此时K线已经变化了 30 秒

**修复建议**:
```python
# 方案: 在59秒扫描前清除缓存
if now.second == 59:
    clear_ohlcv_cache()  # 确保使用最新数据
```

**当前状态**: ✅ 实际上代码中没有使用 `get_cached_ohlcv()`，而是直接从 `provider.get_ohlcv()` 获取数据，所以这个问题目前不存在。但缓存函数存在，未来可能被误用。

---

### 问题3: 重复下单风险

**严重程度**: 🟡 中

**问题描述**:
信号去重使用 `(symbol, timeframe, action)` 作为 key，但 `candle_time` 与实际信号计算的K线不一致（见问题1）。

**代码位置**:
```python
# separated_system/trade_engine.py 第1091-1095行
if candle_time:
    candle_key = (symbol, target_tf, action)
    if not should_execute_signal(symbol, target_tf, action, candle_time):
        logger.debug(f"信号去重: {symbol} {target_tf} {action} 已在K线 {candle_time} 处理过")
        continue
```

**后果**:
- 如果 `candle_time` 是上一根K线的时间戳，而信号是基于当前K线计算的，那么：
  - 当前K线的信号会被记录为上一根K线的时间戳
  - 下一分钟，上一根K线变成了上上根，新的上一根K线时间戳不同，信号去重失效

**修复建议**:
确保 `candle_time` 与信号计算使用的K线一致。

---

### 问题4: UI/回测对不上 - ✅ 已修复

**严重程度**: 🟡 中 → ✅ 已修复

**问题描述**:
UI 显示的信号来自数据库 `signal_events` 表，原本交易引擎写入的是当前时间戳而不是K线时间戳。

**修复内容**:
```python
# separated_system/trade_engine.py
# 修复前:
current_ts = int(time.time() * 1000)
insert_signal_event(..., ts=current_ts, ...)

# 修复后:
signal_ts = candle_time if candle_time else int(time.time() * 1000)
insert_signal_event(..., ts=signal_ts, ...)
```

**修复效果**:
1. ✅ UI 显示的信号时间与K线收盘时间一致
2. ✅ 可以准确对标 TradingView 的信号

---

## ✅ 已正确实现的部分

1. **策略引擎集成**: 正确从 `strategy_registry` 加载 UI 选择的策略
2. **信号过滤逻辑**: 正确跳过 `TP_ORDER_BLOCK`，1m 顶底信号只止盈
3. **日志格式**: 与备份文件一致
4. **数据库持久化**: 信号缓存和信号事件都写入数据库
5. **预风控检查**: 在 15/45 秒执行，不阻塞 59 秒扫描

---

## 🔧 修复状态

| 优先级 | 问题 | 影响 | 状态 |
|--------|------|------|------|
| P0 | candle_time 与信号K线不一致 | 去重失效、重复下单 | ✅ 已修复 |
| P1 | 信号事件时间戳 | UI对不上 | ✅ 已修复 |
| P2 | K线缓存未使用 | 无当前影响 | ⚪ 无需修复 |
| - | TV没信号但机器人有信号 | 设计意图 | ⚪ 正常行为 |

---

## 当前系统配置

### 激进模式（59秒抢跑）

```python
# strategy_v2.py - check_signals()
curr = df.iloc[-1]   # 当前正在跳动的K线（59秒抢跑）
prev = df.iloc[-2]   # 上一根已收盘的K线
prev2 = df.iloc[-3]  # 上上根K线

# strategy_v2.py - run_analysis_with_data()
candle_time = df_with_indicators.iloc[-1]['timestamp']  # 当前K线（与信号计算一致）
```

---

## 审计结论

✅ **所有关键问题已修复**

修复后的系统：
1. ✅ 信号计算使用未收盘的K线（59秒抢跑模式）
2. ✅ 信号去重使用的 `candle_time` 与信号计算的K线一致（都是当前K线）
3. ✅ UI 显示的信号时间与K线时间戳一致
4. ✅ 重复下单风险已消除
5. ⚠️ 与TradingView可能有差异（设计意图，抢跑优势）
