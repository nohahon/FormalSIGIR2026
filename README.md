This repository describes how to perform the experiments for the paper ``Bridging Formal and Informal Mathematics: Towards a multi modal retrieval task for formalized mathematics''.


## Installation

### Install Python deps
```shell
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```


### Clone mathlib4

git clone https://github.com/leanprover-community/mathlib4.git

### Setup
## Create stacks_project.csv
```shell
python -m stacks
```
## Create leandocs.csv

by querying api.zbmath.org with the ZBL_IDs in lean_zbl_ids.csv

## Usage

Output files and experiments for the LLM-based experiments in Section 4.4 are described in the file readme.txt in the folder LLM Experiments.

To rerun the retrieval experiments of section 4.3, run

```shell
python mathlib_refs.py
```

You can include your own retrieval function in mathlib_refs.py.
Make sure that your function works the same way as the default lean_search:
That is, given a dataframe as input with specified input column, it appends a column named retriever + output_suffix.
Entries in that column MUST be of the form list["result":{"module_name":list[],"signature":str,"name":list[],...},...]

To evaluate your retrieval function on all datasets, run
```shell
python mathlib_refs.py test your_retriever
```

