# Kevin Patel

import sys
import os
import logging

import numpy as np
import pandas as pd

from common_util import load_json
from data.common import ACCESS_UTIL_DIR, default_col_subsetsfile


col_subsetsfile = default_col_subsetsfile

col_subsetters = load_json(col_subsetsfile, dir_path=ACCESS_UTIL_DIR)


"""
	*********** ACCESS EXAMPLES ***********
	
	Filter trmi etf news v2:
		trmi_etf_news_v2_qual = [col_subsetters['#trmi']['all'], col_subsetters['#trmi']['etf_filter'], col_subsetters['#trmi']['news_filter'], col_subsetters['#trmi']['v2_filter']]
		trmi_cols = chained_filter(df.columns, trmi_etf_news_v2_qual)
		df.loc[:, trmi_cols]

	Filter pba ohlc data:
		pba_ohlc_qual = [col_subsetters['#pba']['ohlc']]
		pba_cols = chained_filter(df.columns, pba_ohlc_qual)
		df.loc[:, pba_cols]

	Filter pba ohlc and vol ohlc data:
		pba_ohlc_qual = [col_subsetters['#pba']['ohlc']]
		vol_ohlc_qual = [col_subsetters['#vol']['ohlc']]
		pba_cols = chained_filter(df.columns, pba_ohlc_qual)
		vol_cols = chained_filter(df.columns, vol_ohlc_qual)
		df.loc[:, pba_cols + vol_cols]

	Filter all rows before 2018:
		date_range = {
		    'id': ('lt', 2018)
		}
		df.loc[search_df(df, date_range)]

	Group by four year periods:
		df.groupby(pd.Grouper(freq='4Y'))




"""