FROM opensuse/tumbleweed
MAINTAINER Jimmy Berry <jimmy@boombatower.com>

RUN zypper -n in \
  git \
  python3-bugzilla \
  python3-pip \
  python3-pyaml \
  python3-requests \
  python3-xdg

# package not available
RUN pip3 install anytree

ADD . /srv
