# Kevin Patel

# *********** COMMON TO ALL CRUNCH PACKAGES ***********
import sys
from os.path import dirname, realpath

sys.path.insert(0, dirname(dirname(dirname(realpath(sys.argv[0])))))

# ********** SPECIFIC TO THIS CRUNCH PACKAGE **********
# RECON
from os import sep
from common_util import RECON_DIR

# OTHER STAGE DEPENDENCIES


# PACKAGE CONSTANTS
DATASET_DIR = RECON_DIR +'dataset' +sep
REPORT_DIR = RECON_DIR +'report' +sep
TEST_DIR = RECON_DIR +'test' +sep
PIPE_DIR = RECON_DIR +'pipe' +sep
CV_DIR = RECON_DIR +'cv' +sep
dum = 0


# PACKAGE DEFAULTS
default_pipefile = 'pipe.json'
default_cv_file = 'cv_kfold.json'
default_gta_dataset = 'drl.json'
default_gta_test = 'corr_count.json'


# PACKAGE UTIL FUNCTIONS

