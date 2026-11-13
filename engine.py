"""Fogbound: deterministic state for a small AI-narrated adventure. Python 3.10+."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import copy

LOCATIONS = {"hall": "雾港候车厅", "office": "封闭值班室", "platform": "旧站台", "train": "第七车厢"}
ITEMS = {"ticket": "一张旧车票", "lamp": "手电筒", "key": "铜钥匙", "manifest": "失踪者名单"}
ACTIONS = {
    "look": "环顾四周", "talk": "向守站人询问末班车", "lamp": "拿起长椅上的手电筒",
    "office": "用钥匙打开值班室", "search": "用手电检查值班室抽屉", "hall": "返回候车厅",
    "platform": "走向旧站台", "board": "持车票登车离开", "reveal": "向列车员出示失踪者名单",
    "unknown": "尝试一个尚未支持的行动",
}
INTRO = "雨水沿着站牌滴落，整座车站只剩一盏灯。你攥着一张泛黄的车票，票面写着：雾港，23:47。长椅上放着一支手电筒，守站人站在关闭的值班室门旁。他看了一眼你的车票，低声说：‘最后一班车，别只顾着上去。’"

@dataclass
class State:
    location: str = "hall"
    inventory: list[str] = field(default_factory=lambda: ["ticket"])
    clues: list[str] = field(default_factory=list)
    turn: int = 0
    ending: str | None = None

    def public(self) -> dict[str, Any]:
        return {**asdict(self), "location_name": LOCATIONS[self.location],
                "inventory_names": [ITEMS[x] for x in self.inventory]}

    @classmethod
    def from_dict(cls, raw: dict) -> "State":
        if not isinstance(raw, dict): raise ValueError("存档不是对象")
        loc = raw.get("location", "hall")
        inventory = raw.get("inventory", ["ticket"])
        clues = raw.get("clues", [])
        turn = raw.get("turn", 0)
        ending = raw.get("ending")
        if loc not in LOCATIONS or not isinstance(inventory, list) or any(x not in ITEMS for x in inventory):
            raise ValueError("存档包含无效地点或物品")
        if len(inventory) != len(set(inventory)) or "ticket" not in inventory:
            raise ValueError("存档物品重复或缺少车票")
        if not isinstance(clues, list) or len(clues) > 20 or any(not isinstance(x, str) or len(x)>200 for x in clues):
            raise ValueError("线索格式错误")
        if type(turn) is not int or not 0 <= turn <= 1000 or ending not in (None, "escape", "truth"):
            raise ValueError("回合或结局无效")
        return cls(loc, list(inventory), list(clues), turn, ending)


def available(state: State) -> list[dict[str, str]]:
    if state.ending: return []
    ids = ["look"]
    if state.location == "hall":
        ids += ["talk"]
        if "lamp" not in state.inventory: ids += ["lamp"]
        ids += ["office", "platform"]
    elif state.location == "office": ids += ["search", "hall", "platform"]
    elif state.location == "platform": ids += ["board", "reveal", "hall"]
    return [{"id": a, "label": ACTIONS[a]} for a in ids]


def resolve(state: State, intent: str) -> tuple[State, dict[str, Any]]:
    """Return a new state. Model text is never executed and cannot edit inventory."""
    new = copy.deepcopy(state)
    event: dict[str, Any] = {"intent": intent, "accepted": False, "reason": "", "gained": [], "ending": None}
    if state.ending:
        event["reason"] = "故事已经结束。重新开始可以探索另一条结局。"
        return new, event
    if intent not in ACTIONS or intent == "unknown":
        event["reason"] = "这个动作没有对应的可执行规则；地点、背包和结局保持不变。可以描述探索、询问、取物、开门或登车。"
        return new, event
    if intent not in {a["id"] for a in available(state)}:
        event["reason"] = "你现在不在能执行这个动作的位置。"
        return new, event
    if intent == "office" and "key" not in state.inventory:
        event["reason"] = "值班室门锁着。你没有铜钥匙，门没有打开。"
        return new, event
    if intent == "search" and "lamp" not in state.inventory:
        event["reason"] = "抽屉藏在黑暗里。没有手电筒，你无法读清其中的纸张。"
        return new, event
    if intent == "reveal" and "manifest" not in state.inventory:
        event["reason"] = "你还没有找到失踪者名单，不能凭空向列车员出示它。"
        return new, event
    event["accepted"] = True
    new.turn += 1
    if intent == "look":
        event["reason"] = {"hall":"你看见守站人、长椅上的手电筒、上锁的值班室和通向站台的路。", "office":"你看见封闭的抽屉；名单可能藏在里面。", "platform":"末班列车停在旧站台，列车员正在验票。"}.get(state.location, "你环顾车厢。")
    elif intent == "talk":
        if "key" not in new.inventory:
            new.inventory.append("key"); event["gained"] = ["铜钥匙"]
            new.clues.append("守站人把铜钥匙交给你，让你去值班室找名单。")
            event["reason"] = "守站人交给你铜钥匙，提醒你检查值班室里的名单。"
        else: event["reason"] = "守站人提醒：钥匙已经在你手里；名单藏在值班室。没有再次获得钥匙。"
    elif intent == "lamp":
        if "lamp" not in new.inventory: new.inventory.append("lamp"); event["gained"] = ["手电筒"]
        event["reason"] = "你拿起长椅上的手电筒。"
    elif intent == "office": new.location = "office"; event["reason"] = "你用铜钥匙打开门，进入值班室；钥匙仍在背包里。"
    elif intent == "search":
        if "manifest" not in new.inventory:
            new.inventory.append("manifest"); event["gained"] = ["失踪者名单"]
            new.clues.append("名单写着：向列车员出示此页，才能让被遗忘的乘客回家。")
            event["reason"] = "你用手电照亮抽屉，找到失踪者名单。名单提示：到站台把它交给列车员。"
        else: event["reason"] = "抽屉已经空了。失踪者名单仍在你的背包里，没有重复获得物品。"
    elif intent == "hall": new.location = "hall"; event["reason"] = "你回到雾港候车厅，背包和线索保持不变。"
    elif intent == "platform": new.location = "platform"; event["reason"] = "你来到旧站台，列车员站在第七车厢门前。"
    elif intent == "board":
        new.location = "train"; new.ending = "escape"; event["ending"] = "escape"
        event["reason"] = "你持车票登上末班车，独自离开雾港。达成结局一：独自离站。未揭开失踪者名单的秘密。"
    elif intent == "reveal":
        new.location = "train"; new.ending = "truth"; event["ending"] = "truth"
        event["reason"] = "你向列车员出示失踪者名单。他为被遗忘的乘客打开第七车厢。你与他们一起离开。达成结局二：带他们回家。"
    return new, event


def validate_narration(text: str) -> bool:
    """Basic shape check, not a guarantee of semantic consistency."""
    return isinstance(text, str) and 25 <= len(text.strip()) <= 1000 and "<script" not in text.lower()
