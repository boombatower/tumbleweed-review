from datetime import timedelta
import os
from os import path
from packaging.version import parse as version_parse
import re
import stat
from urllib.parse import urljoin
from util.common import ensure_directory
from util.common import request_cached
from util.common import request_cached_path
import yaml

SNAPSHOT_BASEURL = 'http://download.opensuse.org/history/'
BINARY_REGEX = r'(?:.*::)?(?P<filename>(?P<name>.*?)-(?P<version>[^-]+)-(?P<release>[^-]+)\.(?P<arch>[^-\.]+))\.rpm'
BINARY_INTEREST = [
    # Base.
    'kernel-source',
    'gcc',
    # Automatically includes gcc\d+ for -1, 0, +1 of current version.
    # Graphics.
    'Mesa',
    'llvm',
    'xorg-x11-server',
    'xf86-video-ati',
    'xf86-video-amdgpu',
    'xf86-video-intel',
    'xf86-video-nouveau',
    'xwayland',
    # Desktop: Plasma.
    'libqt5-qtbase-devel',
    'plasma-framework',
    'plasma5-workspace',
    'kate', # kde applications.
    # Desktop: GNOME.
    'gnome-builder',
    'gtk3-devel',
]
BINARY_INTEREST_GCC = r'^gcc(?P<major_version>\d+)$'

def list_download(cache_dir):
    url = urljoin(SNAPSHOT_BASEURL, 'list')
    return request_cached(url, cache_dir).strip().splitlines()

def snapshot_url(release, path):
    return urljoin(SNAPSHOT_BASEURL, '/'.join([release, path]))

def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def list_detail_download(cache_dir, releases):
    details = {}

    binary_regex = re.compile(BINARY_REGEX)
    binary_gcc_regex = re.compile(BINARY_INTEREST_GCC)
    ttl_never = timedelta(days=300) # Should never change.
    ttl_retry = timedelta(hours=4) # While waiting for snapshot.
    for release in releases:
        details_release = {}

        url = snapshot_url(release, 'disk')
        disk_path = request_cached_path(url, cache_dir)
        if path.exists(disk_path) and not os.stat(disk_path)[stat.ST_SIZE]:
            logger.debug('using retry ttl for %s disk file', release)
            disk_ttl = ttl_retry
        else:
            disk_ttl = ttl_never
        disk = request_cached(url, cache_dir, disk_ttl).strip().splitlines()

        if len(disk) != 2:
            # Skip for now and retry later.
            logger.debug('skipping %s due to invalid disk file', release)

            if len(disk) != 0:
                # Clear cache file to indicate invalid.
                open(disk_path, 'w').write('')

            continue

        details_release['disk_base'] = sizeof_fmt(int(disk[0].split('\t')[0]))
        details_release['binary_unique_count'] = int(disk[1].split(' ')[0])
        details_release['disk_shared'] = 'unknown'

        url = snapshot_url(release, 'rpm.list')
        binaries = request_cached(url, cache_dir, ttl_never).strip().splitlines()
        details_release['binary_count'] = len(binaries)

        binary_interest = {}
        for binary in binaries:
            binary_match = binary_regex.match(path.basename(binary))
            if not binary_match:
                continue

            binary_name = binary_match.group('name')
            # Include all packages of interest and any gcc\d+ package to be filtered later.
            if not (binary_name in BINARY_INTEREST or binary_gcc_regex.match(binary_name)):
                continue

            # When multiple verisons of the same binary are present ensure the latest version wins.
            if (binary_name not in binary_interest or
                version_parse(binary_interest[binary_name]) < version_parse(binary_match.group('version'))):
                binary_interest[binary_name] = binary_match.group('version')

        # Assuming the default gcc version is found filter major gcc packages to near the version.
        if 'gcc' in binary_interest:
            gcc_major_version = int(binary_interest['gcc'])
            gcc_major_versions = [gcc_major_version - 1, gcc_major_version, gcc_major_version + 1]
            binary_interest_filtered = {}
            for binary_name, binary_version in binary_interest.items():
                match = binary_gcc_regex.match(binary_name)
                if match:
                    if int(match.group('major_version')) not in gcc_major_versions:
                        continue

                binary_interest_filtered[binary_name] = binary_version

            binary_interest = binary_interest_filtered

        details_release['binary_interest'] = binary_interest

        url = snapshot_url(release, 'rpm.unique.list')
        binaries = request_cached(url, cache_dir, ttl_never).strip().splitlines()

        binary_interest_changed = set()
        for binary in binaries:
            binary_match = binary_regex.match(path.basename(binary))
            if binary_match and binary_match.group('name') in binary_interest:
                binary_interest_changed.add(binary_match.group('name'))

        details_release['binary_interest_changed'] = list(sorted(binary_interest_changed))

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
