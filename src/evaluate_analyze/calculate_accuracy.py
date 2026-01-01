#!/usr/bin/env python3
"""
统计 JSONL 文件中的正确率
按照 type-difficulty 和 domain、language 维度进行统计
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict


def load_jsonl(file_path):
    """读取 JSONL 文件"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def calculate_accuracy(data):
    """计算各个维度的正确率"""

    # 用于统计各个维度的数据
    type_difficulty_stats = defaultdict(lambda: {'total': 0, 'correct': 0})
    domain_stats = defaultdict(lambda: {'total': 0, 'correct': 0})
    lang_stats = defaultdict(lambda: {'total': 0, 'correct': 0})

    for item in data:
        # 获取相关信息
        score = item.get('score', 0)
        info = item.get('info', {})

        # type-difficulty 组合
        type_name = info.get('type', 'unknown')
        difficulty = info.get('difficulty_level', 'unknown')

        # 将 "single-source" 转换为 "single_source"
        type_name = type_name.replace('-', '_')

        # 组合 key
        type_difficulty_key = f"{type_name}_{difficulty}"
        type_difficulty_stats[type_difficulty_key]['total'] += 1
        type_difficulty_stats[type_difficulty_key]['correct'] += score

        # domain 统计
        domain = info.get('domain', 'unknown')
        domain_stats[domain]['total'] += 1
        domain_stats[domain]['correct'] += score

        # language 统计
        lang = info.get('lang', 'unknown')
        lang_stats[lang]['total'] += 1
        lang_stats[lang]['correct'] += score

    # 计算正确率
    result = {}

    # type-difficulty 正确率
    type_difficulty_keys = [
        'single_source_easy',
        'single_source_medium',
        'single_source_hard',
        'multi_source_easy',
        'multi_source_medium',
        'multi_source_hard'
    ]

    type_difficulty_accuracies = []
    for key in type_difficulty_keys:
        if type_difficulty_stats[key]['total'] > 0:
            accuracy = type_difficulty_stats[key]['correct'] / type_difficulty_stats[key]['total']
            result[key] = accuracy
            type_difficulty_accuracies.append(accuracy)
        else:
            result[key] = 0.0

    # avg_type
    if type_difficulty_accuracies:
        result['avg_type'] = sum(type_difficulty_accuracies) / len(type_difficulty_accuracies)
    else:
        result['avg_type'] = 0.0

    # language 正确率
    for lang in ['cn', 'en']:
        if lang_stats[lang]['total'] > 0:
            result[lang] = lang_stats[lang]['correct'] / lang_stats[lang]['total']
        else:
            result[lang] = 0.0

    # domain 正确率
    domain_keys = ['game', 'conference', 'organization', 'education']
    domain_accuracies = []
    for domain in domain_keys:
        if domain_stats[domain]['total'] > 0:
            accuracy = domain_stats[domain]['correct'] / domain_stats[domain]['total']
            result[domain] = accuracy
            domain_accuracies.append(accuracy)
        else:
            result[domain] = 0.0

    # avg_domain
    if domain_accuracies:
        result['avg_domain'] = sum(domain_accuracies) / len(domain_accuracies)
    else:
        result['avg_domain'] = 0.0

    # avg_all: 所有指标的平均值（除了 avg_type 和 avg_domain）
    all_values = []
    for key in type_difficulty_keys + ['cn', 'en'] + domain_keys:
        all_values.append(result[key])

    if all_values:
        result['avg_all'] = sum(all_values) / len(all_values)
    else:
        result['avg_all'] = 0.0

    return result


def main():
    parser = argparse.ArgumentParser(description='统计 JSONL 文件中的正确率')
    parser.add_argument('input_file', type=str, help='输入的 JSONL 文件路径')
    parser.add_argument('output_file', type=str, help='输出的 JSON 文件路径')

    args = parser.parse_args()

    # 读取数据
    print(f"读取文件: {args.input_file}")
    data = load_jsonl(args.input_file)
    print(f"共读取 {len(data)} 条记录")

    # 计算正确率
    print("计算正确率...")
    result = calculate_accuracy(data)

    # 保存结果
    print(f"保存结果到: {args.output_file}")
    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    print("完成！")
    print("\n结果:")
    print(json.dumps(result, indent=4, ensure_ascii=False))


if __name__ == '__main__':
    main()
