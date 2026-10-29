# V-CRISP 合成离散事件装配基准

[English](README.md)

V-CRISP 是一个面向装配任务规划的合成离散事件基准。它用一组可重复运行的场景，比较不同的计划检查和恢复方式在候选计划出错、环境状态变化时会带来什么差异。项目的重点很简单：让实验逻辑、原始记录和分析过程都能被检查和复现。

这个基准的范围是明确且有限的。它是有限状态仿真，不是实体机器人或工厂实验；不使用大语言模型、视觉语言模型、ROS、感知、几何运动规划、碰撞检测或独立验证的安全模型。因此，结果只说明本仓库所定义的仿真条件，不应延伸到真实生产系统。

## 基准内容

每个场景都会从独立重置的建模状态开始。名义装配配方经过扰动后形成候选计划，再由以下五种方法之一处理：

- `rule_script`：执行固定配方，不提供错误恢复。
- `classical_global`：根据完整建模状态重建配方；它是类似 Oracle 的参考方法，不是可直接部署的规划器。
- `semantic_direct`：直接调度扰动后的候选计划，不做模式检查，也不恢复。
- `structured_no_verify`：检查候选计划的模式，并依据当前建模状态重建计划，但不会在调度前检查工艺和资源约束。
- `vcrisp`：使用结构化候选计划、编译器、调度前检查、执行器事件记录和经验证的后缀修复。

候选计划的错误包括工具错误、顺序错误、遗漏检查、未知目标和遗漏换工具。场景中还可安排一次扰动，例如抓取失败、位姿偏移、工位阻塞、工具不可用、检查拒绝或低置信度。这些名称代表有限状态条件，不是实际物理故障，也不是传感器观测。

## 运行环境

参考运行环境为 arm64 macOS、Python 3.9.6、NumPy 2.0.2 和 Matplotlib 3.9.4。需要 Python 3.9 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## 复现实验

请在仓库根目录运行下面的命令。`run_experiments.py` 会替换 `results/` 中的权威输出，因此不要把不同批次的运行结果混在一起。

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

主实验包含 4,800 个配对场景和 24,000 条方法级记录，覆盖 20 个随机种子、每个分层 10 个重置回合、三种配方规模、两种无扰动候选错误配置、六种扰动类型和五种方法。敏感性实验包含 2,400 个配对场景和 12,000 条记录，候选错误率分别为 0.05、0.10、0.20 和 0.30。

## 查看结果

`results/` 保存一次完整运行的机器可读记录，包含原始回合数据、源代码哈希、分析表、配对自举对比、完整性审计和定性轨迹。主要汇总表为：

- `results/analysis/table_overall.csv`
- `results/analysis/table_robustness.csv`
- `results/analysis/table_runtime_scalability.csv`

使用某次运行结果前，应先检查 `results/analysis/integrity_audit.json`。其中应报告配对记录完整、没有重复项，且源代码哈希没有不一致。

时间相关字段使用的是抽象动作成本单位，不是实际制造过程的耗时。`disturbance_detected` 表示执行器到达了预定状态并记录原因代码，不表示传感器检测成功；`human_intervention` 表示恢复未发生时设置的模拟升级标记，不是对人工操作的测量。

`figures/publication/` 中保存正式图件。图 1 是抽象的三维工作站状态示意，用来说明事件流，而不是机器人仿真或实体机器人实验的证据。PDF、SVG 及相应的 JSON 质量记录是归档图件。

## 引用与发布

引用本仓库时请使用 `CITATION.cff`。`v1.0.1` 已由 Zenodo 归档，其版本 DOI 为 [10.5281/zenodo.23766150](https://doi.org/10.5281/zenodo.23766150)。引用该归档版本时应使用这个版本 DOI；[概念 DOI](https://doi.org/10.5281/zenodo.23766149) 会始终指向 Zenodo 中的最新版本。`.zenodo.json` 用于为后续 Zenodo 发布提供元数据。

在完整重跑实验并生成图件后，可以用下面的命令生成发布校验清单：

```bash
python3 make_release_manifest.py
```

`SHA256SUMS` 覆盖可执行源代码、权威结果、正式图件、许可证和发布元数据。

## 许可证

源代码采用 [Apache-2.0](LICENSE) 许可证。`results/` 中的合成基准记录和正式图件采用 [CC BY 4.0](LICENSE-DATA) 许可证。

许可证只规定复用方式，并不扩大实验结论的范围。本仓库不支持关于工厂数据、实体机器人、真实 LLM 或 VLM 性能、几何可行性、碰撞规避、独立安全验证、安全认证或部署就绪性的主张。
