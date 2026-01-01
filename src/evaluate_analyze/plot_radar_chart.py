import json
import numpy as np
import matplotlib.pyplot as plt

# --- 1. 环境配置 (ACL 论文风格) ---
# 优先使用 Serif 字体（如 Times New Roman 的替代品），确保学术感
plt.rcParams['font.family'] = 'serif'
plt.rcParams['axes.unicode_minus'] = False

# --- 2. 读取数据 (保留您的原始逻辑) ---
with open('results/all.json', 'r') as f:
    ours_data = json.load(f)

with open('results/no.json', 'r') as f:
    v_gems_data = json.load(f)

# 定义六个维度
categories = [
    'Single Source\nEasy',
    'Single Source\nMedium',
    'Single Source\nHard',
    'Multi Source\nEasy',
    'Multi Source\nMedium',
    'Multi Source\nHard'
]

ours_values = [
    ours_data['single_source_easy'],
    ours_data['single_source_medium'],
    ours_data['single_source_hard'],
    ours_data['multi_source_easy'],
    ours_data['multi_source_medium'],
    ours_data['multi_source_hard']
]

v_gems_values = [
    v_gems_data['single_source_easy'],
    v_gems_data['single_source_medium'],
    v_gems_data['single_source_hard'],
    v_gems_data['multi_source_easy'],
    v_gems_data['multi_source_medium'],
    v_gems_data['multi_source_hard']
]

# categories = [
#     'Chinese',
#     'English',
#     'Game',
#     'Education',
#     'Organization',
#     'Conference'
# ]

# ours_values = [
#     ours_data['cn'],
#     ours_data['en'],
#     ours_data['game'],
#     ours_data['education'],
#     ours_data['organization'],
#     ours_data['conference']
# ]

# v_gems_values = [
#     v_gems_data['cn'],
#     v_gems_data['en'],
#     v_gems_data['game'],
#     v_gems_data['education'],
#     v_gems_data['organization'],
#     v_gems_data['conference']
# ]

# --- 3. 数据闭合处理 ---
N = len(categories)
angles = [n / float(N) * 2 * np.pi for n in range(N)]
ours_plot = ours_values + ours_values[:1]
web_plot = v_gems_values + v_gems_values[:1]
angles_plot = angles + angles[:1]

# --- 4. 绘图核心 ---
fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
fig.subplots_adjust(left=0.1, right=0.8, top=0.8, bottom=0.1)

# 设置底色
ax.set_facecolor('#fdfdfd')

# 绘制 Ours (蓝色)
ax.plot(angles_plot, ours_plot, 'o-', linewidth=3.5, label='Ours',
        color='#2E86DE', markersize=10, zorder=3)
ax.fill(angles_plot, ours_plot, alpha=0.2, color='#2E86DE')

# 绘制 VGems (红色)
ax.plot(angles_plot, web_plot, 's-', linewidth=3.5, label='VGems',
        color='#EE5A6F', markersize=10, zorder=2)
ax.fill(angles_plot, web_plot, alpha=0.2, color='#EE5A6F')

# --- 5. 坐标轴与标签优化 ---
# 维度标签：加大、加粗、增加间距 (pad)
ax.set_xticks(angles)
ax.set_xticklabels(categories, size=25, weight='bold', color='black')
ax.tick_params(axis='x', pad=40) 

# Y轴刻度：稍微放大，颜色淡化
ax.set_ylim(0, 1.0)
ax.set_yticks([0.2, 0.4, 0.6, 0.8])
ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8'], size=14, color='gray')

plt.title('Ours vs VGems',
          size=35, weight='bold', pad=60)

# 图例显著放大，放在右上角
# 将 loc 改为 'lower left'，并调整 bbox_to_anchor 坐标
legend = ax.legend(loc='lower left', 
                   bbox_to_anchor=(-0.25, -0.35), # 第一个参数控制左右偏移，第二个参数控制上下偏移
                   fontsize=25,
                   frameon=True, 
                   shadow=False, 
                   edgecolor='black')
legend.get_frame().set_linewidth(1.5)

# 增强网格和外圈粗细
ax.grid(True, linestyle='--', linewidth=1, color='gray', alpha=0.4)
ax.spines['polar'].set_linewidth(2)

# --- 8. 保存输出 ---
plt.tight_layout()
# 保存为 PDF 以获得矢量效果
plt.savefig('results/type_comparison.pdf', bbox_inches='tight', dpi=300)
plt.savefig('results/type_comparison.png', bbox_inches='tight', dpi=300)

print("雷达图已保存至: results/type_comparison.pdf")
plt.show()