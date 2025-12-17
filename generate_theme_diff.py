import difflib
import os

# 获取修改前的文件内容（模拟）
original_content = '''
def render_dashboard(view_model, actions):
    """Render dashboard"""
    # Set page style
    st.markdown("""
    <style>
        .stApp { background-color: #f7f7f9; font-family: 'Microsoft YaHei'; }
        [data-testid="stSidebar"] { background-color: #fff; border-right: 1px solid #e5e5e5; }
        div[data-testid="stMetric"] { background: #fff; border-radius: 10px; padding: 15px; border-left: 4px solid #ff7eb3; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
        div.stButton > button { background: #ff7eb3; color: white !important; border: none; font-weight: bold; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)
    
    # Main page layout
    col_main, col_chat = st.columns([7, 3])
'''

# 获取当前文件内容
with open('ui_legacy.py', 'r', encoding='utf-8') as f:
    current_content = f.read()

# 提取render_dashboard函数部分
start_idx = current_content.find('def render_dashboard(view_model, actions):')
if start_idx != -1:
    end_idx = current_content.find('def ', start_idx + 1)
    if end_idx == -1:
        end_idx = len(current_content)
    current_content = current_content[start_idx:end_idx]

# 生成diff
diff = difflib.unified_diff(
    original_content.splitlines(),
    current_content.splitlines(),
    fromfile='ui_legacy.py.old',
    tofile='ui_legacy.py.new',
    lineterm=''
)

# 输出修改文件清单
print("### 修改文件清单")
print("1. `d:\\MyTradingBot\\ui_legacy.py` - 删除了覆盖主题的白色背景CSS代码")
print()

# 输出diff
print("### git diff")
print('```diff')
print(''.join([line + '\n' for line in diff]))
print('```')

# 简短说明
print("### 简短说明")
print("- 删除了`render_dashboard`函数中强制设置白色背景的CSS代码，包括：")
print("  - `.stApp { background-color: #f7f7f9; }`")
print("  - `[data-testid=\"stSidebar\"] { background-color: #fff; }`")
print("  - 其他覆盖主题样式的规则")
print("- 确保应用程序现在使用`.streamlit/config.toml`中定义的深色主题和`assets/theme_tiktok.css`中定义的抖音风格样式")
print("- 所有文字现在将使用浅色字体，在深色背景下清晰可读")
