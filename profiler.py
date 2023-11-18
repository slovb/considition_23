import cProfile

from main import main
from data_keys import MapNames as MN


if __name__ == "__main__":
    cProfile.run('main(MN.goteborg)')
