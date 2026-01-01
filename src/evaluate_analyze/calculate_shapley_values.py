import json
import os

# 定义所有场景（12个维度）
scenarios = [
    'single_source_easy',
    'single_source_medium',
    'single_source_hard',
    'multi_source_easy',
    'multi_source_medium',
    'multi_source_hard',
    'cn',
    'en',
    'game',
    'conference',
    'organization',
    'education'
]

# 读取所有JSON文件
results_dir = 'results'
data = {}

json_files = [
    'all.json',
    'no.json',
    'no_counter.json',
    'no_url_stack.json',
    'no_vlm.json',
    'only_counter.json',
    'only_url_stack.json',
    'only_vlm.json'
]

print("正在读取JSON文件...")
for filename in json_files:
    filepath = os.path.join(results_dir, filename)
    with open(filepath, 'r') as f:
        key = filename.replace('.json', '')
        data[key] = json.load(f)
        print(f"  ✓ 已读取: {filename}")

print("\n" + "="*60)
print("开始计算Shapley值...")
print("="*60)

# 创建shapley文件夹（如果不存在）
shapley_dir = 'shapley'
os.makedirs(shapley_dir, exist_ok=True)

# ========================================
# 1. 计算 Counter 的贡献
# ========================================
print("\n【1/3】计算 Counter 的 Shapley 值...")
counter_contribution = {}

for scenario in scenarios:
    # Shapley公式: c_counter = [(only_counter - no) + (no_vlm - only_url_stack + no_url_stack - only_vlm)/2 + (all - no_counter)] / 3

    only_counter = data['only_counter'][scenario]
    no = data['no'][scenario]
    no_vlm = data['no_vlm'][scenario]
    only_url_stack = data['only_url_stack'][scenario]
    no_url_stack = data['no_url_stack'][scenario]
    only_vlm = data['only_vlm'][scenario]
    all_val = data['all'][scenario]
    no_counter = data['no_counter'][scenario]

    # 计算Shapley值
    term1 = only_counter - no
    term2 = (no_vlm - only_url_stack + no_url_stack - only_vlm) / 2
    term3 = all_val - no_counter

    shapley_value = (term1 + term2 + term3) / 3
    counter_contribution[scenario] = round(shapley_value, 6)

    print(f"  {scenario:25s}: {shapley_value:+.6f}")

# 保存Counter的Shapley值
counter_output = os.path.join(shapley_dir, 'counter_shapley.json')
with open(counter_output, 'w') as f:
    json.dump(counter_contribution, f, indent=4, ensure_ascii=False)
print(f"\n✓ Counter Shapley值已保存至: {counter_output}")

# ========================================
# 2. 计算 URL Stack 的贡献
# ========================================
print("\n【2/3】计算 URL Stack 的 Shapley 值...")
url_stack_contribution = {}

for scenario in scenarios:
    # Shapley公式: c_url_stack = [(only_url_stack - no) + (no_vlm - only_counter + no_counter - only_vlm)/2 + (all - no_url_stack)] / 3

    only_url_stack = data['only_url_stack'][scenario]
    no = data['no'][scenario]
    no_vlm = data['no_vlm'][scenario]
    only_counter = data['only_counter'][scenario]
    no_counter = data['no_counter'][scenario]
    only_vlm = data['only_vlm'][scenario]
    all_val = data['all'][scenario]
    no_url_stack = data['no_url_stack'][scenario]

    # 计算Shapley值
    term1 = only_url_stack - no
    term2 = (no_vlm - only_counter + no_counter - only_vlm) / 2
    term3 = all_val - no_url_stack

    shapley_value = (term1 + term2 + term3) / 3
    url_stack_contribution[scenario] = round(shapley_value, 6)

    print(f"  {scenario:25s}: {shapley_value:+.6f}")

# 保存URL Stack的Shapley值
url_stack_output = os.path.join(shapley_dir, 'url_stack_shapley.json')
with open(url_stack_output, 'w') as f:
    json.dump(url_stack_contribution, f, indent=4, ensure_ascii=False)
print(f"\n✓ URL Stack Shapley值已保存至: {url_stack_output}")

# ========================================
# 3. 计算 VLM 的贡献
# ========================================
print("\n【3/3】计算 VLM 的 Shapley 值...")
vlm_contribution = {}

for scenario in scenarios:
    # Shapley公式: c_vlm = [(only_vlm - no) + (no_counter - only_url_stack + no_url_stack - only_counter)/2 + (all - no_vlm)] / 3

    only_vlm = data['only_vlm'][scenario]
    no = data['no'][scenario]
    no_counter = data['no_counter'][scenario]
    only_url_stack = data['only_url_stack'][scenario]
    no_url_stack = data['no_url_stack'][scenario]
    only_counter = data['only_counter'][scenario]
    all_val = data['all'][scenario]
    no_vlm = data['no_vlm'][scenario]

    # 计算Shapley值
    term1 = only_vlm - no
    term2 = (no_counter - only_url_stack + no_url_stack - only_counter) / 2
    term3 = all_val - no_vlm

    shapley_value = (term1 + term2 + term3) / 3
    vlm_contribution[scenario] = round(shapley_value, 6)

    print(f"  {scenario:25s}: {shapley_value:+.6f}")

# 保存VLM的Shapley值
vlm_output = os.path.join(shapley_dir, 'vlm_shapley.json')
with open(vlm_output, 'w') as f:
    json.dump(vlm_contribution, f, indent=4, ensure_ascii=False)
print(f"\n✓ VLM Shapley值已保存至: {vlm_output}")

# ========================================
# 4. 汇总所有Shapley值
# ========================================
print("\n" + "="*60)
print("汇总所有Shapley值...")
print("="*60)

summary = {}
for scenario in scenarios:
    summary[scenario] = {
        'counter': counter_contribution[scenario],
        'url_stack': url_stack_contribution[scenario],
        'vlm': vlm_contribution[scenario],
        'total': round(counter_contribution[scenario] + url_stack_contribution[scenario] + vlm_contribution[scenario], 6)
    }

# 保存汇总结果
summary_output = os.path.join(shapley_dir, 'shapley_summary.json')
with open(summary_output, 'w') as f:
    json.dump(summary, f, indent=4, ensure_ascii=False)
print(f"\n✓ Shapley值汇总已保存至: {summary_output}")

# 打印汇总表格
print("\n" + "="*90)
print("Shapley值汇总表")
print("="*90)
print(f"{'场景':<30s} {'Counter':>12s} {'URL Stack':>12s} {'VLM':>12s} {'Total':>12s}")
print("-"*90)
for scenario in scenarios:
    s = summary[scenario]
    print(f"{scenario:<30s} {s['counter']:>+12.6f} {s['url_stack']:>+12.6f} {s['vlm']:>+12.6f} {s['total']:>+12.6f}")

print("="*90)
print(f"\n✅ 所有计算完成！结果已保存到 '{shapley_dir}/' 文件夹")
