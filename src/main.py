#!/usr/bin/python3

import argparse
import logging
import os
from os import path
import sys
from util.common import CACHE_ROOT_DIR
from util.common import jekyll_init
from util.git import sync
from xdg.BaseDirectory import save_cache_path

import mail
import markdown

SCRIPT_PATH = path.dirname(path.realpath(__file__))
ROOT_PATH = path.normpath(path.join(SCRIPT_PATH, '..'))

def main(args):
    print('TODO')

def directory_type(string):
    if path.isdir(string):
        return string

    raise argparse.ArgumentTypeError('{} is not a directory'.format(string))

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
    parser.add_argument('--read-only',
                        action='store_true',
                        help='opperate on site in read-only mode')

    subparsers = parser.add_subparsers(title='subcommands')
    mail.argparse_configure(subparsers)
    markdown.argparse_configure(subparsers)

    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='[%(levelname).1s] %(message)s')
    logger = logging.getLogger()
    args.logger = logger

    repo_url = None
    if not args.output_dir:
        if args.read_only:
            repo_url = 'https://github.com/boombatower/tumbleweed-review-site'
        else:
            repo_url = 'git@github.com:boombatower/tumbleweed-review-site'
        args.output_dir = sync(args.cache_dir, repo_url)

    jekyll_init(args.output_dir)

    ret = args.func(args)
    if repo_url and path.exists(path.join(args.output_dir, '.git')) and not ret:
        sync(args.cache_dir, repo_url)
    sys.exit(ret)
