from dataclasses import dataclass
from data_keys import GeneralKeys as GK


@dataclass
class Settings:
    multiprocessing = False
    cache_folder = "cache"
    log_folder = "log"
    game_folder = "my_games"
    starting_point = "func"
    max_stations = 2

    partial_additions = True
    do_sets = True
    do_groups = True
    group_size = 16
    # groups_distance_limit = 10.0

    sandbox_explore_how_many = 16
    do_sandbox_groups = False
    sandbox_group_size = 2
    sandbox_groups_distance_limit = 5.0
    do_sandbox_sets = True
    sandbox_too_near = 1.0
    granularity = 1e4


@dataclass
class KW:
    limit = "limit"
    limits = {
        GK.groceryStoreLarge: 5,
        GK.groceryStore: 20,
        GK.gasStation: 8,
        GK.convenience: 20,
        GK.kiosk: 3,
    }
    nearby = "nearby"
