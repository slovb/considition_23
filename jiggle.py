import sys
from typing import Tuple

from settings import Settings
from best import best


def jiggle(mapName: str):
    total, id = best(mapName)
    formatted_total = "{:,}".format(total).replace(",", " ")
    print(f"{formatted_total}\t{id}")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        jiggle(sys.argv[1])
    else:
        print("Wrong number of arguments")
