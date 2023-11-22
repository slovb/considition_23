from dataclasses import dataclass
from data_keys import GeneralKeys as GK


@dataclass
class Settings:
    cache_folder = "cache"
    log_folder = "log"
    game_folder = "my_games"
    starting_point = "func"
    max_stations = 2

    do_multiprocessing = False

    do_sets = False
    do_groups = True
    group_size = 16
    groups_distance_limit = 100.0

    sandbox_explore_how_many = 4
    do_sandbox_groups = True
    sandbox_group_size = 2
    sandbox_groups_distance_limit = 100.0
    do_sandbox_sets = True
    sandbox_too_near = 1.0
    granularity = 1e5


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
