param(
    [switch]$SkipCheck = $false,
    [switch]$Verbose = $false
)

# ============ 启动前系统检查脚本 ============
# 该脚本在启动交易系统前进行全面检查

$ErrorActionPreference = "Stop"
$scriptPath = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   交易系统启动检查 (PowerShell 版本)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 颜色定义
$colors = @{
    'Green' = 'Green'
    'Red' = 'Red'
    'Yellow' = 'Yellow'
    'Cyan' = 'Cyan'
    'Gray' = 'Gray'
}

function Write-Check([string]$message, [bool]$passed) {
    if ($passed) {
        Write-Host "  ✓ $message" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $message" -ForegroundColor Red
    }
}

function Write-Info([string]$message) {
    Write-Host "  ℹ $message" -ForegroundColor Cyan
}

function Write-Warning([string]$message) {
    Write-Host "  ⚠ $message" -ForegroundColor Yellow
}

# ============ 1. 检查 Python ============
Write-Host "[1/5] 检查 Python..." -ForegroundColor Cyan
try {
    $pythonVersion = python --version 2>&1
    $passed = $?
    Write-Check "Python: $pythonVersion" $passed
    if (-not $passed) {
        throw "Python 不可用"
    }
} catch {
    Write-Host ""
    Write-Host "错误：Python 不可用或未安装" -ForegroundColor Red
    Write-Host ""
    Write-Host "解决方案：" -ForegroundColor Yellow
    Write-Host "  1. 从 https://www.python.org 下载 Python 3.8+"
    Write-Host "  2. 安装时勾选 'Add Python to PATH'"
    Write-Host "  3. 重启此脚本"
    Write-Host ""
    exit 1
}

# ============ 2. 检查依赖包 ============
Write-Host ""
Write-Host "[2/5] 检查 Python 依赖包..." -ForegroundColor Cyan

$requiredPackages = @('streamlit', 'pandas', 'numpy', 'ccxt', 'cryptography', 'psycopg2')
$missingPackages = @()

foreach ($pkg in $requiredPackages) {
    try {
        python -c "import $pkg" 2>$null
        if ($?) {
            Write-Check "包: $pkg" $true
        } else {
            $missingPackages += $pkg
            Write-Check "包: $pkg" $false
        }
    } catch {
        $missingPackages += $pkg
        Write-Check "包: $pkg" $false
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host ""
    Write-Host "错误：缺失以下必要包：$($missingPackages -join ', ')" -ForegroundColor Red
    Write-Host ""
    Write-Host "解决方案：运行以下命令安装依赖" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements.txt"
    Write-Host ""
    exit 1
}

# ============ 3. 检查配置 ============
Write-Host ""
Write-Host "[3/5] 检查配置..." -ForegroundColor Cyan

$runMode = [Environment]::GetEnvironmentVariable("RUN_MODE")
if (-not $runMode) {
    $runMode = "sim"
    Write-Warning "RUN_MODE 未设置，使用默认值: $runMode"
} else {
    Write-Check "运行模式: $runMode" $true
}

# 检查关键配置
$configOk = $true
if ($runMode -in @("paper", "live")) {
    $apiKey = [Environment]::GetEnvironmentVariable("OKX_API_KEY")
    $apiSecret = [Environment]::GetEnvironmentVariable("OKX_API_SECRET")
    $passphrase = [Environment]::GetEnvironmentVariable("OKX_API_PASSPHRASE")
    
    if ([string]::IsNullOrEmpty($apiKey)) {
        Write-Check "API Key 已设置" $false
        $configOk = $false
    } else {
        Write-Check "API Key 已设置" $true
    }
    
    if ([string]::IsNullOrEmpty($apiSecret)) {
        Write-Check "API Secret 已设置" $false
        $configOk = $false
    } else {
        Write-Check "API Secret 已设置" $true
    }
    
    if ([string]::IsNullOrEmpty($passphrase)) {
        Write-Check "Passphrase 已设置" $false
        $configOk = $false
    } else {
        Write-Check "Passphrase 已设置" $true
    }
    
    if (-not $configOk) {
        Write-Host ""
        Write-Host "错误：运行模式为 '$runMode'，但 API 凭证未完整设置" -ForegroundColor Red
        Write-Host ""
        Write-Host "请设置以下环境变量：" -ForegroundColor Yellow
        Write-Host "  [System.Environment]::SetEnvironmentVariable('OKX_API_KEY', 'your_key')"
        Write-Host "  [System.Environment]::SetEnvironmentVariable('OKX_API_SECRET', 'your_secret')"
        Write-Host "  [System.Environment]::SetEnvironmentVariable('OKX_API_PASSPHRASE', 'your_passphrase')"
        Write-Host ""
        exit 1
    }
} else {
    Write-Check "模拟模式（无需 API 密钥）" $true
}

# ============ 4. 检查数据库 ============
Write-Host ""
Write-Host "[4/5] 检查数据库..." -ForegroundColor Cyan

$dbPath = "quant_system.db"
$dataDir = "data"

if (-not (Test-Path $dataDir)) {
    try {
        New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
        Write-Check "数据目录已创建: $dataDir" $true
    } catch {
        Write-Host ""
        Write-Host "错误：无法创建数据目录" -ForegroundColor Red
        Write-Host $_.Exception.Message
        Write-Host ""
        exit 1
    }
} else {
    Write-Check "数据目录存在: $dataDir" $true
}

# 检查数据库文件是否可写
if (Test-Path $dbPath) {
    try {
        (Get-ChildItem $dbPath).Attributes -bor 'Archive'
        Write-Check "数据库文件可访问: $dbPath" $true
    } catch {
        Write-Check "数据库文件可访问: $dbPath" $false
        Write-Warning "将在启动时重新创建数据库"
    }
} else {
    Write-Check "数据库将在启动时创建: $dbPath" $true
}

# ============ 5. 检查后端文件 ============
Write-Host ""
Write-Host "[5/5] 检查后端文件..." -ForegroundColor Cyan

$backendFiles = @("separated_system\trade_engine.py", "trade_engine.py")
$backendFound = $false
$backendPath = ""

foreach ($file in $backendFiles) {
    if (Test-Path $file) {
        Write-Check "后端文件存在: $file" $true
        $backendFound = $true
        $backendPath = $file
        break
    }
}

if (-not $backendFound) {
    Write-Host ""
    Write-Host "错误：未找到后端入口文件" -ForegroundColor Red
    Write-Host "期望位置：$($backendFiles -join ' 或 ')"
    Write-Host ""
    exit 1
}

# ============ 所有检查通过 ============
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "   ✓ 所有检查通过！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "系统已准备就绪，可以启动应用。" -ForegroundColor Green
Write-Host ""
Write-Host "启动命令："
Write-Host "  1. 启动完整系统（后端 + 前端）："
Write-Host "     & '.\一键启动.bat'"
Write-Host ""
Write-Host "  2. 仅启动后端："
Write-Host "     python $backendPath"
Write-Host ""
Write-Host "  3. 仅启动前端："
Write-Host "     streamlit run app.py --server.port 8501"
Write-Host ""
