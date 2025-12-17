"""
启动时配置与依赖校验模块

该模块在应用启动前执行，确保所有必需的配置和依赖都已就位。
- 检查必需的环境变量
- 检查关键 Python 包
- 验证数据库可访问性
- 检查敏感配置在正确的运行模式下已设置
"""

import os
import sys
from typing import Tuple, List, Dict, Any
import importlib


class StartupValidator:
    """启动验证器"""

    # 按运行模式定义必需的环境变量
    # 注意：API密钥不再是必需的，因为用户可以在前端UI中输入
    REQUIRED_ENV_BY_MODE = {
        'sim': {
            'optional': ['LOG_LEVEL'],
            'required': []
        },
        'paper': {
            'required': [],  # API密钥可在前端UI中配置，不强制要求环境变量
            'optional': ['LOG_LEVEL', 'OKX_SANDBOX', 'OKX_API_KEY', 'OKX_API_SECRET', 'OKX_API_PASSPHRASE']
        },
        'live': {
            'required': [],  # API密钥可在前端UI中配置，不强制要求环境变量
            'optional': ['LOG_LEVEL', 'OKX_API_KEY', 'OKX_API_SECRET', 'OKX_API_PASSPHRASE']
        }
    }

    # 关键 Python 依赖
    REQUIRED_PACKAGES = [
        'streamlit',
        'pandas',
        'numpy',
        'ccxt',
        'requests',
        'cryptography',
        'psycopg2',
        'plotly'
    ]

    # 可选但推荐的依赖
    RECOMMENDED_PACKAGES = [
        'python_dotenv',
        'sqlalchemy'
    ]

    @staticmethod
    def check_packages(verbose: bool = False) -> Tuple[bool, List[str], List[str]]:
        """
        检查所有必需和推荐的 Python 包

        返回: (is_all_required_available, missing_required, missing_recommended)
        """
        missing_required = []
        missing_recommended = []

        for pkg in StartupValidator.REQUIRED_PACKAGES:
            try:
                importlib.import_module(pkg)
                if verbose:
                    try:
                        print(f"  [OK] {pkg}")
                    except UnicodeEncodeError:
                        print(f"  OK: {pkg}")
            except ImportError:
                missing_required.append(pkg)
                if verbose:
                    try:
                        print(f"  [MISSING] {pkg} (required)")
                    except UnicodeEncodeError:
                        print(f"  MISSING: {pkg} (required)")

        for pkg in StartupValidator.RECOMMENDED_PACKAGES:
            try:
                importlib.import_module(pkg)
                if verbose:
                    try:
                        print(f"  [OK] {pkg}")
                    except UnicodeEncodeError:
                        print(f"  OK: {pkg}")
            except ImportError:
                missing_recommended.append(pkg)
                if verbose:
                    try:
                        print(f"  [OPTIONAL] {pkg} (recommended)")
                    except UnicodeEncodeError:
                        print(f"  OPTIONAL: {pkg} (recommended)")

        is_all_required_available = len(missing_required) == 0
        return is_all_required_available, missing_required, missing_recommended

    @staticmethod
    def check_config(run_mode: str = None, verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """
        检查运行模式下的配置完整性

        参数:
            run_mode: 运行模式 ('sim', 'paper', 'live')，若为 None 则从环境变量读取
            verbose: 是否打印详细信息

        返回: (is_valid, details_dict)
        """
        if run_mode is None:
            run_mode = os.getenv('RUN_MODE', 'sim').lower()

        if run_mode not in StartupValidator.REQUIRED_ENV_BY_MODE:
            return False, {
                'run_mode': run_mode,
                'error': f"未知的运行模式: {run_mode}。必须是: sim/paper/live"
            }

        required_vars = StartupValidator.REQUIRED_ENV_BY_MODE[run_mode]['required']
        optional_vars = StartupValidator.REQUIRED_ENV_BY_MODE[run_mode]['optional']

        missing_required = []
        missing_optional = []

        for var in required_vars:
            value = os.getenv(var)
            if not value or value.strip() == '':
                missing_required.append(var)
                if verbose:
                    try:
                        print(f"  [MISSING] {var} (required)")
                    except UnicodeEncodeError:
                        print(f"  MISSING: {var} (required)")
            else:
                # 对敏感信息脱敏显示
                masked_value = value[:5] + '***' if len(value) > 5 else '***'
                if verbose:
                    try:
                        print(f"  [OK] {var} = {masked_value}")
                    except UnicodeEncodeError:
                        print(f"  OK: {var} = {masked_value}")

        for var in optional_vars:
            value = os.getenv(var)
            if not value or value.strip() == '':
                missing_optional.append(var)
                if verbose:
                    try:
                        print(f"  [OPTIONAL] {var} (optional)")
                    except UnicodeEncodeError:
                        print(f"  OPTIONAL: {var} (optional)")
            else:
                if verbose:
                    try:
                        print(f"  [OK] {var}")
                    except UnicodeEncodeError:
                        print(f"  OK: {var}")

        is_valid = len(missing_required) == 0

        details = {
            'run_mode': run_mode,
            'is_valid': is_valid,
            'missing_required': missing_required,
            'missing_optional': missing_optional,
            'timestamp': __import__('time').time()
        }

        return is_valid, details

    @staticmethod
    def check_database(db_path: str = None, verbose: bool = False) -> Tuple[bool, str]:
        """
        检查数据库文件的可访问性

        参数:
            db_path: 数据库路径，若为 None 则使用默认
            verbose: 是否打印详细信息

        返回: (is_accessible, message)
        """
        if db_path is None:
            from db_config import DATA_DIR
            db_path = os.path.join(DATA_DIR, 'quant_system.db')

        # 检查父目录是否存在
        db_dir = os.path.dirname(db_path) or '.'
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                if verbose:
                    try:
                        print(f"  [OK] Database directory created: {db_dir}")
                    except UnicodeEncodeError:
                        print(f"  OK: Database directory created: {db_dir}")
            except Exception as e:
                if verbose:
                    try:
                        print(f"  [ERROR] Cannot create database directory: {e}")
                    except UnicodeEncodeError:
                        print(f"  ERROR: Cannot create database directory: {e}")
                return False, f"Cannot create directory {db_dir}: {str(e)}"

        # 检查数据库文件是否可写
        if os.path.exists(db_path):
            if not os.access(db_path, os.R_OK | os.W_OK):
                if verbose:
                    try:
                        print(f"  [ERROR] Database file is not readable/writable: {db_path}")
                    except UnicodeEncodeError:
                        print(f"  ERROR: Database file is not readable/writable: {db_path}")
                return False, f"Database file is not readable/writable: {db_path}"
            if verbose:
                try:
                    print(f"  [OK] Database file is accessible: {db_path}")
                except UnicodeEncodeError:
                    print(f"  OK: Database file is accessible: {db_path}")
        else:
            # 尝试创建测试文件
            try:
                test_file = os.path.join(db_dir, '.write_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                if verbose:
                    try:
                        print(f"  [OK] Database directory is writable, database will be created on startup: {db_path}")
                    except UnicodeEncodeError:
                        print(f"  OK: Database directory is writable, database will be created on startup: {db_path}")
            except Exception as e:
                if verbose:
                    try:
                        print(f"  [ERROR] Database directory is not writable: {e}")
                    except UnicodeEncodeError:
                        print(f"  ERROR: Database directory is not writable: {e}")
                return False, f"Database directory is not writable: {str(e)}"

        return True, f"Database path is accessible: {db_path}"

    @staticmethod
    def run_full_check(verbose: bool = True) -> Tuple[bool, Dict[str, Any]]:
        """
        执行完整的启动检查

        返回: (all_passed, results_dict)
        """
        if verbose:
            try:
                print("\n" + "=" * 60)
                print("[系统检查] 启动前系统检查")
                print("=" * 60)
            except UnicodeEncodeError:
                print("\n" + "=" * 60)
                print("[System Check] Starting pre-startup system checks")
                print("=" * 60)

        results = {
            'packages': None,
            'config': None,
            'database': None,
            'all_passed': False,
            'timestamp': __import__('time').time()
        }

        # 1. 检查依赖包
        if verbose:
            try:
                print("\n[1/3] 检查 Python 依赖...")
            except UnicodeEncodeError:
                print("\n[1/3] Checking Python dependencies...")
        pkg_ok, missing_req, missing_opt = StartupValidator.check_packages(verbose=verbose)
        results['packages'] = {
            'ok': pkg_ok,
            'missing_required': missing_req,
            'missing_optional': missing_opt
        }

        if not pkg_ok:
            if verbose:
                try:
                    print("\n[ERROR] 缺失必需的 Python 包:")
                    for pkg in missing_req:
                        print(f"   - {pkg}")
                    print("\n[HINT] 解决方案: pip install -r requirements.txt")
                except UnicodeEncodeError:
                    print("\n[ERROR] Missing required Python packages:")
                    for pkg in missing_req:
                        print(f"   - {pkg}")
                    print("\n[HINT] Solution: pip install -r requirements.txt")
            return False, results

        # 2. 检查配置
        if verbose:
            try:
                print("\n[2/3] 检查配置...")
            except UnicodeEncodeError:
                print("\n[2/3] Checking configuration...")
        config_ok, config_details = StartupValidator.check_config(verbose=verbose)
        results['config'] = config_details

        if not config_ok:
            if verbose:
                try:
                    print(f"\n[ERROR] 配置不完整 (运行模式: {config_details['run_mode']}):")
                    for var in config_details['missing_required']:
                        print(f"   - 缺失: {var}")
                    print(f"\n[HINT] 解决方案: 请设置以下环境变量:")
                    print(f"   export {' '.join(config_details['missing_required'])}")
                    print(f"\n   或使用 .env 文件配置这些变量")
                except UnicodeEncodeError:
                    print(f"\n[ERROR] Incomplete configuration (run mode: {config_details['run_mode']}):")
                    for var in config_details['missing_required']:
                        print(f"   - Missing: {var}")
            return False, results

        # 3. 检查数据库
        if verbose:
            try:
                print("\n[3/3] 检查数据库...")
            except UnicodeEncodeError:
                print("\n[3/3] Checking database...")
        db_ok, db_msg = StartupValidator.check_database(verbose=verbose)
        results['database'] = {
            'ok': db_ok,
            'message': db_msg
        }

        if not db_ok:
            if verbose:
                try:
                    print(f"\n[ERROR] 数据库检查失败: {db_msg}")
                except UnicodeEncodeError:
                    print(f"\n[ERROR] Database check failed: {db_msg}")
            return False, results

        # 所有检查通过
        results['all_passed'] = True
        if verbose:
            try:
                print("\n" + "=" * 60)
                print("[OK] 所有检查通过！系统已准备好启动")
                print("=" * 60 + "\n")
            except UnicodeEncodeError:
                print("\n" + "=" * 60)
                print("[OK] All checks passed! System is ready to start.")
                print("=" * 60 + "\n")

        return True, results

    @staticmethod
    def validate_and_exit(run_mode: str = None) -> None:
        """
        执行检查，若失败则打印错误并退出

        参数:
            run_mode: 运行模式，若为 None 则从环境变量读取
        """
        all_passed, results = StartupValidator.run_full_check(verbose=True)

        if not all_passed:
            print("\n❌ 启动检查失败。请修正以上错误后重试。")
            sys.exit(1)


# 测试函数
def test_validator():
    """用于测试启动验证器的独立函数"""
    all_passed, results = StartupValidator.run_full_check(verbose=True)
    return all_passed


if __name__ == '__main__':
    # 允许直接运行此脚本进行检查
    StartupValidator.validate_and_exit()
