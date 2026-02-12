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
## Create leandocs.csv by querying api.zbmath.org with the ZBL_IDs in lean_zbl_ids.csv

## Usage

Output files and experiments for the LLM-based experiments in Section 4.4 are described in the file readme.txt in the folder LLM Experiments.
