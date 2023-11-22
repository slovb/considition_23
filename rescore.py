import os
import sys
import json

from dotenv import load_dotenv

from data_keys import (
    ScoringKeys as SK,
)
from original_scoring import calculateScore
from settings import Settings
from submit import load_game, get_solution

from api import getGeneralData, getMapData

load_dotenv()
apiKey = os.environ["apiKey"]


def verify(id: str) -> None:
    game = load_game(id)
    mapName = game[SK.mapName]
    ##Get map data from Considition endpoint
    mapEntity = getMapData(mapName, apiKey, Settings.cache_folder)
    ##Get non map specific data from Considition endpoint
    generalData = getGeneralData(Settings.cache_folder)
    solution = get_solution(game)
    scoredSolution = calculateScore(mapName, solution, mapEntity, generalData)
    if scoredSolution:
        print(json.dumps(scoredSolution, indent=4))
        print("-" * 80)
        print(f"id: {scoredSolution[SK.gameId]}")
        print(f"Score: {json.dumps(scoredSolution[SK.gameScore], indent=4)}")
        total = scoredSolution[SK.gameScore][SK.total]
        print("Total: {:,}".format(int(total)))


if __name__ == "__main__":
    if len(sys.argv) == 2:
        verify(sys.argv[1])
    else:
        print("Wrong number of arguments")
