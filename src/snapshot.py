from os import path
import requests
from urllib.parse import urljoin
from util.common import ensure_directory
from util.common import request_cached
import yaml

SNAPSHOT_BASEURL = 'http://download.tumbleweed.boombatower.com/'

def list_download(cache_dir):
    url = urljoin(SNAPSHOT_BASEURL, 'list')
    return request_cached(url, cache_dir).strip().splitlines()

def main(logger_, cache_dir, data_dir):
    global logger
    logger = logger_

    ensure_directory(cache_dir)
    ensure_directory(data_dir)

    releases = list_download(cache_dir)
    with open(path.join(data_dir, 'snapshot.yaml'), 'w') as outfile:
        yaml.safe_dump(releases, outfile, default_flow_style=False)

def argparse_main(args):
    cache_dir = path.join(args.cache_dir, 'snapshot')
    data_dir = path.join(args.output_dir, 'data')
    main(args.logger, cache_dir, data_dir)

def argparse_configure(subparsers):
    parser = subparsers.add_parser(
        'snapshot',
        help='Ingest snapshoted release data.')
    parser.set_defaults(func=argparse_main)
