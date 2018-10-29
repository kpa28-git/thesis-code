# Kevin Patel

import sys
from os import sep
from os.path import isfile, getsize
from copy import deepcopy
from collections import defaultdict
import logging

from dask import delayed
import pandas as pd
from pandas.util import hash_pandas_object

from common_util import DATA_DIR, load_df, dump_df, makedir_if_not_exists, chained_filter, search_df, query_df, recursive_dict, list_get_dict, list_set_dict, dict_path, str_now, benchmark
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
			"""Return path suffix of df on disk for given candidate entry, relative to DATA_DIR """
			rel_path_dir = sep.join([entry['root'], entry['basis'], entry['freq']]) +sep

			sorted_ss = sorted(filter(lambda c: c.startswith(entry['stage']), DR_STAGE))
			if (sorted_ss):
				rel_path_dir += sep.join(map(cls.ss_to_path_loader(entry), sorted_ss)) +sep

			return rel_path_dir

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
				return rec, load_df(rec.name, dir_path=DATA_DIR+rec.dir, dti_freq=rec.freq, **kwargs)
			
			return load_rec_df

		@classmethod
		def dump(cls, df, entry, path_pfx=DATA_DIR, update_record=False):
			"""
			XXX - break this down and make it more elegant
			"""
			entry['id'], is_new = cls.get_id(entry)
			entry['name'] = cls.get_name(entry)
			entry['dir'] = cls.get_path(entry)
			dump_location = path_pfx+entry['dir']
			makedir_if_not_exists(dump_location)

			with benchmark('', suppress=True) as b:
				logging.debug('dest {}'.format(dump_location))
				entry['size'] = dump_df(df, entry['name'], dir_path=dump_location)
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
	def get_rec_matches(cls, search_dict, direct_query=False, **kwargs):
		"""Provide generator to get matched records"""
		yield from cls.DataRecordAPI.matched(search_dict, direct_query=direct_query)

	@classmethod
	def get_df_from_rec(cls, rec, col_subsetter=None, path_pfx=DATA_DIR, **kwargs):
		selected = load_df(rec.name, dir_path=path_pfx+rec.dir, dti_freq=rec.freq, **kwargs)
		if (col_subsetter is not None):
			return selected[chained_filter(selected.columns, col_subsetter)]

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
		result, recs = recursive_dict(), recursive_dict()
		result_paths = []

		for edg_path, edg in paths_to_end:
			ecs = None if (col_subsetter is None) else list_get_dict(col_subsetter, edg_path)

			for sd_name, sd_cs in construct_search_subset_dict(edg, end_cs=ecs).items():
				sd_path = edg_path + [sd_name]
				add_desc_as_path_identifier = True if ('desc' in sd_cs[0] and isinstance(sd_cs[0]['desc'], list)) else False

				for rec, df in cls.generate(sd_cs[0]):
					seps = [getattr(rec, separator) for separator in separators]
					df_path = seps + sd_path + [rec.desc] if (add_desc_as_path_identifier) else seps + sd_path

					result_paths.append(df_path)
					filtered_df = df if (sd_cs[1] is None) else df[chained_filter(df.columns, sd_cs[1])]
					list_set_dict(result, df_path, filtered_df)
					list_set_dict(recs, df_path, rec)

		return result_paths, recs, result


	@classmethod
	def lazy_load(cls, df_getter, col_subsetter, separators=['root'], how='subsets', subset=None, **kwargs):
		"""
		Return paths, rec dicts, and df dicts identically to load_from_dg, but defer final loading of DataFrames using dask.delayed.
		"""
		def get_search_dicts(end_dg, end_cs=None, how=how, subset=subset):
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
		end_paths = list(dict_path(df_getter, stop_cond=hit_bottom))
		result, recs = recursive_dict(), recursive_dict()
		result_paths = []

		for end_path, end_dg in end_paths:
			end_cs = None if (col_subsetter is None) else list_get_dict(col_subsetter, end_path)
			search_dicts = get_search_dicts(end_dg, end_cs=end_cs)

			for name, search_dict_col_subsetter in search_dicts.items():
				path = end_path + [name]
				search_dict, sd_col_subsetter = search_dict_col_subsetter

				# If desc is in search_dict and refers to a list of desc values, use these to distinguish items
				desc_in_path = True if ('desc' in search_dict and isinstance(search_dict['desc'], list)) else False

				for rec in cls.get_rec_matches(search_dict):
					seps = [getattr(rec, separator) for separator in separators]
					df_path = seps + path + [rec.desc] if (desc_in_path) else seps + path
					result_paths.append(df_path)
					list_set_dict(result, df_path, delayed(cls.get_df_from_rec)(rec, sd_col_subsetter))
					list_set_dict(recs, df_path, rec)

		return result_paths, recs, result

	@classmethod
	def get_record_view(cls):
		return cls.DataRecordAPI.get_record_view()

	@classmethod
	def dump(cls, df, entry, **kwargs):
		cls.DataRecordAPI.assert_valid_entry(entry)
		cls.DataRecordAPI.dump(df, entry, **kwargs)
	
	@classmethod
	def update_record(cls):
		cls.DataRecordAPI.dump_record()


DataAPI.initialize()
