# Academic PPT Design Studio & `academic-ppt-design` Skill (v4.0)

> **通用、跨学科、自由页数（3–30+ 页）的专业学术 PPT 生成系统与开源 Agent Skill** —— 以**顶刊美编级科研绘图（One Slide, One Dedicated Publication-Grade Scientific Figure）**为第一优先级，输出 **100% 原子级图/文全分离、原生可编辑、零填充去框**的 `.pptx` 文件。

## 核心架构（4 层解耦）

```text
Desktop Web Studio (React 19 + TypeScript + Vite)
   │  • 自由页数 (3–30+) · 15 套全链路科研色板热切换
   │  • FigureWorkbench (A01–A10 范式切换、Best-of-N 挑图、自然语言局部重绘、本地原图替换)
   │  • L1 / L2 / L3 三层隔离预览 & 实时规范门禁条
   ▼  DeckSpec JSON Schema (v4.0)
Multi-Agent Orchestration Layer (Planner -> Art Director -> Figure Critic -> Slide Visual QA)
   ▼
Scientific Figure Factory (5 大生产级后端引擎) + python-pptx 原生编译器 + audit_pptx 门禁
   ├── palettes.py          15 套高引期刊 & SCI 实测 HEX 色板 + 3D 材质词典
   ├── chemdraw_engine.py   RDKit ACS 1996 固定物理键长 (fixedBondLength) + 柔色光晕
   ├── cylview3d_engine.py  ETKDGv3 + MMFF94 + Phong Z-Buffer 描边 3D 球棍（零幻觉）
   ├── origin_engine.py     600 DPI 1:1 物理尺寸 8 套 OriginPro 发表图预设
   ├── sci3d_art_engine.py  A01–A08 美编 Prompt 编译器 + Best-of-N + 真透明 Alpha 抠图
   └── vector_mech.py       精确外部双切线放大镜、同心圆环综述、催化双循环、4 阶段路线闭环
```

## 十大顶刊绘图范式 (`A01`–`A10`)

| 范式 | 名称 | 核心视觉语法 | 主导引擎 |
| :--- | :--- | :--- | :--- |
| **A01** | 3D 剖切装置 + 放大镜微界面 | 左侧玻璃/球磨反应釜 + 精确双切线拉出微观孔道放大圆窗 | `Sci3DArtEngine` + `VectorMechanismEngine` |
| **A02** | 3D 团聚失效 vs 多孔限域分散 | 高光团聚体（`×`）vs 半透明多孔沸石/MOF 笼单分散锚定（`✓`） | `Sci3DArtEngine` + 原生标注 |
| **A03** | 2D 扁平微立体编辑插画 | 统一深海蓝描边 + 方向渐变 + 物理场激活（压电/光电/声） | `Sci3DArtEngine` (Editorial) |
| **A04** | CYLview 风格 3D 球棍分子 | ETKDGv3 3D 构象 + `#4A4A4A` 轮廓描边高光球与双色半圆柱键 | `CYLview3DEngine` |
| **A05** | ChemDraw ACS 1996 + 柔色光晕 | 全局固定物理键长 + 主题杂原子着色 + 高亮活性位点圆晕 | `ChemDrawEngine` |
| **A06** | OriginPro 600 DPI 1:1 谱学套图 | 8 套预设：动力学样条、直标增幅柱、电化学联排、XPS 分峰、DFT/ML | `OriginPlotEngine` |
| **A07** | VESTA 晶体多面体 + 双色分屏 | 顶部配位八面体晶格 + 上浅蓝/下浅粉界面对比 | `Sci3DArtEngine` + `OriginPlotEngine` |
| **A08** | Nature Reviews 黑线多尺度三联 | 宏观生态闭环 $\to$ 介观器件剖面 $\to$ 微观 Problem/Solution 圆 | `Sci3DArtEngine` (Line-Art) |
| **A09** | 同心圆环综述 & BioRender 通路 | 3–4 层同心圆环（长文本自动切换中心圆 + 4 弧带通路卡） | `VectorMechanismEngine` |
| **A10** | 全矢量催化双循环 / 路线 / 象限 | 耦合双催化循环、4 阶段线稿图标闭环路线、研究空白靶心象限 | `VectorMechanismEngine` |

## 快速启动

### 1. 生成 10 大范式标准测试样张与 15 套色板卡
```powershell
D:\academic-ppt-design\backend\.venv\Scripts\python.exe D:\academic-ppt-design\skill\scripts\generate_archetype_gallery.py
```

### 2. 运行自动化全量测试（Milestone 1–4）
```powershell
D:\academic-ppt-design\backend\.venv\Scripts\python.exe -m pytest D:\academic-ppt-design\backend\tests -v -p no:cacheprovider
```

### 3. 启动后端 FastAPI 服务与前端桌面工作台
```powershell
# 终端 1：启动 FastAPI 引擎 (端口 8000)
D:\academic-ppt-design\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir D:\academic-ppt-design\backend --host 127.0.0.1 --port 8000 --reload

# 终端 2：启动前端 Vite 工作台 (端口 5173)
$env:PATH = "D:\node-portable\node-v24.22.0-win-x64;$env:PATH"
cd D:\academic-ppt-design\frontend
npm run dev
```

### 4. 作为 MCP Server 接入外部 Agent 客户端
```json
{
  "mcpServers": {
    "academic-ppt-design": {
      "command": "D:\\academic-ppt-design\\backend\\.venv\\Scripts\\python.exe",
      "args": ["-m", "app.mcp_server"],
      "cwd": "D:\\academic-ppt-design\\backend"
    }
  }
}
```
