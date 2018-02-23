from bug import bugzilla_url
from mail import mailing_list_url
from main import ROOT_PATH
from os import path
from score import stability_level
from snapshot import snapshot_url
from util.common import ensure_directory
from util.common import release_parts
from util.common import yaml_load

def data_load(data_dir):
    return yaml_load(data_dir, 'bug.yaml'), \
        yaml_load(data_dir, 'mail.yaml'), \
        yaml_load(data_dir, 'score.yaml'), \
        yaml_load(data_dir, 'snapshot.yaml')

def bug_build(bug_release):
    lines = []

    for bug in sorted(bug_release, key=lambda b: b['id']):
        line = link_format('{}: {}'.format(
            bug['id'], bug['summary']), bugzilla_url(bug['id']))
        if bug['status'] == 'RESOLVED':
            line = '~~{}~~'.format(line)
        lines.append('- ' + line)

    return len(lines), '\n'.join(lines)

def mail_build(mail_release):
    lines = []

    for thread in sorted(mail_release['threads'],
                         key=lambda t: t['reference_count'], reverse=True):
        line = link_format(thread['summary'], mailing_list_url(thread['messages'][0]))
        line += ' ({} refs)'.format(thread['reference_count'])
        extra = []
        for message in thread['messages'][1:]:
            extra.append(link_format(message, mailing_list_url(message)))

        if len(extra):
            line += '; ' + ', '.join(extra)

        lines.append('- ' + line)

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

def posts_build(posts_dir, bug, mail, score, snapshot):
    template_path = path.join(ROOT_PATH, 'jekyll', '_posts', '.template.md')
    with open(template_path, 'r') as template_handle:
        template = template_handle.read()

    # Likely want to ingest release data as seperate item directly from source.
    for release, mail_release in mail.items():
        reference_count_bug, bug_markdown = bug_build(bug.get(release, []))
        reference_count_mail, mail_markdown = mail_build(mail_release)
        reference_count = reference_count_bug + reference_count_mail
        score_release = score.get(release, {}).get('score', 'n/a')

        variables = {
            'release_available': str(release in snapshot).lower(),
            'release_reference_count': reference_count,
            'release_reference_count_mail': reference_count_mail,
            'release_score': score_release,
            'release_stability_level': stability_level(release, score_release),
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

        if not bug_markdown:
            bug_markdown = 'no relevant bugs'
        if not mail_markdown:
            mail_markdown = 'no relevant mails'

        links = '- ' + '\n- '.join(links)

        post = template.format(
            release=release,
            variables=variables_format(variables),
            bug=bug_markdown,
            bug_count=reference_count_bug,
            mail=mail_markdown,
            mail_count=mail_release['thread_count'],
            mail_reference_count=reference_count_mail,
            binary_interest=binary_interest,
            links=links,
        )

        date = '-'.join(release_parts(release))
        post_name = '{}-release.md'.format(date)
        post_path = path.join(posts_dir, post_name)
        with open(post_path, 'w') as post_handle:
            post_handle.write(post)

def main(logger_, posts_dir, data_dir):
    global logger
    logger = logger_

    ensure_directory(posts_dir)
    bug, mail, score, snapshot = data_load(data_dir)
    posts_build(posts_dir, bug, mail, score, snapshot)

def argparse_main(args):
    posts_dir = path.join(args.output_dir, '_posts')
    data_dir = path.join(args.output_dir, 'data')
    main(args.logger, posts_dir, data_dir)

def argparse_configure(subparsers):
    parser = subparsers.add_parser(
        'markdown',
        help='Generate markdown files for Jekyll site.')
    parser.set_defaults(func=argparse_main)
