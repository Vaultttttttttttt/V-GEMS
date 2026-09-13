L5:Harness Self-Improvement调研

# 一个总结
Harness Self-Improvement 是指 Agent 系统利用自身执行过程中产生的 trajectory、environment feedback、evaluation result 和 failure evidence，对模型外部的运行时 Harness 进行持续修改，从而在不必更新基础模型参数的情况下提升系统能力。其优化范围可以覆盖 execution、tooling、context、state/memory、lifecycle/orchestration、observability、verification 和 governance 等多个层面。近年来的研究已经由早期的 prompt、memory 和 skill refinement，逐渐扩展到 end-to-end harness program search、trace-guided repair、source-level rewriting、online continual adaptation、learned harness editing 以及 behavior-aware validation。

# 定义
```
Agent = Model + Harness
```
其中 Model 提供基础推理能力，而 Harness 决定：模型在什么环境中运行、看到什么信息、能调用什么工具、状态如何保存、执行流程如何推进、失败后怎么办、结果如何验证以及行为受到什么约束。

# harness layer分层
通过几篇综述，可以结合确认：

```
H=(E,T,C,S,L,O,V,G)​
```
其中

|子层|全称|核心问题|可以优化的内容|
|-|-|-|-|
|E|Execution|Agent 怎么运行？|execution loop、sandbox、retry、timeout、termination、fallback、parallelism|
|T|Tooling|Agent 能做什么？|tool schema、tool description、routing、tool selection、parameters、error handling|
|C|Context|模型当前看到什么？|system prompt、context construction、retrieval、compression、ordering、token allocation|
|S|State / Memory|跨步骤/跨任务记住什么？|short-term state、persistent memory、experience、state update、retrieval、forgetting|
|L|Lifecycle / Orchestration|一次任务怎么组织？|planner、critic、pre/post hooks、control flow、multi-agent coordination|
|O|Observability|怎么知道系统发生了什么？|traces、logging、cost、tool trace、failure trace、provenance|
|V|Verification|怎么判断做对没有？|verifier、tests、judge、acceptance rule、regression check|
|G|Governance|什么行为允许发生？|permissions、safety constraints、action blocking、audit、human approval|

所以Harness Self-Improvement就是看修改了哪些layer。

# 如何看RSI有提升
|评测维度|核心问题|指标|解释|
|-|-|-|-|
|最终性能提升 Effectiveness|RSI 后系统是否真的更强？|$\Delta S=S(H_T,D_{\text{test}})-S(H_0,D_{\text{test}})$|最基础指标。$H_0 $为初始 Harness，$H_T $为 RSI 后 Harness。必须在独立测试集上比较。|
|Held-out 泛化能力|RSI 是真正学到了能力，还是记住了优化任务？|$S(H_T,D_{\text{held-out}})>S(H_0,D_{\text{held-out}})$|RSI 过程不能接触 $D_{\text{held-out}}$。这是判断是否发生真正泛化的核心。|
|改进过程 Learning Dynamics|RSI 是否持续变好，而不是最后偶然找到一个好版本？|$S_0,S_1,\ldots,S_T$|应绘制 RSI iteration–performance 曲线，而不是只汇报$H_0$和 $H_T $|
|单调性 / 稳定性|RSI 是否会出现越改越差？|$\text{Regression Step Rate}=\frac{1}{T}\sum_{t=1}^{T}\mathbf{1}[S_t<S_{t-1}]$|衡量所有 RSI 更新中，有多少比例导致性能下降。该值越低，说明自我改进过程越稳定。|
|能力退化 Regression|新 Harness 是否把原来会做的任务改坏？|$\displaystyle \mathrm{RR}=\frac{\lvert\{x\in D:H_0(x)=1\land H_T(x)=0\}\rvert}{\lvert\{x\in D:H_0(x)=1\}\rvert}$|D 表示评测任务集合，$H_0 $表示 RSI 前的初始 Harness，$H_T$表示经过 T 轮 RSI 优化后的 Harness。$H_0(x)=1 $表示初始 Harness 能够正确完成任务 x，而$H_T(x)=0 $表示 RSI 后的 Harness 在该任务上失败。公式分子表示“原本能够正确完成、但 RSI 后被改坏的任务数量”，分母表示“初始 Harness 原本能够正确完成的任务总数”。因此，Regression Rate 用于衡量 RSI 过程中已有能力被破坏的比例，其数值越低越好；当 $\mathrm{RR}=0 $时，表示 RSI 后没有出现已有能力退化。|
|Task Generalization|是否能泛化到没见过的新任务？|$\Delta S_{\text{task}}=S(H_T,D_{\text{new-task}})-S(H_0,D_{\text{new-task}})$|测试任务与优化任务属于相近领域，但具体任务、问题或任务类型在 RSI 阶段未出现，用于评价任务级迁移能力。|
|Model Generalization|Harness 的改进是否依赖某个特定模型？|$\Delta S_m=S(H_T,M_m,D)-S(H_0,M_m,D)$|将优化后的 Harness 替换到不同基础模型 $(M_m)$上测试。如果多个模型都获得提升，说明学到的是较通用的 Harness 机制，而不是针对某个模型的特定技巧|
|Domain Generalization|RSI 学到的机制能否迁移到不同任务领域？|$\Delta S_{\text{domain}}=S(H_T,D_B)-S(H_0,D_B)$|在领域 (A) 上进行 Harness RSI，在不同领域 (B) 上测试。相比 Task Generalization 更严格，用于评价改进机制是否具有跨领域迁移能力。|
|成本 Cost|得到这次提升花了多少资源？|$C_{\text{RSI}}=\alpha N_{\text{token}}+\beta N_{\text{tool}}+\gamma T_{\text{wall}}+\delta C_{\text{compute}}$|应报告 RSI 优化过程消耗的 token、模型调用次数、工具调用次数、运行时间和计算资源等。|

# 论文
|论文|推荐理由|E|T|C|S|L|O|V|G|介绍链接|
|-|-|-|-|-|-|-|-|-|-|-|
|Meta-Harness: End-to-End Optimization of Model Harnesses|能够从所有历史harness中得到进化，对于历史harness的处理可以借鉴|$\surd$|$\surd$|$\surd$|$\surd$|$\surd$||||[Meta Harness](https://arxiv.org/abs/2603.28052)|
|From Failed Trajectories to Reliable LLM Agents: Diagnosing and Repairing Harness Flaws|对于错误的定位和评测部分可以借鉴，这部分处理的很细|$\surd$|$\surd$|$\surd$||$\surd$|$\surd$|$\surd$|$\surd$|[Harness Fix](https://arxiv.org/abs/2606.06324)|
|Living-Harness Is an Interactive-Agent Evolver|一个只修改了S的论文，简单易懂可以参考||||$\surd$|||||[Living-Harness](https://arxiv.org/abs/2607.26598)|
|Contextual Agent Security: A Policy for Every Purpose|一个只修改了G的论文，简单易懂可以参考||||||||$\surd$|[Contextual Agent Security](https://arxiv.org/abs/2501.17070)|
|Watson: A Cognitive Observability Framework for the Reasoning of LLM-Powered Agents|一个只修改了O的论文，简单易懂可以参考||||||$\surd$|||[Watson](https://arxiv.org/abs/2411.03455)|
|TTHE: Test-Time Harness Evolution|通过一个无标签的label来把harnesst分多个branch迭代然后最后统一选出一个harnesst+1的思路比较新颖|$\surd$|$\surd$|$\surd$||$\surd$||$\surd$||[TTHE](https://arxiv.org/abs/2607.08124)|
|MOSS: Self-Evolution through Source-Level Rewriting in Autonomous Agent Systems|这里的测试评估引入了工程方面的评估，而不是单纯测试集上面的评估|$\surd$|$\surd$|$\surd$|$\surd$|$\surd$|||$\surd$|[MOSS](https://arxiv.org/abs/2605.22794)|
|HarnessX: A Composable, Adaptive, and Evolvable Agent Harness Foundry|全方面改了，同时思路中的把一个harness组件表达为9个层面的结构化配置，觉得这个严格映射有帮助|$\surd$|$\surd$|$\surd$|$\surd$|$\surd$|$\surd$|$\surd$|$\surd$|[HarnessX](https://arxiv.org/abs/2606.14249)|