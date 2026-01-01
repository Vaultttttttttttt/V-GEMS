import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']
plt.rcParams['font.size'] = 20
plt.rcParams['axes.linewidth'] = 1.5# 坐标轴线的粗细

# 核心调整：设置全局字体粗细为 Bold 或 Semi-Bold
# 'weight' 参数可以接受 'normal', 'bold', 'heavy', 'light', 'ultrabold', 'ultralight' 或一个数字 (0-1000)
# 'bold' 是一个常见的选择，但如果需要更细腻的控制，可以使用 'semibold' (如 600)
plt.rcParams['font.weight'] = 'bold' 

# 可选：单独设置子组件的粗细（推荐）
# 标题、X轴和Y轴标签通常需要加粗
plt.rcParams['axes.titleweight'] = 'bold' # 标题粗细
plt.rcParams['axes.labelweight'] = 'bold' # X轴和Y轴标签粗细
# plt.rcParams['xtick.major.width'] = 1.2 # X轴主刻度线的粗细
# plt.rcParams['ytick.major.width'] = 1.2 # Y轴主刻度线的粗细

# 定义目录和文件
error_dir = Path('/Users/wxj/Library/Mobile Documents/com~apple~CloudDocs/VGems/src/evaluate_results/error_accessment')

# 定义8个消融实验的文件名和显示名称
experiments = [
    ('all_classified_stats.json', 'All (Ours)'),
    ('no_counter_classified_stats.json', 'No Counter'),
    ('no_url_stack_classified_stats.json', 'No URL Stack'),
    ('no_vlm_classified_stats.json', 'No VLM'),
    ('only_counter_classified_stats.json', 'Only Counter'),
    ('only_url_stack_classified_stats.json', 'Only URL Stack'),
    ('only_vlm_classified_stats.json', 'Only VLM'),
    ('no_classified_stats.json', 'No (Baseline)')
]

# 读取所有统计数据
data = {}
for filename, display_name in experiments:
    filepath = error_dir / filename
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            data[display_name] = json.load(f)
    else:
        print(f"Warning: {filename} not found")

# 定义分类顺序和颜色（从左到右）
categories = ['Correct', 'Missing', 'Imprecise', 'Totally Incorrect', 'Hallucination', 'Refusal']
# colors = {
#     'Correct': '#4CAF50',           # 绿色 - 正确
#     'Missing': '#FFEB3B',            # 黄色 - 缺失
#     'Imprecise': '#FFC107',          # 琥珀色 - 不精确
#     'Totally Incorrect': '#FF9800',  # 橙色 - 完全错误
#     'Hallucination': '#F44336',      # 红色 - 幻觉
#     'Refusal': '#2196F3'             # 蓝色 - 拒绝
# }

colors = {
    'Correct': '#A5D6A7',
    'Missing': '#FFF176',
    'Imprecise': '#FFAB91',
    'Totally Incorrect': '#FF8A65',
    'Hallucination': '#E57373',
    'Refusal': '#90CAF9'
}

# 准备数据
experiment_names = [name for _, name in experiments if name in data]
category_percentages = {cat: [] for cat in categories}

for exp_name in experiment_names:
    for cat in categories:
        if cat in data[exp_name]:
            category_percentages[cat].append(data[exp_name][cat]['percentage'])
        else:
            category_percentages[cat].append(0)

# 创建图形
fig, ax = plt.subplots(figsize=(10, 6))

# 绘制横向堆叠柱状图
y_pos = np.arange(len(experiment_names))
left = np.zeros(len(experiment_names))

bars = []
for cat in categories:
    bar = ax.barh(y_pos, category_percentages[cat], left=left,
                  label=cat, color=colors[cat], edgecolor='none')
    bars.append(bar)
    left += np.array(category_percentages[cat])

# 设置标签
ax.set_xlabel('Percentage (%)', fontsize=20, fontweight='bold')
ax.set_title('Prediction Distribution', fontsize=20, fontweight='bold', pad=15)

# 设置y轴
ax.set_yticks(y_pos)
ax.set_yticklabels(experiment_names, fontsize=20, fontweight='bold')

# 设置x轴范围和刻度
ax.set_xlim(0, 100)
ax.set_xticks(range(0, 101, 10))
ax.set_xticklabels([f'{x}' for x in range(0, 101, 10)])

# 添加网格线（垂直）
ax.grid(axis='x', linestyle='--', alpha=0.3, linewidth=0.8)
ax.set_axisbelow(True)

# 添加图例（放在右上角外侧）
legend = ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5),
                   frameon=True, shadow=False, framealpha=0.95,
                   edgecolor='gray', fontsize=15)
legend.get_frame().set_linewidth(1.2)

# 调整布局
plt.tight_layout()

# 保存图片
output_dir = error_dir.parent / 'error_accessment'
output_png = output_dir / 'prediction_distribution_stacked.png'
output_pdf = output_dir / 'prediction_distribution_stacked.pdf'

plt.savefig(output_png, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
plt.savefig(output_pdf, bbox_inches='tight', facecolor='white', edgecolor='none')

print("✓ Error Assessment堆叠柱状图已保存:")
print(f"  - {output_png}")
print(f"  - {output_pdf}")

# 打印数据表格供验证
print("\n" + "="*100)
print("各实验的分类分布")
print("="*100)
header = f"{'Experiment':<20s} " + " ".join([f"{cat:>12s}" for cat in categories])
print(header)
print("-"*100)

for exp_name in experiment_names:
    row = f"{exp_name:<20s} "
    for cat in categories:
        if cat in data[exp_name]:
            row += f"{data[exp_name][cat]['percentage']:>11.1f}% "
        else:
            row += f"{'0.0%':>12s} "
    print(row)

print("="*100)

plt.show()
