import sqlite3
import json
import os

# 连接数据库
db_path = 'quant_system.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询所有用户配置
cursor.execute("SELECT username, api_config FROM users;")
user_configs = cursor.fetchall()

# 更新每个用户的配置，将交易所相关字段改为中性命名
for username, config_json in user_configs:
    try:
        config = json.loads(config_json)
        
        # 检查并更新交易所相关字段，改为OKX命名
        updated = False
        if 'live_bg_key' in config:
            config['live_okx_key'] = config.pop('live_bg_key')
            updated = True
        if 'live_bg_secret' in config:
            config['live_okx_secret'] = config.pop('live_bg_secret')
            updated = True
        if 'live_bg_pass' in config:
            config['live_okx_pass'] = config.pop('live_bg_pass')
            updated = True
        if 'sandbox_bg_key' in config:
            config['sandbox_okx_key'] = config.pop('sandbox_bg_key')
            updated = True
        if 'sandbox_bg_secret' in config:
            config['sandbox_okx_secret'] = config.pop('sandbox_bg_secret')
            updated = True
        if 'sandbox_bg_pass' in config:
            config['sandbox_okx_pass'] = config.pop('sandbox_bg_pass')
            updated = True
        
        # 更新数据库
        if updated:
            new_config_json = json.dumps(config)
            cursor.execute(
                "UPDATE users SET api_config = ? WHERE username = ?;",
                (new_config_json, username)
            )
            print(f"更新了用户 {username} 的配置")
            
    except json.JSONDecodeError:
        print(f"用户 {username} 的配置JSON解析错误: {config_json}")
        continue

# 提交更改
conn.commit()

# 再次检查数据库内容，确认更新成功
print("\n更新后的配置示例:")
cursor.execute("SELECT username, api_config FROM users LIMIT 2;")
updated_configs = cursor.fetchall()
for username, config_json in updated_configs:
    print(f"用户 {username}: {config_json}")

# 关闭数据库连接
conn.close()
print("\n数据库更新完成")
