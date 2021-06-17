#!/usr/bin/env python3
from os.path import dirname
from pathlib import Path
from collections import Counter

import file_cache

with open(Path(dirname(__file__)) / 'corrections.txt') as f:
    corrections_lines = f.readlines()
corrections = Counter(corrections_lines)

for correction, count in corrections.items():
    if count < 2:
        continue  # Only consider corrections that are submitted multiple times.
    artist_name, album_name, original_count, count = correction.strip().split('\t')
    original_count_cache, img_url = file_cache.get_from_cache(*[artist_name, album_name], func_name='_get_album_details').split(',')
    if original_count != original_count_cache:
        continue  # Skip values that are already updated
    print('Updating: '+correction)
    file_cache.update_cache(*[artist_name, album_name], func_name='_get_album_details', result=','.join((count, img_url)))

