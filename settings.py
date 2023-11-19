from dataclasses import dataclass


@dataclass
class Settings:
    cache_folder = "cache"
    log_folder = "log"
    game_folder = "my_games"
    starting_point = "func"
    max_stations = 2

    do_multiprocessing = False

    do_mega = True
    mega_count = 1
    do_sets = True
    do_groups = True
    group_size = 16
    groups_distance_limit = 100.0

    sandbox_explore_how_many = 32
    do_sandbox_groups = True
    sandbox_group_size = 3
    sandbox_groups_distance_limit = 100.0
    do_sandbox_sets = True
    sandbox_too_near = 10.0
