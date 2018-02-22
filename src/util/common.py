import os
from os import path
import shutil

CACHE_ROOT_DIR = 'tumbleweed-review'

def ensure_directory(directory):
    if not path.isdir(directory):
        os.makedirs(directory)

def jekyll_init(site_dir):
    from main import ROOT_PATH
    jekyll_dir = path.join(ROOT_PATH, 'jekyll')
    for name in ('.gitignore', '_config.yml', 'index.md'):
        shutil.copy(path.join(jekyll_dir, name), path.join(site_dir, name))
