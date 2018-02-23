from datetime import date
from os import path
from util.common import ensure_directory
from util.common import release_to_date
from util.common import yaml_load
import yaml

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

def bug_score(bugs):
    return len(bugs) / 10

def mail_score(mail_release):
    impact = 0
    for thread in mail_release['threads']:
        impact += max(min(thread['reference_count'], 25), 3)
    return impact

def snapshot_score(snapshot):
    if not snapshot:
        return 10

    impact = 0

    binary_interest = snapshot['binary_interest']
    binary_interest_changed = snapshot['binary_interest_changed']

    parts = binary_interest['kernel-source'].split('.')
    if len(parts) == 3:
        minor = int(parts[2])
        if minor <= 1:
            impact += 15
        elif minor <= 3:
            impact += 10

    if 'Mesa' in binary_interest_changed:
        parts = binary_interest['Mesa'].split('.')
        if len(parts) == 3:
            minor = int(parts[2])
            if minor == 0:
                impact += 5

    if snapshot['binary_unique_count'] / snapshot['binary_count'] > 0.35:
        impact += 10

    return impact

def score(bugs, mail, snapshot):
    scores = {}

    impact_previous = None
    for release, mail_release in mail.items():
        impact = 0
        impact += bug_score(bugs.get(release, []))
        impact += mail_score(mail_release)
        impact += snapshot_score(snapshot.get(release, None))

        if impact_previous:
            impact += 0.40 * impact_previous
        impact_previous = impact

        score = int(100 - impact)
        scores[release] = {
            'score': score,
            'stability_level': stability_level(release, score),
        }

    return scores

def main(logger_, data_dir):
    global logger
    logger = logger_

    ensure_directory(data_dir)

    bugs = yaml_load(data_dir, 'bug.yaml')
    mail = yaml_load(data_dir, 'mail.yaml')
    snapshot = yaml_load(data_dir, 'snapshot.yaml')
    scores = score(bugs, mail, snapshot)

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
