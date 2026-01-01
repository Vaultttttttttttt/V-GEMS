import json
import os
from openai import OpenAI

# 读取配置（使用与app.py相同的配置）
if 'DASHSCOPE_API_KEY' in os.environ:
    llm_cfg = {
        'model': 'qwen-plus',
        'api_key': os.getenv('DASHSCOPE_API_KEY'),
        'model_server': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    }
elif 'OPENAI_API_KEY' in os.environ and 'OPENAI_MODEL_SERVER' in os.environ:
    llm_cfg = {
        'model': 'qwen3-coder-plus',
        'api_key': 'sk-e543e83d6c394411b3343369aa9027a2',
        'model_server': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    }
elif 'OPENAI_API_KEY' in os.environ:
    llm_cfg = {
        'model': 'gpt-4',
        'api_key': os.getenv('OPENAI_API_KEY'),
        'model_server': 'https://api.openai.com/v1'
    }
else:
    # 使用默认配置
    llm_cfg = {
        'model': 'gpt-4o',
        'api_key': 'sk-j4sDnXhD62ejl2fvclSYhkLNiwa9zv6w1P0QFw6B4RAsiZJZ',
        'model_server': 'http://49.51.37.239:3008/v1'
    }

    # llm_cfg = {
    #     'model': 'qwen3-plus',
    #     'api_key': 'sk-e543e83d6c394411b3343369aa9027a2',
    #     'model_server': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    # }

# 初始化OpenAI客户端
client = OpenAI(
    api_key=llm_cfg['api_key'],
    base_url=llm_cfg['model_server']
)

def classify_answer(question, answer, pred, reasoning, score):
    """
    使用AI分类答案类型

    Args:
        question: 问题
        answer: 标准答案
        pred: 预测答案
        reasoning: 之前的评判理由
        score: 评分（1表示正确，0表示错误）

    Returns:
        str: 答案分类 (Correct, Refusal, Hallucination, Partially Correct)
    """

    # 如果score为1，直接标记为Correct
    if score == 1:
        return "Correct"

    # 如果pred为空或者仅包含空白字符
    if not pred or pred.strip() == "":
        return "Refusal"

#     prompt = f"""You are an expert evaluator, and now the answer is wrong, but I need to know the type of error. Please classify the predicted answer into one of the following categories:

# **Categories:**
# 1. **Hallucination**: The prediction is completely wrong or contains fabricated information.
# 2. **Partially Correct**: The prediction contains some correct information but also has errors or omissions.

# **Question**: {question}

# **Reference Answer**: {answer}

# **Predicted Answer**: {pred}

# **Instructions**:
# - Analyze the predicted answer carefully against the reference answer.
# - Choose the most appropriate category.
# - Return ONLY the category name without any explanation.

# **Output**: (Choose one: Hallucination or Partially Correct. Don't output anything else.)
# """

    prompt = f"""### Role
    You are a rigorous QA evaluator. You have been given a Question, a Reference Answer, and a Model Prediction that is known to be imperfect (Score < 1).

    ### Task
    Classify the error in the "Predicted Answer" into one of the following distinct categories.

    ### Error Taxonomy
    [Hallucination]
    - **Critical Fail**: The prediction includes specific facts (dates, names, numbers, methods) that are objectively false or contradict the reference.
    - The model "made things up".

    [Totally Incorrect]
    - The prediction is structurally complete but the logic/answer is wrong.
    - It is not a hallucination, but simply a wrong answer (e.g., answering "Blue" when the answer is "Red").

    [Missing]
    - The prediction is **Partially Correct**. It does not contain false info, but it failed to mention a critical part of the reference answer (e.g., missed 2 out of 3 list items).

    [Imprecise]
    - The prediction is **Partially Correct**. It touches on the right concepts but is too vague, general, or poorly phrased to be considered a full match.

    ### Data
    [Question]:
    {question}

    [Reference Answer]:
    {answer}

    [Predicted Answer]:
    {pred}

    ### Instruction
    1. Read the Reference Answer to establish the ground truth.
    2. Check if the Prediction contradicts the truth (Hallucination/Totally Incorrect) or just lacks detail (Missing/Imprecise).
    3. Output **ONLY** the category name from the list above. No other text.

    ### Output(Choose one: Hallucination or Totally Incorrect or Missing or Imprecise. Don't output anything else.)
    """

    try:
        response = client.chat.completions.create(
            model=llm_cfg['model'],
            messages=[
                {'role': 'system', 'content': 'You are an expert answer evaluator. Return only the category name.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.1,
            max_tokens=50
        )

        classification = response.choices[0].message.content.strip()
        print(f"AI Classification Response: {classification}")
        # 验证返回的分类是否有效
        valid_categories = ['Hallucination', 'Totally Incorrect', 'Missing', 'Imprecise']

        # 尝试匹配分类
        for category in valid_categories:
            if category.lower() in classification.lower():
                return category

        # 如果没有匹配到，返回默认值并打印警告
        print(f"Warning: Unexpected classification '{classification}', defaulting to 'Hallucination'")
        return "Hallucination"

    except Exception as e:
        print(f"Error during classification: {e}")
        return "Hallucination"  # 默认为错误

def process_jsonl_file(input_path, output_path, max_lines=None):
    """
    处理JSONL文件，为每条数据添加distribution字段

    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        max_lines: 最多处理的行数（None表示处理全部）
    """

    print(f"正在读取文件: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 如果指定了max_lines，只处理前N行
    if max_lines:
        lines = lines[:max_lines]
        print(f"[测试模式] 只处理前 {max_lines} 条数据")

    total = len(lines)
    print(f"共有 {total} 条数据需要处理\n")

    processed_data = []

    # 统计计数器
    stats = {
        'Correct': 0,
        'Refusal': 0,
        'Hallucination': 0,
        'Totally Incorrect': 0,
        'Missing': 0,
        'Imprecise': 0
    }

    for i, line in enumerate(lines, 1):
        try:
            data = json.loads(line.strip())

            question = data.get('question', '')
            answer = data.get('answer', '')
            pred = data.get('pred', '')
            reasoning = data.get('reasoning', '')
            score = data.get('score', 0)  # 获取score字段

            # 分类答案（传入score参数）
            distribution = classify_answer(question, answer, pred, reasoning, score)

            # 添加distribution字段
            data['distribution'] = distribution

            # 更新统计
            stats[distribution] += 1

            processed_data.append(data)

            # 打印进度（标注是否使用了快速路径）
            percentage = (i / total) * 100
            fast_label = "[FAST]" if score == 1 or (not pred or pred.strip() == "") else "[AI]  "
            print(f"{fast_label} [{i}/{total}] ({percentage:.1f}%) - Index: {data.get('index', 'N/A')} - Classification: {distribution}")

        except json.JSONDecodeError as e:
            print(f"Error parsing line {i}: {e}")
            continue
        except Exception as e:
            print(f"Error processing line {i}: {e}")
            continue

    # 保存结果
    print(f"\n正在保存结果到: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        for data in processed_data:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')

    print(f"✅ 处理完成！共处理 {len(processed_data)} 条数据\n")

    # 打印统计信息
    print("="*60)
    print("分类统计")
    print("="*60)
    for category, count in stats.items():
        percentage = (count / total) * 100 if total > 0 else 0
        print(f"{category:20s}: {count:5d} ({percentage:5.1f}%)")
    print("="*60)

    # 保存统计结果到JSON文件
    stats_with_percentage = {}
    for category, count in stats.items():
        percentage = (count / total) * 100 if total > 0 else 0
        stats_with_percentage[category] = {
            'count': count,
            'percentage': round(percentage, 2)
        }

    stats_with_percentage['total'] = total

    # 统计文件路径（与输出文件同目录）
    stats_output = output_path.replace('.jsonl', '_stats.json')
    with open(stats_output, 'w', encoding='utf-8') as f:
        json.dump(stats_with_percentage, f, indent=4, ensure_ascii=False)

    print(f"\n✅ 统计结果已保存至: {stats_output}")

if __name__ == "__main__":
    input_file = "/Users/wxj/Library/Mobile Documents/com~apple~CloudDocs/VGems/src/evaluate_results/only_counter.jsonl"
    output_file = "/Users/wxj/Library/Mobile Documents/com~apple~CloudDocs/VGems/src/evaluate_results/error_accessment/only_counter_classified.jsonl"

    # 测试模式：先处理10条数据
    # 如果需要处理全部，将max_lines参数设为None
    print("注意：这将调用AI API处理680条数据，可能需要较长时间和费用。")
    print("建议先测试少量数据，确认无误后再处理全部。\n")

    import sys
    # if len(sys.argv) > 1 and sys.argv[1] == "--full":
    print("运行完整模式...")
    process_jsonl_file(input_file, output_file, max_lines=None)
    # else:
    #     print("运行测试模式（前10条数据）...")
    #     print("如需处理全部数据，请运行: python classify_answers.py --full\n")
    #     test_output = output_file.replace('.jsonl', '_test.jsonl')
    #     process_jsonl_file(input_file, test_output, max_lines=10)
