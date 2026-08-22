"""
Strategic AI Advisor & Heuristics Engine for Unciv.
Provides domain-specific tactical analysis, expansion planning, tech pathfinding,
military threat evaluation, and dynamic user directive parsing.
"""

from typing import Dict, Any, List, Optional, Tuple
import math

class StrategicAdvisor:
    """
    Analyzes game state and map topology to provide high-level strategic guidance
    and actionable recommendations for LLM decision-making.
    """

    def __init__(self):
        self.user_directive: str = ""
        self.directive_weights: Dict[str, float] = {
            "science": 1.0,
            "military": 1.0,
            "culture": 1.0,
            "economy": 1.0,
            "expansion": 1.0,
            "diplomacy": 1.0
        }
        self.target_civilizations: List[str] = []
        self.target_tags: List[str] = []

    def set_directive(self, directive: str):
        """
        Sets a high-level strategic directive from the user/player
        (e.g., 'Focus on science and be aggressive against players that control European nations')
        and calculates strategic weights and focus tags.
        """
        self.user_directive = directive.strip()
        self._parse_directive(self.user_directive)

    def _parse_directive(self, directive: str):
        """
        Parses natural language directives into weights and targeting rules.
        """
        d_lower = directive.lower()

        # Reset base weights
        self.directive_weights = {
            "science": 1.0,
            "military": 1.0,
            "culture": 1.0,
            "economy": 1.0,
            "expansion": 1.0,
            "diplomacy": 1.0
        }
        self.target_civilizations = []
        self.target_tags = []

        if not directive:
            return

        # Science focus
        if any(w in d_lower for w in ["science", "research", "technology", "tech", "scientific"]):
            self.directive_weights["science"] = 2.5

        # Military / Aggression focus
        if any(w in d_lower for w in ["military", "aggressive", "war", "conquer", "attack", "domination", "crush"]):
            self.directive_weights["military"] = 2.5

        # Culture / Policies
        if any(w in d_lower for w in ["culture", "cultural", "policy", "policies", "wonder", "wonders"]):
            self.directive_weights["culture"] = 2.0

        # Economy / Gold
        if any(w in d_lower for w in ["gold", "economy", "economic", "wealth", "commerce", "trade"]):
            self.directive_weights["economy"] = 2.0

        # Expansion / Settle
        if any(w in d_lower for w in ["expand", "settle", "expansion", "cities", "growth", "colonize"]):
            self.directive_weights["expansion"] = 2.0

        # Regional / National targeting
        european_nations = ["rome", "greece", "england", "france", "germany", "russia", "spain", "austria", "poland", "byzantium", "dutch", "carthage", "celtic"]
        asian_nations = ["china", "japan", "india", "mongolia", "korea", "persia", "arabia", "ottoman", "babylon", "siam"]
        american_nations = ["america", "aztec", "maya", "inca", "iroquois", "brazil", "shoshone"]

        if "european" in d_lower or "europe" in d_lower:
            self.target_tags.append("European")
            self.target_civilizations.extend([c.capitalize() for c in european_nations])
        if "asian" in d_lower or "asia" in d_lower:
            self.target_tags.append("Asian")
            self.target_civilizations.extend([c.capitalize() for c in asian_nations])
        if "american" in d_lower or "america" in d_lower:
            self.target_tags.append("American")
            self.target_civilizations.extend([c.capitalize() for c in american_nations])

        # Explicit civ names
        all_civs = european_nations + asian_nations + american_nations
        for civ in all_civs:
            if civ in d_lower and civ.capitalize() not in self.target_civilizations:
                self.target_civilizations.append(civ.capitalize())

    def analyze(self, state: Dict[str, Any], map_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Runs comprehensive analysis on current state and returns structured strategic advice.
        """
        military = self._analyze_military(state, map_data)
        expansion = self._analyze_expansion(state, map_data)
        bottlenecks = self._detect_bottlenecks(state)
        rec_focus = self._get_recommended_focus(state, military, bottlenecks)

        analysis = {
            "user_directive": self.user_directive or "Default balanced grand strategy",
            "strategic_weights": self.directive_weights,
            "target_civs": self.target_civilizations,
            "recommended_focus": rec_focus,
            "military_assessment": military,
            "expansion_analysis": expansion,
            "technology_roadmap": self._analyze_technology(state),
            "city_management_advice": self._analyze_cities(state),
            "bottlenecks_and_alerts": bottlenecks,
            "suggested_actions": []
        }

        # Generate prioritized action list
        analysis["suggested_actions"] = self._generate_suggested_actions(analysis, state)
        return analysis

    def _get_recommended_focus(self, state: Optional[Dict[str, Any]] = None,
                                military: Optional[Dict[str, Any]] = None,
                                bottlenecks: Optional[List[str]] = None) -> str:
        """
        Dynamically calculates active strategic focus:
        1. Emergency live crisis overrides (Severe Unhappiness, Bankruptcy, Total War)
        2. Configured player strategic directives (Science, Domination, Culture, Expansion)
        3. Progression phase heuristics (Early Scouting, Midgame Infrastructure)
        """
        # 1. Emergency Live Situation Overrides
        if state:
            stats = state.get("stats", {})
            happiness = stats.get("happiness", 0)
            gold = stats.get("gold", 0)
            gpt = stats.get("gold_per_turn", 0)

            # Severe happiness crisis
            if happiness <= -10:
                return "Emergency: Civil Unrest & Luxuries"
            elif happiness < 0:
                return "Happiness Stabilization & Luxuries"

            # Economic bankruptcy
            if gold <= 0 and gpt < -2:
                return "Economic Solvency & Debt Relief"

        if military:
            wars = military.get("active_wars", [])
            threat = military.get("threat_level", "Low")
            if len(wars) > 0:
                if self.directive_weights.get("military", 1.0) > 1.5:
                    return "Total War & Conquest"
                return "Military Defense & War Mobilization"
            elif "Moderate" in threat or "High" in threat:
                return "Border Defense & Barbarian Suppression"

        # 2. Player Directive Focus
        weights = self.directive_weights
        top_focus = max(weights.items(), key=lambda x: x[1])
        if top_focus[1] > 1.2:
            f_name = top_focus[0].lower()
            if f_name == "science":
                return "Scientific Advancement & Tech Leap"
            elif f_name == "military":
                return "Military Mobilization & Domination"
            elif f_name == "culture":
                return "Cultural Prosperity & Wonder Building"
            elif f_name == "economy":
                return "Commercial Empire & Wealth Generation"
            elif f_name == "expansion":
                return "Rapid Imperial Expansion & Settlement"
            return top_focus[0].capitalize()

        # 3. Dynamic Era / Progression Phase Defaults
        if state:
            turn = state.get("turn", 0)
            cities = state.get("cities", [])
            if turn < 20 and len(cities) <= 1:
                return "Early Exploration & Capital Growth"
            elif len(cities) >= 4 and state.get("stats", {}).get("happiness", 0) > 5:
                return "Imperial Infrastructure & Development"

        return "Balanced Growth & Exploration"

    def _analyze_military(self, state: Dict[str, Any], map_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        units = state.get("units", [])
        mil_units = [u for u in units if u.get("is_military")]
        civ_units = [u for u in units if u.get("is_civilian")]

        known_civs = state.get("known_civilizations", [])
        wars = [c["civ_name"] for c in known_civs if c.get("is_at_war")]

        # Count nearby threats if map available
        threat_count = 0
        if map_data and "tiles" in map_data:
            for t in map_data["tiles"]:
                if t.get("military_unit") and not any(my_civ in t.get("military_unit", "") for my_civ in [state.get("active_civ", ""), "Barbarians"]):
                    threat_count += 1
                elif "Barbarian" in t.get("military_unit", ""):
                    threat_count += 1

        threat_level = "Low"
        if len(wars) > 0:
            threat_level = "High (Active War)"
        elif threat_count >= 3:
            threat_level = "Moderate (Enemies/Barbarians sighted)"

        need_more_military = len(mil_units) < len(state.get("cities", [])) * 2 or len(wars) > 0 or self.directive_weights["military"] > 1.5

        # Civ targeting
        targets_at_war = [c for c in wars if c in self.target_civilizations]
        potential_targets = [c["civ_name"] for c in known_civs if c["civ_name"] in self.target_civilizations and not c.get("is_at_war")]

        return {
            "military_units_count": len(mil_units),
            "civilian_units_count": len(civ_units),
            "threat_level": threat_level,
            "active_wars": wars,
            "priority_targets": self.target_civilizations,
            "target_civs_in_game": [c["civ_name"] for c in known_civs if c["civ_name"] in self.target_civilizations],
            "should_produce_military": need_more_military,
            "suggested_targets_to_attack": targets_at_war or potential_targets
        }

    def _analyze_expansion(self, state: Dict[str, Any], map_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        cities = state.get("cities", [])
        units = state.get("units", [])
        settlers = [u for u in units if u.get("name") == "Settler"]
        happiness = state.get("stats", {}).get("happiness", 0)

        can_expand = happiness >= 4
        candidate_spots = []

        if map_data and "tiles" in map_data:
            # Score tiles for settlement
            for tile in map_data["tiles"]:
                if tile.get("city"):
                    continue
                score = 0
                x, y = tile.get("x", 0), tile.get("y", 0)
                terrain = tile.get("terrain", "")
                features = tile.get("features", [])
                resource = tile.get("resource")

                if "Mountain" in terrain or "Ocean" in terrain or "Coast" in terrain:
                    continue

                if "River" in features or "Freshwater" in features:
                    score += 4
                if "Hills" in terrain:
                    score += 3
                if "Plains" in terrain or "Grassland" in terrain:
                    score += 2
                if resource:
                    score += 6
                if "Forest" in features:
                    score += 1

                # Distance penalty from current cities
                for c in cities:
                    loc = c.get("location", [0, 0])
                    dist = max(abs(x - loc[0]), abs(y - loc[1]))
                    if dist < 3: # Too close
                        score -= 10
                    elif dist <= 6:
                        score += 3

                if score > 5:
                    candidate_spots.append({
                        "x": x,
                        "y": y,
                        "score": score,
                        "terrain": terrain,
                        "resource": resource
                    })

            candidate_spots.sort(key=lambda s: s["score"], reverse=True)

        return {
            "city_count": len(cities),
            "settlers_available": len(settlers),
            "happiness_allows_expansion": can_expand,
            "recommended_next_settle_spots": candidate_spots[:3]
        }

    def _analyze_technology(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tech_info = state.get("technology", {})
        cur_tech = tech_info.get("current_tech", "None")
        researchable = tech_info.get("researchable_techs", [])

        # Score researchable techs based on strategic weights
        scored_techs = []
        for t in researchable:
            name = t.get("name", "")
            cost = t.get("cost", 100)
            score = 10.0

            # Science techs
            if name in ["Writing", "Philosophy", "Education", "Scientific Theory"]:
                score += 8.0 * self.directive_weights["science"]
            # Military techs
            elif name in ["Archery", "Bronze Working", "Iron Working", "Horseback Riding", "Construction", "Machinery"]:
                score += 8.0 * self.directive_weights["military"]
            # Growth / Economy techs
            elif name in ["Pottery", "Animal Husbandry", "Calendar", "Trapping", "Wheel", "Currency"]:
                score += 6.0 * (self.directive_weights["economy"] + self.directive_weights["expansion"]) / 2

            # Lower cost gives slight preference
            score += max(0, 10 - cost / 10)

            scored_techs.append({
                "name": name,
                "turns": t.get("turns", 0),
                "strategic_score": round(score, 1),
                "category": self._categorize_tech(name)
            })

        scored_techs.sort(key=lambda x: x["strategic_score"], reverse=True)

        return {
            "current_tech": cur_tech,
            "turns_left": tech_info.get("turns_to_finish", 0),
            "recommended_next_techs": scored_techs[:4]
        }

    def _categorize_tech(self, name: str) -> str:
        if name in ["Writing", "Philosophy", "Education", "Scientific Theory", "Pottery", "Theology"]:
            return "Science & Faith"
        if name in ["Archery", "Bronze Working", "Iron Working", "Horseback Riding", "Machinery", "Steel"]:
            return "Military"
        if name in ["Wheel", "Currency", "Banking", "Economics", "Trapping"]:
            return "Economy"
        return "General Development"

    def _analyze_cities(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        cities = state.get("cities", [])
        city_advice = []

        for c in cities:
            name = c.get("name", "")
            cur_prod = c.get("current_construction", "")
            turns = c.get("turns_to_finish", 0)
            pop = c.get("population", 1)
            buildable_units = c.get("buildable_units", [])
            buildable_bldgs = c.get("buildable_buildings", [])

            suggestions = []
            if not cur_prod or cur_prod == "":
                # Pick best construction
                if pop <= 2 and any("Monument" in b for b in buildable_bldgs):
                    suggestions.append("Monument (Early culture & border expansion)")
                elif any("Library" in b for b in buildable_bldgs) and self.directive_weights["science"] >= 1.5:
                    suggestions.append("Library (Boost science output)")
                elif self.directive_weights["military"] >= 1.8 and buildable_units:
                    u_name = buildable_units[0].split(" (")[0].strip()
                    suggestions.append(f"{u_name} (Military build-up)")
                elif any("Worker" in u for u in buildable_units) and pop >= 2:
                    suggestions.append("Worker (Improve tiles)")
                elif any("Granary" in b for b in buildable_bldgs):
                    suggestions.append("Granary (Food & population growth)")
                elif buildable_bldgs:
                    b_name = buildable_bldgs[0].split(" (")[0].strip()
                    suggestions.append(f"{b_name} (Building infrastructure)")
                elif buildable_units:
                    u_name = buildable_units[0].split(" (")[0].strip()
                    suggestions.append(f"{u_name} (Unit)")

            city_advice.append({
                "name": name,
                "population": pop,
                "current_construction": cur_prod or "IDLE (Needs production order!)",
                "turns_left": turns,
                "food_per_turn": c.get("food_per_turn", 0),
                "production_per_turn": c.get("production_per_turn", 0),
                "recommended_constructions": suggestions
            })

        return city_advice

    def _detect_bottlenecks(self, state: Dict[str, Any]) -> List[str]:
        alerts = []
        stats = state.get("stats", {})
        happiness = stats.get("happiness", 0)
        gold = stats.get("gold", 0)
        gpt = stats.get("gold_per_turn", 0)

        if happiness < 0:
            alerts.append(f"Unhappiness deficit ({happiness}): City growth and combat strength reduced!")
        if gpt < 0 and gold < 20:
            alerts.append(f"Gold bleed ({gpt} gpt, treasury: {gold}): Danger of unit disbandment or science penalty!")

        for c in state.get("cities", []):
            if not c.get("current_construction"):
                alerts.append(f"City [{c.get('name')}] has NO active production item!")

        tech = state.get("technology", {})
        if not tech.get("current_tech") or tech.get("current_tech") == "None":
            alerts.append("No active technology is currently being researched!")

        for u in state.get("units", []):
            if u.get("is_idle") and u.get("movement", 0) > 0:
                alerts.append(f"Unit {u.get('name')} (ID {u.get('id')}) is idle at {u.get('location')}.")

        return alerts

    def _generate_suggested_actions(self, analysis: Dict[str, Any], state: Dict[str, Any]) -> List[str]:
        actions = []
        tech_advice = analysis.get("technology_roadmap", {})
        if tech_advice.get("current_tech") == "None" and tech_advice.get("recommended_next_techs"):
            best_tech = tech_advice["recommended_next_techs"][0]["name"]
            actions.append(f"Choose Technology: Research '{best_tech}' to align with {analysis['recommended_focus']} strategy.")

        # City orders
        for ca in analysis.get("city_management_advice", []):
            if "IDLE" in ca.get("current_construction", ""):
                recs = ca.get("recommended_constructions") or ["Scout"]
                rec = recs[0]
                actions.append(f"City Order: Set production in '{ca['name']}' to '{rec.split(' ')[0]}'.")

        # Settlers
        units = state.get("units", [])
        settler = next((u for u in units if u.get("name") == "Settler"), None)
        if settler:
            spots = analysis.get("expansion_analysis", {}).get("recommended_next_settle_spots", [])
            if spots:
                best = spots[0]
                actions.append(f"Expansion: Move Settler (ID {settler['id']}) to ({best['x']}, {best['y']}) or found city.")
            else:
                actions.append(f"Expansion: Found city with Settler (ID {settler['id']}) at current location.")

        # Military aggression against target civs
        mil = analysis.get("military_assessment", {})
        if mil.get("target_civs_in_game"):
            for t in mil["target_civs_in_game"]:
                if t in mil.get("active_wars", []):
                    actions.append(f"Warfare: Direct military units to assault {t} cities and units!")
                elif self.directive_weights["military"] >= 2.0:
                    actions.append(f"Diplomacy / War: Prepare military forces near {t} borders for declaration.")

        if not actions:
            actions.append("Explore surrounding terrain with scouts/warriors and advance to next turn.")

        return actions
