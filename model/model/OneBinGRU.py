"""
Kevin Patel
"""
import sys
import os
import logging

import numpy as np
import pandas as pd
from hyperopt import hp, STATUS_OK
from keras.models import Model
from keras.layers import Input, Dense, GRU

from common_util import MODEL_DIR
from model.common import MODELS_DIR, ERROR_CODE
from model.model.BinaryClassifier import BinaryClassifier


class OneLayerBinaryGRU(BinaryClassifier):
	"""One layer binary gated recurrent unit classifier."""

	def __init__(self, other_space={}):
		default_space = {
			'layer1_size': hp.choice('layer1_size', [8, 16, 32, 64, 128]),
			'activation': hp.choice('activation', ['relu', 'sigmoid', 'tanh', 'linear']),
			'recurrent_activation': hp.choice('recurrent_activation', ['hard_sigmoid']),
			'stateful': hp.choice('stateful', [True, False])
		}
		super(OneLayerBinaryGRU, self).__init__({**default_space, **other_space})

	def make_model(self, params, input_shape):
		# Define model
		inputs = Input(shape=input_shape, name='inputs')
		layer_one = GRU(params['layer1_size'], activation=params['activation'], recurrent_activation=params['recurrent_activation'], stateful=params['stateful'])(inputs)
		output = Dense(1, activation=params['output_activation'], name='output')(layer_one)

		# Compile model
		model = Model(inputs=inputs, outputs=output)
		model.compile(optimizer=params['opt'](lr=params['lr']), loss=params['loss'], metrics=self.metrics)

		return model
