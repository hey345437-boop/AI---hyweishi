# beijing_time_converter.py
# 北京时间转换器 - UTC到北京时间的转换工具
#
# 核心原则：
# - 内部存储一律使用 UTC 毫秒时间戳
# - UI展示一律转换为北京时间 (Asia/Shanghai, UTC+8)

from datetime import datetime, timezone, timedelta
from typing import Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


class BeijingTimeConverter:
    """
    北京时间转换器
    
    功能：
    1. UTC毫秒时间戳转北京时间 datetime
    2. UTC毫秒时间戳转北京时间字符串
    3. DataFrame 添加北京时间列
    """
    
    @staticmethod
    def to_beijing_datetime(utc_ms: int) -> datetime:
        """
        将 UTC 毫秒时间戳转换为北京时间 datetime
        
        Args:
            utc_ms: UTC 毫秒时间戳
        
        Returns:
            北京时间 datetime 对象（带时区信息）
        """
        utc_dt = datetime.fromtimestamp(utc_ms / 1000, tz=timezone.utc)
        return utc_dt.astimezone(BEIJING_TZ)
    
    @staticmethod
    def to_beijing_str(
        utc_ms: int,
        fmt: str = '%Y-%m-%d %H:%M:%S'
    ) -> str:
        """
        将 UTC 毫秒时间戳转换为北京时间字符串
        
        Args:
            utc_ms: UTC 毫秒时间戳
            fmt: 时间格式字符串，默认 'YYYY-MM-DD HH:MM:SS'
        
        Returns:
            北京时间字符串
        """
        beijing_dt = BeijingTimeConverter.to_beijing_datetime(utc_ms)
        return beijing_dt.strftime(fmt)
    
    @staticmethod
    def convert_ohlcv_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        为 OHLCV DataFrame 添加北京时间列
        
        Args:
            df: 包含 'ts' 列的 DataFrame
        
        Returns:
            添加了 'dt_utc' 和 'dt_bj' 列的 DataFrame
        """
        if df.empty:
            return df
        
        if 'ts' not in df.columns:
            logger.warning("DataFrame missing 'ts' column, skipping time conversion")
            return df
        
        # UTC 时间（计算层使用）
        df['dt_utc'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
        
        # 北京时间（展示层使用）
        df['dt_bj'] = df['dt_utc'].dt.tz_convert('Asia/Shanghai')
        
        return df
    
    @staticmethod
    def format_for_chart(df: pd.DataFrame) -> pd.DataFrame:
        """
        为图表展示格式化 DataFrame
        
        添加 'dt' 列作为图表 x 轴使用（北京时间）
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            添加了 'dt' 列的 DataFrame
        """
        if df.empty:
            return df
        
        # 先转换时间
        df = BeijingTimeConverter.convert_ohlcv_df(df)
        
        # 添加 'dt' 列用于图表 x 轴
        if 'dt_bj' in df.columns:
            df['dt'] = df['dt_bj']
        
        return df
    
    @staticmethod
    def get_current_beijing_time() -> datetime:
        """获取当前北京时间"""
        return datetime.now(BEIJING_TZ)
    
    @staticmethod
    def get_current_beijing_str(fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
        """获取当前北京时间字符串"""
        return BeijingTimeConverter.get_current_beijing_time().strftime(fmt)


class DualChannelChartRenderer:
    """
    双通道信号图表渲染器
    
    功能：
    1. 在K线图上渲染盘中信号标记（橙色）
    2. 在K线图上渲染收线确认信号标记（绿色）
    3. 提供图例说明
    """
    
    # 信号颜色定义
    INTRABAR_COLOR = "#FFA500"    # 橙色 - 抢跑/未确认
    CONFIRMED_COLOR = "#00FF00"   # 绿色 - 收线确认/对标TV
    
    # 信号标签定义
    INTRABAR_LABEL = "抢跑/未确认"
    CONFIRMED_LABEL = "收线确认/对标TV"
    
    # 信号形状定义
    INTRABAR_MARKER = "triangle-up"   # 向上三角
    CONFIRMED_MARKER = "circle"       # 圆形
    
    @classmethod
    def get_signal_style(cls, signal_type: str) -> dict:
        """
        获取信号样式
        
        Args:
            signal_type: "intrabar" | "confirmed"
        
        Returns:
            包含 color, label, marker 的样式字典
        """
        if signal_type == "intrabar":
            return {
                "color": cls.INTRABAR_COLOR,
                "label": cls.INTRABAR_LABEL,
                "marker": cls.INTRABAR_MARKER
            }
        elif signal_type == "confirmed":
            return {
                "color": cls.CONFIRMED_COLOR,
                "label": cls.CONFIRMED_LABEL,
                "marker": cls.CONFIRMED_MARKER
            }
        else:
            return {
                "color": "#FFFFFF",
                "label": "未知",
                "marker": "circle"
            }
    
    @classmethod
    def get_legend_items(cls) -> list:
        """
        获取图例项
        
        Returns:
            图例项列表，每项包含 name, color, marker
        """
        return [
            {
                "name": cls.INTRABAR_LABEL,
                "color": cls.INTRABAR_COLOR,
                "marker": cls.INTRABAR_MARKER,
                "description": "基于未收线K线计算的信号，用于59秒抢跑下单"
            },
            {
                "name": cls.CONFIRMED_LABEL,
                "color": cls.CONFIRMED_COLOR,
                "marker": cls.CONFIRMED_MARKER,
                "description": "基于已收线K线计算的信号，与TradingView对标"
            }
        ]
    
    @classmethod
    def prepare_signal_markers(
        cls,
        signals: list,
        df: pd.DataFrame
    ) -> list:
        """
        准备信号标记数据
        
        Args:
            signals: Signal 对象列表
            df: K线 DataFrame（需要有 'ts' 和 'dt_bj' 列）
        
        Returns:
            标记数据列表，每项包含 x, y, color, label, signal_type
        """
        markers = []
        
        for signal in signals:
            # 查找对应的K线
            candle_row = df[df['ts'] == signal.candle_ts]
            
            if candle_row.empty:
                logger.warning(
                    f"Cannot find candle for signal: "
                    f"{signal.symbol} ts={signal.candle_ts}"
                )
                continue
            
            style = cls.get_signal_style(signal.signal_type)
            
            # 确定标记位置（买入在低点下方，卖出在高点上方）
            if signal.action == "BUY":
                y_value = float(candle_row['low'].iloc[0]) * 0.998
            else:
                y_value = float(candle_row['high'].iloc[0]) * 1.002
            
            marker = {
                "x": candle_row['dt_bj'].iloc[0] if 'dt_bj' in candle_row.columns else candle_row['ts'].iloc[0],
                "y": y_value,
                "color": style["color"],
                "label": style["label"],
                "marker": style["marker"],
                "signal_type": signal.signal_type,
                "action": signal.action,
                "reason": signal.reason
            }
            
            markers.append(marker)
        
        return markers
