import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# 设置论文级别的绘图风格
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']
plt.rcParams['font.size'] = 10
plt.rcParams['axes.linewidth'] = 1.2
plt.rcParams['xtick.major.width'] = 1.2
plt.rcParams['ytick.major.width'] = 1.2
plt.rcParams['xtick.major.size'] = 4
plt.rcParams['ytick.major.size'] = 4

# 读取Shapley值
with open('shapley/counter_shapley.json', 'r') as f:
    counter_shapley = json.load(f)

with open('shapley/url_stack_shapley.json', 'r') as f:
    url_stack_shapley = json.load(f)

with open('shapley/vlm_shapley.json', 'r') as f:
    vlm_shapley = json.load(f)

# 定义配色方案（ACL论文风格：专业、清晰、易于区分）
colors = {
    'counter': '#E8927C',      # 柔和的橙红色
    'url_stack': '#89B6E8',    # 柔和的蓝色
    'vlm': '#8FBC94'           # 柔和的绿色
}

# ============================================
# 图1: Task Type维度（Single Source & Multi Source）
# ============================================

# 定义横坐标和数据
task_categories = ['SS easy', 'SS medium', 'SS hard', 'MS easy', 'MS medium', 'MS hard']
task_keys = ['single_source_easy', 'single_source_medium', 'single_source_hard',
             'multi_source_easy', 'multi_source_medium', 'multi_source_hard']

# 提取数据并转换为整数（乘以1000）
counter_values_task = [int(counter_shapley[key] * 1000) for key in task_keys]
url_stack_values_task = [int(url_stack_shapley[key] * 1000) for key in task_keys]
vlm_values_task = [int(vlm_shapley[key] * 1000) for key in task_keys]

# 创建图1
fig1, ax1 = plt.subplots(figsize=(7, 4))

x = np.arange(len(task_categories))
width = 0.6

# 从下到上堆叠：vlm -> url_stack -> counter
bars1 = ax1.bar(x, vlm_values_task, width, label='VLM',
                color=colors['vlm'], edgecolor='none')
bars2 = ax1.bar(x, url_stack_values_task, width, bottom=vlm_values_task,
                label='URL Stack', color=colors['url_stack'],
                edgecolor='none')
bars3 = ax1.bar(x, counter_values_task, width,
                bottom=np.array(vlm_values_task) + np.array(url_stack_values_task),
                label='Counter', color=colors['counter'],
                edgecolor='none')

# 设置标签和标题
ax1.set_ylabel('Shapley Value', fontsize=11, fontweight='bold')
ax1.set_xlabel('Task Type', fontsize=11, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(task_categories, fontsize=10)
ax1.set_ylim(0, max(np.array(counter_values_task) + np.array(url_stack_values_task) + np.array(vlm_values_task)) * 1.15)

# 添加网格线（仅水平）
ax1.grid(axis='y', linestyle='--', alpha=0.3, linewidth=0.8)
ax1.set_axisbelow(True)

# 添加图例（放在右上角）
legend1 = ax1.legend(loc='upper right', frameon=True, shadow=False,
                     framealpha=0.95, edgecolor='gray', fontsize=10)
legend1.get_frame().set_linewidth(1.2)

# 调整布局
plt.tight_layout()
plt.savefig('shapley/task_type_shapley_stacked.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print("✓ 任务类型Shapley堆叠柱状图已保存:")
print("  - shapley/task_type_shapley_stacked.png")

# ============================================
# 图2: Domain维度
# ============================================

# 定义横坐标和数据
domain_categories = ['en', 'cn', 'game', 'conf', 'organ', 'edu']
domain_keys = ['en', 'cn', 'game', 'conference', 'organization', 'education']

# 提取数据并转换为整数（乘以1000）
counter_values_domain = [int(counter_shapley[key] * 1000) for key in domain_keys]
url_stack_values_domain = [int(url_stack_shapley[key] * 1000) for key in domain_keys]
vlm_values_domain = [int(vlm_shapley[key] * 1000) for key in domain_keys]

# 创建图2
fig2, ax2 = plt.subplots(figsize=(7, 4))

x = np.arange(len(domain_categories))
width = 0.6

# 从下到上堆叠：vlm -> url_stack -> counter
bars1 = ax2.bar(x, vlm_values_domain, width, label='VLM',
                color=colors['vlm'], edgecolor='none')
bars2 = ax2.bar(x, url_stack_values_domain, width, bottom=vlm_values_domain,
                label='URL Stack', color=colors['url_stack'],
                edgecolor='none')
bars3 = ax2.bar(x, counter_values_domain, width,
                bottom=np.array(vlm_values_domain) + np.array(url_stack_values_domain),
                label='Counter', color=colors['counter'],
                edgecolor='none')

# 设置标签和标题
ax2.set_ylabel('Shapley Value', fontsize=11, fontweight='bold')
ax2.set_xlabel('Domain', fontsize=11, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(domain_categories, fontsize=10)
ax2.set_ylim(0, max(np.array(counter_values_domain) + np.array(url_stack_values_domain) + np.array(vlm_values_domain)) * 1.15)

# 添加网格线（仅水平）
ax2.grid(axis='y', linestyle='--', alpha=0.3, linewidth=0.8)
ax2.set_axisbelow(True)

# 添加图例（放在右上角）
legend2 = ax2.legend(loc='upper right', frameon=True, shadow=False,
                     framealpha=0.95, edgecolor='gray', fontsize=10)
legend2.get_frame().set_linewidth(1.2)

# 调整布局
plt.tight_layout()
plt.savefig('shapley/domain_shapley_stacked.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print("\n✓ 领域Shapley堆叠柱状图已保存:")
print("  - shapley/domain_shapley_stacked.png")

print("\n" + "="*60)
print("✅ 所有堆叠柱状图生成完成！")
print("="*60)

# 打印数据表格供验证
print("\n【任务类型维度数值表】")
print(f"{'Category':<15s} {'Counter':>10s} {'URL Stack':>10s} {'VLM':>10s} {'Total':>10s}")
print("-" * 60)
for i, cat in enumerate(task_categories):
    total = counter_values_task[i] + url_stack_values_task[i] + vlm_values_task[i]
    print(f"{cat:<15s} {counter_values_task[i]:>10d} {url_stack_values_task[i]:>10d} {vlm_values_task[i]:>10d} {total:>10d}")

print("\n【领域维度数值表】")
print(f"{'Category':<15s} {'Counter':>10s} {'URL Stack':>10s} {'VLM':>10s} {'Total':>10s}")
print("-" * 60)
for i, cat in enumerate(domain_categories):
    total = counter_values_domain[i] + url_stack_values_domain[i] + vlm_values_domain[i]
    print(f"{cat:<15s} {counter_values_domain[i]:>10d} {url_stack_values_domain[i]:>10d} {vlm_values_domain[i]:>10d} {total:>10d}")

plt.show()
