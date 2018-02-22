from datetime import timedelta
import os
from os import path
import re
import requests
import stat
from urllib.parse import urljoin
from util.common import ensure_directory
from util.common import request_cached
from util.common import request_cached_path
import yaml

SNAPSHOT_BASEURL = 'http://download.tumbleweed.boombatower.com/'
BINARY_REGEX = r'(?:.*::)?(?P<filename>(?P<name>.*?)-(?P<version>[^-]+)-(?P<release>[^-]+)\.(?P<arch>[^-\.]+))\.rpm'
BINARY_INTEREST = [
    # Base.
    'kernel-source',
    'gcc',
    'gcc7',
    # Graphics.
    'Mesa',
    'llvm',
    'xorg-x11-server',
    'xf86-video-ati',
    'xf86-video-amdgpu',
    'xf86-video-intel',
    'xf86-video-nouveau',
    # Desktop: Plasma.
    'libqt5-qtbase-devel',
    'plasma-framework',
    'plasma5-workspace',
    'kate', # kde applications.
    # Desktop: GNOME.
    'gnome-builder',
    'gtk3-devel',
]

def list_download(cache_dir):
    url = urljoin(SNAPSHOT_BASEURL, 'list')
    return request_cached(url, cache_dir).strip().splitlines()

def list_detail_download(cache_dir, releases):
    details = {}

    binary_regex = re.compile(BINARY_REGEX)
    ttl_never = timedelta(days=300) # Should never change.
    ttl_retry = timedelta(hours=4) # While waiting for snapshot.
    for release in releases:
        details_release = {}

        url = urljoin(SNAPSHOT_BASEURL, '/'.join([release, 'disk']))
        disk_path = request_cached_path(url, cache_dir)
        if path.exists(disk_path) and not os.stat(disk_path)[stat.ST_SIZE]:
            logger.debug('using retry ttl for %s disk file', release)
            disk_ttl = ttl_retry
        else:
            disk_ttl = ttl_never
        disk = request_cached(url, cache_dir, disk_ttl).strip().splitlines()

        if len(disk) != 3:
            # Skip for now and retry later.
            logger.debug('skipping %s due to invalid disk file', release)

            if len(disk) != 0:
                # Clear cache file to indicate invalid.
                open(disk_path, 'w').write('')

            continue

        details_release['disk_base'] = disk[0].split('\t')[0]
        details_release['rpm_unique_count'] = int(disk[1].split(' ')[0])
        details_release['disk_shared'] = disk[2].split('\t')[0]

        url = urljoin(SNAPSHOT_BASEURL, '/'.join([release, 'rpm.list']))
        binaries = request_cached(url, cache_dir, ttl_never).strip().splitlines()

        binary_interest = {}
        for binary in binaries:
            binary_match = binary_regex.match(path.basename(binary))
            if binary_match and binary_match.group('name') in BINARY_INTEREST:
                binary_interest[binary_match.group('name')] = binary_match.group('version')

        details_release['binary_interest'] = binary_interest

        url = urljoin(SNAPSHOT_BASEURL, '/'.join([release, 'rpm.unique.list']))
        binaries = request_cached(url, cache_dir, ttl_never).strip().splitlines()

        binary_interest_changed = []
        for binary in binaries:
            binary_match = binary_regex.match(path.basename(binary))
            if binary_match and binary_match.group('name') in BINARY_INTEREST:
                binary_interest_changed.append(binary_match.group('name'))

        details_release['binary_interest_changed'] = binary_interest_changed

        details[release] = details_release

    return details

def main(logger_, cache_dir, data_dir):
    global logger
    logger = logger_

    ensure_directory(cache_dir)
    ensure_directory(data_dir)

    releases = list_download(cache_dir)
    details = list_detail_download(cache_dir, releases)

    with open(path.join(data_dir, 'snapshot.yaml'), 'w') as outfile:
        yaml.safe_dump(details, outfile, default_flow_style=False)

def argparse_main(args):
    cache_dir = path.join(args.cache_dir, 'snapshot')
    data_dir = path.join(args.output_dir, 'data')
    main(args.logger, cache_dir, data_dir)

def argparse_configure(subparsers):
    parser = subparsers.add_parser(
        'snapshot',
        help='Ingest snapshotted release data.')
    parser.set_defaults(func=argparse_main)
