#!/usr/bin/python3

import argparse
import logging
import os
from os import path
import sys
from util.common import CACHE_ROOT_DIR
from xdg.BaseDirectory import save_cache_path

import mail

def main(args):
    print('TODO')

def directory_type(string):
    if path.isdir(string):
        return string

    argparse.ArgumentTypeError('{} is not a directory'.format(string))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Tumbleweed snapshot review data ingest and formatting tool.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.set_defaults(func=main)

    parser.add_argument('--cache-dir',
                        type=directory_type,
                        default=save_cache_path(CACHE_ROOT_DIR),
                        help='cache directory')
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        help='print debugging information')
    parser.add_argument('-o', '--output-dir',
                        type=directory_type,
                        help='output directory')

    subparsers = parser.add_subparsers(title='subcommands')
    mail.argparse_configure(subparsers)

    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='[%(levelname).1s] %(message)s')
    logger = logging.getLogger()
    args.logger = logger

    sys.exit(args.func(args))
