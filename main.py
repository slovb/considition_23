import os
from typing import Optional
from dotenv import load_dotenv

from api import getGeneralData, getMapData
from data_keys import (
    MapNames as MN,
)


from regular_solver import RegularSolver
from sandbox_solver import SandboxSolver
from settings import Settings
from solver import Solver


load_dotenv()
apiKey = os.environ["apiKey"]


def main(mapName: Optional[str] = None) -> None:
    for folder in [Settings.game_folder, Settings.log_folder, Settings.cache_folder]:
        if not os.path.exists(folder):
            print(f"Creating folder {folder}")
            os.makedirs(folder)

    try:
        apiKey = os.environ["apiKey"]
    except Exception as e:
        raise SystemExit("Did you forget to create a .env file with the apiKey?")

    if not mapName:
        # User selct a map name
        print(f"1: {MN.stockholm}")
        print(f"2: {MN.goteborg}")
        print(f"3: {MN.malmo}")
        print(f"4: {MN.uppsala}")
        print(f"5: {MN.vasteras}")
        print(f"6: {MN.orebro}")
        print(f"7: {MN.london}")
        print(f"8: {MN.berlin}")
        print(f"9: {MN.linkoping}")
        print(f"10: {MN.sSandbox}")
        print(f"11: {MN.gSandbox}")
        option_ = input("Select the map you wish to play: ")

        match option_:
            case "1":
                mapName = MN.stockholm
            case "2":
                mapName = MN.goteborg
            case "3":
                mapName = MN.malmo
            case "4":
                mapName = MN.uppsala
            case "5":
                mapName = MN.vasteras
            case "6":
                mapName = MN.orebro
            case "7":
                mapName = MN.london
            case "8":
                mapName = MN.berlin
            case "9":
                mapName = MN.linkoping
            case "10":
                mapName = MN.sSandbox
            case "11":
                mapName = MN.gSandbox
            case _:
                print("Invalid choice.")

    if mapName:
        ##Get map data from Considition endpoint
        mapEntity = getMapData(mapName, apiKey, Settings.cache_folder)
        ##Get non map specific data from Considition endpoint
        generalData = getGeneralData(Settings.cache_folder)

        if mapEntity and generalData:
            solver: Solver
            if mapName in [MN.gSandbox, MN.sSandbox]:
                solver = SandboxSolver(mapName, mapEntity, generalData)
            else:
                solver = RegularSolver(mapName, mapEntity, generalData)
            solver.initialize()
            solver.solve()

            formatted_best = "{:,}".format(int(solver.best)).replace(",", " ")
            print(f"Best: {formatted_best}\t{solver.best_id}")
        else:
            raise SystemExit("ERR Missing data")


if __name__ == "__main__":
    main()
