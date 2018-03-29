# Kevin Patel

# *********** COMMON TO ALL CRUNCH PACKAGES ***********
import sys
from os.path import dirname, realpath

sys.path.insert(0, dirname(dirname(dirname(realpath(sys.argv[0])))))

# ********** SPECIFIC TO THIS CRUNCH PACKAGE **********
# DATA

from os import sep
from common_util import DATA_DIR

# PACKAGE CONSTANTS
DR_NAME = 'data_record'
DR_FMT = 'csv'

DR_IDS = ['id', 'name', 'dir']										# Autogenerated columns
DR_REQ = ['freq', 'root', 'basis', 'stage']							# Minimum needed to dump a df
DR_STAGE = ['recon_type', 'eda_type']								# Stage specific dump requirements, prepended by stage name
DR_META = ['raw_cat', 'history']									# Other misc metadata (mutable: all)
DR_GEN = ['size', 'dumptime', 'hash', 'created', 'modified'] 		# Other autogenerated columns (mutable: all)
DR_COLS = DR_IDS + DR_REQ + DR_STAGE + DR_META + DR_GEN

ACCESS_UTIL_DIR = DATA_DIR +'access_util' +sep

# PACKAGE DEFAULTS
default_col_subsetsfile = 'col_subsets_hourly.json'
default_row_subsetsfile = 'row_subsets_hourly.json'
