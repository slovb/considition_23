from dataclasses import dataclass
from typing import Dict
import typing

from data_keys import ScoringKeys as SK


@dataclass
class STag:
    start = "start"
    add = "add"
    change = "change"
    group = "group"


def get_total(score: Dict) -> float:
    return score[SK.gameScore][SK.total]


class Suggestion:
    def __init__(self, change: dict, tag: str) -> None:
        self.change = change
        self.tag = tag
        self.score: Dict[str, typing.any] = {}
        self.total = 0.0

    def has_score(self) -> bool:
        return self.score is not None

    def set_score(self, score: Dict) -> None:
        self.score = score
        self.total = get_total(score)

    def has_total(self) -> bool:
        return self.total is not None

    def get_game_id(self) -> str:
        if self.score is None:
            raise SystemError("Missing score")
        return self.score[SK.gameId]


# TODO migrate to this, don't subclass
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
