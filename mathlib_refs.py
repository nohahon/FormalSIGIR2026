import os
import re
import bibtexparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote, urlparse
import mwparserfromhell
import yaml
import argparse



# Configuration #DELETE!!
HOME = os.getcwd()
MATHLIB4_LOC = os.path.join(HOME,'mathlib4')
USER_AGENT = "Test Theorem Retrieval (your@username.com)"
REQUEST_DELAY = 1  # seconds between requests to avoid rate limiting
WIKI_API_URL = "https://en.wikipedia.org/w/api.php"
SE_API_URL = "https://api.stackexchange.com/2.3/questions"
LEAN_FINDER_URL = "delta-lab-ai/Lean-Finder"
WIKIDATA_PREFIX = 'https://www.wikidata.org/wiki/'
HEADERS = {"User-Agent": USER_AGENT}
mathlib_url = 'https://github.com/leanprover-community/mathlib4/tree/ed96f50f75b1f89c4561f2ba2d837eb169052094/'


PROPERTY_DICT = {"QID":"qid","Label":"Len",
                 "Description":"Den",
                 "instance of":'P31',
                 "part of":'P37',
                 "Formal Proof":"P1603",
                 "MaRDI Profile Type":"P1460",
                 "Wikidata QID":"P12",
                 "full work available at URL":"P205",
                 "formalized in :":"P1648",
                 "date":"P140",
                 "author":"P16",
                 "author name string":"P43"}
KEYS_FOR_FORMAL_PROOFS = {"Len":"",
                          "P31":"Q6480412",
                          "qid":'',
                          "Den":'',
                          "P205":'',
                          "P1648":'Q27041',
                          "P140":'',
                          "P16":'',
                          "P43":''}


#### Handle wikipedia theorems specifically

def get_theorems_bulk(titles):
    results = []
    # Wikipedia allows up to 50 titles per API call
    BATCH_SIZE = 50

    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i: i + BATCH_SIZE]
        # print(f"Fetching batch {i} to {i + len(batch)}...")

        params = {
            "action": "query",
            "format": "json",
            "prop": "revisions",
            "rvprop": "content",  # Get the raw wikitext
            "titles": "|".join(batch),
            "redirects": 1
        }

        try:
            r = requests.post(WIKI_API_URL, data=params, headers=HEADERS, timeout=30)
            data = r.json()
        except Exception as e:
            print(f"Error fetching batch: {e}")
            continue
        if data['query'].get('normalized'):
            normalizations_dict = {it['from']:it['to'] for it in data['query']['normalized']}
        else:
            normalizations_dict = {}
        if data['query'].get('redirects'):
            redirects_dict = {it['from']:it['to'] for it in data['query']['redirects']}
            fragments_dict = {it['to']:it['tofragment'] for it in data['query']['redirects'] if 'tofragment' in it.keys()}
            # if fragments_dict:
            #     print(fragments_dict)
        else:
            redirects_dict = {}
            fragments_dict = {}
        batch_redirected = [{'original':b, 'redirected':redirects_dict.get(normalizations_dict.get(b,b),normalizations_dict.get(b,b))} for b in batch]
        # batch_redirected = [it if it['redirected'] else {'original':it['original'],'redirected':it['original']} for it in batch_redirected]
        for it in batch_redirected:
            if '#' in it['original']:
                it['section_info'] = unquote(it['original'].split('#')[-1]).replace('_',' ')
            else:
                it['section_info'] = fragments_dict.get(it['redirected'])
        pages = data.get("query", {}).get("pages", {})
        title_to_id = {page_data.get('title','Unknown'):page_id for page_id, page_data in pages.items()}
        for b in batch_redirected:
            # print(b)
            page_id = title_to_id.get(b['redirected'])
            page_data = pages.get(page_id)

            # Handle missing pages or redirects that failed
            if "missing" in page_data:
                results.append('')
                continue

            # Extract the raw wikitext
            try:
                raw_text = page_data["revisions"][0]["*"]
            except (KeyError, IndexError):
                results.append('')
                continue

            # --- LOCAL PARSING ---
            # Parse the text into a tree object
            wikicode = mwparserfromhell.parse(raw_text)

            # Find section by heading name (case-insensitive usually preferred)
            # matches=... does a regex match on the heading title
            if b['section_info']:
                theorem_sections = wikicode.get_sections(matches=b['section_info'])
            else:
                theorem_sections = wikicode.get_sections(matches=r"(?i)^Theorem|Statement|Formulation|Formal Statement|Definition$")

            if theorem_sections:
                # Pure section content (no heading text, no == == markup)
                content = theorem_sections[0].strip_code()  # plain text
                # content = str(theorem_sections[0])                # ← uncomment if you want to keep wikitext
            else:
                # Fallback: the lead/introductory section (the article summary)
                lead = wikicode.get_sections(
                    include_lead=True,
                    include_headings=False  # harmless for lead, keeps API consistent
                )[0]
                content = lead.strip_code()  # plain text
                # content = str(lead)                               # ← keep wikitext if preferred

            results.append(content if content.strip() else '')  # optional: treat empty as None
    return results


#### Mathlib References
def extract_references():
    # extracts references from all lean files in mathlib4
    # returns dict[dict[list]]] keys are filepaths
    files_w_refs = {}
    for dirpath, dirnames, filenames in os.walk(os.path.join(HOME,'mathlib4')):
        for filename in filenames:
            if not filename.endswith('.lean'):
                continue
            with open(os.path.join(dirpath,filename), encoding='utf-8') as fh:
                try:
                    mathlib_file = fh.read()
                except:
                    print(os.path.join(dirpath,filename))
            # are given under after a line ## References
            mathlib_file_sp = mathlib_file.split('## ')
            for line in mathlib_file_sp:
                if line.startswith('References'):
                    endcomment = re.search('-/',line)
                    line = line[:endcomment.start()] if endcomment else line[:]
                    # References following mathlib's refs.bib file follow the pattern [ref_identifier]
                    line_bibrefs = re.findall(r'\[\S+\]',line)
                    # Matches links in general
                    line_wikilinks = re.findall(r'http\S+[A-Za-z\d]',line)
                    line_wikilinks = [link+')' if '(' in link and not ')' in link else link for link in line_wikilinks ]
                    if line_bibrefs or line_wikilinks:
                        files_w_refs[os.path.join(dirpath,filename)] = {'bibrefs':line_bibrefs,'wikilinks':line_wikilinks}
                    break
    return files_w_refs

def match_bibrefs_to_bib_file(books_ok=False):
    # Extracts zbl_ids from retrieved mathlib references
    # returns: dict[list] keys are filepaths
    files_w_refs = extract_references()
    # This is a processed file, with zbl_ids added compared to mathlib's default refs.bib file
    bibtex = bibtexparser.load(open(os.path.join(HOME,'references_with_zbl.bib'),encoding='utf-8'))
    bibtex_entries = bibtex.entries
    #collection of all identifiers in the bib file
    bibtex_ids = [entry['ID'] for entry in bibtex.entries]
    nonbooks_w_zbl = {}
    for key in files_w_refs.keys():
        #remove bracket from reference text
        ids = [id_w_brackets[1:-1] for id_w_brackets in files_w_refs[key]['bibrefs']]
        #match these to the collected ones
        bibtex_pos = [bibtex_ids.index(id) for id in ids if id in bibtex_ids]
        bibtex_pos = [i for i in bibtex_pos if 'zbl_new' in bibtex_entries[i].keys()]
        if not books_ok:
            bibtex_pos = [i for i in bibtex_pos if not bibtex_entries[i]['ENTRYTYPE']=='book']

        nonbooks_w_zbl[key] = [bibtex_entries[i]['zbl_new'] for i in bibtex_pos]
        if not nonbooks_w_zbl[key]:
            nonbooks_w_zbl.pop(key)
    return nonbooks_w_zbl




###Stacks attribute
def extract_stacks_attribute_refs():
    # we identify lines of mathlib4 code which reference the stacks project using the
    # @stacks tag returns list[dict], items containing tags, lean code, and tailor-made for import \
    # into mardi
    files_w_refs = {}
    # j =0
    for dirpath, dirnames, filenames in os.walk(os.path.join(HOME,'mathlib4')):
        for filename in filenames:
            if not filename.endswith('.lean'):
                continue
            # j+=1
            # if j%100==0:
            #     print(filename)
            with open(os.path.join(dirpath,filename), encoding='utf-8') as fh:
                try:
                    mathlib_file = fh.readlines()
                except:
                    print(os.path.join(dirpath,filename))
            part_of_stacks_thm = False
            for i in range(len(mathlib_file)):
                line = mathlib_file[i]
                if line.startswith('@[stacks'):
                    part_of_stacks_thm = True
                    stacks_tag = line[len('@[stacks '):len('@[stacks ')+4]
                    stacks_comment = line[len('@[stacks ')+5:-2].replace('"','')
                    files_w_refs[(stacks_tag, stacks_comment)] = {'code':"",'url':''}
                    files_w_refs[(stacks_tag,stacks_comment)]['url'] = (
                            os.path.join(dirpath,filename)[len(os.path.join(HOME,'mathlib4')):]
                            +f"#L{i+2}").replace(os.path.sep,'/')
                elif part_of_stacks_thm:
                    if not line.strip():
                        files_w_refs[(stacks_tag,stacks_comment)]['url'] += f"-L{i}"
                        part_of_stacks_thm = False
                    else:
                        files_w_refs[(stacks_tag,stacks_comment)]['code'] += line

        stacks_dict = [{'stacks tag': key[0], 'code': files_w_refs[key]['code'], 'Len': f'Formal Proof of Stacks Project Tag {key[0]}', 'Den': key[1],
                        'url':  mathlib_url+
                                 files_w_refs[key]['url']} for key in files_w_refs.keys()]

    return stacks_dict

def augment_informal_proof(proof,df):
    offset = 0
    # for match in re.finditer('Lemma ((\d+\.)+\d+)|Proposition ((\d+\.)+\d+)|Theorem ((\d+\.)+\d+)|Equation ((\d+\.)+\d+)',proof):
    for match in re.finditer(
            '((\d+\.)+\d+)', proof):
        for group in match.groups():
            if group and re.match('(\d+\.)+\d+',group):
                try:
                    augment_statement = df[df['reference']==group].statement.values[0]
                except:
                    print(group)
                    print(proof)
                    augment_statement = ''
                break
        proof = (proof[:match.end()+offset] + " [[" +
                 augment_statement + "]]" +
                proof[match.end()+offset:])
        offset += len(" [[" +
                 augment_statement + "]]")
    return proof

def lean_search(df,column, new_col_name = 'lean_search'):

    texts = df[column].to_list()
    response_jsons_full = []
    headers = {
        'accept': 'application/json',
        # Already added when you pass json=
        # 'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
    }
    for i in range(len(texts)//10+1):
        json_data = {
        'query': [text[:19000] for text in texts[10*i:10*(i+1)]],
        'num_results': 10,
        }
        response = requests.post('https://leansearch.net/search',headers=headers,json=json_data)
        print(i*10)
        try:
            response_jsons_full += response.json()
        except Exception as e:
            print(e)
    df[new_col_name] = response_jsons_full
    return df


def match_cond_code_and_module(lean_search_item, df_row):
    lean_search_result = lean_search_item['result']
    if not lean_search_result['module_name'] in df_row['module_name']:
        return []
    else:
        i = df_row['module_name'].index(lean_search_result['module_name'])

    if lean_search_result['signature']:
        return [i] if (lean_search_result['signature'].replace(' ', '').replace('\n', '')
                in df_row.code[i].replace(' ', '').replace('\n', '')) else []
    else:
        return [i] if (lean_search_result['name'][-1]
                       in df_row['formal_statement'][i]) else []



def match_cond_module(lean_search_item, df_row):
    lean_search_result = lean_search_item['result']
    if not lean_search_result['module_name'] in df_row['module_name']:
        return []
    else:
        return [df_row['module_name'].index(lean_search_result['module_name'])]


# def match_cond_name(lean_search_item, df_row):
#     return lean_search_item['result'].get('name') == df_row['decls']

def recalls(lean_search_results, df_row, match_condition,n):
    recalled = []
    for lean_search_item in lean_search_results[:n]:
        if match_condition=='module':
            recalled+=match_cond_module(lean_search_item, df_row)
        elif match_condition=='code':
            recalled += match_cond_code_and_module(lean_search_item, df_row)
    return len(set(recalled))/len(df_row['module_name'])

def df_evaluate(df, text_column, output_suffix='', avail_columns=['module_name'], retriever='lean_search'):
    # if retriever=='lean_search':
    #     df = lean_search(df, text_column + output_suffix, 'lean_search' + output_suffix)
    # else:
    retriever_func = globals()[retriever]
    #this function must behave the same way that lean_search does!
    #that is, given a dataframe as input with specified input column, it appends a column named retriever + output_suffix.
    #Entries in this column MUST be of the form list["result":{"module_name":list[],"signature":str,"name":list[],...},...]
    df = retriever_func(df, text_column + output_suffix, retriever + output_suffix)


    def _get_scores(df,output_suffix,avail_columns):

        if 'module_name' in avail_columns:
            match_condition='module'
            df['module_match_R@1'+output_suffix] = df.apply(lambda x:
                                recalls(x['lean_search'+output_suffix], x, match_condition,1), axis=1)
            df['module_match_R@5'+output_suffix] = df.apply(lambda x:
                                recalls(x['lean_search'+output_suffix], x, match_condition,5), axis=1)
            df['module_match_R@10'+output_suffix] = df.apply(lambda x:
                                recalls(x['lean_search'+output_suffix], x, match_condition,10), axis=1)
            print('module_match_R@1: ',df['module_match_R@1'+output_suffix].mean())
            print('module_match_R@5: ', df['module_match_R@5'+output_suffix].mean())
            print('module_match_R@10: ', df['module_match_R@10'+output_suffix].mean())

        if 'code' in avail_columns and 'module_name' in avail_columns:
            match_condition='code'
            df['full_match_R@1: '+output_suffix] = df.apply(lambda x:
                                recalls(x['lean_search'+output_suffix], x, match_condition,1), axis=1)
            df['full_match_R@5: '+output_suffix] = df.apply(lambda x:
                                recalls(x['lean_search'+output_suffix], x, match_condition,5), axis=1)
            df['full_match_R@10: '+output_suffix] = df.apply(lambda x:
                                recalls(x['lean_search'+output_suffix], x, match_condition,10), axis=1)
            print(df['full_match_R@1: '+output_suffix].mean())
            print(df['full_match_R@5: '+output_suffix].mean())
            print(df['full_match_R@10: '+output_suffix].mean())
        return df

    df = _get_scores(df,'',avail_columns)
    if output_suffix:
        df = _get_scores(df,output_suffix,avail_columns)

    return df

def evaluate_zbmath_no_books(test=False,retriever='lean_search'):
  #Builds and evaluate zbmath 
    nonbooks_w_zbl = match_bibrefs_to_bib_file()

    all_kinds_ids = []
    for key in nonbooks_w_zbl.keys():
        all_kinds_ids += nonbooks_w_zbl[key]

    nonbooks_w_zbl_inv = {id:[] for id in all_kinds_ids}
    for key in nonbooks_w_zbl:
        for id in nonbooks_w_zbl[key]:
            nonbooks_w_zbl_inv[id].append(key)

    zbl_refs_df = pd.DataFrame([{"zbl_id":key, "module_name":[val[:val.index('.lean')].replace(
        os.path.join(HOME,'mathlib4'),'').split(os.path.sep)[1:] for val in value]}
                                for key, value in nonbooks_w_zbl_inv.items()])


    #collection of abstracts. Can be obtained by querying api.zbmath.org
    zb_docs_df = pd.read_csv(os.path.join(HOME,'leandocs.csv'),
                              encoding='utf-8',delimiter=',',dtype=str)

    zbl_docs_df_test = zbl_refs_df.join(zb_docs_df.set_index('zbl_id'), on='zbl_id', how='inner')
    zbl_docs_df_test = zbl_docs_df_test.dropna(subset='texts',axis='rows')

    ## test
    if test:
        df_evaluate(zbl_docs_df_test,'texts',retriever=retriever)

    return zbl_docs_df_test

def evaluate_zbmath_with_books(test=False,retriever='lean_search'):
    all_w_zbl = match_bibrefs_to_bib_file(books_ok=True)

    all_kinds_ids = []
    for key in all_w_zbl.keys():
        all_kinds_ids += all_w_zbl[key]

    all_w_zbl_inv = {id:[] for id in all_kinds_ids}
    for key in all_w_zbl:
        for id in all_w_zbl[key]:
            all_w_zbl_inv[id].append(key)

    zbl_refs_df_full = pd.DataFrame([{"zbl_id":key, "module_name":[val[:val.index('.lean')].replace(
        os.path.join(HOME,'mathlib4/'),'').split(os.path.sep)[1:] for val in value]}
                                for key, value in all_w_zbl_inv.items()])
    zb_docs_df_full = pd.read_csv(os.path.join(HOME,'leandocs.csv'), encoding='utf-8',names=['zbl_id','texts'],dtype=str)
    zb_docs_df_full = zb_docs_df_full.sort_values(by='texts',key = lambda x:x.str.len())
    zb_docs_df_full = zb_docs_df_full.sort_values(by='zbl_id')
    zb_docs_df_full = zb_docs_df_full.drop_duplicates(subset='zbl_id',keep='first')
    zbl_refs_df_full = zbl_refs_df_full.join(zb_docs_df_full.set_index('zbl_id'),on='zbl_id',how='inner')

    ##test
    zbl_refs_df_full_test = zbl_refs_df_full.dropna(axis='rows',subset='texts')
    if test:
        df_evaluate(zbl_refs_df_full_test,'texts',retriever=retriever)

    return zbl_refs_df_full_test


def evaluate_stacks_project(test=False,retriever='lean_search'):
    stacks_dict = extract_stacks_attribute_refs()
    stacks_formal_df = pd.DataFrame(stacks_dict)

    #run "python stacks.py" in order to create stacks_project.csv
    stacks_texts_full = pd.read_csv(os.path.join(HOME,'stacks_project.csv'),encoding='utf-8')
    stacks_texts_full['content'] = stacks_texts_full['content'].apply(lambda x: BeautifulSoup(x,features="lxml").text[2:-1])
    stacks_texts_full['statement'] = stacks_texts_full.content.apply(lambda text:
                                            text[:text.index('Proof.')].strip() if 'Proof.' in text else text.strip())
    stacks_texts_full['proof'] = stacks_texts_full.content.apply(lambda text:
                        text[text.index('Proof.'):] .strip() if 'Proof.' in text else "")
    stacks_formal_informal = stacks_formal_df.join(stacks_texts_full.set_index('tag'),on='stacks tag').dropna(subset=['content'],axis='rows')
    stacks_formal_informal['formal_proof'] = stacks_formal_informal.code.apply(lambda x:":=".join(x.split(':=')[1:]) if ':=' in x else '')
    stacks_formal_informal['formal_statement'] = stacks_formal_informal.code.apply(lambda x:x.split(':=')[0] if ':=' in x else x)
    stacks_formal_informal['augmented_proof'] = stacks_formal_informal.proof.apply(lambda x:augment_informal_proof(x,stacks_texts_full))
    stacks_formal_informal['augmented_statement'] = stacks_formal_informal.statement.apply(lambda x:x[:25]+augment_informal_proof(x[25:],stacks_texts_full))
    stacks_formal_informal['augmented_content'] = stacks_formal_informal.content.apply(lambda x:x[:25]+augment_informal_proof(x[25:],stacks_texts_full))
    stacks_formal_informal['module_name'] = stacks_formal_informal['url'].apply(lambda x:x[:x.index('.lean')].replace(mathlib_url,'').split('/')[1:])


    #### Evaluate
    stacks_formal_informal_eval_statement = stacks_formal_informal.groupby('augmented_statement').agg(
        {'module_name':lambda x:x.tolist(),
         'formal_statement':lambda x:x.tolist(),
         'code':lambda x:x.tolist()},axis=1).reset_index()
    if test:
        print("Input: Augmented Statement")
        df_evaluate(stacks_formal_informal_eval_statement,'augmented_statement',avail_columns=['module_name','code'])

    stacks_formal_informal_eval_proof = stacks_formal_informal.groupby('augmented_proof').agg(
        {'module_name':lambda x:x.tolist(),
         'formal_statement':lambda x:x.tolist(),
         'code':lambda x:x.tolist()},axis=1).reset_index()
    if test:
        print("Input: Augmented Proof")
        df_evaluate(stacks_formal_informal_eval_proof,
                    'augmented_proof',
                    avail_columns=['module_name','code'],
                    retriever=retriever)

    stacks_formal_informal_eval_content = stacks_formal_informal.groupby('augmented_content').agg(
        {'module_name':lambda x:x.tolist(),
         'formal_statement':lambda x:x.tolist(),
         'code':lambda x:x.tolist()},axis=1).reset_index()
    if test:
        print("Input: Augmented Statement + Augmented Proof")
        df_evaluate(stacks_formal_informal_eval_content,'augmented_content',avail_columns=['module_name','code'])

    return stacks_formal_informal_eval_statement, stacks_formal_informal_eval_proof, stacks_formal_informal_eval_content

def evaluate_wikipedia_references(test=False,retriever='lean_search'):
    files_w_refs = extract_references()
    files_w_wikilinks = {key:[link for link in files_w_refs[key]['wikilinks'] if 'wikipedia' in link] for key in files_w_refs.keys()}
    files_w_wikilinks = [{"uri": key, "link": val } for key, value in files_w_wikilinks.items() for val in value]
    wiki_df = pd.DataFrame(files_w_wikilinks)
    wiki_df['module_name'] = wiki_df['uri'].apply(lambda x:x[:x.index('.lean')].replace(MATHLIB4_LOC,'').split(os.path.sep)[1:])
    wiki_df = wiki_df[wiki_df['link'].str.contains('en.wikipedia')]
    wiki_df = wiki_df[wiki_df['module_name'].apply(lambda x:x[0]=='Mathlib')]
    wiki_df['title'] = wiki_df.link.apply(lambda x:unquote(x.split('/')[-1]))
    wiki_df['texts'] = get_theorems_bulk(wiki_df.title.to_list())
    wiki_df = wiki_df.groupby('texts').agg({'module_name':lambda x:x.tolist()}).reset_index()
    if test:
        df_evaluate(wiki_df, 'texts',retriever=retriever)
    return wiki_df

def evaluate_1000_theorems(test=False,retriever='lean_search'):
    def _parse_1000_theorems_page():
        response = requests.get('https://leanprover-community.github.io/1000.html')
        soup = BeautifulSoup(response.text)
        soup_split = soup.main()
        soup_split_headers = [i for i, tag in enumerate(soup_split) if tag.name == 'h5']
        soup_split_by_headers = [soup_split[soup_split_headers[i]:soup_split_headers[i + 1]] for i in
                                 range(len(soup_split_headers) - 1)]
        soup_split_by_headers.append(soup_split[soup_split_headers[-1]:])
        soup_split_by_headers = soup_split_by_headers[1:]
        soup_split_sources = {split[0].contents[1].contents[0][:-1]: [split[i].attrs.get('href')
                                                                      for i in range(len(split)) if
                                                                      split[i].text == 'source'] for split in
                              soup_split_by_headers}
        theorems_code_sources = {}
        for qid, links in soup_split_sources.items():
            theorems_code_sources[qid] = {}
            for link in links:
                if not 'Mathlib/' in link:
                    continue
                uri = link[link.index('Mathlib/'):link.index('#')]
                line_nos = re.findall(r'\d+', link[link.index('#'):])
                try:
                    with open(os.path.join(HOME, 'mathlib4', uri), encoding='utf-8') as fh:
                        lines = fh.readlines()
                        try:
                            theorems_code_sources[qid][link] = "".join(lines[int(line_nos[0]) - 1:int(line_nos[1])])
                        except:
                            print(line_nos)
                except:
                    print(link)
        return theorems_code_sources
    #obtained from https://github.com/leanprover-community/mathlib4/blob/master/docs/1000.yaml
    with open(os.path.join(HOME,"1000.yaml"),encoding='utf-8') as stream:
        theorems_dict = yaml.safe_load(stream)
    theorems_project_df = pd.DataFrame(theorems_dict).transpose()
    theorems_project_df.index.name = 'wikidata_qid'

    #sparql_query = 'https://w.wiki/HcXE'
    #theorems from wikidata with english-language wikipedia article. obtained from wikidata via query https://w.wiki/HcXE
    theorems_df = pd.read_json(os.path.join(HOME,'named_theorems.json'), dtype={'date':str})
    theorems_df['wikidata_qid'] = theorems_df.cid.apply(lambda x:x.split('/')[-1])
    theorems_df = theorems_df.join(theorems_project_df,how='outer',on='wikidata_qid')
    formal_proofs_df = theorems_df.dropna(subset=['decl','decls','url'],axis='rows',how='all')
    theorems_code_sources = _parse_1000_theorems_page()
    theorems_code_sources = {key:value for key,value in theorems_code_sources.items() if value}
    module_names = {key:[val_key[val_key.index('Mathlib/'):] for val_key in value.keys()]
                    for key,value in theorems_code_sources.items()  if value.keys()}
    formal_proofs_df['module_name'] = formal_proofs_df.wikidata_qid.apply(lambda x:
                    [xi.split('.lean')[0].split('/') for xi in module_names.get(x,[])])
    formal_proofs_df['code'] = formal_proofs_df.wikidata_qid.apply(lambda x:
                                                    [value for key,value in theorems_code_sources.get(x,{}).items()])
    formal_proofs_df = formal_proofs_df.dropna(subset=['article'],axis='rows')
    formal_proofs_df = formal_proofs_df.dropna(subset=['code'],axis='rows')
    formal_proofs_df['formal_statement'] = formal_proofs_df.code.apply(lambda x:x.split(':=')[0] if ':=' in x else x)
    formal_proofs_df['title'] = formal_proofs_df.article.apply(lambda x:unquote(x.split('/')[-1]))
    formal_proofs_df['texts'] = get_theorems_bulk(formal_proofs_df['title'].to_list())
    ###only for evaluation
    formal_proofs_df_test = formal_proofs_df[formal_proofs_df['code'].map(len)>0]
    if test:
        df_evaluate(formal_proofs_df_test, 'texts', avail_columns=['code','module_name'],retriever=retriever)

    return formal_proofs_df_test

if __name__=="__main__":
    parser = argparse.ArgumentParser(
        description="Script that accepts test and retriever arguments"
    )

    # Add positional arguments with defaults using nargs='?'
    parser.add_argument(
        "test",
        nargs='?',  # Makes argument optional
        default="test",
        help="Mode (default: %(default)s)"
    )

    parser.add_argument(
        "retriever",
        nargs='?',
        default="lean_search",
        help="Retriever value argument (default: %(default)s)"
    )

    args = parser.parse_args()


    # Example of storing them in variables for later use:
    test     = args.test
    retriever = args.retriever
    if test =='test':
        test = True
    else:
        test = False

####zbmath documents not including books
    # retrieve lean files with zbmath references.
    print("Evaluating zbmath, no books")
    print(evaluate_zbmath_no_books(test,retriever))
    #----------------------------------------------------
    ####zbmath documents  including books
    print("Evaluating zbmath, books included")
    print(evaluate_zbmath_with_books(test,retriever))
#--------------------------------------------------------------------------------------
    ### Lean files with links to wikipedia

    print("Evaluating Wikipedia Links")
    print(evaluate_wikipedia_references(test,retriever))
    # --------------------------------------------------------------------------------------

    ### 1000 theorems
    print("Evaluating 1000 Theorems")
    print(evaluate_1000_theorems(test,retriever))
    # --------------------------------------------------------------------------------------

    #### Stacks
    print("Evaluating Stacks Project")
    print(evaluate_stacks_project(test,retriever))



