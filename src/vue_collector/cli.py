import argparse
import sys

from .format import format_vue_dir


def main() -> None:
    parser = argparse.ArgumentParser(prog='vue-collector')
    sub = parser.add_subparsers(dest='command')
    fmt = sub.add_parser('format', help='Format .vue files in-place')
    fmt.add_argument('dir', help='Directory with .vue files')
    args = parser.parse_args()

    if args.command == 'format':
        changed = format_vue_dir(args.dir)
        for p in changed:
            print(f'Formatted: {p}')
        if not changed:
            print('All files already formatted.')
    else:
        parser.print_help()
        sys.exit(1)
