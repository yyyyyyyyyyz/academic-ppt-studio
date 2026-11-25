"""Chemical Name/SMILES Grounding, PubChem Verification & Native ChemDraw .cdxml Exporter."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx
from rdkit import Chem
from rdkit.Chem import AllChem


# Curated RDKit-verified dictionary of classic medicinal chemistry drugs & catalytic intermediates
_KNOWN_COMPOUNDS: Dict[str, str] = {
    "osimertinib": "COc1cc(N(C)CCN(C)C)c(NC(=O)C=C)cc1Nc2nccc(n2)c3cn(C)c4ccccc34",
    "奥希替尼": "COc1cc(N(C)CCN(C)C)c(NC(=O)C=C)cc1Nc2nccc(n2)c3cn(C)c4ccccc34",
    "gefitinib": "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN4CCOCC4",
    "吉非替尼": "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN4CCOCC4",
    "erlotinib": "COCCOc1cc2ncnc(Nc3cccc(C#C)c3)c2cc1OCCOC",
    "厄洛替尼": "COCCOc1cc2ncnc(Nc3cccc(C#C)c3)c2cc1OCCOC",
    "imatinib": "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc4nccc(n4)c5cccnc5",
    "伊马替尼": "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc4nccc(n4)c5cccnc5",
    "dasatinib": "Cc1nc(Nc2ncc(s2)C(=O)Nc3c(C)cccc3Cl)cc(n1)N4CCN(CCO)CC4",
    "达沙替尼": "Cc1nc(Nc2ncc(s2)C(=O)Nc3c(C)cccc3Cl)cc(n1)N4CCN(CCO)CC4",
    "brigatinib": "COc1cc(N2CCC(N3CCN(C)CC3)CC2)ccc1Nc4ncc(Cl)c(Nc5ccccc5P(C)(C)=O)n4",
    "布加替尼": "COc1cc(N2CCC(N3CCN(C)CC3)CC2)ccc1Nc4ncc(Cl)c(Nc5ccccc5P(C)(C)=O)n4",
    "nirmatrelvir": "CC1(C)[C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@@H](NC(=O)C(F)(F)F)C(C)(C)C)C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N",
    "奈玛特韦": "CC1(C)[C@@H]2[C@H]1[C@H](N(C2)C(=O)[C@@H](NC(=O)C(F)(F)F)C(C)(C)C)C(=O)N[C@@H](C[C@@H]3CCNC3=O)C#N",
    "penicillin g": "CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@H]1C(=O)O",
    "青霉素": "CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@H]1C(=O)O",
    "artemisinin": "C[C@@H]1CC[C@H]2[C@@H](C)C(=O)O[C@@H]3O[C@@]4(C)CC[C@@H]1[C@@]23OO4",
    "青蒿素": "C[C@@H]1CC[C@H]2[C@@H](C)C(=O)O[C@@H]3O[C@@]4(C)CC[C@@H]1[C@@]23OO4",
    "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
    "阿司匹林": "CC(=O)Oc1ccccc1C(=O)O",
    "ibuprofen": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "布洛芬": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "ibp": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "ibrutinib": "C=CC(=O)N1CCC[C@H](n2nc(-c3ccc(Oc4ccccc4)cc3)c5c(N)ncnc25)C1",
    "伊布替尼": "C=CC(=O)N1CCC[C@H](n2nc(-c3ccc(Oc4ccccc4)cc3)c5c(N)ncnc25)C1",
    "sotorasib": "C=CC(=O)N1CCN(c2nc(=O)n(-c3c(C)ccnc3C(C)C)c4nc(-c5c(F)cccc5O)c(F)cc24)[C@H](C)C1",
    "索托拉西布": "C=CC(=O)N1CCN(c2nc(=O)n(-c3c(C)ccnc3C(C)C)c4nc(-c5c(F)cccc5O)c(F)cc24)[C@H](C)C1",
    "remdesivir": "CCC(CC)COC(=O)[C@H](C)N[P@](=O)(OC[C@H]1O[C@](C#N)(c2ccc3c(N)ncnn23)[C@H](O)[C@@H]1O)Oc4ccccc4",
    "瑞德西韦": "CCC(CC)COC(=O)[C@H](C)N[P@](=O)(OC[C@H]1O[C@](C#N)(c2ccc3c(N)ncnn23)[C@H](O)[C@@H]1O)Oc4ccccc4",
    "paclitaxel": "CC(=O)O[C@H]1C(=O)[C@@]2(C)[C@@H](O)C[C@H]3OC[C@@]3(OC(C)=O)[C@H]2[C@H](OC(=O)c4ccccc4)[C@]5(O)C[C@H](OC(=O)[C@H](O)[C@@H](NC(=O)c6ccccc6)c7ccccc7)C(C)=C1C5(C)C",
    "紫杉醇": "CC(=O)O[C@H]1C(=O)[C@@]2(C)[C@@H](O)C[C@H]3OC[C@@]3(OC(C)=O)[C@H]2[C@H](OC(=O)c4ccccc4)[C@]5(O)C[C@H](OC(=O)[C@H](O)[C@@H](NC(=O)c6ccccc6)c7ccccc7)C(C)=C1C5(C)C",
    "fenbufen": "O=C(O)CCC(=O)c1ccc(-c2ccccc2)cc1",
    "芬布芬": "O=C(O)CCC(=O)c1ccc(-c2ccccc2)cc1",
    "tucaresol": "O=Cc1cc(COc2ccc(C(=O)O)cc2)ccc1O",
    "peracetic acid": "CC(=O)OO",
    "过氧乙酸": "CC(=O)OO",
    "paa": "CC(=O)OO",
    "acetaminophen": "CC(=O)Nc1ccc(O)cc1",
    "对乙酰氨基酚": "CC(=O)Nc1ccc(O)cc1",
    "curcumin": "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O",
    "姜黄素": "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O",
    "doxorubicin": "COc1cccc2c1C(=O)c1c(O)c3c(c(O)c1C2=O)C[C@@](O)(C(=O)CO)C[C@@H]3O[C@H]1C[C@H](N)[C@H](O)[C@H](C)O1",
    "阿霉素": "COc1cccc2c1C(=O)c1c(O)c3c(c(O)c1C2=O)C[C@@](O)(C(=O)CO)C[C@@H]3O[C@H]1C[C@H](N)[C@H](O)[C@H](C)O1",
    "metformin": "CN(C)C(=N)NC(=N)N",
    "二甲双胍": "CN(C)C(=N)NC(=N)N",
    "quinazoline": "c1ccc2ncncc2c1",
    "喹唑啉": "c1ccc2ncncc2c1",
    "morpholine": "C1COCCN1",
    "吗啉": "C1COCCN1",
}

_SMILES_IN_TEXT_PAT = re.compile(r"SMILES[:：]\s*([A-Za-z0-9@+\-\[\]\(\)=#$./\\]+)", flags=re.IGNORECASE)


def canonicalize_smiles(raw: str) -> Optional[str]:
    """Return RDKit canonical SMILES when raw parses as a valid molecule (>=2 atoms)."""
    cand = (raw or "").strip()
    if not cand or len(cand) > 400 or any(ch.isspace() for ch in cand) or not cand.isascii():
        return None
    try:
        mol = Chem.MolFromSmiles(cand)
        if mol is not None and mol.GetNumAtoms() >= 2:
            return Chem.MolToSmiles(mol, isomericSmiles=True)
    except Exception:
        return None
    return None


def resolve_compound_smiles(query: str, allow_pubchem: bool = False, timeout: float = 3.5) -> Optional[str]:
    """Resolve a SMILES string, Chinese/English drug name, or PubChem compound name into canonical SMILES."""
    q = (query or "").strip()
    if not q:
        return None

    lowered = q.lower()
    if lowered in _KNOWN_COMPOUNDS:
        return canonicalize_smiles(_KNOWN_COMPOUNDS[lowered])

    direct = canonicalize_smiles(q)
    if direct:
        return direct

    # Partial match against known compound keys
    for key, smi in _KNOWN_COMPOUNDS.items():
        if key in lowered:
            return canonicalize_smiles(smi)

    if allow_pubchem and len(q) <= 80:
        try:
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(q)}/property/CanonicalSMILES/JSON"
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    props = data.get("PropertyTable", {}).get("Properties", [])
                    if props and isinstance(props[0], dict):
                        for k in ("CanonicalSMILES", "ConnectivitySMILES", "IsomericSMILES"):
                            smi = props[0].get(k)
                            canon = canonicalize_smiles(str(smi or ""))
                            if canon:
                                return canon
        except Exception:
            return None

    return None


def extract_compounds_from_text(text: str) -> List[Tuple[str, str]]:
    """Extract ordered (label, canonical_smiles) pairs from SMILES annotations and drug names."""
    raw = text or ""
    found: List[Tuple[str, str]] = []
    seen_smiles = set()

    for smi in _SMILES_IN_TEXT_PAT.findall(raw):
        canon = canonicalize_smiles(smi)
        if canon and canon not in seen_smiles:
            seen_smiles.add(canon)
            found.append(("分子结构", canon))

    lowered = raw.lower()
    # Longer keys first so e.g. 'osimertinib' matches before 'ibp'
    for name in sorted(_KNOWN_COMPOUNDS.keys(), key=len, reverse=True):
        if name.isascii() and len(name) <= 3 and not re.search(rf"\b{re.escape(name)}\b", lowered):
            continue
        if name in lowered:
            canon = canonicalize_smiles(_KNOWN_COMPOUNDS[name])
            if canon and canon not in seen_smiles:
                seen_smiles.add(canon)
                found.append((name, canon))

    return found


def export_mol_to_cdxml(
    smiles: str,
    output_cdxml: Path | str,
    bond_length_pt: float = 14.4,
    color_hex: str = "#000000",
) -> Path:
    """Export an RDKit molecule with ACS 1996 coordinates to a native editable ChemDraw .cdxml XML file."""
    canon = resolve_compound_smiles(smiles) or smiles
    mol = Chem.MolFromSmiles(canon)
    if mol is None:
        raise ValueError(f"Invalid SMILES for CDXML export: {smiles}")

    mol = Chem.Mol(mol)
    AllChem.Compute2DCoords(mol)
    conf = mol.GetConformer()
    try:
        Chem.WedgeMolBonds(mol, conf)
    except Exception:
        pass

    # Compute median RDKit 2D bond length in coordinate units so bond lengths match bond_length_pt (14.4 pt)
    bond_lengths: List[float] = []
    for b in mol.GetBonds():
        p1 = conf.GetAtomPosition(b.GetBeginAtomIdx())
        p2 = conf.GetAtomPosition(b.GetEndAtomIdx())
        d = ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5
        if d > 1e-4:
            bond_lengths.append(d)
    median_len = sorted(bond_lengths)[len(bond_lengths) // 2] if bond_lengths else 1.5
    scale = float(bond_length_pt) / max(median_len, 1e-3)

    coords: List[Tuple[float, float]] = []
    for idx in range(mol.GetNumAtoms()):
        pos = conf.GetAtomPosition(idx)
        # CDXML Y increases downward
        coords.append((pos.x * scale, -pos.y * scale))

    xs = [c[0] for c in coords] or [0.0]
    ys = [c[1] for c in coords] or [0.0]
    ox = 72.0 - min(xs)
    oy = 72.0 - min(ys)
    coords = [(x + ox, y + oy) for x, y in coords]

    w_pt = max(140.0, (max(xs) - min(xs)) + 144.0)
    h_pt = max(120.0, (max(ys) - min(ys)) + 144.0)

    r_hex = color_hex.lstrip("#")
    cr = int(r_hex[0:2], 16) if len(r_hex) == 6 else 0
    cg = int(r_hex[2:4], 16) if len(r_hex) == 6 else 0
    cb = int(r_hex[4:6], 16) if len(r_hex) == 6 else 0

    lines: List[str] = [
        '<?xml version="1.0" encoding="UTF-8" ?>',
        '<!DOCTYPE CDXML SYSTEM "http://www.cambridgesoft.com/xml/cdxml.dtd" >',
        (
            f'<CDXML CreationProgram="Academic PPT Studio" BondLength="{bond_length_pt:.2f}" '
            'LineWidth="0.60" BoldWidth="2.00" BondSpacing="18" ChainAngle="120" '
            'LabelFont="3" LabelSize="10" LabelFace="96">'
        ),
        '  <colortable>',
        '    <color r="1" g="1" b="1"/>',
        '    <color r="0" g="0" b="0"/>',
        f'    <color r="{cr / 255.0:.4f}" g="{cg / 255.0:.4f}" b="{cb / 255.0:.4f}"/>',
        '  </colortable>',
        '  <fonttable>',
        '    <font id="3" charset="iso-8859-1" name="Arial"/>',
        '  </fonttable>',
        f'  <page id="1" BoundingBox="0 0 {w_pt:.2f} {h_pt:.2f}">',
        '    <fragment id="2">',
    ]

    next_id = 10
    atom_id_map: Dict[int, int] = {}
    for idx, atom in enumerate(mol.GetAtoms()):
        nid = next_id
        next_id += 1
        atom_id_map[idx] = nid
        ax, ay = coords[idx]
        elem = atom.GetAtomicNum()
        sym = atom.GetSymbol()
        charge = atom.GetFormalCharge()
        total_h = atom.GetTotalNumHs()
        if elem == 6 and charge == 0:
            lines.append(f'      <n id="{nid}" p="{ax:.2f} {ay:.2f}"/>')
        else:
            label = sym
            if total_h == 1:
                label += "H"
            elif total_h > 1:
                label += f"H{total_h}"
            if charge > 0:
                label += "+" if charge == 1 else f"+{charge}"
            elif charge < 0:
                label += "-" if charge == -1 else f"{charge}"
            esc_lbl = html.escape(label)
            lines.append(
                f'      <n id="{nid}" p="{ax:.2f} {ay:.2f}" Element="{elem}" NumHydrogens="{total_h}">'
                f'<t p="{ax:.2f} {ay:.2f}"><s font="3" size="10" face="96">{esc_lbl}</s></t></n>'
            )

    for b in mol.GetBonds():
        bid = next_id
        next_id += 1
        b_id = atom_id_map[b.GetBeginAtomIdx()]
        e_id = atom_id_map[b.GetEndAtomIdx()]
        btype = b.GetBondType()
        order_attr = ""
        if btype == Chem.BondType.DOUBLE:
            order_attr = ' Order="2"'
        elif btype == Chem.BondType.TRIPLE:
            order_attr = ' Order="3"'
        elif btype == Chem.BondType.AROMATIC:
            order_attr = ' Order="1.5"'
        disp_attr = ""
        bdir = b.GetBondDir()
        if bdir == Chem.BondDir.BEGINWEDGE:
            disp_attr = ' Display="WedgeBegin"'
        elif bdir == Chem.BondDir.BEGINDASH:
            disp_attr = ' Display="WedgedHashBegin"'
        lines.append(f'      <b id="{bid}" B="{b_id}" E="{e_id}"{order_attr}{disp_attr}/>')

    lines.extend([
        '    </fragment>',
        '  </page>',
        '</CDXML>',
    ])

    out_p = Path(output_cdxml)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text("\n".join(lines), encoding="utf-8")
    return out_p
