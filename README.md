# V-GEMS: Vision-Guided Exploration and Multi-Source Search

V-GEMS is an improved web traversal and information retrieval system built on an multi-agent idea. This system can intelligently browse web pages, extract information, and answer complex multi-source questions.

## 📋 Table of Contents

- [Environment Setup](#-environment-setup)
- [Real-time Dataset Generation](#-real-time-dataset-generation)
- [Running the System](#-running-the-system)
- [Evaluation](#-evaluation)

---

## 🛠 Environment Setup

### 1. Create Virtual Environment

```bash
conda create -n v_gems python=3.10
conda activate v_gems
```

### 2. Clone Repository and Install Dependencies

```bash
git clone https://github.com/your-repo/v-gems.git
cd v-gems

# Install Python dependencies
pip install -r requirements.txt

# Run post-installation setup
crawl4ai-setup

# Verify installation
crawl4ai-doctor
```

### 3. Configure API Keys

Before running, please set the API key environment variables:

**Using OpenAI API:**

```bash
export OPENAI_API_KEY=YOUR_API_KEY
export OPENAI_MODEL_SERVER=OPENAI_MODEL_SERVER
```

**Or using Dashscope API:**

```bash
export DASHSCOPE_API_KEY=YOUR_API_KEY
```

## 📊 Real-time Dataset Generation

V-GEMS provides real-time dataset generation functionality to collect data from official websites and generate question-answer pairs.

### Step 1: Collect Target Official Websites

Run the following command to collect all target official websites:

```bash
cd src
python collect_official_websites.py
```

**Script Functions:**
- Collects various official websites from search engines (education, conferences, games, organizations)
- Categorizes by predefined classifications and languages
- Saves results to `generated_dataset/official_websites.json`

**Website Categories:**
- Education (Chinese/English): Universities, colleges
- Conference (Chinese/English): Academic conferences, symposiums
- Game (Chinese/English): Game companies, game products
- Organization (Chinese/English): Associations, societies, foundations

### Step 2: Generate Question-Answer Dataset

Run the following command to generate the current day's dataset from collected websites:

```bash
python generate_qa_from_websites.py
```

**Script Functions:**
- Reads the collected official website list
- Intelligently browses web pages and extracts information
- Generates single-source and multi-source question-answer pairs
- Saves results to `generated_dataset/v_gems_qa.jsonl`

**Data Distribution:**
- **Single-source questions**: 80 easy + 140 medium + 120 hard
- **Multi-source questions**: 80 easy + 140 medium + 120 hard
- **Total**: 680 question-answer pairs

**Data Format Example:**

```json
{
  "question": "Question content",
  "answer": "Answer content",
  "root_url": "Official website URL",
  "info": {
    "source_website": ["url1"] or ["url1", "url2"],
    "golden_path": ["root->button1->button2"] or ["root->button1", "root->button2->button3"],
    "type": "single-source" or "multi-source",
    "difficulty_level": "easy" or "medium" or "hard",
    "domain": "game" or "conference" or "education" or "organization",
    "lang": "cn" or "en"
  }
}
```

---

## 🚀 Running the System

### Launch V-GEMS Interactive Interface

Run the following command to start the Streamlit-based interactive interface:

```bash
cd src
streamlit run app.py --server.fileWatcherType none
```

**System Features:**
- Input questions in the browser interface
- Automatic navigation of relevant web pages
- Visual language model for understanding page content
- URL stack management for browsing history
- Counter-based search strategy optimization
- Accurate multi-source answers

**Usage Example:**
1. Enter your question in the interface
2. System automatically begins web traversal
3. Real-time display of visited pages and extracted information
4. Final comprehensive answer provided

---

## 🔍 Evaluation

### Run Evaluation Script

Use `evaluate_v_gems.py` to evaluate V-GEMS performance on the generated dataset:

```bash
cd src
python evaluate_v_gems.py
```

**Evaluation Options:**

```bash
# Test first 10 questions
python evaluate_v_gems.py --limit 10

# Test all questions
python evaluate_v_gems.py
```

**Evaluation Process:**
1. Load questions from `generated_dataset/v_gems_qa.jsonl`
2. Run V-GEMS agent to answer each question
3. Save answers to `evaluation_results/v_gems_answers.jsonl`
4. Support checkpoint resumption functionality

**Evaluation Metrics:**
- **Accuracy**: Correctness of answers
- **Success Rate**: Proportion of successfully answered questions
- **Error Analysis**: Detailed analysis of failure cases

**View Evaluation Results:**

After evaluation completes, results are saved in:
- Answer file: `evaluation_results/v_gems_answers.jsonl`
- Checkpoint file: `evaluation_results/eval_checkpoint.json`

---

## 📈 Performance Analysis

V-GEMS employs multiple innovative techniques to enhance web traversal and information retrieval performance:

- **Vision Language Model (VLM)**: Understands visual layout and content of web pages
- **URL Stack Management**: Effectively manages browsing history, avoids redundant visits
- **Intelligent Counter**: Optimizes search strategy, improves efficiency
- **Multi-Agent Framework**: Effective memory management and task decomposition

---

## 📁 Project Structure

```
v-gems/
├── src/
│   ├── app.py                          # Streamlit interactive interface
│   ├── agent.py                        # V-GEMS agent core
│   ├── collect_official_websites.py    # Website collection script
│   ├── generate_qa_from_websites.py    # QA dataset generation
│   ├── evaluate_v_gems.py              # Evaluation script
│   ├── tools_for_eval.py               # Evaluation tools
│   ├── utils.py                        # Utility functions
│   ├── prompts.py                      # Prompt templates
│   ├── generated_dataset/              # Generated dataset directory
│   │   ├── official_websites.json      # Collected website list
│   │   └── v_gems_qa.jsonl            # Generated QA data
│   └── evaluation_results/             # Evaluation results directory
│       ├── v_gems_answers.jsonl       # Evaluation answers
│       └── eval_checkpoint.json        # Evaluation checkpoint
├── requirements.txt                    # Python dependencies
└── README.md                          # Project documentation
```