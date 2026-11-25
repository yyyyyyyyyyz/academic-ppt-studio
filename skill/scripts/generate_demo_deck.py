"""Generate a full 8-slide demonstration .pptx, DeckSpec JSON, previews, and audit report."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FIGURE_PROVIDER_MODE", "local")
os.environ.setdefault("LLM_PROVIDER_MODE", "local")

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.planner_agent import PlannerAgent
from app.agents.qa_agent import SlideVisualQAAgent
from app.config import get_settings
from app.figure_factory.factory import ScientificFigureFactory
from app.schemas.deck_spec import ScenarioType


DEMO_SOURCE = """# 无溶剂球磨介导非贵金属催化 C–N 交叉偶联机制与绿色制药应用研究
## 1. 研究背景与痛点立题
传统均相偶联依赖高沸点极性溶剂（DMF/DMSO），存在溶剂废液庞大、金属催化剂易团聚失活及分离纯化能耗高等核心痛点。
## 2. 科学问题与研究空白
机械化学条件下固体传质受限，且副产物 H2O 会抑制 Ni2+ 活性中心循环，如何在无溶剂环境中实现原位限域与能垒调控尚属空白。
## 3. 总体技术路线
构建“无溶剂剪切引发—ZSM-5 孔道原位锁水—双中心协同偶联—核磁/动力学定量互证”四阶段闭环技术路线。
## 4. 催化循环与三维构型调控
SMILES: CN(C)CCN(Cc1ccccc1)c2ccccn2
通过双齿配体立体位阻设计与双循环催化耦合，显著降低关键 C–N 成键决速步活化能垒。
## 5. 定量效率与过程绿色度对比
目标医药中间体分离收率达 91.2%，过程质量强度 PMI 降至 4.8（降幅 -91.7%），底物普适性涵盖芳氯与杂芳环。
## 6. 总结与未来展望
确立了跨尺度固相限域催化通用范式，后续将拓展至连续流微反应器放大及临床前原料药库合成。
"""


def main() -> int:
    settings = get_settings(ensure_dirs=True)
    out_dir = settings.demo_deck_root
    out_dir.mkdir(parents=True, exist_ok=True)

    planner = PlannerAgent()
    deck = planner.plan_deck(
        source_text=DEMO_SOURCE,
        deck_title="无溶剂球磨介导非贵金属催化 C–N 偶联机制研究",
        author="药化硕士研究生",
        affiliation="药学院计算与药物合成实验室",
        scenario=ScenarioType.defense,
        target_slide_count=8,
        palette_id="lancet",
        is_proposal=False,
        deck_id="academic_demo_lancet",
    )

    qa_agent = SlideVisualQAAgent(factory=ScientificFigureFactory(settings=settings))
    pptx_path, report, previews = qa_agent.build_and_verify(deck, out_dir, max_rounds=2)

    spec_path = out_dir / "deck_spec.json"
    spec_path.write_text(deck.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
    (out_dir / "audit_report.json").write_text(json.dumps(report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"PPTX: {pptx_path}")
    print(f"Previews: {len(previews)} slides -> {out_dir / 'previews'}")
    print(f"Audit passed={report.passed}, filled_body_boxes={report.filled_body_boxes}, min_body_pt={report.min_body_pt_observed}, min_any_pt={report.min_any_pt_observed}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
