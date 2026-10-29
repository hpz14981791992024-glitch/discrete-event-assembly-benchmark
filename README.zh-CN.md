# V-CRISP 合成离散事件装配基准

[English](README.md)

本仓库提供一个可复现的、边界明确的合成离散事件装配基准。它用于考察：在已声明的状态转移与注入错误条件下，类型化候选计划接口、调度前建模约束检查、执行器事件记录和有界后缀修复是否会改变回合结果。

本仓库不是实体机器人或工厂实验。它不使用大语言模型、视觉语言模型、ROS、感知、几何任务与运动规划、碰撞检测，也不包含独立验证的安全模型。调度前检查器与调度保护器共享同一套建模动作语义，因此“零保护器拒绝”不能被解释为独立的安全验证证据。

## 方法与适用范围

每个配对场景均从独立重置的建模状态开始。CSV 中五种方法的含义如下：

- `rule_script`：不含恢复机制的固定配方。
- `classical_global`：利用完整建模状态重建配方的符号参考方法；它不是可部署的经典规划器。
- `semantic_direct`：经过扰动的候选计划直接调度，不进行模式检查或恢复。
- `structured_no_verify`：经过扰动的结构化候选计划，进行模式检查和未经验证的当前状态重建，但不执行过程或资源的调度前检查。
- `vcrisp`：结构化候选计划、编译器、调度前检查器、执行器事件记录和经验证的后缀修复。

候选计划是对名义配方施加的受控随机扰动，而不是 LLM 或 VLM 的输出。建模候选错误包括工具错误、顺序错误、缺少检查、未知目标和缺少换工具；单事件扰动包括抓取失败、位姿偏移、工位阻塞、工具不可用、检查拒绝和低置信度。这些均为有限状态基准条件，不是传感器观测或物理故障。

## 运行环境

测试环境为 arm64 macOS、Python 3.9.6、NumPy 2.0.2 和 Matplotlib 3.9.4。需要 Python 3.9 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## 完整复现

在仓库根目录执行。第一条实验命令会替换权威 `results/` 输出，不能混合不同运行批次的文件。

```bash
python3 -m py_compile \
  simulator.py run_experiments.py analyze_results.py audit_results.py \
  generate_qualitative_trace.py make_release_manifest.py \
  figures/audit_panel_alignment.py figures/make_figure1_composite.py \
  figures/make_publication_figures.py
python3 -m unittest -v test_simulator.py
python3 run_experiments.py --output-dir results
python3 analyze_results.py --results-dir results
python3 audit_results.py --results-dir results
python3 generate_qualitative_trace.py --output-dir results/analysis
python3 figures/make_figure1_composite.py
python3 figures/make_publication_figures.py
python3 make_release_manifest.py
```

主实验包含 4,800 个配对场景和 24,000 条方法记录；敏感性实验包含 2,400 个配对场景和 12,000 条记录。主实验使用 20 个随机种子、每个分层 10 个重置回合、三种配方规模、两种无扰动候选错误配置、六种扰动类型和五种方法。敏感性分析测试候选错误率 0.05、0.10、0.20 和 0.30。

## 输出与解读

`results/` 是一次完整运行的权威机器可读记录，包含逐方法原始回合记录、源代码哈希、分析表、配对自举对比、完整性审计和定性轨迹。主要表格来源为：

- `results/analysis/table_overall.csv`
- `results/analysis/table_robustness.csv`
- `results/analysis/table_runtime_scalability.csv`

使用结果前，`results/analysis/integrity_audit.json` 必须报告配对完整、无重复记录且无源哈希不一致。虚拟工期和事件到完成时间是抽象的“动作成本”单位，不是实际加工时间。

字段 `disturbance_detected` 表示有限状态执行器到达预定事件并输出原因代码，不是传感器检测结果。字段 `human_intervention` 是控制器在未恢复时设置的模拟升级标记，不是人工干预测量。因此，结果仅报告事件记录率和模拟升级率，不应被解释为感知性能或人工绩效。

`figures/publication/` 保存最终图件。图 1 是抽象工作站状态的三维示意图，用于解释建模事件流，不构成机器人仿真或实体机器人证据。PDF、SVG 及其 JSON 质量审计记录是归档图件；PNG、TIFF 和叠加审计文件只是渲染副产物。

## 发布与引用

正式发布文件由 `SHA256SUMS` 记录。它包含权威结果、正式图件、可执行源代码、引用元数据和许可证，并排除本地环境、历史或冒烟结果、未投稿论文及非规范图件副产物。

规范仓库地址为 [hpz14981791992024-glitch/discrete-event-assembly-benchmark](https://github.com/hpz14981791992024-glitch/discrete-event-assembly-benchmark)。`CITATION.cff` 和 `.zenodo.json` 记录洪鹏智、张嘉明及其单位信息。Zenodo 的版本 DOI 只能在实际归档后填写，不能预先编造。

## 许可证

可执行源代码采用 Apache-2.0 许可证，见 [LICENSE](LICENSE)。`results/` 中的合成基准记录与正式图件采用 CC-BY-4.0，见 [LICENSE-DATA](LICENSE-DATA)。未投稿论文仅在本地保留，不属于公开工件。

上述许可证不改变证据边界：发布记录仅支持本项目声明的有限状态合成基准结论，不能被描述为工厂数据、实体机器人数据、真实 LLM/VLM 性能、几何可行性、碰撞规避、独立安全验证、安全认证或部署就绪性证据。
