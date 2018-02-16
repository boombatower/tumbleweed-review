import os
from os import path

CACHE_ROOT_DIR = 'tumbleweed-review'

def ensure_directory(directory):
    if not path.isdir(directory):
        os.makedirs(directory)
