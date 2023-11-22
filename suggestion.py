from dataclasses import dataclass
from typing import Dict

from data_keys import ScoringKeys as SK


@dataclass
class STag:
    start = "start"
    add = "add"
    change = "change"
    group = "group"


def get_total(score: Dict[str, Dict]) -> float:
    return score[SK.gameScore][SK.total]


class Suggestion:
    def __init__(self, change: Dict[str, Dict], tag: str) -> None:
        self.change = change
        self.tag = tag


class ScoredSuggestion:
    def __init__(self, suggestion: Suggestion, score: Dict) -> None:
        self.change = suggestion.change
        self.tag = suggestion.tag
        self.score = score
        self.total = get_total(score)

    def get_game_id(self) -> str:
        if self.score is None:
            raise SystemError("Missing score")
        return self.score[SK.gameId]
