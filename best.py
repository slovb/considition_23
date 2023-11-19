import sys

from settings import Settings


def best(mapName):
    with open(f"{Settings.log_folder}/{mapName}.txt", "r", encoding="utf8") as f:
        scores = []
        for line in f.readlines():
            parts = line.rstrip().split(" ")
            score = int(parts[0])
            id = parts[1]
            scores.append((score, id))
    return max(scores)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        total, id = best(sys.argv[1])
        formatted_total = "{:,}".format(total).replace(",", " ")
        print(f"{formatted_total}\t{id}")
    else:
        print("Wrong number of arguments")
