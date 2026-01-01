"""
VGems Evaluation Script

This script evaluates VGems agent on the generated dataset by:
1. Loading questions from v_gems_qa.jsonl
2. Running VGems agent on each question
3. Saving the agent's answers to a results file
4. Comparing with ground truth answers (optional)

Usage:
    python evaluate_v_gems.py --limit 10  # Test first 10 questions
    python evaluate_v_gems.py             # Test all questions
"""

import asyncio
import json
import os
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional
from tqdm import tqdm

# Import VGems components
from agent import VGems
from utils import get_info

# Import headless tools (this registers all tools without Streamlit dependencies)
import tools_for_eval  # noqa: F401

# Configuration
DATASET_FILE = Path("generated_dataset/v_gems_qa.jsonl")
RESULTS_DIR = Path("evaluation_results")
RESULTS_FILE = RESULTS_DIR / "v_gems_answers.jsonl"
CHECKPOINT_FILE = RESULTS_DIR / "eval_checkpoint.json"

# VGems configuration
LLM_CONFIG = {
    'model': 'Qwen3-235B-A22B-Instruct-2507',
    'api_key': 'xwmyrxGRGl9xu6DgyPBEcvTvwGkuEQAopB/ARfWbi8I=',
    'model_server': 'https://qwen235b.openapi-qb.sii.edu.cn/v1',
    'generate_cfg': {
        'top_p': 0.8,
        'max_input_tokens': 120000,
        'max_retries': 20
    },
}

MAX_ROUNDS = 100  # Maximum steps per query


class VGemsEvaluator:
    def __init__(self):
        self.dataset = []
        self.checkpoint = self.load_checkpoint()
        RESULTS_DIR.mkdir(exist_ok=True)

    def load_checkpoint(self) -> Dict:
        """Load checkpoint to resume evaluation."""
        if CHECKPOINT_FILE.exists():
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"completed_indices": []}

    def save_checkpoint(self):
        """Save checkpoint."""
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.checkpoint, f, ensure_ascii=False, indent=2)

    def load_dataset(self, limit: Optional[int] = None):
        """Load questions from v_gems_qa.jsonl."""
        if not DATASET_FILE.exists():
            raise FileNotFoundError(
                f"Dataset file not found: {DATASET_FILE}\n"
                f"Please run generate_qa_from_websites.py first to generate the dataset."
            )

        with open(DATASET_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                qa_item = json.loads(line)
                self.dataset.append(qa_item)

        if limit:
            self.dataset = self.dataset[:limit]

        print(f"✓ Loaded {len(self.dataset)} questions from {DATASET_FILE}")

        # Show statistics
        stats = {
            "single-source": 0,
            "multi-source": 0,
            "easy": 0,
            "medium": 0,
            "hard": 0
        }
        for item in self.dataset:
            info = item.get("info", {})
            stats[info.get("type", "unknown")] += 1
            stats[info.get("difficulty_level", "unknown")] += 1

        print(f"\nDataset statistics:")
        print(f"  Single-source: {stats['single-source']}")
        print(f"  Multi-source: {stats['multi-source']}")
        print(f"  Easy: {stats['easy']}")
        print(f"  Medium: {stats['medium']}")
        print(f"  Hard: {stats['hard']}")
        print()

    def clean_session(self):
        """Clean up session files between queries."""
        # Clear BUTTON_URL_ADIC.json
        with open("BUTTON_URL_ADIC.json", "w") as f:
            json.dump({}, f)

        # Clear nav_chain.json
        with open("nav_chain.json", "w") as f:
            json.dump([], f)

        # Reset count
        with open("count.txt", "w") as f:
            f.write("0")

        # Reset navigation step counter
        with open("navigation_steps.txt", "w") as f:
            f.write("0")

    def count_navigation_steps(self) -> int:
        """
        Count the number of navigation steps (button clicks / page visits).

        Reads navigation_steps.txt which is incremented by visit_page/visit_url tools.

        Returns:
            Number of button clicks/page navigations
        """
        try:
            with open("navigation_steps.txt", "r") as f:
                steps = int(f.read().strip())
            return steps
        except Exception as e:
            print(f"[WARNING] Failed to count navigation steps: {e}")
            return 0

    async def run_v_gems(self, question: str, root_url: str) -> tuple[Optional[str], int, bool, Optional[str]]:
        """
        Run VGems agent on a single question.

        Args:
            question: User question
            root_url: Starting website URL

        Returns:
            Tuple of (answer, steps, success, error_message)
        """
        try:
            # Clean session files
            self.clean_session()

            # Set ROOT_URL
            with open("ROOT_URL.txt", "w") as f:
                f.write(root_url)

            # Set query
            with open("query.txt", "w") as f:
                f.write(question)

            # Initialize agent
            tools = ["visit_page", "visit_url", "url_stack", "count_usefulness",
                     "query_requirement"]

            llm_cfg = LLM_CONFIG.copy()
            llm_cfg["query"] = question
            llm_cfg["action_count"] = MAX_ROUNDS

            bot = VGems(llm=llm_cfg, function_list=tools)
            bot._call_tool('query_requirement', action_input=json.dumps({"op": "set", "query": question}, ensure_ascii=False))

            # Get initial page
            html, markdown, screenshot = await get_info(root_url)

            # Check if initial page load failed
            if not html and "Error:" in markdown:
                print(f"    ✗ Failed to load initial page: {markdown}")
                return None, 0, False, f"Initial page load failed: {markdown}"

            # Save initial screenshot (CRITICAL: matches Streamlit behavior)
            if screenshot:
                import base64
                print("Saving initial screenshot...")
                image_folder = "images/"
                if not os.path.exists(image_folder):
                    os.makedirs(image_folder)

                # Save screenshot as 0.png (initial page)
                image_path = os.path.join(image_folder, "0.png")
                with open(image_path, "wb") as f:
                    f.write(base64.b64decode(screenshot))

                # Save screenshot info for VLM access
                from tools_for_eval import save_screenshot_info
                save_screenshot_info(image_path, root_url)
                print(f"  ✓ Screenshot saved to {image_path}")

            # Extract buttons from initial page
            from tools_for_eval import extract_links_with_text
            buttons = extract_links_with_text(html, root_url)

            # Prepare initial message
            start_prompt = f"""query:
{question}

official website:
{root_url}

IMPORTANT INITIAL STEPS (YOU MUST FOLLOW):
1. First, initialize the url_stack:
   Action: url_stack
   Action Input: {{"op": "init", "url": "{root_url}"}}

2. Then proceed with your exploration based on the observation.

Observation: website information:

{markdown[:2000]}

clickable button:

{buttons}

Each button is wrapped in a <button> tag
"""

            messages = [{'role': 'user', 'content': start_prompt}]

            # Run agent
            iterations = 0
            answer = None
            for response in bot.run(messages=messages, lang="zh"):
                iterations += 1
                if len(response) > 0 and response[-1].get("role") == "assistant":
                    content = response[-1].get("content", "")
                    # Check if Final Answer is reached
                    if "Final Answer" in content or "最终答案" in content:
                        # Extract the answer
                        if "Final Answer:" in content:
                            answer = content.split("Final Answer:", 1)[1].strip()
                        elif "最终答案：" in content:
                            answer = content.split("最终答案：", 1)[1].strip()
                        else:
                            answer = content
                        break

                if iterations >= MAX_ROUNDS:
                    break

            # Calculate actual navigation steps (button clicks)
            # Steps = number of pages visited (excluding the initial root page)
            steps = self.count_navigation_steps()

            return answer, steps, True, None

        except Exception as e:
            error_msg = str(e)
            print(f"    ✗ Error: {error_msg}")
            return None, 0, False, error_msg

    async def evaluate(self, limit: Optional[int] = None):
        """Main evaluation function."""
        print("\n" + "="*80)
        print("VGems Evaluation on Generated Dataset")
        print("="*80 + "\n")

        # Load dataset
        self.load_dataset(limit)

        # Filter out already completed questions
        completed_indices = set(self.checkpoint["completed_indices"])
        pending_items = [
            (idx, item) for idx, item in enumerate(self.dataset)
            if idx not in completed_indices
        ]

        if not pending_items:
            print("✓ All questions already evaluated!")
            return

        print(f"Already completed: {len(completed_indices)}")
        print(f"Pending: {len(pending_items)}")
        print(f"\nStarting evaluation...\n")

        # Run evaluation
        success_count = 0
        fail_count = 0

        for idx, item in tqdm(pending_items, desc="Evaluating"):
            question = item["question"]
            ground_truth = item["answer"]
            root_url = item["root_url"]
            info = item.get("info", {})

            print(f"\n{'='*80}")
            print(f"[{idx + 1}/{len(self.dataset)}] Question: {question[:80]}...")
            print(f"Root URL: {root_url}")
            print(f"Type: {info.get('type')}, Difficulty: {info.get('difficulty_level')}, Domain: {info.get('domain')}")
            print(f"{'='*80}")

            # Run VGems
            agent_answer, steps, success, error = await self.run_v_gems(question, root_url)

            if success and agent_answer:
                success_count += 1
                print(f"✓ Completed in {steps} steps")
                print(f"Agent answer: {agent_answer[:200]}...")
            else:
                fail_count += 1
                print(f"✗ Failed" + (f" - {error}" if error else ""))

            # Save result
            result = {
                "index": idx,
                "question": question,
                "answer": ground_truth,  # Ground truth answer (for evaluate.py)
                "pred": agent_answer if agent_answer else "",  # Agent prediction (for evaluate.py)
                "root_url": root_url,
                "info": info,
                "evaluation": {
                    "success": success,
                    "steps": steps,
                    "error": error
                },
                "timestamp": time.time()
            }

            with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')

            # Update checkpoint
            self.checkpoint["completed_indices"].append(idx)
            self.save_checkpoint()

            # Small delay between queries
            await asyncio.sleep(1)

        # Final summary
        total = len(pending_items)
        print("\n" + "="*80)
        print("EVALUATION SUMMARY")
        print("="*80)
        print(f"Total questions evaluated: {total}")
        print(f"✓ Successful: {success_count} ({success_count/total*100:.1f}%)")
        print(f"✗ Failed: {fail_count} ({fail_count/total*100:.1f}%)")
        print(f"\nResults saved to: {RESULTS_FILE}")
        print("="*80 + "\n")


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Evaluate VGems on generated dataset')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of questions to evaluate (for testing)')
    parser.add_argument('--max-rounds', type=int, default=100,
                       help='Maximum steps per query (default: 100)')
    args = parser.parse_args()

    global MAX_ROUNDS
    MAX_ROUNDS = args.max_rounds

    # Run evaluation
    evaluator = VGemsEvaluator()
    await evaluator.evaluate(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
