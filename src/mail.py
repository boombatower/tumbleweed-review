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

# openSUSE switched over to new mailing list system (see issue #9).
MIGRATION_YEAR = 2020
MIGRATION_MONTH = 11

MAILING_LIST = 'opensuse-factory'
MAILING_LIST_SHORT = 'factory'
MAILING_LIST_URL_PRE = 'https://lists.opensuse.org/{list}/{year}-{month}/msg{number:05d}.html'
MAILING_LIST_URL_POST = 'https://github.com/boombatower/tumbleweed-review/issues/10'
MAILBOX_URL_PRE = 'https://lists.opensuse.org/{list}/{list}-{year}-{month}.mbox.gz'
MAILBOX_URL_POST = 'https://lists.opensuse.org/archives/list/{list}@lists.opensuse.org/export/{list}@lists.opensuse.org-{year}-{month}.mbox.gz?start=2020-{month}-01&end={end_date}'
MAILBOX_PATH='{list}-{year}-{month}.mbox'
RELEASE_PATTERN_PRE = r'^\[{list}\] New Tumbleweed snapshot (?P<version>\d+) released!$'
RELEASE_PATTERN_POST = r'^New Tumbleweed snapshot (?P<version>\d+) released!$'
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

def month_next_start(date):
    return (date.replace(day=17) + timedelta(days=17)).replace(day=1)

def mboxes_download_url(month_date, year, month):
    # Does not handle partial month split and parsing both mail boxes.
    if month_date.year > MIGRATION_YEAR or (month_date.year >= MIGRATION_YEAR and month_date.month >= MIGRATION_MONTH):
        end_date = month_next_start(month_date)
        return MAILBOX_URL_POST.format(list=MAILING_LIST_SHORT, year=year, month=month, end_date=end_date)

    return MAILBOX_URL_PRE.format(list=MAILING_LIST, year=year, month=month)

def mboxes_download(cache_dir, month_start, refresh=True):
    """Download mboxes for given month range."""
    mbox_paths = {}
    month_previous = None
    for month_date in month_generator(month_start):
        year = str(month_date.year)
        month = month_date.strftime('%m')
        logger.info('ingest {}-{}'.format(year, month))

        mbox_url = mboxes_download_url(month_date, year, month)
        mbox_name = MAILBOX_PATH.format(list=MAILING_LIST, year=year, month=month)
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
    release_pattern = re.compile(RELEASE_PATTERN_PRE.format(list=MAILING_LIST))
    for mbox_path, month in sorted(mbox_paths.items()):
        if int(month[0]) > MIGRATION_YEAR or (int(month[0]) >= MIGRATION_YEAR and int(month[1]) >= MIGRATION_MONTH + 1):
            # To test ones sanity the mailing list prefix was dropped after the
            # migration so this will miss 20201129 released on Nov 30.
            release_pattern = re.compile(RELEASE_PATTERN_POST)

        index = '-'.join(month)
        mbox = mailbox.mbox(mbox_path)

        for key in mbox.iterkeys():
            message = mbox[key]
            logger.debug('<%s> %s', key, message['subject'])

            # Newer mailing list seems to include 'dead' mail.
            if message['message-id'] is None or message['subject'] is None:
                continue

            # Build tree of message to aid in relating messages to release.
            parent = None
            if message['in-reply-to']:
                in_reply_to = message_id_normalize(message['in-reply-to'])
                if in_reply_to in lookup:
                    parent = lookup[in_reply_to]
                else:
                    logger.debug('message {} not found'.format(in_reply_to))

            # Either no in-reply-to or message not found, attempt references.
            if not parent and message['references']:
                # By checking references in reverse order the deepest message
                # will be selected as parent.
                for reference in reversed(re.split(r'[\n\s]+', message['references'])):
                    reference = message_id_normalize(reference)
                    if reference in lookup:
                        parent = lookup[reference]
                        break
                    else:
                        logger.debug('message {} not found'.format(reference))

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

# The newer mailing list strips <> from the in-reply-to header while leaving <>
# in the message-id. As such normalize other headers so they will match the
# message-id. Also pray upstream has a reasonable explanation for this.
def message_id_normalize(message_id):
    if message_id.startswith('<'):
        return message_id

    return '<{}>'.format(message_id)

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

def discussions_export(lookup, releases, discussions):
    export = {}
    for release, message_id in sorted(releases.items()):
        export[release] = {
            'announcement': lookup[message_id].name,
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

def mailing_list_url(message):
    month, number = message.split('.')
    year, month = month.split('-')

    if int(year) > MIGRATION_YEAR or (int(year) >= MIGRATION_YEAR and int(month) >= MIGRATION_MONTH):
        # New mailing list does not produce predictable URLs nor include the
        # Archived-At header in the mbox downloads.
        return MAILING_LIST_URL_POST

    return MAILING_LIST_URL_PRE.format(
        list=MAILING_LIST, year=year, month=month, number=int(number))

def main(logger_, cache_dir, start_month, output_dir, refresh=True):
    global logger
    logger = logger_

    ensure_directory(cache_dir)

    mbox_paths = mboxes_download(cache_dir, start_month, refresh)
    root, lookup, releases = mboxes_process(mbox_paths)
    discussions = discussions_find(root, lookup, releases)
    discussions = discussions_reduce(discussions)
    export = discussions_export(lookup, releases, discussions)

    ensure_directory(output_dir)
    with open(path.join(output_dir, 'mail.yaml'), 'w') as outfile:
        yaml.safe_dump(export, outfile)

    if logger.isEnabledFor(logging.DEBUG):
        from anytree import RenderTree, AsciiStyle
        print(RenderTree(root, style=AsciiStyle()).by_attr())

    discussion_print(export)

def argparse_main(args):
    cache_dir = path.join(args.cache_dir, 'mbox')
    output_dir = path.join(args.output_dir, 'data')
    main(args.logger, cache_dir, args.start_month, output_dir, not args.no_refresh)

def date_month_arg(string):
    try:
        return datetime.strptime(string, "%Y-%m").date()
    except ValueError:
        raise argparse.ArgumentTypeError('invalid date "{}"'.format(string))

def argparse_configure(subparsers):
    parser = subparsers.add_parser(
        'mail',
        help='Ingest {} mailing list data and dump as JSON and YAML.'.format(MAILING_LIST))
    parser.set_defaults(func=argparse_main)
    parser.add_argument('--no-refresh',
                        action='store_true',
                        help='do not refresh relevant mboxes')
    parser.add_argument('-s', '--start-month',
                        type=date_month_arg,
                        default='2016-01',
                        help='Start month from which to ingest mboxes')
