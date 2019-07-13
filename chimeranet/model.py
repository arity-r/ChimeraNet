"""model module
"""

import numpy as np
import keras.backend as K
from keras.models import Model
from keras.layers import Input, Lambda, Reshape, Activation
from keras.layers import Dense, LSTM, Bidirectional

class ChimeraNetModel:
    """ChimeraNetModel class
    """
    def __init__(self, time_frames, mel_bins, n_channels, d_embeddings):
        """
        """
        self.T = time_frames
        self.F = mel_bins
        self.C = n_channels
        self.D = d_embeddings
    def loss_deepclustering(self):
        def _loss_deepclustering(y_true, y_pred):
            y_true_flatten = K.reshape(y_true, (-1, self.T*self.F, self.C))
            y_pred_flatten = K.reshape(y_pred, (-1, self.T*self.F, self.D))
            A = K.batch_dot(y_true_flatten, y_true_flatten, axes=(2, 2))
            Ahat = K.batch_dot(y_pred_flatten, y_pred_flatten, axes=(2, 2))
            return K.sum(K.pow(A - Ahat, 2), axis=(1, 2))\
                / K.cast_to_floatx(self.F*self.T)
        return _loss_deepclustering

    def loss_mask(self):
        def _loss_mask(y_true, y_pred):
            mixture = K.expand_dims(y_true[:, :, :, self.C])
            mixture /= K.mean(mixture)
            mask_true = y_true[:, :, :, :self.C]
            return K.sum(
                K.pow((mask_true - y_pred)*mixture, 2), axis=(1, 2, 3)
            ) / 2
        return _loss_mask

    def build_model(self, n_blstm_units=500, n_blstm_layers=4):
        inputs = Input(shape=(self.T, self.F), name='input')
        blstm_top = inputs
        for i in range(1, n_blstm_layers+1):
            blstm_top = Bidirectional(
                LSTM(n_blstm_units, return_sequences=True),
                name='body_blstm_{}'.format(i)
            )(blstm_top)
        body_linear = Dense(self.F*self.D, name='body_linear')(blstm_top)
        body = Reshape((self.T, self.F, self.D), name='body')(body_linear)

        embd_activation = Activation('tanh', name='embedding_activation')(body)
        embedding = Lambda(
            lambda x: K.l2_normalize(x, axis=-1), name='embedding'
        )(embd_activation)
        mask_slices = [
            Lambda(
                lambda x: x[:, :, f, :], name='mask_slice_{}'.format(f+1)
            )(body)
            for f in range(self.F)
        ]
        mask_linears = [
            Dense(
                self.C, activation='softmax', name='mask_linear_{}'.format(f+1)
            )(mask_slices[f])
            for f in range(self.F)
        ]
        mask = Lambda(lambda x: K.stack(x, axis=2), name='mask')(mask_linears)
    
        model = Model(inputs=inputs, outputs=[embedding, mask])
        return model
