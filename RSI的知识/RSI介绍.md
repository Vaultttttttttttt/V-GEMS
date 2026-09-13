RSI介绍

# 背景
递归自我改进（Recursive Self-Improvement，RSI）是指智能系统能够利用自身运行过程中产生的经验、反馈和评测结果，对自身的能力或运行机制进行持续优化，并进一步提升其后续自我改进的能力。其核心思想可以概括为：系统不仅能够解决任务，还能够分析自身不足、修改自身，并利用改进后的系统继续进行下一轮优化。

RSI 的思想可以追溯到早期的自修改人工智能研究，例如 Gödel Machine，其目标是让智能系统能够修改自身程序以获得更高的性能。但由于真实智能系统十分复杂，传统基于形式证明的自修改方法难以实际应用。

近年来，大语言模型和 Agent 技术的发展使 RSI 逐渐从理论概念走向工程实践。LLM 已具备代码生成、错误分析、反思和工具使用等能力，同时 Agent 在执行任务过程中会产生大量 trajectory、reward、error、tool result 等反馈信息，使系统可以形成：

```
执行任务 → 获取反馈 → 分析失败 → 修改系统 → 重新评测
```
的闭环。

当前 RSI 的优化对象已经从早期较简单的 输出结果、Prompt 和 Memory，逐渐扩展到 Tool、Skill、Workflow、Agent Architecture、Harness、训练数据甚至模型本身。进一步地，真正意义上的递归自我改进还要求系统能够优化自身的 Improvement Mechanism，即不仅“改进自己”，还能够“改进自己进行改进的方法”。

因此，可以将 RSI 看作 Agent 从固定人工设计系统逐渐向持续、自主、自适应演化系统发展的重要研究方向。

# 框架公式
参考综述 [The Path to Recursive Self-Improving Agents: Foundation, Framework, and Future Directions](https://www.preprints.org/manuscript/202608.0051) ，一个 Agent System 可以写成x：

```
x = (M,H,D,T,Imp)
```
其中：

|代号|全称|语义|
|-|-|-|
|M|Foundation Model|基础使用模型|
|H|Agent Harness|Harness 决定模型看到什么、能做什么、怎么调用工具、怎么组织 workflow|
|D|Agent Data System|Data System 管 trajectory、environment、task、training/evaluation data|
|T|Agent Trainer|Trainer 把这些经验变成参数更新|
|Imp|Improvement Mechanism|Imp 则负责最外层的“诊断 → 提出修改 → 验证 → 接受修改”整个优化机制|

# 具体分层
这里根据优化的位置，分为这几个层级：

|层级|名称|
|-|-|
|Layer 0|Output Self-Refinement|
|Layer 1|Memory Self-Improvement|
|Layer 2|Prompt Self-Improvement|
|Layer 3|Skill Self-Improvement|
|Layer 4|Agent Loop Self-Improvement|
|Layer 5|Harness Self-Improvement|
|Layer 6|Model Self-Improvement|
|Layer 7|Improvement Mechanism Self-Improvement|

层级从上至下改的东西越来越多、越来越重要

## Layer 0：Output Self-Refinement
通过模型内置的方法来提高最终回答。

```
本来输出 y0 = M(x0)
analyze = M(x0, y0)
最终输出y1 = M(analyze, x0, y0)

单论QA中的，不涉及跨对话
```
同一个模型先生成答案，再评价答案，然后修改答案。因为没有修改结构中的任何东西，所以不算严格的RSI，算是Self-Refinement

## Layer 1：Memory Self-Improvement
将模型的每一次轨迹全部保存起来。即可以修改memory

```
Trajectoryt​ → Memoryt+1​
Contextt+1 ​= Query + Retrieve(Memoryt+1​)
```
变了D。

### 案例1
论文名：[Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)

```
如果模型任务失败，就会产生一个feedback，
然后生成一个Reflection=“我这次为什么失败”，
下一次任务：Prompt=Task+Previous Reflections
```
## Layer 2：Prompt Self-Improvement
可以修改：system prompt、task instruction、few-shot examples、role prompt、guidelines、playbook、context-selection rules、compression rules、context ordering、context budget。即控制模型行为的文本接口不断优化。

```
Prompt/Contextt → ​optimizer​ → Prompt/Contextt+1​
```
### 案例1
论文名：[Promptbreeder: Self-Referential Self-Improvement Via Prompt Evolution](https://arxiv.org/abs/2309.16797)

同时优化Prompt、TaskPrompt、MutationPrompt

### 案例2
论文名：[ACON: Optimizing Context Compression for Long-horizon LLM Agents](https://arxiv.org/abs/2510.00615)

acon考虑怎么压缩context/memory

```
根据原来的成功的Context压缩为Compressed Context
如果Compressed Context结果为fail
那么就是说明压缩过程把一些关键的信息给弄没了
所以优化Compressed Contextt → Compressed Contextt+1
```
## Layer 3：Skill Self-Improvement
可以优化：tool selection、tool description、API wrapper、tool implementation、tool routing、skill document、skill code、function library、tool invocation policy。

```
Trajectory → Reusable Skill/Tool
```
## Layer 4：Agent Loop Self-Improvement
可以优化：Planner 要不要存在、Critic 要不要存在、几个 Agent、Agent 顺序、并行还是串行、什么时候 reflection、什么时候 tool calling、什么时候 retry、谁负责验证、message 怎么传、communication graph 怎么连。

主要是修改Agent Loop、workflow。

### 案例1
论文名：[AgentSquare: Automatic LLM Agent Search in Modular Design Space](https://arxiv.org/abs/2410.06153)

```
把一个 Agent 拆成四大模块：
    Planning
    Reasoning
    Tool Use 
    Memory
然后做这4个模块的 Module Evolution + Recombination
搜索最好的 Agent architecture
```
### 案例2
论文名：[AFlow: Automating Agentic Workflow Generation](https://arxiv.org/abs/2410.10762)

```
直接把 workflow 表示成 code graph：
    LLM nodes+edges
然后使用 MCTS 搜索 workflow。
之后每轮 workflowt → run → score → modification → workflowt+1 来不断更新workflow
```
## Layer 5：Harness Self-Improvement（我们的选择）
可以优化：context construction、memory policy、tool interface、error handling、retry、termination、verification、state tracking、sandbox、action filtering、workflow、observability、recovery。

就是优化整个harness了，与layer4相比，agent loop属于harness，所以layer5大于layer4。

### 案例1
论文名：[From Failed Trajectories to Reliable LLM Agents: Diagnosing and Repairing Harness Flaws](https://arxiv.org/abs/2606.06324)

```
整个流程大概是：
Harnesst
    ↓
Failed Trajectories
    ↓
HTIR
    ↓
Failure Localization
    ↓
Harness Layer Attribution
    ↓
Scoped Repair<--------------------
    ↓                            |
Regression Validation-------------
    ↓
Harnesst+1
```
### 案例2
论文名：[Meta-Harness: End-to-End Optimization of Model Harnesses](https://arxiv.org/abs/2603.28052)

```
从history harness{harness1, harness2 ... harnesst-1}中选出几个好的harness_need{}，
然后根据harness_need{}来优化harnesst → harnesst+1
```
## Layer 6：Model Self-Improvement
常见的rl方法来优化模型本身，修改模型本身参数。

## Layer 7：Improvement Mechanism Self-Improvement
优化Improvement Mechanism本身。

```
前面的layer都是
    Ht+1​=Imp(Ht​)
    Mt+1​=Imp(Mt​)
    Dt+1=Imp(Dt)
    ...
但是Imp都是不变的，layer7则是：
    Impt+1=Improve(Impt)
真正的修改Imp
```