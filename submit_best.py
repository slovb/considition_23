import sys

from best import best
from submit import submit


if __name__ == '__main__':
    if len(sys.argv) == 2:
        _, id = best(sys.argv[1])
        submit(id)
    else:
        print('Wrong number of arguments')
