from anytree import Node
import argparse
from datetime import date
from datetime import datetime
from datetime import timedelta
import gzip
import io
import logging
import mailbox
import os
from os import path
import re
import requests
import shutil
import sys
from util.common import ensure_directory
from xdg.BaseDirectory import save_cache_path
import yaml

MAILING_LIST = 'opensuse-factory'
MAILING_LIST_URL = 'https://lists.opensuse.org/{list}/{year}-{month}/msg{number:05d}.html'
MAILBOX_URL = 'https://lists.opensuse.org/{list}/{list}-{year}-{month}.mbox.gz'
RELEASE_PATTERN = r'^\[{list}\] New Tumbleweed snapshot (?P<version>\d+) released!$'
RELEASE_PATTERN_SHORT = r'^New Tumbleweed snapshot (?P<version>\d+)( released!)?$'

def month_generator(month_start):
    """Generate months from now backwards until and including start month."""
    month = date.today()
    while True:
        month = month.replace(day=1)
        yield month

        if month <= month_start:
            break

        month = month.replace(day=1) - timedelta(days=17)

def mboxes_download(cache_dir, month_start, refresh=True):
    """Download mboxes for given month range."""
    mbox_paths = {}
    month_previous = None
    for month_date in month_generator(month_start):
        year = str(month_date.year)
        month = month_date.strftime('%m')
        logger.info('ingest {}-{}'.format(year, month))

        mbox_url = MAILBOX_URL.format(list=MAILING_LIST, year=year, month=month)
        mbox_name = path.basename(mbox_url)[:-3] # Remove .gz extension.
        mbox_path = path.join(cache_dir, mbox_name)
        mbox_paths[mbox_path] = (year, month)

        if path.exists(mbox_path):
            mbox_modified = datetime.fromtimestamp(path.getmtime(mbox_path)).date()
            mbox_incomplete = not month_previous or mbox_modified <= month_previous
            month_previous = month_date

            if refresh and mbox_incomplete:
                # Remove cache for current month and previous month if it was
                # not updated since the first of the next month (previous).
                logger.debug('removed from cache')
                os.remove(mbox_path)
            else:
                logger.debug('available from cache')
                continue

        # Download, decompress, and write to cache.
        response = requests.get(mbox_url)
        with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as mbox_gzip:
            with open(mbox_path, 'wb') as mbox_file:
                shutil.copyfileobj(mbox_gzip, mbox_file)

    return mbox_paths

def mboxes_process(mbox_paths):
    """Process a set of mboxes instead message tree and detect releases."""
    root = Node('root')
    lookup = {}
    releases = {}

    # Process in reverse order to allow newer messages to reference older ones.
    release_pattern = re.compile(RELEASE_PATTERN.format(list=MAILING_LIST))
    for mbox_path, month in sorted(mbox_paths.items()):
        index = '-'.join(month)
        mbox = mailbox.mbox(mbox_path)

        for key in mbox.iterkeys():
            message = mbox[key]
            logger.debug('<%s> %s', key, message['subject'])

            # Build tree of message to aid in relating messages to release.
            parent = None
            if message['in-reply-to']:
                if message['in-reply-to'] in lookup:
                    parent = lookup[message['in-reply-to']]
                else:
                    logger.debug('message {} not found'.format(message['in-reply-to']))

            # Either no in-reply-to or message not found, attempt references.
            if not parent and message['references']:
                # By checking references in reverse order the deepest message
                # will be selected as parent.
                for reference in reversed(re.split(r'[\n\s]+', message['references'])):
                    if reference in lookup:
                        parent = lookup[reference]
                        break

            if not parent:
                parent = root

            # Detect release announcement.
            match = release_pattern.match(message['subject'])
            if match:
                release = match.group('version')
                logger.debug('found release %s', release)
                releases[release] = message['message-id']
            else:
                release = False

            lookup[message['message-id']] = Node(
                '{}.{}'.format(index, key), parent=parent, message=message, month=month, release=release)

    return root, lookup, releases

def discussions_find(root, lookup, releases):
    """Find discussions relevant to releases within tree."""
    releases_reverse = sorted(releases, reverse=True)
    discussions = {}
    for message_node in root.children:
        message = message_node.message
        if message_node.release:
            # Add all direct replies to release announcement.
            discussions[message_node.release] = list(message_node.children)
        else:
            # Add any root threads referencing release. In the case of multiple
            # releases referenced choose the last one. For example:
            #   update 20180207 -> 20180209 plasma crashing
            # From 2018-02.402, 2018-02.404. It may make sense to handle
            # specific cases instead of general rule.
            for release in releases_reverse:
                if release in message['subject']:
                    discussions.setdefault(release, [])
                    discussions[release].append(message_node)
                    break

        # It may make sense to search depth first to find nested threads post
        # subject change and grab the first one.

    return discussions

def discussions_reduce(discussions):
    """Merge discussions whose subject reduces to the same summary"""
    for release, message_nodes in discussions.items():
        message_nodes_merged = {}
        for message_node in message_nodes:
            summary = subject_reduce(message_node.message, release)
            if summary not in message_nodes_merged:
                message_nodes_merged[summary] = [message_node]
            else:
                message_nodes_merged[summary].append(message_node)

        discussions[release] = message_nodes_merged

    return discussions

def subject_reduce(message, release):
    """Reduce subject to essential summary without mail clutter."""
    subject = message['subject']

    # Strip reply and mailing list prefixes.
    subject = subject.replace('\n', '')
    subject = re.sub(r'^[Rr][Ee]:\s*', '', subject)
    subject = re.sub(r'^\[{}\] '.format(MAILING_LIST), '', subject)
    subject = re.sub(r'^[Rr][Ee]:\s*', '', subject)

    if re.match(RELEASE_PATTERN_SHORT, subject):
        # Subject matches announcement, could attempt looking at body.
        return 'no summary given'

    # Remove references to release (may work better special-casing).
    subject = re.sub(r'\((?:was|re):[^)]+\)', '', subject)
    subject = re.sub(r',?\s?(?:was|re):.*$', '', subject)
    subject = re.sub(r'after(?: (?:updating|upgrading|latest))?(?: to)?(?: [Ss]napshot)?(?: TW)? {}'.format(release), '', subject)
    subject = re.sub(r'update \d+ (?:->|to) \d+', '', subject)
    subject = re.sub(r' (?:in|with)(?: [Ss]napshot)? {}'.format(release), '', subject)
    subject = re.sub(r'^.*?{}(?::\s| - )?'.format(release), '', subject)
    subject = subject.strip()

    if not subject:
        return 'failed to summarize'

    return subject

def discussions_export(releases, discussions):
    export = {}
    for release in sorted(releases):
        export[release] = {
            'reference_count': 0,
            'thread_count': 0,
            'threads': [],
        }

        if release not in discussions:
            continue

        for summary, messages in discussions[release].items():
            thread = {
                'reference_count': 0,
                'summary': summary,
                'messages': [],
            }

            for message in messages:
                thread['messages'].append(message.name)

                thread_size = len(message.descendants) + 1 # Include self.
                thread['reference_count'] += thread_size
                export[release]['reference_count'] += thread_size

            export[release]['threads'].append(thread)
            export[release]['thread_count'] += 1

    return export

def discussion_print(export):
    for release, details in export.items():
        print('{} <{} / {}>'.format(release, details['reference_count'], details['thread_count']))

        for thread in details['threads']:
            print('- {} <{} / {}>'.format(
                thread['summary'], thread['reference_count'], ', '.join(thread['messages'])))

def main(args):
    global logger
    logger = args.logger

    cache_dir = path.join(args.cache_dir, 'mbox')
    ensure_directory(cache_dir)

    mbox_paths = mboxes_download(cache_dir, args.start_month, not args.no_refresh)
    root, lookup, releases = mboxes_process(mbox_paths)
    discussions = discussions_find(root, lookup, releases)
    discussions = discussions_reduce(discussions)
    export = discussions_export(releases, discussions)

    output_dir = path.join(args.output_dir, 'data')
    ensure_directory(output_dir)
    with open(path.join(output_dir, 'mail.yaml'), 'w') as outfile:
        yaml.safe_dump(export, outfile)

    if logger.isEnabledFor(logging.DEBUG):
        from anytree import RenderTree, AsciiStyle
        print(RenderTree(root, style=AsciiStyle()).by_attr())

    discussion_print(export)

def date_month_arg(string):
    try:
        return datetime.strptime(string, "%Y-%m").date()
    except ValueError:
        raise argparse.ArgumentTypeError('invalid date "{}"'.format(string))

def argparse_configure(subparsers):
    parser = subparsers.add_parser(
        'mail',
        help='Ingest {} mailing list data and dump as JSON and YAML.'.format(MAILING_LIST))
    parser.set_defaults(func=main)
    parser.add_argument('--no-refresh',
                        action='store_true',
                        help='do not refresh relevant mboxes')
    parser.add_argument('-s', '--start-month',
                        type=date_month_arg,
                        default='2016-01',
                        help='Start month from which to ingest mboxes')
