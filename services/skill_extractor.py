# services/skill_extractor.py
import re
from config.config_loader import SKILLS_DICT

def _build_canonical_map(skills_cfg):
    canon_map = {}
    if not skills_cfg:
        return {}
    if isinstance(skills_cfg, dict) and "skills" in skills_cfg:
        skills = skills_cfg.get("skills", [])
        norm = {k.lower(): v for k, v in skills_cfg.get("normalization_map", {}).items()}
        for s in skills:
            canon_map.setdefault(s, set()).add(s.lower())
        for variant, canon in norm.items():
            canon_map.setdefault(canon, set()).add(variant.lower())
            canon_map.setdefault(canon, set()).add(canon.lower())
    else:
        # fallback: old mapping style
        norm = {k.lower(): v for k, v in (skills_cfg or {}).items()}
        for variant, canon in norm.items():
            canon_map.setdefault(canon, set()).add(variant.lower())
            canon_map.setdefault(canon, set()).add(canon.lower())
    for canon, s in list(canon_map.items()):
        s.add(canon.lower())
        canon_map[canon] = set(s)
    return canon_map

def extract_skills(text: str):
    if not text:
        return []
    text_l = text.lower()
    canon_map = _build_canonical_map(SKILLS_DICT)
    matches = []
    for canon, syns in canon_map.items():
        earliest = None
        for syn in sorted(syns, key=lambda x: -len(x)):
            syn_re = re.escape(syn).replace(r'\ ', r'\s+')
            # allow dots and + inside token by not breaking them
            m = re.search(r'(?<!\w)'+syn_re+r'(?!\w)', text_l)
            if m:
                pos = m.start()
                if earliest is None or pos < earliest:
                    earliest = pos
        if earliest is not None:
            matches.append((earliest, canon))
    matches.sort(key=lambda x: x[0])
    seen = set(); out = []
    for _, canon in matches:
        if canon not in seen:
            seen.add(canon); out.append(canon)
    return out
