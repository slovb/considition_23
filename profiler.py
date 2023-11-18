from main import main
from data_keys import MapNames as MN
import cProfile

if __name__ == "__main__":
    cProfile.run('main(MN.goteborg)')
