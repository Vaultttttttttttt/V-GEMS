"""
VGemsQA Dataset Generation Script

This script generates QA pairs for the VGems dataset by:
1. Loading official websites from official_websites.json (with domain info)
2. Generating single-source QA pairs by navigating to random depths
3. Generating multi-source QA pairs by combining content from multiple pages

Data distribution:
- Single-source: 80 easy (depth 2-4), 140 medium (depth 4-6), 120 hard (depth 6-8)
- Multi-source: 80 easy (depth 2-4), 140 medium (depth 4-6), 120 hard (depth 6-8)
Total: 680 QA pairs

Output format:
{
  "question": "问题内容",
  "answer": "答案内容",
  "root_url": "官方网站URL",
  "info": {
    "source_website": ["url1"] or ["url1", "url2"],
    "golden_path": ["root->button1->button2"] or ["root->button1", "root->button2->button3"],
    "type": "single-source" or "multi-source",
    "difficulty_level": "easy" or "medium" or "hard",
    "domain": "game" or "conference" or "education" or "organization",
    "lang": "cn" or "en"
  }
}
"""

import asyncio
import json
import random
import re
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import time
from openai import OpenAI
from tqdm import tqdm

# Configuration
LLM_CONFIG = {
    'model': 'qwen3-coder-plus',
    'api_key': 'sk-e543e83d6c394411b3343369aa9027a2',
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
}

# Data distribution requirements
DATA_DISTRIBUTION = {
    "single_source": {
        "easy": 80,      # depth 2-4
        "medium": 140,   # depth 4-6
        "hard": 120      # depth 6-8
    },
    "multi_source": {
        "easy": 80,      # depth 2-4
        "medium": 140,   # depth 4-6
        "hard": 120      # depth 6-8
    }
}

# Files
OUTPUT_DIR = Path("generated_dataset")
WEBSITES_FILE = OUTPUT_DIR / "official_websites.json"
QA_FILE = OUTPUT_DIR / "v_gems_qa.jsonl"
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint.json"

# Initialize OpenAI client for LLM calls
client = OpenAI(
    api_key=LLM_CONFIG['api_key'],
    base_url=LLM_CONFIG['base_url']
)


class QAGenerator:
    def __init__(self):
        self.websites = {}  # {url: {"domain": str, "lang": str}}
        self.checkpoint = self.load_checkpoint()
        OUTPUT_DIR.mkdir(exist_ok=True)

    def load_checkpoint(self) -> Dict:
        """Load checkpoint to resume from previous run."""
        if CHECKPOINT_FILE.exists():
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "single_source_generated": {"easy": 0, "medium": 0, "hard": 0},
            "multi_source_generated": {"easy": 0, "medium": 0, "hard": 0}
        }

    def save_checkpoint(self):
        """Save checkpoint."""
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.checkpoint, f, ensure_ascii=False, indent=2)

    def load_websites(self):
        """Load official websites from JSON file (format: {url: {"domain": str, "lang": str}})."""
        if not WEBSITES_FILE.exists():
            raise FileNotFoundError(
                f"❌ {WEBSITES_FILE} not found!\n"
                f"Please run collect_official_websites.py first to collect websites."
            )

        with open(WEBSITES_FILE, 'r', encoding='utf-8') as f:
            self.websites = json.load(f)

        print(f"✓ Loaded {len(self.websites)} official websites from {WEBSITES_FILE}")

        if len(self.websites) == 0:
            raise ValueError("No websites found in official_websites.json!")

        # Show domain and language distribution
        domain_counts = {}
        lang_counts = {}
        for url, info in self.websites.items():
            domain = info["domain"]
            lang = info["lang"]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        print(f"\nDomain distribution:")
        for domain, count in sorted(domain_counts.items()):
            percentage = count / len(self.websites) * 100
            print(f"  {domain.capitalize()}: {count} ({percentage:.1f}%)")

        print(f"\nLanguage distribution:")
        for lang, count in sorted(lang_counts.items()):
            percentage = count / len(self.websites) * 100
            print(f"  {lang.upper()}: {count} ({percentage:.1f}%)")
        print()

    def select_random_website(self) -> Tuple[str, str, str]:
        """
        Select a random website with proper distribution weighting.

        Target distributions:
        - Language: cn 60.5%, en 39.5%
        - Domain: education 46.3%, conference 24%, game 21.9%, organization 7.9%

        Returns:
            Tuple of (url, domain, lang)
        """
        # Define target weights
        lang_weights = {"cn": 0.605, "en": 0.395}
        domain_weights = {
            "education": 0.463,
            "conference": 0.240,
            "game": 0.219,
            "organization": 0.079
        }

        # Group websites by (domain, lang)
        grouped = {}
        for url, info in self.websites.items():
            key = (info["domain"], info["lang"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(url)

        # Calculate combined weights for each group
        group_weights = []
        group_urls = []

        for (domain, lang), urls in grouped.items():
            combined_weight = domain_weights.get(domain, 0) * lang_weights.get(lang, 0)
            group_weights.append(combined_weight)
            group_urls.append((urls, domain, lang))

        # Normalize weights
        total_weight = sum(group_weights)
        if total_weight > 0:
            group_weights = [w / total_weight for w in group_weights]

        # Select a group based on weights
        selected_idx = random.choices(range(len(group_urls)), weights=group_weights, k=1)[0]
        urls, domain, lang = group_urls[selected_idx]

        # Select a random URL from the group
        url = random.choice(urls)

        return url, domain, lang

    async def navigate_to_depth(self, root_url: str, target_depth: int) -> Optional[Tuple[str, str, str]]:
        """
        Navigate from root URL to a page at target_depth by randomly clicking links.

        Args:
            root_url: Starting website URL
            target_depth: Number of clicks to perform (1-8)

        Returns:
            Tuple of (final_url, page_content, golden_path) or None if navigation fails
        """
        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )

        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_until="domcontentloaded",
            page_timeout=30000
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            current_url = root_url
            path_steps = ["root"]  # Track the golden path

            for depth in range(target_depth):
                try:
                    # Fetch current page
                    result = await crawler.arun(
                        url=current_url,
                        config=run_config
                    )

                    if not result.success:
                        return None

                    # If this is the target depth, return the content
                    if depth == target_depth - 1:
                        golden_path = "->".join(path_steps)
                        return (current_url, result.markdown, golden_path)

                    # Extract all internal links with their text
                    soup = BeautifulSoup(result.html, 'html.parser')
                    links = []  # [(url, button_text), ...]

                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        full_url = urljoin(current_url, href)

                        # Only follow internal links (same domain)
                        if urlparse(full_url).netloc == urlparse(root_url).netloc:
                            # Avoid common non-content links
                            if not any(skip in full_url.lower() for skip in
                                      ['login', 'logout', 'register', 'download',
                                       '.pdf', '.zip', '.jpg', '.png', '#']):
                                # Get link text (button text)
                                button_text = link.get_text(strip=True)
                                if not button_text:
                                    button_text = "Read more"  # Default text for links without text
                                links.append((full_url, button_text))

                    if not links:
                        # No more links to follow, return current page
                        golden_path = "->".join(path_steps)
                        return (current_url, result.markdown, golden_path)

                    # Randomly select next link
                    next_url, button_text = random.choice(links)
                    path_steps.append(button_text[:50])  # Limit button text length
                    current_url = next_url

                    # Small delay
                    await asyncio.sleep(0.5)

                except Exception as e:
                    print(f"    ✗ Navigation error at depth {depth}: {e}")
                    return None

            return None

    def generate_qa_with_llm(self, content: str, difficulty: str, domain: str, language: str, is_multi_source: bool = False) -> Optional[Dict]:
        """
        Use LLM to generate a QA pair from page content.

        Args:
            content: Page content (markdown)
            difficulty: "easy", "medium", or "hard"
            domain: "education", "conference", "game", or "organization"
            language: "cn" or "en" - determines the language of generated QA
            is_multi_source: Whether this is for multi-source QA

        Returns:
            Dict with "question" and "answer" keys, or None if generation fails
        """
        # Choose prompt based on language
        if language == "cn":
            example_format = '{{"question": "问题内容", "answer": "答案内容"}}'

            # Domain-specific instructions in Chinese
            domain_instructions = {
                "education": "问题应该关注学校的专业设置、师资力量、招生信息、学术成就、校园设施等教育相关内容。",
                "conference": "问题应该关注会议的主题、时间地点、演讲嘉宾、投稿要求、议程安排等会议相关内容。",
                "game": "问题应该关注游戏玩法、角色设定、更新内容、活动信息、系统要求等游戏相关内容。",
                "organization": "问题应该关注组织的宗旨、成员构成、活动项目、服务内容、申请加入方式等组织相关内容。"
            }
        else:  # en
            example_format = '{{"question": "Question content", "answer": "Answer content"}}'

            # Domain-specific instructions in English
            domain_instructions = {
                "education": "Questions should focus on academic programs, faculty, admissions, research achievements, campus facilities, and other education-related topics.",
                "conference": "Questions should focus on conference themes, dates and locations, keynote speakers, submission requirements, program schedules, and other conference-related topics.",
                "game": "Questions should focus on gameplay mechanics, character design, updates, events, system requirements, and other game-related topics.",
                "organization": "Questions should focus on organizational mission, membership, activities, services, application procedures, and other organization-related topics."
            }

        domain_instruction = domain_instructions.get(domain, "")

        if is_multi_source:
            if language == "cn":
                quality_requirements = """质量要求（非常重要）：
1. 问题必须有明确的、可验证的客观答案（如：具体的时间、地点、人名、数字、特定事实等）
2. 避免生成主观性问题（如："怎么样"、"如何评价"、"有什么看法"等）
3. 答案必须直接来自页面内容，不要编造或推测
4. 问题类型示例：
   ✓ 好的问题: "学校成立于哪一年？" "会议的投稿截止日期是什么时候？" "该游戏支持多少名玩家？"
   ✗ 避免的问题: "学校怎么样？" "会议有什么特点？" "游戏好不好玩？"
5. 答案要简洁准确，包含具体信息，不要模糊或笼统的描述"""

                prompt = f"""你是一个专业的QA数据集生成助手。我会给你两个网页的内容，请基于这两个页面的信息生成一个问答对。

网站领域: {domain}
{domain_instruction}

{quality_requirements}

任务要求：
1. 问题需要结合两个页面的信息才能回答
2. 问题应与 {domain} 领域相关
3. 难度级别: {difficulty}
   - easy: 信息直接明显，容易找到
   - medium: 需要理解和整合信息
   - hard: 需要深入分析和推理
4. 用中文生成问题和答案

请直接返回JSON格式：
{example_format}

网页内容：
{content[:8000]}
"""
            else:
                quality_requirements = """Quality Requirements (VERY IMPORTANT):
1. Questions MUST have clear, verifiable, objective answers (e.g., specific dates, locations, names, numbers, concrete facts)
2. Avoid subjective questions (e.g., "How good is...", "What do you think about...", "How would you rate...")
3. Answers must come directly from the page content, do not make up or speculate
4. Question type examples:
   ✓ Good questions: "When was the university founded?" "What is the paper submission deadline?" "How many players does the game support?"
   ✗ Avoid: "How is the university?" "What are the conference features?" "Is the game fun?"
5. Answers should be concise and accurate with specific information, not vague or general descriptions"""

                prompt = f"""You are a professional QA dataset generation assistant. I will give you content from two web pages, please generate a QA pair based on the information from both pages.

Website domain: {domain}
{domain_instruction}

{quality_requirements}

Requirements:
1. The question should require information from both pages to answer
2. The question should be related to the {domain} domain
3. Difficulty level: {difficulty}
   - easy: Information is direct and obvious, easy to find
   - medium: Requires understanding and integration of information
   - hard: Requires in-depth analysis and reasoning
4. Generate question and answer in English

Please return JSON format directly:
{example_format}

Web page content:
{content[:8000]}
"""
        else:
            if language == "cn":
                quality_requirements = """质量要求（非常重要）：
1. 问题必须有明确的、可验证的客观答案（如：具体的时间、地点、人名、数字、特定事实等）
2. 避免生成主观性问题（如："怎么样"、"如何评价"、"有什么看法"等）
3. 答案必须直接来自页面内容，不要编造或推测
4. 问题类型示例：
   ✓ 好的问题: "学校成立于哪一年？" "会议的投稿截止日期是什么时候？" "该游戏支持多少名玩家？"
   ✗ 避免的问题: "学校怎么样？" "会议有什么特点？" "游戏好不好玩？"
5. 答案要简洁准确，包含具体信息，不要模糊或笼统的描述"""

                prompt = f"""你是一个专业的QA数据集生成助手。我会给你一个网页的内容，请基于该页面的信息生成一个问答对。

网站领域: {domain}
{domain_instruction}

{quality_requirements}

任务要求：
1. 问题应该能从该页面内容中找到答案
2. 问题应与 {domain} 领域相关
3. 难度级别: {difficulty}
   - easy: 信息直接明显，容易找到
   - medium: 需要理解和整合信息
   - hard: 需要深入分析和推理
4. 用中文生成问题和答案

请直接返回JSON格式：
{example_format}

网页内容：
{content[:8000]}
"""
            else:
                quality_requirements = """Quality Requirements (VERY IMPORTANT):
1. Questions MUST have clear, verifiable, objective answers (e.g., specific dates, locations, names, numbers, concrete facts)
2. Avoid subjective questions (e.g., "How good is...", "What do you think about...", "How would you rate...")
3. Answers must come directly from the page content, do not make up or speculate
4. Question type examples:
   ✓ Good questions: "When was the university founded?" "What is the paper submission deadline?" "How many players does the game support?"
   ✗ Avoid: "How is the university?" "What are the conference features?" "Is the game fun?"
5. Answers should be concise and accurate with specific information, not vague or general descriptions"""

                prompt = f"""You are a professional QA dataset generation assistant. I will give you a web page's content, please generate a QA pair based on the information from this page.

Website domain: {domain}
{domain_instruction}

{quality_requirements}

Requirements:
1. The question should be answerable from this page's content
2. The question should be related to the {domain} domain
3. Difficulty level: {difficulty}
   - easy: Information is direct and obvious, easy to find
   - medium: Requires understanding and integration of information
   - hard: Requires in-depth analysis and reasoning
4. Generate question and answer in English

Please return JSON format directly:
{example_format}

Web page content:
{content[:8000]}
"""

        try:
            response = client.chat.completions.create(
                model=LLM_CONFIG['model'],
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                qa_pair = json.loads(json_match.group())
                return qa_pair
            else:
                print(f"    ✗ Failed to extract JSON from LLM response")
                return None

        except Exception as e:
            print(f"    ✗ LLM generation error: {e}")
            return None

    async def generate_single_source_qa(self):
        """
        Generate single-source QA pairs.
        """
        print(f"\n{'='*80}")
        print("Generating Single-Source QA Pairs")
        print(f"{'='*80}\n")

        for difficulty, target_count in DATA_DISTRIBUTION["single_source"].items():
            current_count = self.checkpoint["single_source_generated"][difficulty]

            if current_count >= target_count:
                print(f"✓ {difficulty.capitalize()}: Already completed ({current_count}/{target_count})")
                continue

            print(f"\nGenerating {difficulty} single-source QA pairs ({current_count}/{target_count})...")

            # Determine depth range for this difficulty
            if difficulty == "easy":
                depth_range = (2, 4)
            elif difficulty == "medium":
                depth_range = (4, 6)
            else:  # hard
                depth_range = (6, 8)

            pbar = tqdm(total=target_count - current_count, desc=f"Single-source {difficulty}")

            while current_count < target_count:
                # Select a website with proper distribution weighting
                website, domain, language = self.select_random_website()

                # Randomly select depth within range
                depth = random.randint(depth_range[0], depth_range[1])

                try:
                    # Navigate to target depth
                    result = await self.navigate_to_depth(website, depth)

                    if result is None:
                        continue

                    url, content, golden_path = result

                    if len(content.strip()) < 100:
                        # Content too short
                        continue

                    # Generate QA pair
                    qa_pair = self.generate_qa_with_llm(content, difficulty, domain, language, is_multi_source=False)

                    if qa_pair is None:
                        continue

                    # Save to file with new format
                    qa_data = {
                        "question": qa_pair["question"],
                        "answer": qa_pair["answer"],
                        "root_url": website,
                        "info": {
                            "source_website": [url],
                            "golden_path": [golden_path],
                            "type": "single-source",
                            "difficulty_level": difficulty,
                            "domain": domain,
                            "lang": language
                        }
                    }

                    with open(QA_FILE, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(qa_data, ensure_ascii=False) + '\n')

                    current_count += 1
                    self.checkpoint["single_source_generated"][difficulty] = current_count
                    self.save_checkpoint()

                    pbar.update(1)

                except Exception as e:
                    print(f"    ✗ Error: {e}")
                    continue

            pbar.close()
            print(f"✓ Completed {difficulty} single-source QA pairs ({current_count}/{target_count})")

    async def generate_multi_source_qa(self):
        """
        Generate multi-source QA pairs.
        """
        print(f"\n{'='*80}")
        print("Generating Multi-Source QA Pairs")
        print(f"{'='*80}\n")

        for difficulty, target_count in DATA_DISTRIBUTION["multi_source"].items():
            current_count = self.checkpoint["multi_source_generated"][difficulty]

            if current_count >= target_count:
                print(f"✓ {difficulty.capitalize()}: Already completed ({current_count}/{target_count})")
                continue

            print(f"\nGenerating {difficulty} multi-source QA pairs ({current_count}/{target_count})...")

            # Determine depth range for this difficulty
            if difficulty == "easy":
                depth_range = (2, 4)
            elif difficulty == "medium":
                depth_range = (4, 6)
            else:  # hard
                depth_range = (6, 8)

            pbar = tqdm(total=target_count - current_count, desc=f"Multi-source {difficulty}")

            while current_count < target_count:
                # Select a website with proper distribution weighting
                website, domain, language = self.select_random_website()

                # Randomly select two depths within range
                depth1 = random.randint(depth_range[0], depth_range[1])
                depth2 = random.randint(depth_range[0], depth_range[1])

                try:
                    # Navigate to first target depth
                    result1 = await self.navigate_to_depth(website, depth1)
                    if result1 is None:
                        continue

                    url1, content1, golden_path1 = result1

                    # Navigate to second target depth
                    result2 = await self.navigate_to_depth(website, depth2)
                    if result2 is None:
                        continue

                    url2, content2, golden_path2 = result2

                    # Make sure they're different pages
                    if url1 == url2:
                        continue

                    if len(content1.strip()) < 100 or len(content2.strip()) < 100:
                        # Content too short
                        continue

                    # Combine content for QA generation
                    if language == "cn":
                        combined_content = f"=== 第一个页面 ===\n{content1[:4000]}\n\n=== 第二个页面 ===\n{content2[:4000]}"
                    else:
                        combined_content = f"=== First Page ===\n{content1[:4000]}\n\n=== Second Page ===\n{content2[:4000]}"

                    # Generate QA pair
                    qa_pair = self.generate_qa_with_llm(combined_content, difficulty, domain, language, is_multi_source=True)

                    if qa_pair is None:
                        continue

                    # Save to file with new format
                    qa_data = {
                        "question": qa_pair["question"],
                        "answer": qa_pair["answer"],
                        "root_url": website,
                        "info": {
                            "source_website": [url1, url2],
                            "golden_path": [golden_path1, golden_path2],
                            "type": "multi-source",
                            "difficulty_level": difficulty,
                            "domain": domain,
                            "lang": language
                        }
                    }

                    with open(QA_FILE, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(qa_data, ensure_ascii=False) + '\n')

                    current_count += 1
                    self.checkpoint["multi_source_generated"][difficulty] = current_count
                    self.save_checkpoint()

                    pbar.update(1)

                except Exception as e:
                    print(f"    ✗ Error: {e}")
                    continue

            pbar.close()
            print(f"✓ Completed {difficulty} multi-source QA pairs ({current_count}/{target_count})")

    async def run(self):
        """Main execution flow."""
        print("\n" + "="*80)
        print("VGemsQA Dataset Generation")
        print("="*80)

        # Load websites
        self.load_websites()

        # Generate single-source QA pairs
        await self.generate_single_source_qa()

        # Generate multi-source QA pairs
        await self.generate_multi_source_qa()

        # Summary
        print("\n" + "="*80)
        print("GENERATION COMPLETE")
        print("="*80)
        print(f"\nSingle-source QA pairs:")
        for diff, count in self.checkpoint["single_source_generated"].items():
            print(f"  {diff.capitalize()}: {count}/{DATA_DISTRIBUTION['single_source'][diff]}")
        print(f"\nMulti-source QA pairs:")
        for diff, count in self.checkpoint["multi_source_generated"].items():
            print(f"  {diff.capitalize()}: {count}/{DATA_DISTRIBUTION['multi_source'][diff]}")

        total_generated = (
            sum(self.checkpoint["single_source_generated"].values()) +
            sum(self.checkpoint["multi_source_generated"].values())
        )
        print(f"\nTotal QA pairs: {total_generated}/680")
        print(f"\nResults saved to: {QA_FILE}")
        print("="*80 + "\n")


async def main():
    generator = QAGenerator()
    await generator.run()


if __name__ == "__main__":
    asyncio.run(main())
