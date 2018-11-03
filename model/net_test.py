"""
Kevin Patel
"""

import sys
import os
from os import sep
from os.path import splitext
from functools import partial, reduce
import logging

import numpy as np
import pandas as pd
from dask import delayed, compute, visualize
from keras.models import Sequential
from keras.layers import Dense, Activation, Dropout, LSTM
from keras.optimizers import SGD, RMSprop, Adadelta, Adam, Adamax, Nadam

from common_util import RECON_DIR, JSON_SFX_LEN, DT_CAL_DAILY_FREQ, get_cmd_args, in_debug_mode, pd_common_index_rows, load_json, benchmark
from model.common import DATASET_DIR, FILTERSET_DIR, default_dataset, default_nt_filter, default_target_col_idx
from model.model_util import prepare_transpose_data, prepare_masked_labels
from model.models.ThreeLayerBinaryFFN import ThreeLayerBinaryFFN
from model.models.OneLayerBinaryLSTM import OneLayerBinaryLSTM
from recon.dataset_util import prep_dataset, prep_labels, gen_group
from recon.split_util import get_train_test_split, pd_binary_clip
from recon.label_util import shift_label


def net_test(argv):
	cmd_arg_list = ['dataset=', 'filterset=', 'idxfilters=', 'assets=', 'target_col_idx=', 'visualize']
	cmd_input = get_cmd_args(argv, cmd_arg_list, script_name='net_test')
	dataset_name = cmd_input['dataset='] if (cmd_input['dataset='] is not None) else default_dataset
	filterset_name = cmd_input['filterset='] if (cmd_input['filterset='] is not None) else '_'.join(['default', dataset_name])
	filter_idxs =  list(map(str.strip, cmd_input['idxfilters='].split(','))) if (cmd_input['idxfilters='] is not None) else default_nt_filter
	assets = list(map(str.strip, cmd_input['assets='].split(','))) if (cmd_input['assets='] is not None) else None
	target_col_idx = int(cmd_input['target_col_idx=']) if (cmd_input['target_col_idx='] is not None) else default_target_col_idx
	run_compute = True if (cmd_input['visualize'] is None) else False

	dataset_dict = load_json(dataset_name, dir_path=DATASET_DIR)
	filter_dict = load_json(filterset_name, dir_path=FILTERSET_DIR)

	filterset = []
	for filter_idx in filter_idxs:
		selected = [flt for flt in filter_dict[filter_idx] if (flt not in filterset)]
		filterset.extend(selected)
	dataset = prep_dataset(dataset_dict, assets=assets, filters_map={'features': filterset})

	logging.info('assets: ' +str('all' if (assets==None) else ', '.join(assets)))
	logging.info('dataset: {} {} df(s)'.format(len(dataset['features']['paths']), dataset_name[:-JSON_SFX_LEN]))
	logging.info('filter: {} [{}]'.format(filterset_name[:-JSON_SFX_LEN], str(', '.join(filter_idxs))))
	logging.debug('filterset: {}'.format(filterset))
	logging.debug('fpaths: {}'.format(dataset['features']['paths']))
	logging.debug('lpaths: {}'.format(dataset['labels']['paths']))
	logging.debug('rpaths: {}'.format(dataset['row_masks']['paths']))

	labs_filter = [ # EOD, FBEOD, FB
	{
		"exact": [],
		"startswith": ["pba_"],
		"endswith": [],
		"regex": [],
		"exclude": None
	},
	{
		"exact": [],
		"startswith": [],
		"endswith": ["_eod(0%)", "_eod(1%)", "_eod(2%)", "_fb", "_fbeod"],
		"regex": [],
		"exclude": None
	}]

	ThreeLayerBinaryFFN_params = {
		'opt': SGD,
		'lr': 0.001,
		'epochs': 50,
		'batch_size':128,
		'output_activation': 'sigmoid',
		'loss': 'binary_crossentropy',
		'layer1_size': 64,
		'layer1_dropout': .6,
		'layer2_size': 32,
		'layer2_dropout': .4,
		'layer3_size': 16,
		'activation': 'tanh'
	}

	OneLayerBinaryLSTM_params = {
		'opt': RMSprop,
		'lr': 0.001,
		'epochs': 50,
		'batch_size':128,
		'output_activation': 'sigmoid',
		'loss': 'binary_crossentropy',
		'layer1_size': 32,
		'activation': 'tanh'
	}

	final_dfs = {}
	if (run_compute):
		logging.info('executing...')
		for paths, dfs in gen_group(dataset):
			fpaths, lpaths, rpaths = paths
			features, labels, row_masks = dfs
			asset = fpaths[0]
			logging.info('fpaths: {}'.format(fpaths))
			logging.info('lpaths: {}'.format(lpaths))
			logging.info('rpaths: {}'.format(rpaths))

			final_feature = prepare_transpose_data(features.loc[:, ['pba_avgPrice']], row_masks)
			masked_labels = prepare_masked_labels(labels, ['bool'], labs_filter)
			shifted_label = delayed(shift_label)(masked_labels.iloc[:, target_col_idx]).dropna()
			pos_label, neg_label = delayed(pd_binary_clip, nout=2)(shifted_label)
			f, lpos, lneg = delayed(pd_common_index_rows, nout=3)(final_feature, pos_label, neg_label).compute()

			test_model_with_labels(ThreeLayerBinaryFFN_params, ThreeLayerBinaryFFN, f, {'pos': lpos, 'neg':lneg})


def test_model_with_labels(params, model_exp, feats, labels_dict):
	for label_name, label in labels_dict.items():
		loss = test_model(params, model_exp, feats, label).__dict__
		print("{label_name} loss: {loss}".format(label_name=label_name, loss=loss.__dict__))
		print("{label_name} loss: {loss}".format(label_name=label_name, loss=dir(loss)))


def test_model(params, model_exp, feats, label, test_ratio=.25, shuffle=False):
	feat_train, feat_test, lab_train, lab_test = get_train_test_split(feats, label, test_ratio=test_ratio, shuffle=shuffle)
	exp = model_exp()
	mod = exp.make_model(params, (feats.shape[1],))
	fit = exp.fit_model(params, mod, (feat_train, lab_train), val_data=(feat_test, lab_test), val_split=test_ratio, shuffle=shuffle)
	return fit


if __name__ == '__main__':
	with benchmark('time to finish') as b:
		net_test(sys.argv[1:])
