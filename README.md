# tumbleweed-review

Tools for ingesting various data sources and scoring Tumbleweed release stability.

## data sources

The following data sources our considered.

- [bugzilla](https://bugzilla.opensuse.org/)
- [opensuse-factory mailing list](https://lists.opensuse.org/archives/list/factory@lists.opensuse.org/)
- [Tumbleweed snapshot metadata](http://download.tumbleweed.boombatower.com/)

## scoring

The above data sources are reviewed and each snapshot is given a stability score. The goal being to error on the side of caution and to allow users to avoid troublesome releases. Obviously, there are many enthusiasts who enjoy encountering issues and working to resolve them, but others are looking for a relatively stable experience.

Releases with a low score will continue to impact future release scores with a gradual trail-off. Given that issues generally are not fixed immediately in the next release this assumes the next few releases may still be affected. If the issue persists and is severe it will likely be mentioned again in the mailing list and the score again reduced.

Major system components that are either release candidates or low minor releases are also considered to be risky. For example, recent `Mesa` release candidates caused white/black screens for many users which is not-trivial to recover from for less-technical users. Such issues come around from time to time since openQA does not test on real world hardware where such graphic driver issues are generally encountered.

Release stability is considered to be `pending` for the first week after release to allow time for reports to surface. This of course depends on enthusiasts who update often, encounter, and report problems.

The scoring is likely to be tweaked over time to reflect observations. It may also make sense to add a manual override feature to aid scoring when something critical is encountered.

## future

Integrating the scoring data into the [tumbleweed-cli](https://github.com/boombatower/tumbleweed-cli) would allow users to pick a minimum stability level or score and only update to those releases. Such a mechanism can be vital for systems run by family members, servers, or the wave of gamers looking for the latest OSS graphics stack.

## usage

A subcommand is provided for each data source, scoring, and output to markdown. Eventually, a one-stop command will be provided, but for now the data subcommands should be run first followed by scoring and then markdown.

- `bug`, `mail`, `snapshot`
- `score`
- `markdown`

Use the `--read-only` flag to clone the production site and dump local changed into it without committing. Otherwise use the `--output-dir` flag to dump elsewhere without a clone.

## production

The regularly updated site can be viewed at [review.tumbleweed.boombatower.com](http://review.tumbleweed.boombatower.com/).
