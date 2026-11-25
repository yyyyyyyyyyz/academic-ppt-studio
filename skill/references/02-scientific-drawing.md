# 02 · Scientific Drawing Standards, 10 Archetypes & 5 Engines

## Core Principle: One Slide, One Dedicated Publication-Grade Figure
Every content slide binds a dedicated `figure_spec` inspected by `FigureCriticAgent` before `.pptx` assembly.

## 10 Publication Archetypes (`A01`–`A10`)
| ID | Archetype | Key Visual Grammar | Primary Engine(s) |
| :--- | :--- | :--- | :--- |
| `A01` | Cutaway Reactor + Zoom Lens | Translucent borosilicate vessel + exact external-bitangent magnifying circle into porous micro-cavity | `Sci3DArtEngine` + `VectorMechanismEngine` |
| `A02` | Agglomeration vs. Dispersion | Sintered inactive cluster (`×`) vs. porous MOF/zeolite cage anchoring single active spheres (`✓`) | `Sci3DArtEngine` + native badges |
| `A03` | Editorial Flat-3D Vector | Uniform `#1E3A5F` outlines, directional gradient shading, physical field triggers (piezo/photo/acoustic) | `Sci3DArtEngine` (editorial mode) |
| `A04` | CYLview 3D Ball-and-Stick | ETKDGv3 + MMFF94 3D geometry, Phong spheres with `#4A4A4A` contours, two-tone half-cylinder bonds | `CYLview3DEngine` |
| `A05` | ChemDraw ACS 1996 + Halo | Global locked `fixedBondLength`, theme heteroatoms, soft Gaussian pastel highlight halo | `ChemDrawEngine` |
| `A06` | OriginPro 600 DPI Suite | 1:1 physical inches, 4-sided inward ticks, zero gridlines, 8 publication presets | `OriginPlotEngine` |
| `A07` | VESTA Polyhedra Split | Crystallographic coordination octahedra/tetrahedra + bi-color control vs. modified microenvironment | `Sci3DArtEngine` + `OriginPlotEngine` |
| `A08` | Multi-Scale Line-Art Trio | `a` macro loop $\to$ `b` mesoscale device cross-section $\to$ `c` Problem/Solution split circle | `Sci3DArtEngine` (line-art mode) |
| `A09` | Sunburst & BioRender Hub | Concentric 3-ring taxonomy with white dividers (auto-switches to 4 curved hub cards for long text) | `VectorMechanismEngine` |
| `A10` | Vector Cycles & Roadmaps | Coupled dual catalytic cycles, 4-stage closed-loop icon roadmap, gap quadrant bullseye, $\Delta G$ concept curve | `VectorMechanismEngine` + `icon_library` |

## Engine Engineering Rules
1. **`ChemDrawEngine`**: Lock `fixedBondLength` (default `28 px` at 1x) and compute canvas from molecular coordinate span so small and large molecules share identical ring scale.
2. **`CYLview3DEngine`**: Never delegate 3D molecules to raster image generators; render deterministically from RDKit 3D conformers.
3. **`OriginPlotEngine`**: Set `figsize=(box_w_in, box_h_in)` and export at `600 DPI` so `14 pt` plot typography equals `14 pt` on the slide. Place legends above the outer top border or use direct inline curve-end labels.
4. **`Sci3DArtEngine`**: Inject active palette `material_prompt_terms` + `STRICTLY ZERO TEXT...` negative gate, generate Best-of-$N$ ($N \ge 2$), run border-seeded Alpha Matting + white-fringe decontamination, and pass `detected_text_count == 0` + score `>= 8.5`.
5. **Proposal Rigor Gate**: When `is_proposal == True`, unverified `OriginPlotEngine` curves are blocked and automatically routed to SOP / probe / characterization matrix diagrams.
