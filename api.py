from typing import Dict, Optional
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()
domain = os.environ["domain"]


def getMapData(mapName, apiKey: str, cache_folder: str) -> Optional[Dict]:
    path = f"{cache_folder}/{mapName}.json"
    if not os.path.exists(path):
        print(f"getting map data for {mapName}")
        try:
            resp = requests.get(
                f"{domain}/api/Game/getMapData?mapName={mapName}",
                headers={"x-api-key": apiKey},
            )
            resp.raise_for_status()
        except:
            print(resp)
            return None
        else:
            with open(path, "w", encoding="utf8") as f:
                json.dump(resp.json(), f, indent=4)
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)


def getGeneralData(cache_folder: str) -> Optional[Dict]:
    path = f"{cache_folder}/general.json"
    if not os.path.exists(path):
        print("getting general data")
        try:
            resp = requests.get(f"{domain}/api/Game/getGeneralGameData")
            resp.raise_for_status()
        except:
            print(resp)
            return None
        else:
            with open(path, "w", encoding="utf8") as f:
                json.dump(resp.json(), f, indent=4)
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)


def getGame(id_: str) -> Optional[Dict]:
    try:
        resp = requests.get(f"{domain}/api/Game/getGameData?gameId={id_}")
        resp.raise_for_status()
    except:
        print(resp)
        return None
    else:
        return resp.json()


def submit(mapName: str, solution: Dict, apiKey: str) -> Optional[Dict]:
    try:
        resp = requests.post(
            f"{domain}/api/Game/submitSolution?mapName={mapName}",
            headers={"x-api-key": apiKey},
            json=solution,
        )
        resp.raise_for_status()
    except:
        print(resp)
        return None
    else:
        return resp.json()
