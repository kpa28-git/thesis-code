# Kevin Patel

# *********** COMMON TO ALL CRUNCH PACKAGES ***********
import sys
from os.path import dirname, realpath

sys.path.insert(0, dirname(dirname(realpath(sys.argv[0]))))

from common_util import *

# ********** SPECIFIC TO THIS CRUNCH PACKAGE **********
# PACKAGE CONSTANTS
TRMI_CONFIG_FNAME = 'trmi.json'
TRMI_CONFIG_DIR = CRUNCH_DIR

# PACKAGE DEFAULTS
default_pricefile = 'richard@marketpsychdata.com--N166567660.csv'
default_pathsfile = 'paths.json'
default_columnsfile = 'columns.json'
default_rowsfile = 'rows.json'
