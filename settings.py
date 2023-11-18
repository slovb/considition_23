from dataclasses import dataclass


@dataclass
class Settings:
    cache_folder = "cache"
    log_folder = "log"
    game_folder = "my_games"
    max_stations = 2
    starting_point = 'func'
    do_mega = True
    mega_count = 1
    do_sets = False
    do_groups = True
    do_multiprocessing = False
    group_size = 16
