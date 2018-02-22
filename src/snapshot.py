from os import path
import requests
from urllib.parse import urljoin
import yaml

SNAPSHOT_BASEURL = 'http://download.tumbleweed.boombatower.com/'

def ingest_list():
    url = urljoin(SNAPSHOT_BASEURL, 'list')
    response = requests.get(url)
    return response.text.strip().splitlines()

def main(logger_, data_dir):
    global logger
    logger = logger_

    releases = ingest_list()
    with open(path.join(data_dir, 'snapshot.yaml'), 'w') as outfile:
        yaml.safe_dump(releases, outfile, default_flow_style=False)

def argparse_main(args):
    data_dir = path.join(args.output_dir, 'data')
    main(args.logger, data_dir)

def argparse_configure(subparsers):
    parser = subparsers.add_parser(
        'snapshot',
        help='Ingest snapshoted release data.')
    parser.set_defaults(func=argparse_main)
