import pandas as pd
import json
from concurrent.futures import as_completed
from requests_futures.sessions import FuturesSession
import requests
import os

# change if needed.
HOME = os.getcwd()
tag_url_prefix = 'https://stacks.math.columbia.edu/data/tag/'
tag_structure_suffix = '/structure'
tags_content_suffix = '/content/full'
parts = ['0ELQ', '0ELP', '0ELV', '0ELT', '0ELN', '0ELW', '0ELS', '0ELR', '0ELU']
structures = [json.loads(requests.get(tag_url_prefix+prt+tag_structure_suffix).content) for prt in parts]

def tree_to_list(tree, depth=0, parents=None):
    result = []
    if parents is None:
        parents = []

    for node in tree:
        try:
            node_info = {'tag': node['tag'], 'name':node['name'], 'reference':node['reference'],
                        'type':node['type'],'depth': depth, 'parents': parents}
            result.append(node_info)
        except:
            node_info = {'tag': node['tag'], 'name': 'N/A', 'reference': node['reference'],
                         'type': node['type'], 'depth': depth, 'parents': parents}
            result.append(node_info)
        if 'children' in node:
            result.extend(tree_to_list(node['children'], depth + 1, [node['tag']] + parents))

    return result

structure_list = tree_to_list(structures)
structure_df = pd.DataFrame(structure_list)

with FuturesSession() as session:
    futures = [session.get(tag_url_prefix+structure_df.iloc[_]['tag']+'/content/full') for _ in range(20950)]
    for future in as_completed(futures):
        response = future.result()

d = {'content':[future.result().content for future in futures]}
content_df = pd.DataFrame(d)
structure_df['content'] = content_df

structure_df.to_csv(os.path.join(HOME,'stacks_project.csv',index=False)
