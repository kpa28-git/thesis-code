# Kevin Patel

import sys
import os
from functools import partial
import logging

import numpy as np
import pandas as pd

from common_util import DT_HOURLY_FREQ, DT_BIZ_DAILY_FREQ, DT_CAL_DAILY_FREQ, get_custom_biz_freq
from mutate.common import STANDARD_DAY_LEN
from mutate.pattern_util import gaussian_breakpoints, uniform_breakpoints, get_sym_list, symbolize_value
from mutate.fracdiff import get_weights


""" ********** APPLY FUNCTIONS ********** """
def apply_rt_df(df, ser_transform_fn, freq=None, dna=True):	# regular transform
	res = df.transform(ser_transform_fn)
	return res.dropna(axis=0, how='all') if (dna) else res

def apply_gbt_df(df, ser_transform_fn, agg_freq, dna=True):	# groupby transform
	res = df.groupby(pd.Grouper(freq=agg_freq)).transform(ser_transform_fn)
	return res.dropna(axis=0, how='all') if (dna) else res

def apply_gagg_df(df, ser_agg_fn, agg_freq, dna=True):		# groupby aggregation
	res = df.groupby(pd.Grouper(freq=agg_freq)).agg(ser_agg_fn)
	return res.dropna(axis=0, how='all') if (dna) else res


""" ********** TRANSFORMS ********** """
def difference(num_periods):
	return lambda ser: ser.diff(periods=num_periods)

def expanding_fracdiff(d, size, thresh):
	"""
	Expanding Window Fractional Differencing
	XXX - Implement
	"""
	pass
# 	def expanding_fracdiff(ser):
# 		_ser = ser.dropna()
# 		weights = get_weights(d, size=_ser.size, thresh=thresh)
# 		# Determine initial calcs to be skipped based on weight-loss threshold
# 		weight_changes = np.cumsum(abs(weights))
# 		weight_changes /= weight_changes[-1]
# 		skip = weight_changes[weight_changes > thresh].shape[0]

# 	return lambda ser: ser.transform(dot_weights_fn)

def fixed_fracdiff(d, size, thresh):
	"""
	Fixed Window Fractional Differencing
	"""
	weights = get_weights(d, size=size, thresh=thresh)
	dot_weights_fn = lambda ser: ser.dot(weights)
	return lambda ser: ser.dropna().rolling(window=len(weights), min_periods=len(weights)).apply(dot_weights_fn)

def moving_average(num_periods):
	return lambda ser: ser.rolling(window=num_periods, min_periods=num_periods).mean()

NORM_FUN_MAP = {
	'dzn': lambda ser: (ser-ser.mean()) / ser.std(),
	'dmx': lambda ser: 2 * ((ser-ser.min()) / (ser.max()-ser.min())) - 1
}

def normalize(norm_type):
	return lambda ser: ser.transform(NORM_FUN_MAP[norm_type])

SYM_MAP = {
	"gau": gaussian_breakpoints,
	"uni": uniform_breakpoints
}

def symbolize(sym_type, num_sym, numeric_symbols=True):
	"""
	Return symbolization encoder.
	Does not perform paa or any other subseries downsampling/aggregation.

	Args:
		sym_type (str): determines type of breakpoint used
		num_sym (int): alphabet size
		numeric_symbols (boolean): numeric or non-numeric symbols

	Return:
		symbol encoder function
	"""
	breakpoint_dict = SYM_MAP[sym_type]
	breakpoints = breakpoint_dict[num_sym]
	symbols = get_sym_list(breakpoints, numeric_symbols=numeric_symbols)
	encoder = partial(symbolize_value, breakpoints=breakpoints, symbols=symbols)

	logging.debug('breakpoints: ' +str(breakpoints))
	logging.debug('symbols: ' +str(symbols))

	return lambda ser: ser.transform(encoder)


""" ********** FILTERS ********** """
def single_row_filter(specifier):
	if (specifier == 'f'):
		return lambda ser: ser.loc[ser.first_valid_index()] if (ser.first_valid_index() is not None) else None
	elif (specifier == 'l'):
		return lambda ser: ser.loc[ser.last_valid_index()] if (ser.last_valid_index() is not None) else None
	elif (isinstance(specifier, int)):
		return lambda ser: ser.nth(specifier)


""" ********** JSON-STR-TO-CODE TRANSLATORS ********** """
RUNT_FN_TRANSLATOR = {
	"diff": difference,
	"efracdiff": expanding_fracdiff,
	"ffracdiff": fixed_fracdiff,
	"ma": moving_average,
	"norm": normalize,
	"sym": symbolize,
	"srf": single_row_filter
}

RUNT_TYPE_TRANSLATOR = {
	"rt": apply_rt_df,
	"gbt": apply_gbt_df,
	"gagg": apply_gagg_df
}

RUNT_FREQ_TRANSLATOR = {
	"hourly": DT_HOURLY_FREQ,
	"cal_daily": DT_CAL_DAILY_FREQ,
	"biz_daily": DT_BIZ_DAILY_FREQ,
	None: None
}