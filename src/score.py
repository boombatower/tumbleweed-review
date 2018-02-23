from datetime import date
from os import path
from util.common import ensure_directory
from util.common import release_to_date
from util.common import yaml_load
import yaml

def mail_score(mail_release):
    impact = 0
    for thread in mail_release['threads']:
        impact += max(min(thread['reference_count'], 25), 3)
    return impact

def stability_level(release, score):
    release_date = release_to_date(release)
    if (date.today() - release_date).days < 7:
        return 'pending'

    if score == 'n/a':
        return 'unknown'

    score = int(score)
    if score > 90:
        return 'stable'
    if score > 70:
        return 'moderate';
    return 'unstable'

def score(mail):
    scores = {}

    for release, mail_release in mail.items():
        score = 100
        score -= mail_score(mail_release)

        scores[release] = int(score)

    return scores

def main(logger_, data_dir):
    global logger
    logger = logger_

    ensure_directory(data_dir)

    mail = yaml_load(data_dir, 'mail.yaml')
    scores = score(mail)

    with open(path.join(data_dir, 'score.yaml'), 'w') as outfile:
        yaml.safe_dump(scores, outfile, default_flow_style=False)

def argparse_main(args):
    data_dir = path.join(args.output_dir, 'data')
    main(args.logger, data_dir)

def argparse_configure(subparsers):
    parser = subparsers.add_parser(
        'score',
        help='Score snapshots based on ingested data.')
    parser.set_defaults(func=argparse_main)
