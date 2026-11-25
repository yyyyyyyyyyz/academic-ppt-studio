# Skill: Word 论文 / 开题报告转学术 PPT 大纲与高级排版规划引擎 (`word-to-ppt-outline/v2`)

> 与后端 `backend/app/skills/word_to_outline_skill.md` 同步，供内部 `OutlineAgent` / `PlannerAgent` 及所有外部大模型按统一规则将 Word/PDF 文档总结为小红书/顶刊答辩级信息图 PPT 大纲。

- **输入**：Word/PDF 解析后的分段正文、提取表格（`ParsedTable`）、化合物名称/SMILES 列表、汇报场景与页数预算。
- **输出**：严格 JSON（`title`、`summary`、`slides[]`）以及可编辑 Markdown 大纲（`# 标题` / `## 分页` / `SMILES:`）。
- **核心约束**：
  1. 零幻觉数值，真实表格/KPI 优先保留；开题模式不编造实测性能。
  2. 信息图表化：每页正文精炼（标题 ≤ 18 字、核心结论 ≤ 38 字、要点 2–4 条 ≤ 26 字），避免连续两页版式重复。
  3. 全量 13 种 `layout_id` 语义排版库：`bg_top_summary_3box`、`pain_points_left_arrows`、`dual_compare_cards`、`tri_column_showcase`、`lit_overview_dual_card`、`hub_spoke_radial`、`quadrant_2x2_matrix`、`timeline_chevron_flow`、`roadmap_layered_matrix`、`mechanism_3col_flow`、`fig_left_3step_chain`、`vs_center_wing`、`data_dashboard_table`。
  4. **多色语义配色规范（全模型默认生效）**：所有配色方案自动导出多色语义槽位（`s1` 主锚 / `s2` 次锚 / `s3` 第三层级 / `alert` 痛点对照与高光数值），驱动多卡片、四象限、流程阶梯与 `VS` 对照分色呈现。
  5. 为每页匹配最合适的 `2d`（`acs1996` / `minimal_mono` / `nature_burgundy` / `jacs_terracotta` / `shaded_scaffold` / `reactive_spot`）或 `3d`（`ball_stick` / `pymol_neon_green` / `metallic_studio` / `stick_clean` / `spacefill_cpk`）工作室级 PBR 分子结构式风格。
