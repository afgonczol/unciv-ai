import json
from typing import Dict, Any, List, Optional

class Civilopedia:
    """
    In-engine Civilopedia knowledge manager for Unciv AI.
    Queries the authoritative active in-memory Ruleset from UncivBridge,
    ensuring 100% fidelity to active rules (Vanilla vs. Gods & Kings vs. Mods).
    """

    def __init__(self, engine=None):
        self.engine = engine
        self._cache: Dict[str, Any] = {}
        self._is_loaded = False

    def load_active_ruleset(self, force_reload: bool = False):
        """
        Fetches and caches the full active ruleset from the game engine.
        """
        if self._is_loaded and not force_reload:
            return

        if not self.engine:
            return

        try:
            data = self.engine.query_civilopedia(category="all")
            if data:
                self._cache = data
                self._is_loaded = True
        except Exception:
            pass

    def get_unit(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up unit stats (combat strength, movement, cost, uniques)."""
        self.load_active_ruleset()
        units = self._cache.get("units", [])
        for u in units:
            if u.get("name", "").lower() == name.lower():
                return u
        # Fallback to direct query if not in cache
        if self.engine:
            res = self.engine.query_civilopedia(category="unit", name=name)
            return res.get("item")
        return None

    def get_building(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up building/wonder stats (yields, cost, maintenance, uniques)."""
        self.load_active_ruleset()
        buildings = self._cache.get("buildings", [])
        for b in buildings:
            if b.get("name", "").lower() == name.lower():
                return b
        if self.engine:
            res = self.engine.query_civilopedia(category="building", name=name)
            return res.get("item")
        return None

    def get_tech(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up tech cost, era, prerequisites, and what it unlocks."""
        self.load_active_ruleset()
        techs = self._cache.get("technologies", [])
        for t in techs:
            if t.get("name", "").lower() == name.lower():
                return t
        if self.engine:
            res = self.engine.query_civilopedia(category="tech", name=name)
            return res.get("item")
        return None

    def get_policy(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up policy branch and uniques."""
        self.load_active_ruleset()
        policies = self._cache.get("policies", [])
        for p in policies:
            if p.get("name", "").lower() == name.lower():
                return p
        if self.engine:
            res = self.engine.query_civilopedia(category="policy", name=name)
            return res.get("item")
        return None

    def get_civilization(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up civilization traits, unique units, and unique structures."""
        self.load_active_ruleset()
        nations = self._cache.get("nations", [])
        for n in nations:
            if n.get("name", "").lower() == name.lower():
                return n
        if self.engine:
            res = self.engine.query_civilopedia(category="nation", name=name)
            return res.get("item")
        return None

    def get_civ_dossier(self, civ_name: str) -> Dict[str, Any]:
        """
        Generates a Turn 0 Civilization Strategic Dossier summarizing unique abilities,
        unique units, and unique buildings for the active civilization.
        """
        civ = self.get_civilization(civ_name) or {}
        unique_units = []
        for u_name in civ.get("unique_units", []):
            u_info = self.get_unit(u_name)
            if u_info:
                unique_units.append({
                    "name": u_name,
                    "replaces": u_info.get("replaces"),
                    "strength": u_info.get("strength"),
                    "ranged_strength": u_info.get("ranged_strength"),
                    "movement": u_info.get("movement"),
                    "uniques": u_info.get("uniques", [])
                })
            else:
                unique_units.append({"name": u_name})

        unique_buildings = []
        for b_name in civ.get("unique_buildings", []):
            b_info = self.get_building(b_name)
            if b_info:
                unique_buildings.append({
                    "name": b_name,
                    "replaces": b_info.get("replaces"),
                    "cost": b_info.get("cost"),
                    "maintenance": b_info.get("maintenance"),
                    "uniques": b_info.get("uniques", [])
                })
            else:
                unique_buildings.append({"name": b_name})

        return {
            "civilization": civ_name,
            "leader": civ.get("leader_name", "Unknown"),
            "unique_ability": civ.get("unique_name", ""),
            "unique_ability_effects": civ.get("uniques", []),
            "unique_units": unique_units,
            "unique_buildings": unique_buildings,
            "unique_improvements": civ.get("unique_improvements", [])
        }

    def annotate_item(self, category: str, name: str) -> str:
        """
        Generates a compact, high-value inline annotation string (e.g. for prompt briefing).
        Examples:
          - "Library (75p: +1 Science / 2 Pop, 1g upkeep)"
          - "Colosseum (100p: +2 Happiness, 1g upkeep)"
          - "Legion (75p: 17 Str, 2 Move, builds Roads & Forts)"
          - "Pottery (25 sci: Unlocks Granary, Shrine)"
        """
        cat = category.lower()
        clean_name = name.split(" (")[0].strip()

        if cat in ("unit", "units"):
            u = self.get_unit(clean_name)
            if not u:
                return name
            parts = []
            cost = u.get("cost", 0)
            if cost > 0:
                parts.append(f"{cost}p")
            strn = u.get("strength", 0)
            r_strn = u.get("ranged_strength", 0)
            if r_strn > 0:
                parts.append(f"{r_strn} Ranged Str")
            elif strn > 0:
                parts.append(f"{strn} Str")
            mov = u.get("movement", 0)
            if mov > 0:
                parts.append(f"{mov} Move")
            uniques = u.get("uniques", [])
            for un in uniques[:2]:
                parts.append(un.replace("[", "").replace("]", ""))
            return f"{clean_name} ({', '.join(parts)})" if parts else clean_name

        elif cat in ("building", "buildings", "wonder", "wonders"):
            b = self.get_building(clean_name)
            if not b:
                return name
            parts = []
            cost = b.get("cost", 0)
            if cost > 0:
                parts.append(f"{cost}p")
            stats = []
            def fmt_val(v):
                if isinstance(v, (int, float)):
                    return int(v) if v == int(v) else round(v, 1)
                return v

            if b.get("science", 0) > 0:
                stats.append(f"+{fmt_val(b['science'])} Science")
            if b.get("culture", 0) > 0:
                stats.append(f"+{fmt_val(b['culture'])} Culture")
            if b.get("food", 0) > 0:
                stats.append(f"+{fmt_val(b['food'])} Food")
            if b.get("production", 0) > 0:
                stats.append(f"+{fmt_val(b['production'])} Prod")
            if b.get("gold", 0) > 0:
                stats.append(f"+{fmt_val(b['gold'])} Gold")
            if b.get("happiness", 0) > 0:
                stats.append(f"+{fmt_val(b['happiness'])} Happiness")
            if b.get("faith", 0) > 0:
                stats.append(f"+{fmt_val(b['faith'])} Faith")
            if b.get("maintenance", 0) > 0:
                stats.append(f"{fmt_val(b['maintenance'])}g upkeep")
            for un in b.get("uniques", [])[:2]:
                stats.append(un.replace("[", "").replace("]", ""))
            all_parts = parts + stats
            return f"{clean_name} ({', '.join(all_parts)})" if all_parts else clean_name

        elif cat in ("tech", "techs", "technology", "technologies"):
            t = self.get_tech(clean_name)
            if not t:
                return name
            unlocks = []
            if t.get("unlocked_units"):
                unlocks.extend(t["unlocked_units"][:2])
            if t.get("unlocked_buildings"):
                unlocks.extend(t["unlocked_buildings"][:2])
            if t.get("unlocked_wonders"):
                unlocks.extend(t["unlocked_wonders"][:1])
            cost_str = f"{t.get('cost', 0)} sci"
            unlock_str = f"Unlocks {', '.join(unlocks)}" if unlocks else ""
            parts = [cost_str]
            if unlock_str:
                parts.append(unlock_str)
            return f"{clean_name} ({', '.join(parts)})"

        elif cat in ("policy", "policies"):
            p = self.get_policy(clean_name)
            if not p:
                return name
            uniques = [u.replace("[", "").replace("]", "") for u in p.get("uniques", [])[:2]]
            return f"{clean_name} ({', '.join(uniques)})" if uniques else clean_name

        return name

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search across all active ruleset items matching keyword."""
        self.load_active_ruleset()
        results = []
        q = query.lower().strip()
        for u in self._cache.get("units", []):
            if q in u.get("name", "").lower() or any(q in un.lower() for un in u.get("uniques", [])):
                results.append({"category": "unit", **u})
        for b in self._cache.get("buildings", []):
            if q in b.get("name", "").lower() or any(q in un.lower() for un in b.get("uniques", [])):
                results.append({"category": "building", **b})
        for t in self._cache.get("technologies", []):
            if q in t.get("name", "").lower() or any(q in un.lower() for un in t.get("uniques", [])):
                results.append({"category": "technology", **t})
        for p in self._cache.get("policies", []):
            if q in p.get("name", "").lower() or any(q in un.lower() for un in p.get("uniques", [])):
                results.append({"category": "policy", **p})
        return results
