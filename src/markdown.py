from mail import mailing_list_url
from main import ROOT_PATH
from os import path
from snapshot import snapshot_url
from util.common import ensure_directory
import yaml

def data_load(data_dir):
    mail = None
    snapshot = None

    mail_path = path.join(data_dir, 'mail.yaml')
    if path.exists(mail_path):
        with open(mail_path, 'r') as mail_handle:
            mail = yaml.safe_load(mail_handle)

    snapshot_path = path.join(data_dir, 'snapshot.yaml')
    if path.exists(snapshot_path):
        with open(snapshot_path, 'r') as mail_handle:
            snapshot = yaml.safe_load(mail_handle)

    return mail, snapshot

def mail_build(mail_release):
    lines = []

    for thread in sorted(mail_release['threads'],
                         key=lambda t: t['reference_count'], reverse=True):
        lines.append('- <{}> {}'.format(thread['reference_count'], thread['summary']))
        for message in thread['messages']:
            lines.append('  - [{}]({})'.format(message, mailing_list_url(message)))

    return mail_release['reference_count'], '\n'.join(lines)

def variables_format(variables):
    out = ''
    for key, value in sorted(variables.items()):
        out += '{}: {}\n'.format(key, value)
    return out.strip()

def table_format(headings, data, bold):
    out = []
    out.append(' | '.join(headings))
    out.append(' | '.join(['---'] * len(headings)))
    for key, value in data.items():
        if key in bold:
            key = '**{}**'.format(key)
        out.append(' | '.join([key, value]))
    return '\n'.join(out)

def link_format(text, href):
    return '[{}]({})'.format(text, href)

def posts_build(posts_dir, mail, snapshot):
    template_path = path.join(ROOT_PATH, 'jekyll', '_posts', '.template.md')
    with open(template_path, 'r') as template_handle:
        template = template_handle.read()

    # Likely want to ingest release data as seperate item directly from source.
    for release, mail_release in mail.items():
        reference_count_mail, mail_markdown = mail_build(mail_release)
        reference_count = reference_count_mail

        variables = {
            'release_available': str(release in snapshot).lower(),
            'release_reference_count': reference_count,
            'release_reference_count_mail': reference_count_mail,
            'release_score': 0,
            'release_stability_level': 'unknown',
            'release_version': release,
        }
        links = []

        links.append(link_format('mail announcement', mailing_list_url(mail_release['announcement'])))

        if release in snapshot:
            release_snapshot = snapshot[release]
            for key, value in release_snapshot.items():
                if not key.startswith('binary_interest'):
                    variables['release_{}'.format(key)] = value

            binary_interest = table_format(['Binary', 'Version'], release_snapshot['binary_interest'], release_snapshot['binary_interest_changed'])

            links.append(link_format('binary unique list', snapshot_url(release, 'rpm.unique.list')))
            links.append(link_format('binary list', snapshot_url(release, 'rpm.list')))
        else:
            binary_interest = ''

        if not mail_markdown:
            mail_markdown = 'No interesting mail references.'

        links = '- ' + '\n- '.join(links)

        post = template.format(
            release=release,
            variables=variables_format(variables),
            binary_interest=binary_interest,
            links=links,
            mail=mail_markdown,
        )

        date = '-'.join([release[0:4], release[4:6], release[6:8]])
        post_name = '{}-release.md'.format(date)
        post_path = path.join(posts_dir, post_name)
        with open(post_path, 'w') as post_handle:
            post_handle.write(post)

def main(args):
    global logger
    logger = args.logger

    posts_dir = path.join(args.output_dir, '_posts')
    ensure_directory(posts_dir)
    data_dir = path.join(args.output_dir, 'data')

    mail, snapshot = data_load(data_dir)
    posts_build(posts_dir, mail, snapshot)

def argparse_configure(subparsers):
    parser = subparsers.add_parser(
        'markdown',
        help='Generate markdown files for Jekyll site.')
    parser.set_defaults(func=main)
