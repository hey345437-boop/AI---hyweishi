#!/bin/bash
# 交易机器人一键启动脚本（Linux版本）

echo "=== 启动交易机器人 ==="

# 创建 logs 目录（如果不存在）
mkdir -p logs

# 激活虚拟环境
source trade_env/bin/activate

# 启动后端服务
nohup python separated_system/trade_engine.py > logs/trade_engine.log 2>&1 &
echo "后端服务已启动，日志文件：logs/trade_engine.log"

# 等待5秒，确保后端服务启动完成
sleep 5

# 启动前端服务
nohup streamlit run app.py > logs/streamlit.log 2>&1 &
echo "前端服务已启动，日志文件：logs/streamlit.log"
echo "前端地址: http://localhost:10000"
echo "交易机器人启动完成！"
