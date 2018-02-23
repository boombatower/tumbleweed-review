---
title: About
---

<iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/CSXRreUjiIc" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>

Install [tumbleweed-cli](https://github.com/boombatower/tumbleweed-cli) to take advantage of _Tumbleweed Snapshots_.

```
zypper in tumbleweed-cli
tumbleweed init
```

During init the original repo files are kept and can be restored by:

```
tumbleweed uninit
```

To see local status:

```
tumbleweed status
```

To update to the _latest_ snapshot:

```
tumbleweed update
```

To install a specific snapshot:

```
tumbleweed switch --install SNAPSHOT
```

Due to a [hosting limitation](http://release-tools.opensuse.org/2018/02/09/w05-06.html#tumbleweed-snapshots-update-and-mesa-postmortem-usage) _50_ snapshots will be kept. Given snapshots are released near daily that will generally cover over two months.

## links

- [Announcing Tumbleweed Snapshots: Rolling With You](http://release-tools.opensuse.org/2017/11/22/Tumbleweed-Snapshots.html)
- [Tumbleweed dasbhoard](http://tumbleweed.boombatower.com/) (refreshed on load, will take a minute)
- [Tumbleweed snapshots download hub](http://download.tumbleweed.boombatower.com/)
- source code
  - [generator](https://github.com/boombatower/tumbleweed-review)
  - [site](https://github.com/boombatower/tumbleweed-review-site)
