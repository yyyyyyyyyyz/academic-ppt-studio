# Skill: Word 论文 / 开题报告转学术 PPT 大纲规划引擎 (`word-to-ppt-outline/v1`)

> 与后端 `backend/app/skills/word_to_outline_skill.md` 同步，供内部 `OutlineAgent` / `PlannerAgent` 及外部大模型按统一规则将 Word/PDF 文档总结为结构化 PPT 大纲。

- **输入**：Word/PDF 解析后的分段正文、提取表格（`ParsedTable`）、化合物名称/SMILES 列表、汇报场景与页数预算。
- **输出**：严格 JSON（`title`、`summary`、`slides[]`）以及可编辑 Markdown 大纲（`# 标题` / `## 分页` / `SMILES:`）。
- **核心约束**：
  1. 零幻觉数值，真实表格/KPI 优先保留；开题模式不编造实测性能。
  2. 每页正文精炼（标题 ≤ 18 字、核心结论 ≤ 38 字、要点 2–3 条 ≤ 26 字）。
  3. 明确为每页匹配最合适的 `2d`（`acs1996` / `minimal_mono` / `nature_burgundy` / `jacs_terracotta` / `shaded_scaffold` / `reactive_spot`）或 `3d`（`ball_stick` / `pymol_neon_green` / `metallic_studio` / `stick_clean` / `spacefill_cpk`）分子结构式风格。
