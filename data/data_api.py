# Kevin Patel

import sys
from os import sep
from os.path import isfile, getsize
from copy import deepcopy
from collections import defaultdict
import logging

import pandas as pd
from pandas.util import hash_pandas_object

from common_util import DATA_DIR, load_df, dump_df, makedir_if_not_exists, get_subset, search_df, query_df, recursive_dict, list_get_dict, list_set_dict, dict_path, str_now, benchmark
from data.common import DR_NAME, DR_FMT, DR_COLS, DR_IDS, DR_REQ, DR_STAGE, DR_META, DR_GEN


class DataAPI:
	"""
	The Global API used to load or dump dataframes. All real implementation is done in the inner class, the outer
	class is just a generic interface. This is to make swapping out the backend easier
	XXX:
		- move DataRecordAPI to it's own class file, have DataAPI inherit from it
		- implement a SQL backend for DataRecordAPI
	"""
	class DataRecordAPI:
		"""
		Global storage structure for the storage of dataframe records dumped by other stages.
		Currently only supports single threaded access.
		
		Entry:
			id (int): integer id
			name (str): filename of df on disk
			root (str): the root dependency of this df; for raw stage data this is a join group but for others it's a df name
			basis (str): the direct dependency (parent) of this dataframe; for raw stage data root always equals basis
			stage (str): the stage the data originated from
		"""
		@classmethod
		def reload_record(cls):
			cls.DATA_RECORD = load_df(DR_NAME, dir_path=DATA_DIR, data_format=DR_FMT)
			assert list(cls.DATA_RECORD.columns)==DR_COLS, 'loaded data record columns don\'t match schema'

		@classmethod
		def reset_record(cls):
			cls.DATA_RECORD = pd.DataFrame(columns=DR_COLS)

		@classmethod
		def dump_record(cls):
			dump_df(cls.DATA_RECORD, DR_NAME, dir_path=DATA_DIR, data_format=DR_FMT)

		@classmethod
		def get_record_view(cls):
			return cls.DATA_RECORD.loc[:, :]

		@classmethod
		def assert_valid_entry(cls, entry):
			"""Assert whether or not entry is a validly formatted entry to the data record."""
			# XXX - convert to set operations, easier to read and understand

			# Required fields:
			assert all((col in entry and entry[col] is not None) for col in DR_REQ), 'missing a required general rec entry field (DR_REQ)'
			assert all((col in entry and entry[col] is not None) for col in DR_STAGE if col.startswith(entry['stage'])), 'missing a required stage rec entry field (DR_STAGE)'

			# Required omissions (autogenerated):
			assert all((col not in entry) for col in DR_IDS), 'can\'t pass an autogenerated rec entry field (DR_IDS)'
			assert all((col not in entry) for col in DR_GEN), 'can\'t pass an autogenerated rec entry field (DR_GEN)'

		@classmethod
		def get_id(cls, entry):
			"""Return id of matched entry in the df record, else return a new id."""
			match = search_df(cls.DATA_RECORD, entry)
			entry_id = len(cls.DATA_RECORD.index) if (match.empty) else match.values[0]
			return entry_id, match.empty

		@classmethod
		def get_name(cls, entry):
			return '_'.join([entry['root'], entry['stage'], str(entry['id'])])

		@classmethod
		def ss_to_path_loader(cls, entry):
			"""
			Return stage specific field to string subdirectory mapping function.
			Inner function accesses entry fields via closure.
			"""
			def ss_to_path(col_name):
				field = entry[col_name]
				return {
					list: (lambda: '_'.join(field)),		  # Preserves field ordering in path
					set: (lambda: '_'.join(sorted(field))),
					str: (lambda: field),
					None: (lambda: str(field))
				}.get(type(field), None)()

			return ss_to_path

		@classmethod
		def get_path(cls, entry):
			"""Return path of df on disk for given candidate entry"""
			path_dir = DATA_DIR +sep.join([entry['root'], entry['basis'], entry['freq']]) +sep

			sorted_ss = sorted(filter(lambda c: c.startswith(entry['stage']), DR_STAGE))
			if (sorted_ss):
				path_dir += sep.join(map(cls.ss_to_path_loader(entry), sorted_ss)) +sep

			return path_dir

		@classmethod
		def matched(cls, search_dict, direct_query=False):
			"""Yield iterator of NamedTuples from matched entry subset"""
			if (direct_query):
				match_ids = query_df(cls.DATA_RECORD, search_dict)
			else:
				match_ids = search_df(cls.DATA_RECORD, search_dict)
			yield from cls.DATA_RECORD.loc[match_ids].itertuples()

		@classmethod
		def loader(cls, **kwargs):
			"""Return a loader function that takes a record entry and returns something"""

			def load_rec_df(rec):
				return rec, load_df(rec.name, dir_path=rec.dir, dti_freq=rec.freq, **kwargs)
			
			return load_rec_df

		@classmethod
		def dump(cls, df, entry, update_record=False):
			"""
			XXX - break this down and make it more elegant
			"""
			entry['id'], is_new = cls.get_id(entry)
			entry['name'] = cls.get_name(entry)
			entry['dir'] = cls.get_path(entry)

			makedir_if_not_exists(entry['dir'])
			with benchmark('', suppress=True) as b:
				entry['size'] = dump_df(df, entry['name'], dir_path=entry['dir'])
			entry['dumptime'] = round(b.time, 2)
			entry['hash'] = sum(hash_pandas_object(df))
			addition = pd.DataFrame(columns=DR_COLS, index=[entry['id']])

			if (is_new):
				entry['created'] = str_now()
				addition.loc[entry['id']] = entry
				cls.DATA_RECORD = pd.concat([cls.DATA_RECORD, addition], copy=False)
			else:
				entry['modified'] = str_now()
				addition.loc[entry['id']] = entry
				cls.DATA_RECORD.update(addition)

			if (update_record):
				cls.dump_record()

	@classmethod
	def initialize(cls):
		try:
			cls.DataRecordAPI.reload_record()
		except FileNotFoundError as e:
			cls.DataRecordAPI.reset_record()
			logging.warning('DataAPI initialize: Data record not found, loading empty record')

	
	@classmethod
	def print_record(cls):
		print(cls.DataRecordAPI.get_record_view())

	@classmethod
	def generate(cls, search_dict, direct_query=False, **kwargs):
		"""Provide generator interface to get data"""
		yield from map(cls.DataRecordAPI.loader(**kwargs), cls.DataRecordAPI.matched(search_dict, direct_query=direct_query))

	@classmethod
	def load_from_dg(cls, df_getter, col_subsetter=None, separators=['root'], how='subsets', subset=None, **kwargs):
		"""
		Load data using a df_getter dictionary, and col_subsetter dictionary (optional)
		By default separates the search by root at the bottom level.
		"""

		def construct_search_subset_dict(end_dg, end_cs=None, how=how, subset=subset):
			"""
			Convenience function to construct the search dict (optionally col subsetter dict) based on the how parameter.
			"""
			if (how == 'all'):
				cs_dict = None if (end_cs is None) else end_cs['all']
				return {'all': (end_dg['all'], cs_dict)}

			elif (how == 'subsets'):
				ss_dict = {}

				if (isinstance(subset, list)):
					subsets_dict = {key: val for key, val in end_dg['subsets'].items() if (key in subset)}
				else:
					subsets_dict = end_dg['subsets'] # all subsets

				for s_name, s_dict in subsets_dict.items():
					cs_dict = None if (end_cs is None) else end_cs['subsets'][s_name]
					ss_dict[s_name] = (dict(end_dg['all'], **s_dict), cs_dict)

				return ss_dict

		hit_bottom = lambda val: any(key in val for key in ['all', 'subsets'])
		paths_to_end = list(dict_path(df_getter, stop_cond=hit_bottom))
		result_paths = []
		result = recursive_dict()

		for edg_path, edg in paths_to_end:
			ecs = None if (col_subsetter is None) else list_get_dict(col_subsetter, edg_path)

			for sd_name, sd_cs in construct_search_subset_dict(edg, end_cs=ecs).items():
				sd_path = edg_path + [sd_name]
				add_desc_identifier = True if (isinstance(sd_cs[0]['desc'], list)) else False
				print(sd_cs)

				for rec, df in cls.generate(sd_cs[0]):
					seps = [getattr(rec, separator) for separator in separators]
					df_path = seps + sd_path + [rec.desc] if (add_desc_identifier) else seps + sd_path

					result_paths.append(df_path)
					filtered_df = df if (sd_cs[1] is None) else df[get_subset(df.columns, sd_cs[1])]
					print(filtered_df.columns)
					list_set_dict(result, df_path, filtered_df)

		return result_paths, result


	@classmethod
	def dump(cls, df, entry, **kwargs):
		cls.DataRecordAPI.assert_valid_entry(entry)
		cls.DataRecordAPI.dump(df, entry, **kwargs)
	
	@classmethod
	def update_record(cls):
		cls.DataRecordAPI.dump_record()


DataAPI.initialize()
