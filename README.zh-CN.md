# V-CRISP 合成离散事件装配基准

[English](README.md)

本仓库包含一个用于比较计划检查与恢复策略的有限状态装配基准，以及参考运行的仿真器、回合记录、分析脚本和图件。

场景由程序合成，基准不包含实体机器人、感知、语言模型、几何规划器或独立验证的安全模型。结果反映的是本仓库所实现规则下的行为。

## 基准内容

每个场景都从重置的状态开始。候选计划由名义配方生成，部分场景会注入错误。主实验比较五种方法：

- `rule_script`：执行固定配方，不提供错误恢复。
- `classical_global`：根据完整建模状态重建配方；它是类似 Oracle 的参考方法，不是可直接部署的规划器。
- `semantic_direct`：直接调度扰动后的候选计划，不做模式检查，也不恢复。
- `structured_no_verify`：检查候选计划的模式，并依据当前建模状态重建计划，但不会在调度前检查工艺和资源约束。
- `vcrisp`：使用结构化候选计划、编译器、调度前检查、执行器事件记录和经验证的后缀修复。

候选计划错误包括工具或顺序错误、遗漏检查或换工具，以及未知目标。场景还可安排一次建模扰动，包括抓取失败、位姿偏移、工位阻塞、工具不可用、检查拒绝或低置信度。

组件消融在同一批 4,800 个场景上比较 `structured_no_verify`、仅初始检查（`checker_only`）、仅运行期后缀验证（`repair_only`）和完整的 `vcrisp`。检查器和调度守卫使用相同的动作规则，因此该消融并未测试独立验证器。

## 运行环境

参考运行环境为 arm64 macOS、Python 3.9.6、NumPy 2.0.2 和 Matplotlib 3.9.4。需要 Python 3.9 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## 复现实验

请在仓库根目录运行以下命令。实验命令会替换 `results/` 中的文件；需要保留旧运行时，请事先另存一份。

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
```

主实验包含 4,800 个配对场景和 24,000 条方法记录，使用 20 个随机种子、每个分层 10 个重置回合、三种配方规模、两种无扰动候选错误配置及六种扰动类型。组件消融在同一批场景上产生 19,200 条记录。敏感性实验包含 2,400 个场景和 12,000 条记录，候选错误率分别为 0.05、0.10、0.20 和 0.30。

## 查看结果

原始回合数据分别保存在 `results/episodes_main.csv`、`results/episodes_component_ablation.csv` 和 `results/episodes_sensitivity.csv`。`results/analysis/` 包含汇总表、配对自举结果和定性轨迹，可以从以下文件开始查看：

- `table_overall.csv`：主实验比较。
- `table_component_ablation.csv` 和 `component_ablation_bootstrap.csv`：组件消融比较。
- `table_robustness.csv`：各扰动条件下的结果。
- `table_sensitivity.csv`：各候选错误率下的结果。
- `table_runtime_scalability.csv`：不同配方规模的本机耗时与虚拟工期。
- `integrity_audit.json`：配对、重复记录和源代码哈希检查。

使用结果前，请确认 `integrity_audit.json` 中的审计通过。

虚拟工期字段使用抽象动作成本单位，不是实际制造过程的耗时。沿用名称的 `planning_cpu_ms` 和 `verification_cpu_ms` 由 `time.perf_counter()` 记录本机经过时间，并非 CPU 时间。`disturbance_detected` 表示执行器到达了预定状态并记录原因代码，不表示传感器检测成功；`human_intervention` 表示恢复未发生时设置的模拟升级标记，不是对人工操作的测量。

`figures/publication/` 保存 PDF、SVG 图件及相应的 JSON 质量记录。图 1 是抽象工作站的三维示意，不是机器人仿真或实体实验。

## 引用与发布

引用本仓库时请使用 `CITATION.cff`。包含组件消融结果的归档为 [v1.0.2，DOI 10.5281/zenodo.23768078](https://doi.org/10.5281/zenodo.23768078)。较早的 [v1.0.1 归档](https://doi.org/10.5281/zenodo.23766150) 不包含该消融实验。[概念 DOI](https://doi.org/10.5281/zenodo.23766149) 指向 Zenodo 中的最新版本。

在完整重跑实验并生成图件后，可以用下面的命令生成发布校验清单：

```bash
python3 make_release_manifest.py
```

`SHA256SUMS` 覆盖可执行源代码、权威结果、正式图件、许可证和发布元数据。

## 许可证

源代码采用 [Apache-2.0](LICENSE) 许可证。`results/` 中的合成基准记录和正式图件采用 [CC BY 4.0](LICENSE-DATA) 许可证。
