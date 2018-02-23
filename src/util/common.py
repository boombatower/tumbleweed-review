from datetime import datetime
from datetime import timedelta
import os
from os import path
import requests
import shutil
from urllib.parse import urlparse

CACHE_ROOT_DIR = 'tumbleweed-review'

def ensure_directory(directory):
    if not path.isdir(directory):
        os.makedirs(directory)

def jekyll_init(site_dir):
    from main import ROOT_PATH
    jekyll_dir = path.join(ROOT_PATH, 'jekyll')
    tree_copy(jekyll_dir, site_dir, ignore=shutil.ignore_patterns('.template.md'))
    shutil.copy(path.join(ROOT_PATH, 'LICENSE'), path.join(site_dir, 'LICENSE'))

# Modified from shutil.copytree() to allow for dst to already exist.
def tree_copy(src, dst, symlinks=False, ignore=None):
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    if not path.exists(dst):
        # Changed to only create dir when not exists
        os.makedirs(dst)

    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                tree_copy(srcname, dstname, symlinks, ignore)
            else:
                shutil.copy2(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive tree_copy so that we can
        # continue with other files
        except Error as err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise Error(errors)

def request_cached_path(url, cache_dir):
    url_path = urlparse(url).path[1:] # Remove leading slash.
    return path.join(cache_dir, url_path)

def request_cached(url, cache_dir, ttl=timedelta(hours=1)):
    cache_path = request_cached_path(url, cache_dir)
    if path.exists(cache_path):
        cache_modified = datetime.fromtimestamp(path.getmtime(cache_path))
        cache_delta = datetime.now() - cache_modified
        if cache_delta <= ttl:
            return open(cache_path, 'r').read()
    else:
        ensure_directory(path.dirname(cache_path))

    response = requests.get(url)

    with open(cache_path, 'w') as cache_handle:
        cache_handle.write(response.text)

    return response.text

def release_parts(release):
    return release[0:4], release[4:6], release[6:8]
