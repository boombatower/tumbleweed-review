import argparse
import bugzilla
from datetime import date
from datetime import datetime
from mail import date_month_arg
from os import path
from urllib.parse import urljoin
from util.common import ensure_directory
from util.common import release_to_date
from util.common import yaml_load
import yaml

BUGZILLA_BASEURL = 'https://bugzilla.opensuse.org/'
BUGZILLA_PRODUCT = 'openSUSE Tumbleweed'

def bugzilla_url(bug_id):
    return urljoin(BUGZILLA_BASEURL, 'show_bug.cgi?id={}'.format(bug_id))

def bugzilla_init(apiurl):
    bugzilla_api = bugzilla.Bugzilla(apiurl)
    if not bugzilla_api.logged_in:
        print('Bugzilla credentials required to create bugs.')
        bugzilla_api.interactive_login()
    return bugzilla_api

def bugzilla_query(bugzilla_api, start_month):
    query = bugzilla_api.url_to_query(
        'buglist.cgi?creation_time={}&product={}'.format(start_month, BUGZILLA_PRODUCT))
    query['include_fields'] = ['component', 'creation_time', 'id', 'resolution', 'status', 'summary']
    return bugzilla_api.query(query)

def bug_info(bug):
    return {
        'component': bug.component,
        'create_time': str(bug.creation_time),
        'id': bug.id,
        'resolution': bug.resolution,
        'status': bug.status,
        'summary': bug.summary,
    }

def bug_release_associate(bugs, mail):
    """Associate bugs with a release if they were created after it."""
    bugs_release = {}

    bugs_reversed = reversed(bugs) # Already in order, so start with newest.
    bug_previous = None
    for release in sorted(mail, reverse=True):
        release_date = release_to_date(release)
        bugs_release.setdefault(release, [])

        if bug_previous:
            if bug.creation_time >= release_date:
                bugs_release[release].append(bug_info(bug))
            else:
                continue

        for bug in bugs_reversed:
            if bug.creation_time >= release_date:
                bugs_release[release].append(bug_info(bug))
            else:
                bug_previous = bug
                break

    return bugs_release

def main(logger_, cache_dir, data_dir, bugzilla_apiurl, start_month):
    global logger
    logger = logger_

    ensure_directory(cache_dir)
    ensure_directory(data_dir)

    bugzilla_api = bugzilla_init(bugzilla_apiurl)
    bugs = bugzilla_query(bugzilla_api, start_month)

    mail = yaml_load(data_dir, 'mail.yaml')
    bugs_release = bug_release_associate(bugs, mail)

    with open(path.join(data_dir, 'bug.yaml'), 'w') as outfile:
        yaml.safe_dump(bugs_release, outfile, default_flow_style=False)

def argparse_main(args):
    cache_dir = path.join(args.cache_dir, 'bug')
    data_dir = path.join(args.output_dir, 'data')
    main(args.logger, cache_dir, data_dir, args.bugzilla_apiurl, args.start_month)

def argparse_configure(subparsers):
    parser = subparsers.add_parser(
        'bug',
        help='Ingest bug data from bugzilla.')
    parser.set_defaults(func=argparse_main)
    parser.add_argument('-b', '--bugzilla-apiurl',
                        required=True,
                        metavar='URL',
                        help='bugzilla API URL')
    parser.add_argument('-s', '--start-month',
                        type=date_month_arg,
                        default='2017-12',
                        help='Start month from which to ingest mboxes')
