import difflib
import os

# 读取当前app.py
with open('app.py', 'r', encoding='utf-8') as f:
    app_current = f.readlines()

# 创建一个临时文件来保存修改前的app.py（模拟）
app_old = []
with open('app.py', 'r', encoding='utf-8') as f:
    for line in f:
        app_old.append(line)
        # 找到修复TypeError错误的代码部分
        if 'if paper_positions:' in line:
            # 插入修改前的代码
            next(f)  # 跳过注释行
            app_old.append(next(f))  # 跳过open_positions_dict = {}
            # 插入修改前的循环代码
            app_old.extend([
                '            for pos in paper_positions:\n',
                '                symbol = pos["symbol"]\n',
                '                open_positions_dict[symbol] = {\n',
                '                    "side": pos["side"],\n',
                '                    "size": pos["qty"] * pos["entry_price"],  # 计算持仓价值\n',
                '                    "entry_price": pos["entry_price"]\n',
                '                }\n',
                '            view_model["open_positions"] = open_positions_dict\n'
            ])
            # 跳过当前文件中已修改的代码行
            for _ in range(22):  # 跳过22行修改后的代码
                next(f, None)
            continue
    
# 生成diff
diff = difflib.unified_diff(app_old, app_current, fromfile='app.py.old', tofile='app.py.new')

# 输出结果
print('=== 修改文件清单 ===')
print('app.py - 修复TypeError错误和入场动画问题')
print()
print('=== app.py diff ===')
print(''.join(diff))
