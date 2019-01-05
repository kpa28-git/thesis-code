"""
Kevin Patel
"""
import sys
import os
from os import sep
from os.path import basename
import copy
import subprocess
import logging

import numpy as np
import pandas as pd
from hyperopt import fmin, tpe, Trials
from hyperopt.mongoexp import MongoTrials

from common_util import CRUNCH_DIR, REPORT_DIR, JSON_SFX_LEN, makedir_if_not_exists, get_class_name, str_to_list, get_cmd_args, load_json, benchmark
from model.common import DATASET_DIR, HOPT_WORKER_BIN, TRIALS_COUNT, default_model, default_dataset
from model.model_util import BINARY_CLF_MAP
from model.data_util import datagen, prepare_transpose_data, prepare_label_data, prepare_target_data
from recon.dataset_util import prep_dataset
from recon.split_util import pd_binary_clip
from report.mongo_server import MongoServer


def hexp(argv):
	cmd_arg_list = ['model=', 'dataset=', 'assets=']
	cmd_input = get_cmd_args(argv, cmd_arg_list, script_name=basename(__file__))
	model_code = cmd_input['model='] if (cmd_input['model='] is not None) else default_model
	dataset_fname = cmd_input['dataset='] if (cmd_input['dataset='] is not None) else default_dataset
	assets = str_to_list(cmd_input['assets=']) if (cmd_input['assets='] is not None) else None

	model_obj = BINARY_CLF_MAP[model_code]()
	model_name = get_class_name(model_obj)
	dataset_name = dataset_fname[:-JSON_SFX_LEN]
	dataset_dict = load_json(dataset_fname, dir_path=DATASET_DIR)
	dataset = prep_dataset(dataset_dict, assets=assets, filters_map=None)

	logging.info('model: {}'.format(model_name))
	logging.info('dataset: {} {} df(s)'.format(len(dataset['features']), dataset_name))
	logging.info('assets: {}'.format(str('all' if (assets==None) else ', '.join(assets))))

	with MongoServer() as db:
		for i, (fpath, lpath, _, frec, lrec, _, fcol, lcol, _, feature, label, _) in enumerate(datagen(dataset, feat_prep_fn=prepare_transpose_data, label_prep_fn=prepare_label_data, target_prep_fn=prepare_target_data, how='ser_to_ser')):
			logging.info('parent exp {}'.format(i))
			asset_name = fpath[0]
			assert(asset_name==lpath[0])
			meta = {
				'group': {
					'name': '{asset},{dataset},{model}'.format(asset=asset_name, dataset=dataset_name, model=model_name),
					'asset': asset_name,
					'dataset': dataset_name,
					'model': model_name
				},
				'exp': {
					'name': '{feat},{lab},{dir}',
					'feat': '{featdf}[{featcol}]'.format(featdf=frec.desc, featcol=fcol),
					'lab': '{labdf}[{labcol}]'.format(labdf=lrec.desc, labcol=lcol),
					'dir': '{dir}'
				}
			}
			pos_label, neg_label = pd_binary_clip(label)
			pos_meta, neg_meta = copy.deepcopy(meta), copy.deepcopy(meta)
			pos_meta['exp']['dir'], neg_meta['exp']['dir'] = 'pos', 'neg'
			pos_meta['exp']['name'], neg_meta['exp']['name'] = pos_meta['exp']['name'].format(**pos_meta['exp']), neg_meta['exp']['name'].format(**neg_meta['exp'])

			run_model(model_obj, feature, pos_label, pos_meta, db)
			run_model(model_obj, feature, neg_label, neg_meta, db)


def run_model(mdl, features, label, meta, db, max_evals=TRIALS_COUNT):
	"""
	Run the model over passed (features, labels) using metadata in meta.
	"""
	db_name, exp_name = meta['group']['name'], meta['exp']['name']
	logdir = REPORT_DIR +sep.join([*db_name.split(','), *exp_name.split(',')]) +sep
	makedir_if_not_exists(logdir)
	obj = mdl.make_const_data_objective(features, label, logdir, exp_meta=meta)
	logging.info('{group}: {exp}'.format(group=db_name, exp=exp_name))

	if (db is not None):
		worker_args = [HOPT_WORKER_BIN]
		worker_args.append('--exp-key={exp}'.format(exp=exp_name))					# XXX - only run this experiment
		worker_args.append('--max-jobs={max_jobs}'.format(max_jobs=max_evals))		# XXX - set jobs to number of trials
		worker_args.append('--mongo={db_uri}'.format(db_uri=db.get_mongodb_uri(db_name=db_name)))
		worker_args.append('--poll-interval={poll_interval:1.2f}'.format(poll_interval=0.1))
		worker_args.append('--workdir={dir}'.format(dir=CRUNCH_DIR))
		worker = subprocess.Popen(worker_args, stdout=db.fnull, stderr=subprocess.STDOUT, shell=False)
		logging.info('started worker: {}'.format(' '.join(worker_args)))
		trials = MongoTrials(db.get_mongodb_trials_uri(db_name=db_name), exp_key=exp_name)
		# TODO - maybe add a sleep here to give hyperopt mongo worker time to get up and running
	else:
		trials = Trials()
	best = fmin(obj, mdl.get_space(), algo=tpe.suggest, max_evals=max_evals, trials=trials)
	print('best idx: {}'.format(best))
	# best_params = exp.params_idx_to_name(best)
	# print('best params: {}'.format(best_params))


if __name__ == '__main__':
	with benchmark('time to finish') as b:
		hexp(sys.argv[1:])
