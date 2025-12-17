import sqlite3
import os
import time
import sys
import logging
import traceback
from typing import Dict, Any, Optional, Tuple, List
from contextlib import contextmanager

# 配置日志
logger = logging.getLogger(__name__)

# 尝试导入PostgreSQL支持
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
    logger.info("PostgreSQL 支持已加载 (psycopg2)")
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.info("PostgreSQL 支持未加载，将使用 SQLite")

from db_config import get_db_config_from_env_and_secrets, PROJECT_ROOT, DATA_DIR
import json
from datetime import datetime

# optional: import crypto utils later (lazy)

# 使用 DATA_DIR 作为基准路径
DEFAULT_DB_PATH = os.path.join(DATA_DIR, 'quant_system.db')

# 连接池支持（懒加载）
_connection_pool = None
_use_connection_pool = True  # 可通过环境变量禁用


def _get_pool():
    """获取全局连接池实例（懒加载）"""
    global _connection_pool
    if _connection_pool is None and _use_connection_pool:
        try:
            from connection_pool import get_global_pool
            _connection_pool = get_global_pool()
            logger.info("数据库连接池已启用")
        except Exception as e:
            logger.warning(f"连接池初始化失败，将使用直接连接: {e}")
    return _connection_pool


@contextmanager
def get_pooled_connection(db_config: Optional[Dict[str, Any]] = None):
    """
    获取池化的数据库连接（上下文管理器）
    
    优先使用连接池，如果连接池不可用则回退到直接连接。
    
    Usage:
        with get_pooled_connection() as (conn, db_kind):
            cursor = conn.cursor()
            ...
    """
    pool = _get_pool()
    
    if pool is not None:
        # 使用连接池
        conn = None
        try:
            conn = pool.get_connection()
            db_kind = pool.db_kind
            yield conn, db_kind
        finally:
            if conn is not None:
                pool.return_connection(conn)
    else:
        # 回退到直接连接
        conn, db_kind = _get_connection(db_config)
        try:
            yield conn, db_kind
        finally:
            conn.close()


def debug_db_identity(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """获取并打印数据库身份信息，用于调试DB路径漂移问题
    
    Args:
        db_config: 数据库配置，如果为None则自动从环境获取
    
    Returns:
        dict: 包含数据库身份信息
    """
    if db_config is None:
        db_kind, db_config = get_db_config_from_env_and_secrets()
    else:
        db_kind = db_config.get("kind", "sqlite")
    
    result = {
        "db_kind": db_kind,
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "project_root": str(PROJECT_ROOT)
    }
    
    if db_kind == "postgres":
        # 对于PostgreSQL，只返回URL的前半部分（不包含密码）
        url = db_config.get("url", "")
        if "@" in url:
            # 安全地显示PostgreSQL连接信息
            before_at, after_at = url.split("@", 1)
            safe_url = f"{before_at.split(':', 1)[0]}:***@****"
        else:
            safe_url = "<unknown_url>"
        result["db_url_safe"] = safe_url
    else:
        # 对于SQLite，返回完整的绝对路径
        result["db_path_abs"] = db_config.get("path", DEFAULT_DB_PATH)
    
    return result

def _get_connection(db_config: Optional[Dict[str, Any]] = None) -> Tuple[Any, str]:
    """获取数据库连接，支持SQLite和PostgreSQL
    
    Args:
        db_config: 数据库配置，如果为None则自动从环境获取
    
    Returns:
        tuple: (connection, db_kind)
            connection: 数据库连接对象
            db_kind: 数据库类型（"sqlite"或"postgres"）
    
    Raises:
        ImportError: psycopg2 不可用时尝试连接 PostgreSQL
        ValueError: PostgreSQL URL 未提供
        TypeError: SQLite 路径类型错误
    """
    if db_config is None:
        db_kind, db_config = get_db_config_from_env_and_secrets()
    else:
        db_kind = db_config.get("kind", "sqlite")
    
    try:
        if db_kind == "postgres":
            if not PSYCOPG2_AVAILABLE:
                logger.error("尝试连接 PostgreSQL 但 psycopg2 不可用")
                raise ImportError("psycopg2 not available for PostgreSQL connection")
            
            # PostgreSQL连接
            url = db_config.get("url")
            if not url:
                logger.error("PostgreSQL URL 未配置")
                raise ValueError("PostgreSQL URL not provided")
            
            logger.debug(f"正在连接 PostgreSQL...")
            conn = psycopg2.connect(
                url,
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            logger.debug("PostgreSQL 连接成功")
            return conn, "postgres"
        
        # SQLite连接
        path = db_config.get("path", DEFAULT_DB_PATH)
        if not isinstance(path, (str, os.PathLike)):
            logger.error(f"SQLite 路径类型错误: {type(path).__name__}")
            raise TypeError(f"SQLite path must be str or os.PathLike, got: {type(path).__name__}")
        
        logger.debug(f"正在连接 SQLite: {path}")
        conn = sqlite3.connect(path)
        logger.debug("SQLite 连接成功")
        return conn, "sqlite"
        
    except Exception as e:
        logger.error(
            f"数据库连接失败 | 类型: {db_kind} | 错误: {str(e)}\n"
            f"堆栈跟踪:\n{traceback.format_exc()}"
        )
        raise

def init_db(db_config: Optional[Dict[str, Any]] = None) -> None:
    """初始化数据库表结构"""
    conn, db_kind = _get_connection(db_config)
    try:
        if db_kind == "sqlite":
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA synchronous=NORMAL;')
        
        cursor = conn.cursor()
        
        # 创建bot_config表
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_config (
                id INTEGER PRIMARY KEY CHECK(id=1),
                run_mode TEXT DEFAULT 'sim',
                symbols TEXT DEFAULT '',
                position_size REAL DEFAULT 0.01,
                enable_trading INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0,
                version INTEGER DEFAULT 1,
                selected_strategy_id TEXT DEFAULT NULL,
                paper_initial_balance REAL DEFAULT 200.0,
                api_key TEXT DEFAULT '',
                api_secret_ciphertext TEXT DEFAULT NULL,
                api_secret_iv TEXT DEFAULT NULL,
                okx_api_key TEXT DEFAULT '',
                okx_api_secret_ciphertext TEXT DEFAULT NULL,
                okx_api_secret_iv TEXT DEFAULT NULL,
                okx_api_passphrase_ciphertext TEXT DEFAULT NULL,
                okx_api_passphrase_iv TEXT DEFAULT NULL
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_config (
                id INTEGER PRIMARY KEY CHECK(id=1),
                run_mode TEXT DEFAULT 'sim',
                symbols TEXT DEFAULT '',
                position_size REAL DEFAULT 0.01,
                enable_trading INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0,
                version INTEGER DEFAULT 1,
                selected_strategy_id TEXT DEFAULT NULL,
                paper_initial_balance REAL DEFAULT 200.0,
                api_key TEXT DEFAULT '',
                api_secret_ciphertext TEXT DEFAULT NULL,
                api_secret_iv TEXT DEFAULT NULL,
                okx_api_key TEXT DEFAULT '',
                okx_api_secret_ciphertext TEXT DEFAULT NULL,
                okx_api_secret_iv TEXT DEFAULT NULL,
                okx_api_passphrase_ciphertext TEXT DEFAULT NULL,
                okx_api_passphrase_iv TEXT DEFAULT NULL
            )
            ''')
        
        # 创建control_flags表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS control_flags (
            id INTEGER PRIMARY KEY CHECK(id=1),
            pause_trading INTEGER DEFAULT 0,
            stop_signal INTEGER DEFAULT 0,
            reload_config INTEGER DEFAULT 0,
            allow_live INTEGER DEFAULT 0,
            emergency_flatten INTEGER DEFAULT 0
        )
        ''')
        
        # 创建engine_status表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS engine_status (
            id INTEGER PRIMARY KEY CHECK(id=1),
            alive INTEGER DEFAULT 0,
            ts INTEGER DEFAULT 0,
            cycle_ms INTEGER DEFAULT 0,
            last_error TEXT DEFAULT NULL,
            run_mode TEXT DEFAULT 'sim',
            symbols TEXT DEFAULT '',
            pause_trading INTEGER DEFAULT 0,
            last_plan_order_json TEXT DEFAULT NULL,
            last_okx_latency_ms INTEGER DEFAULT 0
        )
        ''')
        
        # 初始化单行记录
        current_ts = int(time.time())
        if db_kind == "postgres":
            cursor.execute('''
            INSERT INTO bot_config (id, run_mode, symbols, position_size, enable_trading, updated_at, version, api_key, api_secret, api_password, okx_api_key, okx_api_secret, okx_api_passphrase)
            VALUES (1, 'sim', '', 0.01, 0, %s, 1, '', '', '', '', '', '')
            ON CONFLICT (id) DO NOTHING
            ''', (current_ts,))
        else:
            cursor.execute('''
            INSERT OR IGNORE INTO bot_config (id, run_mode, symbols, position_size, enable_trading, updated_at, version, okx_api_key)
            VALUES (1, 'sim', '', 0.01, 0, ?, 1, '')
            ''', (current_ts,))
        # 兼容性：如果旧表存在明文字段，保留此前逻辑（不会覆盖）
        
        if db_kind == "postgres":
            cursor.execute('''
            INSERT INTO control_flags (id)
            VALUES (1)
            ON CONFLICT (id) DO NOTHING
            ''')
        else:
            cursor.execute('''
            INSERT OR IGNORE INTO control_flags (id)
            VALUES (1)
            ''')
        
        if db_kind == "postgres":
            cursor.execute('''
            INSERT INTO engine_status (id, alive, ts)
            VALUES (1, 0, %s)
            ON CONFLICT (id) DO NOTHING
            ''', (current_ts,))
        else:
            cursor.execute('''
            INSERT OR IGNORE INTO engine_status (id, alive, ts)
            VALUES (1, 0, ?)
            ''', (current_ts,))
        
        # 创建performance_metrics表
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id SERIAL PRIMARY KEY,
                ts INTEGER,
                cycle_ms INTEGER,
                okx_latency_ms INTEGER,
                symbols_count INTEGER,
                orders_count INTEGER,
                positions_count INTEGER,
                api_calls INTEGER DEFAULT 0,
                avg_api_latency_ms REAL DEFAULT 0,
                cache_hit_rate REAL DEFAULT 0,
                errors INTEGER DEFAULT 0
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER,
                cycle_ms INTEGER,
                okx_latency_ms INTEGER,
                symbols_count INTEGER,
                orders_count INTEGER,
                positions_count INTEGER,
                api_calls INTEGER DEFAULT 0,
                avg_api_latency_ms REAL DEFAULT 0,
                cache_hit_rate REAL DEFAULT 0,
                errors INTEGER DEFAULT 0
            )
            ''')
        
        # 创建ohlcv_cache表
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ohlcv_cache (
                symbol TEXT,
                timeframe TEXT,
                ts INTEGER,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (symbol, timeframe, ts)
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ohlcv_cache (
                symbol TEXT,
                timeframe TEXT,
                ts INTEGER,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (symbol, timeframe, ts)
            )
            ''')
        
        # 创建signal_events表
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_events (
                id SERIAL PRIMARY KEY,
                symbol TEXT,
                timeframe TEXT,
                ts INTEGER,
                signal_type TEXT,
                price REAL,
                reason TEXT,
                extra_json TEXT,
                channel_type TEXT DEFAULT NULL
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timeframe TEXT,
                ts INTEGER,
                signal_type TEXT,
                price REAL,
                reason TEXT,
                extra_json TEXT,
                channel_type TEXT DEFAULT NULL
            )
            ''')

        # 创建sentiment表（可选，用于后端存储情绪指数）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER,
            value TEXT,
            classification TEXT
        )
        ''')
        
        # P2修复: 创建orders表（订单状态持久化）
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                cl_ord_id TEXT UNIQUE,
                exchange_order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                pos_side TEXT,
                order_type TEXT DEFAULT 'market',
                amount REAL NOT NULL,
                price REAL,
                status TEXT DEFAULT 'pending',
                filled_amount REAL DEFAULT 0,
                avg_price REAL,
                fee REAL DEFAULT 0,
                pnl REAL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                run_mode TEXT,
                timeframe TEXT,
                signal_reason TEXT,
                extra_json TEXT
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cl_ord_id TEXT UNIQUE,
                exchange_order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                pos_side TEXT,
                order_type TEXT DEFAULT 'market',
                amount REAL NOT NULL,
                price REAL,
                status TEXT DEFAULT 'pending',
                filled_amount REAL DEFAULT 0,
                avg_price REAL,
                fee REAL DEFAULT 0,
                pnl REAL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                run_mode TEXT,
                timeframe TEXT,
                signal_reason TEXT,
                extra_json TEXT
            )
            ''')
        
        # P2修复: 创建signal_cache表（信号去重缓存持久化）
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_cache (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                action TEXT NOT NULL,
                candle_time INTEGER NOT NULL,
                updated_at INTEGER DEFAULT 0,
                PRIMARY KEY (symbol, timeframe, action)
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_cache (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                action TEXT NOT NULL,
                candle_time INTEGER NOT NULL,
                updated_at INTEGER DEFAULT 0,
                PRIMARY KEY (symbol, timeframe, action)
            )
            ''')
        
        # 创建account_snapshots表（保存最近一次账户快照）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS account_snapshots (
            id INTEGER PRIMARY KEY CHECK(id=1),
            snapshot_json TEXT,
            updated_at INTEGER DEFAULT 0
        )
        ''')
        
        # 创建paper_balance表（模拟账户余额）
        # 🔥 标准金融字段：
        # - wallet_balance: 钱包余额（静态，充值-提现+已实现盈亏）
        # - unrealized_pnl: 未实现盈亏
        # - equity: 动态权益 = wallet_balance + unrealized_pnl（计算字段，不存储）
        # - used_margin: 已用保证金
        # - available/free_margin: 可用保证金 = equity - used_margin
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_balance (
                id INTEGER PRIMARY KEY CHECK(id=1),
                currency TEXT DEFAULT 'USDT',
                wallet_balance REAL DEFAULT 200.0,
                unrealized_pnl REAL DEFAULT 0.0,
                used_margin REAL DEFAULT 0.0,
                equity REAL DEFAULT 200.0,
                available REAL DEFAULT 200.0,
                updated_at INTEGER DEFAULT 0
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_balance (
                id INTEGER PRIMARY KEY CHECK(id=1),
                currency TEXT DEFAULT 'USDT',
                wallet_balance REAL DEFAULT 200.0,
                unrealized_pnl REAL DEFAULT 0.0,
                used_margin REAL DEFAULT 0.0,
                equity REAL DEFAULT 200.0,
                available REAL DEFAULT 200.0,
                updated_at INTEGER DEFAULT 0
            )
            ''')
        
        # 创建paper_positions表（模拟持仓）
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_positions (
                symbol TEXT,
                pos_side TEXT,
                qty REAL DEFAULT 0.0,
                entry_price REAL DEFAULT 0.0,
                unrealized_pnl REAL DEFAULT 0.0,
                updated_at INTEGER DEFAULT 0,
                signal_type TEXT DEFAULT NULL,
                PRIMARY KEY (symbol, pos_side)
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_positions (
                symbol TEXT,
                pos_side TEXT,
                qty REAL DEFAULT 0.0,
                entry_price REAL DEFAULT 0.0,
                unrealized_pnl REAL DEFAULT 0.0,
                updated_at INTEGER DEFAULT 0,
                signal_type TEXT DEFAULT NULL,
                PRIMARY KEY (symbol, pos_side)
            )
            ''')
        
        # 🔥 创建hedge_positions表（对冲仓位）
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS hedge_positions (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                pos_side TEXT NOT NULL,
                qty REAL DEFAULT 0.0,
                entry_price REAL DEFAULT 0.0,
                unrealized_pnl REAL DEFAULT 0.0,
                signal_type TEXT DEFAULT NULL,
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS hedge_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                pos_side TEXT NOT NULL,
                qty REAL DEFAULT 0.0,
                entry_price REAL DEFAULT 0.0,
                unrealized_pnl REAL DEFAULT 0.0,
                signal_type TEXT DEFAULT NULL,
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            )
            ''')
        
        # 创建paper_fills表（模拟成交记录）
        if db_kind == "postgres":
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_fills (
                id SERIAL PRIMARY KEY,
                ts INTEGER DEFAULT 0,
                symbol TEXT,
                side TEXT,
                pos_side TEXT,
                qty REAL DEFAULT 0.0,
                price REAL DEFAULT 0.0,
                fee REAL DEFAULT 0.0,
                note TEXT DEFAULT ''
            )
            ''')
        else:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER DEFAULT 0,
                symbol TEXT,
                side TEXT,
                pos_side TEXT,
                qty REAL DEFAULT 0.0,
                price REAL DEFAULT 0.0,
                fee REAL DEFAULT 0.0,
                note TEXT DEFAULT ''
            )
            ''')
        
        # === 列迁移：为旧 paper_balance 表添加标准金融字段（必须在 INSERT 之前执行）===
        if db_kind == "sqlite":
            cursor.execute("PRAGMA table_info(paper_balance)")
            pb_existing_columns = {row[1] for row in cursor.fetchall()}
            
            pb_new_columns = {
                'wallet_balance': "REAL DEFAULT 200.0",
                'unrealized_pnl': "REAL DEFAULT 0.0",
                'used_margin': "REAL DEFAULT 0.0",
            }
            
            for col_name, col_def in pb_new_columns.items():
                if col_name not in pb_existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE paper_balance ADD COLUMN {col_name} {col_def}")
                        # 如果是 wallet_balance，用现有的 equity 值初始化
                        if col_name == 'wallet_balance':
                            cursor.execute("UPDATE paper_balance SET wallet_balance = equity WHERE wallet_balance IS NULL OR wallet_balance = 200.0")
                    except Exception:
                        pass
        
        # 初始化paper_balance表（包含标准金融字段）
        if db_kind == "postgres":
            cursor.execute('''
            INSERT INTO paper_balance (id, currency, wallet_balance, unrealized_pnl, used_margin, equity, available, updated_at)
            VALUES (1, 'USDT', 200.0, 0.0, 0.0, 200.0, 200.0, %s)
            ON CONFLICT (id) DO NOTHING
            ''', (current_ts,))
        else:
            cursor.execute('''
            INSERT OR IGNORE INTO paper_balance (id, currency, wallet_balance, unrealized_pnl, used_margin, equity, available, updated_at)
            VALUES (1, 'USDT', 200.0, 0.0, 0.0, 200.0, 200.0, ?)
            ''', (current_ts,))
        
        # === 列迁移：为旧 bot_config 表添加新列（如果不存在）===
        if db_kind == "sqlite":
            # 获取现有列列表
            cursor.execute("PRAGMA table_info(bot_config)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            # 定义需要的新列
            new_columns = {
                'selected_strategy_id': "TEXT DEFAULT NULL",
                'paper_initial_balance': "REAL DEFAULT 200.0",
                'okx_api_secret_ciphertext': "TEXT DEFAULT NULL",
                'okx_api_secret_iv': "TEXT DEFAULT NULL",
                'okx_api_passphrase_ciphertext': "TEXT DEFAULT NULL",
                'okx_api_passphrase_iv': "TEXT DEFAULT NULL",
                'api_secret_ciphertext': "TEXT DEFAULT NULL",
                'api_secret_iv': "TEXT DEFAULT NULL",
                # 🔥 新增：交易参数配置
                'leverage': "INTEGER DEFAULT 20",
                'main_position_pct': "REAL DEFAULT 0.03",
                'sub_position_pct': "REAL DEFAULT 0.01",
                'hard_tp_pct': "REAL DEFAULT 0.02",
                'hedge_tp_pct': "REAL DEFAULT 0.005",
                # 🔥 双通道信号执行模式
                'execution_mode': "TEXT DEFAULT 'intrabar'",
                # 🔥 数据源模式: REST 或 WebSocket
                'data_source_mode': "TEXT DEFAULT 'REST'",
            }
            
            # 逐个添加缺失的列
            for col_name, col_def in new_columns.items():
                if col_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE bot_config ADD COLUMN {col_name} {col_def}")
                        # print(f"✓ Added column: {col_name}")
                    except Exception as e:
                        # 列可能已经存在，忽略错误
                        pass
            
            # === 列迁移：为旧 performance_metrics 表添加新列（如果不存在）===
            cursor.execute("PRAGMA table_info(performance_metrics)")
            pm_existing_columns = {row[1] for row in cursor.fetchall()}
            
            pm_new_columns = {
                'api_calls': "INTEGER DEFAULT 0",
                'avg_api_latency_ms': "REAL DEFAULT 0",
                'cache_hit_rate': "REAL DEFAULT 0",
                'errors': "INTEGER DEFAULT 0",
            }
            
            for col_name, col_def in pm_new_columns.items():
                if col_name not in pm_existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE performance_metrics ADD COLUMN {col_name} {col_def}")
                    except Exception:
                        pass
            
            # === 列迁移：为旧 signal_events 表添加 channel_type 列（双通道信号支持）===
            cursor.execute("PRAGMA table_info(signal_events)")
            se_existing_columns = {row[1] for row in cursor.fetchall()}
            
            if 'channel_type' not in se_existing_columns:
                try:
                    cursor.execute("ALTER TABLE signal_events ADD COLUMN channel_type TEXT DEFAULT NULL")
                except Exception:
                    pass
            
            # 注意：paper_balance 表的迁移已移到 INSERT 之前执行
        
        conn.commit()
    finally:
        conn.close()


def get_bootstrap_state(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """一次性返回初始化启动所需的最小状态集合。

    返回字段：run_mode, selected_strategy_id, paper_balance(dict), has_credentials(bool), last_sentiment
    """
    # 从 bot_config, paper_balance, sentiment (若存在) 聚合
    boot = {
        'run_mode': 'sim',
        'selected_strategy_id': None,
        'paper_balance': {'equity': None, 'available': None},
        'has_credentials': False,
        'last_sentiment': None,
        'updated_at': 0
    }

    bot = get_bot_config(db_config)
    if bot:
        boot['run_mode'] = bot.get('run_mode', boot['run_mode'])
        boot['selected_strategy_id'] = bot.get('selected_strategy_id') if 'selected_strategy_id' in bot else None
        # detect credentials presence (only key visible)
        okx_key = bot.get('okx_api_key') or bot.get('api_key')
        okx_secret_cipher = bot.get('okx_api_secret_ciphertext') or bot.get('api_secret')
        boot['has_credentials'] = bool(okx_key and okx_secret_cipher)
        boot['updated_at'] = bot.get('updated_at', 0)

    paper = get_paper_balance(db_config)
    if paper:
        boot['paper_balance'] = {'equity': paper.get('equity'), 'available': paper.get('available')}

    # try sentiment table if exists
    try:
        conn, db_kind = _get_connection(db_config)
        cursor = conn.cursor()
        if db_kind == 'postgres':
            cursor.execute("SELECT value, classification, ts FROM sentiment ORDER BY ts DESC LIMIT 1")
        else:
            cursor.execute("SELECT value, classification, ts FROM sentiment ORDER BY ts DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            boot['last_sentiment'] = {'value': row[0], 'classification': row[1], 'ts': row[2]}
    except Exception:
        pass

    return boot


def snapshot_account_summary_to_db(snapshot: Dict[str, Any], db_config: Optional[Dict[str, Any]] = None) -> None:
    """将 account summary 的 JSON 快照写入 account_snapshots 表（单行）。"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        js = json.dumps(snapshot)
        ts = int(time.time())
        if db_kind == 'postgres':
            cursor.execute('''INSERT INTO account_snapshots (id, snapshot_json, updated_at) VALUES (1, %s, %s) ON CONFLICT (id) DO UPDATE SET snapshot_json = EXCLUDED.snapshot_json, updated_at = EXCLUDED.updated_at''', (js, ts))
        else:
            cursor.execute('''INSERT OR REPLACE INTO account_snapshots (id, snapshot_json, updated_at) VALUES (1, ?, ?)''', (js, ts))
        conn.commit()
    finally:
        conn.close()


def get_account_snapshot(db_config: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """读取最近一次 account snapshot。"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        if db_kind == 'postgres':
            cursor.execute('SELECT snapshot_json, updated_at FROM account_snapshots WHERE id = %s', (1,))
        else:
            cursor.execute('SELECT snapshot_json, updated_at FROM account_snapshots WHERE id = ?', (1,))
        row = cursor.fetchone()
        if not row:
            return None
        js = row[0]
        try:
            return json.loads(js)
        except Exception:
            return None
    finally:
        conn.close()


def verify_credentials_and_snapshot(db_config: Optional[Dict[str, Any]] = None, exchange_type: str = 'okx') -> Dict[str, Any]:
    """用当前 DB 中的凭证尝试初始化交易所并拉取账户摘要，写入 snapshot 并返回结果。

    返回：{ok: bool, error: str|None, account_summary: dict|None}
    """
    # 加载解密凭证
    creds = load_decrypted_credentials(db_config)
    key = creds.get('okx_api_key')
    secret = creds.get('okx_api_secret')
    passphrase = creds.get('okx_api_passphrase')

    if not key or not secret or not passphrase:
        return {'ok': False, 'error': 'missing_credentials', 'account_summary': None}

    # 动态导入交易所适配器工厂以避免循环依赖
    try:
        from exchange_adapters.factory import ExchangeAdapterFactory
    except Exception as e:
        return {'ok': False, 'error': f'adapter_factory_import_failed: {str(e)[:120]}', 'account_summary': None}

    try:
        # 🔥 关键修复：强制使用实盘模式，禁用 sandbox
        # 本系统只支持 live 和 paper_on_real 两种模式
        exchange_config = {
            'exchange_type': exchange_type,
            'api_key': key,
            'api_secret': secret,
            'api_passphrase': passphrase,
            'run_mode': 'paper_on_real',  # 验证凭证时使用 paper_on_real
            # 注意：不再传递 sandbox/env，OKXAdapter 会强制禁用
        }
        adapter = ExchangeAdapterFactory.get_exchange_adapter(exchange_config)
        adapter.initialize()

        # 拉取余额与持仓（尽量只做最小权限调用）
        bal = None
        pos = None
        try:
            bal = adapter.fetch_balance()
        except Exception as e:
            # balance fetch failed
            return {'ok': False, 'error': f'balance_fetch_failed: {str(e)[:200]}', 'account_summary': None}

        try:
            # 有些适配器没有 fetch_positions，保护调用
            if hasattr(adapter, 'fetch_positions'):
                pos = adapter.fetch_positions()
        except Exception:
            pos = None

        summary = {'balance': bal, 'positions': pos, 'ts': int(time.time())}
        # 写入 snapshot
        try:
            snapshot_account_summary_to_db(summary, db_config)
        except Exception:
            pass

        return {'ok': True, 'error': None, 'account_summary': summary}
    except Exception as e:
        return {'ok': False, 'error': f'init_adapter_failed: {str(e)[:200]}', 'account_summary': None}


def fetch_and_cache_ohlcv(symbol: str, timeframe: str = '1m', limit: int = 200, db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """使用当前凭证拉取 OHLCV 并写入 ohlcv_cache（由 MarketDataProvider/adapter 执行）。"""
    creds = load_decrypted_credentials(db_config)
    key = creds.get('okx_api_key')
    secret = creds.get('okx_api_secret')
    passphrase = creds.get('okx_api_passphrase')
    if not key or not secret or not passphrase:
        return {'ok': False, 'error': 'missing_credentials'}

    try:
        from exchange_adapters.factory import ExchangeAdapterFactory
        exchange_config = {
            'exchange_type': 'okx',
            'api_key': key,
            'api_secret': secret,
            'api_passphrase': passphrase,
        }
        adapter = ExchangeAdapterFactory.get_exchange_adapter(exchange_config)
        adapter.initialize()
        ohlcv = adapter.fetch_ohlcv(symbol, timeframe, limit=limit)
        # upsert into DB
        upsert_ohlcv(symbol, timeframe, ohlcv, db_config)
        return {'ok': True, 'rows': len(ohlcv)}
    except Exception as e:
        return {'ok': False, 'error': str(e)[:200]}


def get_credentials_status(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """返回脱敏的凭证绑定状态，不返回明文或解密后的 secret。"""
    bot = get_bot_config(db_config)
    okx_key = bot.get('okx_api_key') if bot else ''
    status = {'okx_bound': False, 'okx_key_tail': None}
    if okx_key:
        status['okx_bound'] = True
        status['okx_key_tail'] = okx_key[-4:]
    return status


def load_decrypted_credentials(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Optional[str]]:
    """返回解密后的凭证，仅在后端受信任环境调用。慎用。

    返回字典包含 okx_api_key, okx_api_secret, okx_api_passphrase （可能为 None）
    """
    bot = get_bot_config(db_config)
    if not bot:
        return {'okx_api_key': None, 'okx_api_secret': None, 'okx_api_passphrase': None}

    key = bot.get('okx_api_key')
    secret_ct = bot.get('okx_api_secret_ciphertext')
    secret_iv = bot.get('okx_api_secret_iv')
    pass_ct = bot.get('okx_api_passphrase_ciphertext')
    pass_iv = bot.get('okx_api_passphrase_iv')

    result = {'okx_api_key': key, 'okx_api_secret': None, 'okx_api_passphrase': None}
    try:
        if secret_ct and secret_iv:
            from crypto_utils import decrypt_text
            result['okx_api_secret'] = decrypt_text(secret_ct, secret_iv)
        if pass_ct and pass_iv:
            from crypto_utils import decrypt_text
            result['okx_api_passphrase'] = decrypt_text(pass_ct, pass_iv)
    except Exception:
        # 解密失败时返回 None 并记录错误在调用端
        result['okx_api_secret'] = None
        result['okx_api_passphrase'] = None

    return result

def get_bot_config(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """获取机器人配置"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        if db_kind == "postgres":
            cursor.execute('SELECT * FROM bot_config WHERE id = %s', (1,))
        else:
            cursor.execute('SELECT * FROM bot_config WHERE id = ?', (1,))
        
        row = cursor.fetchone()
        if not row:
            return {}
        
        if db_kind == "postgres":
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        else:
            return dict(zip([col[0] for col in cursor.description], row))
    finally:
        conn.close()

def update_bot_config(db_config: Optional[Dict[str, Any]] = None, **fields) -> None:
    """更新机器人配置，自动更新updated_at和version"""
    # 白名单字段检查，确保只更新允许的字段
    allowed_fields = {
        'run_mode', 'symbols', 'position_size', 'enable_trading', 
        'api_key', 'api_secret', 'api_password',
        'okx_api_key', 'okx_api_secret', 'okx_api_passphrase',
        # 加密后的字段（内部使用）
        'okx_api_secret_ciphertext', 'okx_api_secret_iv',
        'okx_api_passphrase_ciphertext', 'okx_api_passphrase_iv',
        'selected_strategy_id', 'paper_initial_balance',
        'updated_at', 'version',
        # 🔥 新增：交易参数配置
        'leverage', 'main_position_pct', 'sub_position_pct', 
        'hard_tp_pct', 'hedge_tp_pct',
        # 🔥 双通道信号执行模式
        'execution_mode'
    }
    
    # 过滤掉不在白名单中的字段
    filtered_fields = {k: v for k, v in fields.items() if k in allowed_fields}

    # 处理凭证加密：若用户传入 okx_api_secret 或 okx_api_passphrase，则使用 crypto_utils 加密并写入 cipher 字段
    try:
        if 'okx_api_secret' in filtered_fields or 'okx_api_passphrase' in filtered_fields:
            from crypto_utils import encrypt_text
            # 准备更新项
            secret = filtered_fields.pop('okx_api_secret', None)
            passphrase = filtered_fields.pop('okx_api_passphrase', None)
            if secret is not None:
                enc = encrypt_text(secret)
                # 写入加密字段
                filtered_fields['okx_api_secret_ciphertext'] = enc['ciphertext']
                filtered_fields['okx_api_secret_iv'] = enc['iv']
            if passphrase is not None:
                enc2 = encrypt_text(passphrase)
                filtered_fields['okx_api_passphrase_ciphertext'] = enc2['ciphertext']
                filtered_fields['okx_api_passphrase_iv'] = enc2['iv']
    except Exception:
        # 如果加密不可用，拒绝写入以防明文落库
        raise
    
    # 确保所有值都是基本类型
    for k, v in filtered_fields.items():
        if not isinstance(v, (str, int, float, bool, type(None))):
            raise TypeError(f"字段 {k} 的值必须是基本类型，获取到: {type(v).__name__}")
    
    conn, db_kind = _get_connection(db_config)
    try:
        # 获取当前version
        current = get_bot_config(db_config)
        new_version = current.get('version', 1) + 1
        
        filtered_fields['updated_at'] = int(time.time())
        filtered_fields['version'] = new_version
        
        # 如果没有要更新的字段，直接返回
        if not filtered_fields:
            return
        
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            # PostgreSQL更新语句
            set_clause = ', '.join([f"{key} = %s" for key in filtered_fields.keys()])
            values = list(filtered_fields.values()) + [1]
            
            cursor.execute(f'''UPDATE bot_config SET {set_clause} WHERE id = %s''', values)
        else:
            # SQLite更新语句
            placeholders = ', '.join([f'{key} = ?' for key in filtered_fields.keys()])
            values = list(filtered_fields.values()) + [1]
            
            cursor.execute(f'''UPDATE bot_config SET {placeholders} WHERE id = ?''', values)
        
        conn.commit()
    finally:
        conn.close()

def get_control_flags(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """获取控制标志"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        if db_kind == "postgres":
            cursor.execute('SELECT * FROM control_flags WHERE id = %s', (1,))
        else:
            cursor.execute('SELECT * FROM control_flags WHERE id = ?', (1,))
        
        row = cursor.fetchone()
        if not row:
            return {}
        
        return dict(zip([col[0] for col in cursor.description], row))
    finally:
        conn.close()

def set_control_flags(db_config: Optional[Dict[str, Any]] = None, **flags) -> None:
    """设置控制标志"""
    conn, db_kind = _get_connection(db_config)
    try:
        if not flags:
            return
        
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            set_clause = ', '.join([f"{key} = %s" for key in flags.keys()])
            values = list(flags.values()) + [1]
            
            cursor.execute(f'''UPDATE control_flags SET {set_clause} WHERE id = %s''', values)
        else:
            placeholders = ', '.join([f'{key} = ?' for key in flags.keys()])
            values = list(flags.values()) + [1]
            
            cursor.execute(f'''UPDATE control_flags SET {placeholders} WHERE id = ?''', values)
        
        conn.commit()
    finally:
        conn.close()

def get_engine_status(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """获取引擎状态"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        if db_kind == "postgres":
            cursor.execute('SELECT * FROM engine_status WHERE id = %s', (1,))
        else:
            cursor.execute('SELECT * FROM engine_status WHERE id = ?', (1,))
        
        row = cursor.fetchone()
        if not row:
            return {}
        
        return dict(zip([col[0] for col in cursor.description], row))
    finally:
        conn.close()

def update_engine_status(db_config: Optional[Dict[str, Any]] = None, **status) -> None:
    """更新引擎状态"""
    conn, db_kind = _get_connection(db_config)
    try:
        if not status:
            return
        
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            set_clause = ', '.join([f"{key} = %s" for key in status.keys()])
            values = list(status.values()) + [1]
            
            cursor.execute(f'''UPDATE engine_status SET {set_clause} WHERE id = %s''', values)
        else:
            placeholders = ', '.join([f'{key} = ?' for key in status.keys()])
            values = list(status.values()) + [1]
            
            cursor.execute(f'''UPDATE engine_status SET {placeholders} WHERE id = ?''', values)
        
        conn.commit()
    finally:
        conn.close()


def get_paper_balance(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    获取模拟账户余额
    
    返回标准金融字段：
    - wallet_balance: 钱包余额（静态）
    - unrealized_pnl: 未实现盈亏
    - used_margin: 已用保证金
    - equity: 动态权益 = wallet_balance + unrealized_pnl
    - available/free_margin: 可用保证金 = equity - used_margin
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute("SELECT * FROM paper_balance WHERE id=1")
        else:
            cursor.execute("SELECT * FROM paper_balance WHERE id=1")
        
        row = cursor.fetchone()
        if row:
            columns = [col[0] for col in cursor.description]
            result = dict(zip(columns, row))
            
            # 确保新字段存在（兼容旧数据库）
            if 'wallet_balance' not in result:
                result['wallet_balance'] = result.get('equity', 200.0)
            if 'unrealized_pnl' not in result:
                result['unrealized_pnl'] = 0.0
            if 'used_margin' not in result:
                result['used_margin'] = 0.0
            
            # 计算派生字段（确保一致性）
            result['equity'] = result['wallet_balance'] + result['unrealized_pnl']
            result['free_margin'] = result['equity'] - result['used_margin']
            result['available'] = result['free_margin']  # 兼容旧代码
            
            return result
        
        # 默认值
        return {
            "id": 1, 
            "currency": "USDT", 
            "wallet_balance": 200.0,
            "unrealized_pnl": 0.0,
            "used_margin": 0.0,
            "equity": 200.0, 
            "available": 200.0,
            "free_margin": 200.0,
            "updated_at": 0
        }
    finally:
        conn.close()


def update_paper_balance(
    wallet_balance: Optional[float] = None,
    unrealized_pnl: Optional[float] = None,
    used_margin: Optional[float] = None,
    equity: Optional[float] = None,
    available: Optional[float] = None,
    updated_at: Optional[int] = None,
    db_config: Optional[Dict[str, Any]] = None
) -> None:
    """
    更新模拟账户余额
    
    标准金融字段：
    - wallet_balance: 钱包余额（静态）
    - unrealized_pnl: 未实现盈亏
    - used_margin: 已用保证金
    - equity: 动态权益（如果提供则直接使用，否则计算）
    - available: 可用保证金（如果提供则直接使用，否则计算）
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        # 获取当前余额
        balance = get_paper_balance(db_config)
        
        # 更新字段
        if wallet_balance is not None:
            balance['wallet_balance'] = wallet_balance
        if unrealized_pnl is not None:
            balance['unrealized_pnl'] = unrealized_pnl
        if used_margin is not None:
            balance['used_margin'] = used_margin
        
        # 计算派生字段
        if equity is not None:
            balance['equity'] = equity
        else:
            # equity = wallet_balance + unrealized_pnl
            balance['equity'] = balance['wallet_balance'] + balance['unrealized_pnl']
        
        if available is not None:
            balance['available'] = available
        else:
            # available = equity - used_margin
            balance['available'] = balance['equity'] - balance['used_margin']
        
        if updated_at is not None:
            balance['updated_at'] = updated_at
        else:
            balance['updated_at'] = int(time.time())
        
        # 执行更新（包含新字段）
        if db_kind == "postgres":
            cursor.execute('''
            UPDATE paper_balance 
            SET currency = %s, wallet_balance = %s, unrealized_pnl = %s, 
                used_margin = %s, equity = %s, available = %s, updated_at = %s 
            WHERE id = 1
            ''', (
                balance['currency'],
                balance['wallet_balance'],
                balance['unrealized_pnl'],
                balance['used_margin'],
                balance['equity'],
                balance['available'],
                balance['updated_at']
            ))
        else:
            cursor.execute('''
            UPDATE paper_balance 
            SET currency = ?, wallet_balance = ?, unrealized_pnl = ?, 
                used_margin = ?, equity = ?, available = ?, updated_at = ? 
            WHERE id = 1
            ''', (
                balance['currency'],
                balance['wallet_balance'],
                balance['unrealized_pnl'],
                balance['used_margin'],
                balance['equity'],
                balance['available'],
                balance['updated_at']
            ))
        
        conn.commit()
    finally:
        conn.close()


def get_paper_positions(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """获取所有模拟持仓"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute("SELECT * FROM paper_positions")
        else:
            cursor.execute("SELECT * FROM paper_positions")
        
        rows = cursor.fetchall()
        positions = {}
        if rows:
            columns = [col[0] for col in cursor.description]
            for row in rows:
                pos_data = dict(zip(columns, row))
                key = f"{pos_data['symbol']}_{pos_data['pos_side']}"
                positions[key] = pos_data
        return positions
    finally:
        conn.close()


def get_paper_position(symbol: str, pos_side: str, db_config: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """获取指定模拟持仓"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute("SELECT * FROM paper_positions WHERE symbol = %s AND pos_side = %s", (symbol, pos_side))
        else:
            cursor.execute("SELECT * FROM paper_positions WHERE symbol = ? AND pos_side = ?", (symbol, pos_side))
        
        row = cursor.fetchone()
        if row:
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        return None
    finally:
        conn.close()


def update_paper_position(symbol: str, pos_side: str, qty: Optional[float] = None, entry_price: Optional[float] = None, unrealized_pnl: Optional[float] = None, updated_at: Optional[int] = None, db_config: Optional[Dict[str, Any]] = None) -> None:
    """更新或插入模拟持仓"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        # 获取当前持仓
        current_pos = get_paper_position(symbol, pos_side, db_config)
        
        # 准备更新数据
        if current_pos:
            # 更新现有记录
            if qty is not None:
                current_pos['qty'] = qty
            if entry_price is not None:
                current_pos['entry_price'] = entry_price
            if unrealized_pnl is not None:
                current_pos['unrealized_pnl'] = unrealized_pnl
            if updated_at is not None:
                current_pos['updated_at'] = updated_at
            else:
                current_pos['updated_at'] = int(time.time())
            
            # 执行更新
            if db_kind == "postgres":
                cursor.execute('''
                UPDATE paper_positions 
                SET qty = %s, entry_price = %s, unrealized_pnl = %s, updated_at = %s 
                WHERE symbol = %s AND pos_side = %s
                ''', (
                    current_pos['qty'],
                    current_pos['entry_price'],
                    current_pos['unrealized_pnl'],
                    current_pos['updated_at'],
                    symbol,
                    pos_side
                ))
            else:
                cursor.execute('''
                UPDATE paper_positions 
                SET qty = ?, entry_price = ?, unrealized_pnl = ?, updated_at = ? 
                WHERE symbol = ? AND pos_side = ?
                ''', (
                    current_pos['qty'],
                    current_pos['entry_price'],
                    current_pos['unrealized_pnl'],
                    current_pos['updated_at'],
                    symbol,
                    pos_side
                ))
        else:
            # 插入新记录
            current_ts = int(time.time())
            if db_kind == "postgres":
                cursor.execute('''
                INSERT INTO paper_positions (symbol, pos_side, qty, entry_price, unrealized_pnl, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (
                    symbol,
                    pos_side,
                    qty or 0.0,
                    entry_price or 0.0,
                    unrealized_pnl or 0.0,
                    current_ts,  # 🔥 添加 created_at
                    updated_at or current_ts
                ))
            else:
                cursor.execute('''
                INSERT INTO paper_positions (symbol, pos_side, qty, entry_price, unrealized_pnl, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    pos_side,
                    qty or 0.0,
                    entry_price or 0.0,
                    unrealized_pnl or 0.0,
                    current_ts,  # 🔥 添加 created_at
                    updated_at or current_ts
                ))
        
        conn.commit()
    finally:
        conn.close()


def delete_paper_position(symbol: str, pos_side: str, db_config: Optional[Dict[str, Any]] = None) -> None:
    """删除模拟持仓"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute("DELETE FROM paper_positions WHERE symbol = %s AND pos_side = %s", (symbol, pos_side))
        else:
            cursor.execute("DELETE FROM paper_positions WHERE symbol = ? AND pos_side = ?", (symbol, pos_side))
        
        conn.commit()
    finally:
        conn.close()


def add_paper_fill(ts: int, symbol: str, side: str, pos_side: str, qty: float, price: float, fee: float = 0.0, note: str = "", db_config: Optional[Dict[str, Any]] = None) -> None:
    """添加模拟成交记录"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute('''
            INSERT INTO paper_fills (ts, symbol, side, pos_side, qty, price, fee, note) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                ts,
                symbol,
                side,
                pos_side,
                qty,
                price,
                fee,
                note
            ))
        else:
            cursor.execute('''
            INSERT INTO paper_fills (ts, symbol, side, pos_side, qty, price, fee, note) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ts,
                symbol,
                side,
                pos_side,
                qty,
                price,
                fee,
                note
            ))
        
        conn.commit()
    finally:
        conn.close()


def get_paper_fills(limit: int = 100, db_config: Optional[Dict[str, Any]] = None) -> list:
    """获取模拟成交记录"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute("SELECT * FROM paper_fills ORDER BY ts DESC LIMIT %s", (limit,))
        else:
            cursor.execute("SELECT * FROM paper_fills ORDER BY ts DESC LIMIT ?", (limit,))
        
        rows = cursor.fetchall()
        fills = []
        if rows:
            columns = [col[0] for col in cursor.description]
            for row in rows:
                fills.append(dict(zip(columns, row)))
        return fills
    finally:
        conn.close()

def get_recent_performance_metrics(limit: int = 20, db_config: Optional[Dict[str, Any]] = None) -> list:
    """获取最近的性能指标数据"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        # 检查performance_metrics表是否存在
        if db_kind == "postgres":
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_name='performance_metrics'")
            if not cursor.fetchone():
                return []
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='performance_metrics'")
            if not cursor.fetchone():
                return []
            
        # 获取性能指标数据
        if db_kind == "postgres":
            cursor.execute('''
            SELECT * FROM performance_metrics 
            ORDER BY ts DESC 
            LIMIT %s
            ''', (limit,))
        else:
            cursor.execute('''
            SELECT * FROM performance_metrics 
            ORDER BY ts DESC 
            LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
        # 转换为字典列表并反转顺序（时间升序）
        metrics = [dict(zip(columns, row)) for row in rows]
        return metrics[::-1]
    finally:
        conn.close()

def insert_performance_metrics(metrics: Dict[str, Any], db_config: Optional[Dict[str, Any]] = None) -> None:
    """插入性能指标数据"""
    conn, db_kind = _get_connection(db_config)
    try:
        # 确保ts字段存在
        if 'ts' not in metrics:
            metrics['ts'] = int(time.time())
        
        cursor = conn.cursor()
        
        # 🔥 获取表中实际存在的列
        if db_kind == "postgres":
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'performance_metrics'")
            existing_columns = {row[0] for row in cursor.fetchall()}
        else:
            cursor.execute("PRAGMA table_info(performance_metrics)")
            existing_columns = {row[1] for row in cursor.fetchall()}
        
        # 🔥 只插入表中存在的列
        filtered_metrics = {k: v for k, v in metrics.items() if k in existing_columns}
        
        if not filtered_metrics:
            return  # 没有可插入的数据
        
        columns = list(filtered_metrics.keys())
        values = list(filtered_metrics.values())
        
        if db_kind == "postgres":
            placeholders = ', '.join(['%s'] * len(columns))
            cursor.execute(f'''INSERT INTO performance_metrics ({', '.join(columns)}) VALUES ({placeholders})''', values)
        else:
            placeholders = ', '.join(['?'] * len(columns))
            cursor.execute(f'''INSERT INTO performance_metrics ({', '.join(columns)}) VALUES ({placeholders})''', values)
        
        conn.commit()
    finally:
        conn.close()


def upsert_ohlcv(symbol: str, timeframe: str, ohlcv_data: list, db_config: Optional[Dict[str, Any]] = None) -> None:
    """插入或更新OHLCV数据到ohlcv_cache表
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        ohlcv_data: OHLCV数据列表，每个元素为 (ts, open, high, low, close, volume)
        db_config: 数据库配置
    """
    if not ohlcv_data:
        return
    
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            # PostgreSQL upsert
            sql = '''
            INSERT INTO ohlcv_cache (symbol, timeframe, ts, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, timeframe, ts) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
            '''
            values = [(symbol, timeframe, ts, open, high, low, close, volume) 
                     for ts, open, high, low, close, volume in ohlcv_data]
            cursor.executemany(sql, values)
        else:
            # SQLite upsert
            sql = '''
            INSERT OR REPLACE INTO ohlcv_cache (symbol, timeframe, ts, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''
            values = [(symbol, timeframe, ts, open, high, low, close, volume) 
                     for ts, open, high, low, close, volume in ohlcv_data]
            cursor.executemany(sql, values)
        
        conn.commit()
    finally:
        conn.close()


def load_ohlcv(symbol: str, timeframe: str, limit: int = 200, db_config: Optional[Dict[str, Any]] = None) -> list:
    """从数据库加载OHLCV数据
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        limit: 加载的数量限制
        db_config: 数据库配置
    
    Returns:
        list: OHLCV数据列表，每个元素为 (ts, open, high, low, close, volume)
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            sql = '''
            SELECT ts, open, high, low, close, volume
            FROM ohlcv_cache
            WHERE symbol = %s AND timeframe = %s
            ORDER BY ts DESC
            LIMIT %s
            '''
            cursor.execute(sql, (symbol, timeframe, limit))
        else:
            sql = '''
            SELECT ts, open, high, low, close, volume
            FROM ohlcv_cache
            WHERE symbol = ? AND timeframe = ?
            ORDER BY ts DESC
            LIMIT ?
            '''
            cursor.execute(sql, (symbol, timeframe, limit))
        
        rows = cursor.fetchall()
        
        # 转换为所需格式并按时间升序返回
        result = [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]
        return result[::-1]  # 反转顺序，使时间升序
    finally:
        conn.close()


def insert_signal_event(symbol: str, timeframe: str, ts: int, signal_type: str, price: float,
                       reason: str = None, extra_json: str = None, 
                       channel_type: str = None,  # 🔥 双通道信号类型: "intrabar" | "confirmed"
                       db_config: Optional[Dict[str, Any]] = None) -> None:
    """插入信号事件到signal_events表
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        ts: 时间戳（毫秒）
        signal_type: 信号类型（BUY/SELL/EXIT）
        price: 信号价格
        reason: 信号原因（可选）
        extra_json: 额外的JSON数据（可选）
        channel_type: 双通道信号类型（可选）: "intrabar" = 盘中抢跑, "confirmed" = 收线确认
        db_config: 数据库配置
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            sql = '''
            INSERT INTO signal_events (symbol, timeframe, ts, signal_type, price, reason, extra_json, channel_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            '''
            cursor.execute(sql, (symbol, timeframe, ts, signal_type, price, reason, extra_json, channel_type))
        else:
            sql = '''
            INSERT INTO signal_events (symbol, timeframe, ts, signal_type, price, reason, extra_json, channel_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''
            cursor.execute(sql, (symbol, timeframe, ts, signal_type, price, reason, extra_json, channel_type))
        
        conn.commit()
    finally:
        conn.close()


def load_signals(symbol: str, timeframe: str, ts_from: int = None, db_config: Optional[Dict[str, Any]] = None) -> list:
    """从数据库加载信号事件
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        ts_from: 起始时间戳（毫秒），如果为None则加载所有
        db_config: 数据库配置
    
    Returns:
        list: 信号事件列表，每个元素为字典
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            if ts_from is not None:
                sql = '''
                SELECT * FROM signal_events
                WHERE symbol = %s AND timeframe = %s AND ts >= %s
                ORDER BY ts ASC
                '''
                cursor.execute(sql, (symbol, timeframe, ts_from))
            else:
                sql = '''
                SELECT * FROM signal_events
                WHERE symbol = %s AND timeframe = %s
                ORDER BY ts ASC
                '''
                cursor.execute(sql, (symbol, timeframe))
        else:
            if ts_from is not None:
                sql = '''
                SELECT * FROM signal_events
                WHERE symbol = ? AND timeframe = ? AND ts >= ?
                ORDER BY ts ASC
                '''
                cursor.execute(sql, (symbol, timeframe, ts_from))
            else:
                sql = '''
                SELECT * FROM signal_events
                WHERE symbol = ? AND timeframe = ?
                ORDER BY ts ASC
                '''
                cursor.execute(sql, (symbol, timeframe))
        
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
        # 转换为字典列表
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()

# ============ P2修复: 订单状态持久化函数 ============

def insert_order(
    cl_ord_id: str,
    symbol: str,
    side: str,
    amount: float,
    pos_side: str = None,
    order_type: str = 'market',
    price: float = None,
    run_mode: str = None,
    timeframe: str = None,
    signal_reason: str = None,
    extra_json: str = None,
    db_config: Optional[Dict[str, Any]] = None
) -> int:
    """
    P2修复: 插入订单记录
    
    参数:
    - cl_ord_id: 客户端订单ID (唯一)
    - symbol: 交易对
    - side: 方向 (buy/sell)
    - amount: 数量
    - pos_side: 持仓方向 (long/short)
    - order_type: 订单类型
    - price: 价格 (市价单为None)
    - run_mode: 运行模式
    - timeframe: 时间周期
    - signal_reason: 信号原因
    - extra_json: 额外信息JSON
    
    返回:
    - 订单ID
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        current_ts = int(time.time())
        
        if db_kind == "postgres":
            cursor.execute('''
            INSERT INTO orders (cl_ord_id, symbol, side, pos_side, order_type, amount, price, 
                               status, created_at, updated_at, run_mode, timeframe, signal_reason, extra_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s, %s)
            RETURNING id
            ''', (cl_ord_id, symbol, side, pos_side, order_type, amount, price, 
                  current_ts, current_ts, run_mode, timeframe, signal_reason, extra_json))
            order_id = cursor.fetchone()[0]
        else:
            cursor.execute('''
            INSERT INTO orders (cl_ord_id, symbol, side, pos_side, order_type, amount, price, 
                               status, created_at, updated_at, run_mode, timeframe, signal_reason, extra_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            ''', (cl_ord_id, symbol, side, pos_side, order_type, amount, price, 
                  current_ts, current_ts, run_mode, timeframe, signal_reason, extra_json))
            order_id = cursor.lastrowid
        
        conn.commit()
        return order_id
    finally:
        conn.close()


def update_order_status(
    cl_ord_id: str,
    status: str,
    exchange_order_id: str = None,
    filled_amount: float = None,
    avg_price: float = None,
    fee: float = None,
    pnl: float = None,
    db_config: Optional[Dict[str, Any]] = None
) -> bool:
    """
    P2修复: 更新订单状态
    
    参数:
    - cl_ord_id: 客户端订单ID
    - status: 状态 (pending/filled/partial/cancelled/failed)
    - exchange_order_id: 交易所订单ID
    - filled_amount: 已成交数量
    - avg_price: 平均成交价
    - fee: 手续费
    - pnl: 盈亏
    
    返回:
    - 是否更新成功
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        current_ts = int(time.time())
        
        # 构建更新字段
        updates = ['status = ?', 'updated_at = ?']
        values = [status, current_ts]
        
        if exchange_order_id is not None:
            updates.append('exchange_order_id = ?')
            values.append(exchange_order_id)
        if filled_amount is not None:
            updates.append('filled_amount = ?')
            values.append(filled_amount)
        if avg_price is not None:
            updates.append('avg_price = ?')
            values.append(avg_price)
        if fee is not None:
            updates.append('fee = ?')
            values.append(fee)
        if pnl is not None:
            updates.append('pnl = ?')
            values.append(pnl)
        
        values.append(cl_ord_id)
        
        if db_kind == "postgres":
            sql = f"UPDATE orders SET {', '.join(u.replace('?', '%s') for u in updates)} WHERE cl_ord_id = %s"
        else:
            sql = f"UPDATE orders SET {', '.join(updates)} WHERE cl_ord_id = ?"
        
        cursor.execute(sql, values)
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_order_by_cl_ord_id(cl_ord_id: str, db_config: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    P2修复: 根据客户端订单ID获取订单
    
    参数:
    - cl_ord_id: 客户端订单ID
    
    返回:
    - 订单字典或None
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute('SELECT * FROM orders WHERE cl_ord_id = %s', (cl_ord_id,))
        else:
            cursor.execute('SELECT * FROM orders WHERE cl_ord_id = ?', (cl_ord_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
    finally:
        conn.close()


def get_recent_orders(limit: int = 50, status: str = None, db_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    P2修复: 获取最近的订单列表
    
    参数:
    - limit: 数量限制
    - status: 状态过滤 (可选)
    
    返回:
    - 订单列表
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if status:
            if db_kind == "postgres":
                cursor.execute('SELECT * FROM orders WHERE status = %s ORDER BY created_at DESC LIMIT %s', (status, limit))
            else:
                cursor.execute('SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?', (status, limit))
        else:
            if db_kind == "postgres":
                cursor.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT %s', (limit,))
            else:
                cursor.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT ?', (limit,))
        
        rows = cursor.fetchall()
        orders = []
        if rows:
            columns = [col[0] for col in cursor.description]
            for row in rows:
                orders.append(dict(zip(columns, row)))
        return orders
    finally:
        conn.close()


# ============ 对冲仓位管理函数 ============

def get_hedge_positions(symbol: str = None, db_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """获取对冲仓位列表
    
    Args:
        symbol: 交易对符号，如果为None则获取所有对冲仓位
        db_config: 数据库配置
    
    Returns:
        list: 对冲仓位列表
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if symbol:
            if db_kind == "postgres":
                cursor.execute("SELECT * FROM hedge_positions WHERE symbol = %s ORDER BY created_at", (symbol,))
            else:
                cursor.execute("SELECT * FROM hedge_positions WHERE symbol = ? ORDER BY created_at", (symbol,))
        else:
            cursor.execute("SELECT * FROM hedge_positions ORDER BY symbol, created_at")
        
        rows = cursor.fetchall()
        positions = []
        if rows:
            columns = [col[0] for col in cursor.description]
            for row in rows:
                positions.append(dict(zip(columns, row)))
        return positions
    finally:
        conn.close()


def add_hedge_position(symbol: str, pos_side: str, qty: float, entry_price: float, 
                       signal_type: str = None, db_config: Optional[Dict[str, Any]] = None) -> int:
    """添加对冲仓位
    
    Args:
        symbol: 交易对符号
        pos_side: 持仓方向 (long/short)
        qty: 数量
        entry_price: 入场价格
        signal_type: 信号类型
        db_config: 数据库配置
    
    Returns:
        int: 新增的对冲仓位ID
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        current_ts = int(time.time())
        
        if db_kind == "postgres":
            cursor.execute('''
            INSERT INTO hedge_positions (symbol, pos_side, qty, entry_price, signal_type, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            ''', (symbol, pos_side, qty, entry_price, signal_type, current_ts, current_ts))
            hedge_id = cursor.fetchone()[0]
        else:
            cursor.execute('''
            INSERT INTO hedge_positions (symbol, pos_side, qty, entry_price, signal_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, pos_side, qty, entry_price, signal_type, current_ts, current_ts))
            hedge_id = cursor.lastrowid
        
        conn.commit()
        return hedge_id
    finally:
        conn.close()


def delete_hedge_position(hedge_id: int, db_config: Optional[Dict[str, Any]] = None) -> None:
    """删除指定的对冲仓位
    
    Args:
        hedge_id: 对冲仓位ID
        db_config: 数据库配置
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute("DELETE FROM hedge_positions WHERE id = %s", (hedge_id,))
        else:
            cursor.execute("DELETE FROM hedge_positions WHERE id = ?", (hedge_id,))
        
        conn.commit()
    finally:
        conn.close()


def delete_hedge_positions_by_symbol(symbol: str, db_config: Optional[Dict[str, Any]] = None) -> int:
    """删除指定交易对的所有对冲仓位
    
    Args:
        symbol: 交易对符号
        db_config: 数据库配置
    
    Returns:
        int: 删除的记录数
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute("DELETE FROM hedge_positions WHERE symbol = %s", (symbol,))
        else:
            cursor.execute("DELETE FROM hedge_positions WHERE symbol = ?", (symbol,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count
    finally:
        conn.close()


def count_hedge_positions(symbol: str, db_config: Optional[Dict[str, Any]] = None) -> int:
    """统计指定交易对的对冲仓位数量
    
    Args:
        symbol: 交易对符号
        db_config: 数据库配置
    
    Returns:
        int: 对冲仓位数量
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute("SELECT COUNT(*) FROM hedge_positions WHERE symbol = %s", (symbol,))
        else:
            cursor.execute("SELECT COUNT(*) FROM hedge_positions WHERE symbol = ?", (symbol,))
        
        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_trading_params(db_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """获取交易参数配置
    
    Returns:
        dict: 包含 leverage, main_position_pct, sub_position_pct, hard_tp_pct, hedge_tp_pct
    """
    bot_config = get_bot_config(db_config)
    return {
        'leverage': bot_config.get('leverage', 20),
        'main_position_pct': bot_config.get('main_position_pct', 0.03),
        'sub_position_pct': bot_config.get('sub_position_pct', 0.01),
        'hard_tp_pct': bot_config.get('hard_tp_pct', 0.02),
        'hedge_tp_pct': bot_config.get('hedge_tp_pct', 0.005),
    }


def update_trading_params(leverage: int = None, main_position_pct: float = None, 
                          sub_position_pct: float = None, hard_tp_pct: float = None,
                          hedge_tp_pct: float = None, db_config: Optional[Dict[str, Any]] = None) -> None:
    """更新交易参数配置
    
    Args:
        leverage: 杠杆倍数
        main_position_pct: 主信号仓位比例
        sub_position_pct: 次信号仓位比例
        hard_tp_pct: 硬止盈比例（仅主仓）
        hedge_tp_pct: 对冲止盈比例
        db_config: 数据库配置
    """
    fields = {}
    if leverage is not None:
        fields['leverage'] = leverage
    if main_position_pct is not None:
        fields['main_position_pct'] = main_position_pct
    if sub_position_pct is not None:
        fields['sub_position_pct'] = sub_position_pct
    if hard_tp_pct is not None:
        fields['hard_tp_pct'] = hard_tp_pct
    if hedge_tp_pct is not None:
        fields['hedge_tp_pct'] = hedge_tp_pct
    
    if fields:
        update_bot_config(db_config, **fields)


# ============ P2修复: 信号缓存持久化函数 ============

def get_signal_cache(symbol: str, timeframe: str, action: str, db_config: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """获取信号缓存的K线时间戳
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        action: 信号动作 (BUY/SELL)
        db_config: 数据库配置
    
    Returns:
        int: K线时间戳，如果不存在返回None
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        
        if db_kind == "postgres":
            cursor.execute(
                'SELECT candle_time FROM signal_cache WHERE symbol = %s AND timeframe = %s AND action = %s',
                (symbol, timeframe, action)
            )
        else:
            cursor.execute(
                'SELECT candle_time FROM signal_cache WHERE symbol = ? AND timeframe = ? AND action = ?',
                (symbol, timeframe, action)
            )
        
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_signal_cache(symbol: str, timeframe: str, action: str, candle_time: int, db_config: Optional[Dict[str, Any]] = None) -> None:
    """设置信号缓存的K线时间戳
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        action: 信号动作 (BUY/SELL)
        candle_time: K线时间戳
        db_config: 数据库配置
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        ts = int(time.time())
        
        if db_kind == "postgres":
            cursor.execute('''
                INSERT INTO signal_cache (symbol, timeframe, action, candle_time, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (symbol, timeframe, action) DO UPDATE SET
                    candle_time = EXCLUDED.candle_time,
                    updated_at = EXCLUDED.updated_at
            ''', (symbol, timeframe, action, candle_time, ts))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO signal_cache (symbol, timeframe, action, candle_time, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (symbol, timeframe, action, candle_time, ts))
        
        conn.commit()
    finally:
        conn.close()


def load_all_signal_cache(db_config: Optional[Dict[str, Any]] = None) -> Dict[tuple, int]:
    """加载所有信号缓存到内存
    
    Returns:
        dict: {(symbol, timeframe, action): candle_time}
    """
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, timeframe, action, candle_time FROM signal_cache')
        rows = cursor.fetchall()
        
        cache = {}
        for row in rows:
            key = (row[0], row[1], row[2])
            cache[key] = row[3]
        return cache
    finally:
        conn.close()


def clear_signal_cache_db(db_config: Optional[Dict[str, Any]] = None) -> None:
    """清除数据库中的信号缓存"""
    conn, db_kind = _get_connection(db_config)
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM signal_cache')
        conn.commit()
    finally:
        conn.close()
