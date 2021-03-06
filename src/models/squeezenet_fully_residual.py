from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import tensorflow.contrib.slim as slim

def fire_module(inputs,
                squeeze_depth,
                expand_depth,
                reuse=None,
                scope=None,
                outputs_collections=None):
    with tf.variable_scope(scope, 'fire', [inputs], reuse=reuse):
        with slim.arg_scope([slim.conv2d, slim.max_pool2d],
                            outputs_collections=None):
            net = squeeze(inputs, squeeze_depth)
            outputs = expand(net, expand_depth)
            return outputs

def fire_residual_module(inputs,
                squeeze_depth,
                expand_depth,
                reuse=None,
                scope=None,
                outputs_collections=None,
                activation_fn=None):
    with tf.variable_scope(scope, 'fire_residual', [inputs], reuse=reuse):

            outputs = fire_module(inputs,
                squeeze_depth,
                expand_depth,
                reuse=None,
                scope=None,
                outputs_collections=None)

            # add shortcut
            outputs = tf.add(outputs, inputs)

            if activation_fn:
            	return activation_fn(outputs)

            return outputs

def fire_residual_module_conv1x1(inputs,
                squeeze_depth,
                expand_depth,
                residual_depth,
                reuse=None,
                scope=None,
                outputs_collections=None,
                activation_fn=None):

	with tf.variable_scope(scope, 'fire_residual', [inputs], reuse=reuse):
		outputs = fire_module(inputs,
                squeeze_depth,
                expand_depth,
                reuse=None,
                scope=None,
                outputs_collections=None)
		outputs = tf.add(outputs, slim.conv2d(inputs, residual_depth, [1, 1], stride=1))

		if activation_fn:
			return activation_fn(outputs)

		return outputs


def squeeze(inputs, num_outputs):
    return slim.conv2d(inputs, num_outputs, [1, 1], stride=1, scope='squeeze')

def expand(inputs, num_outputs):
    with tf.variable_scope('expand'):
        e1x1 = slim.conv2d(inputs, num_outputs, [1, 1], stride=1, scope='1x1')
        e3x3 = slim.conv2d(inputs, num_outputs, [3, 3], scope='3x3')
    return tf.concat([e1x1, e3x3], 3)

def inference(images, keep_probability, phase_train=True, bottleneck_layer_size=128, weight_decay=0.0, reuse=None):
    batch_norm_params = {
        # Decay for the moving averages.
        'decay': 0.995,
        # epsilon to prevent 0s in variance.
        'epsilon': 0.001,
        # force in-place updates of mean and variance estimates
        'updates_collections': None,
        # Moving averages ends up in the trainable variables collection
        'variables_collections': [ tf.GraphKeys.TRAINABLE_VARIABLES ],
    }
    with slim.arg_scope([slim.conv2d, slim.fully_connected],
                        # Weights initialization with He et al.
                        weights_initializer=slim.variance_scaling_initializer(factor=2.0, mode='FAN_IN', uniform=False),
                        weights_regularizer=slim.l2_regularizer(weight_decay),
                        normalizer_fn=slim.batch_norm,
                        normalizer_params=batch_norm_params):
        with tf.variable_scope('squeezeres', [images], reuse=reuse):
            with slim.arg_scope([slim.batch_norm, slim.dropout],
                                is_training=phase_train):
                net = slim.conv2d(images, 96, [7, 7], stride=2, scope='conv1')
                net = slim.max_pool2d(net, [3, 3], stride=2, scope='maxpool1')

                net = fire_residual_module_conv1x1(net, 16, 64, 128, scope='fire2', activation_fn=tf.nn.relu)
                net = fire_residual_module(net, 16, 64, scope='fire3', activation_fn=tf.nn.relu)                                        
                net = fire_residual_module_conv1x1(net, 32, 128, 256, scope='fire4', activation_fn=tf.nn.relu)

                net = slim.max_pool2d(net, [2, 2], stride=2, scope='maxpool4')

                net = fire_residual_module(net, 32, 128, scope='fire5', activation_fn=tf.nn.relu)                
                net = fire_residual_module_conv1x1(net, 48, 192, 384, scope='fire6', activation_fn=tf.nn.relu)
                net = fire_residual_module(net, 48, 192, scope='fire7', activation_fn=tf.nn.relu)
                net = fire_residual_module_conv1x1(net, 64, 256, 512, scope='fire8', activation_fn=tf.nn.relu)
                
                net = slim.max_pool2d(net, [3, 3], stride=2, scope='maxpool8')

                net = fire_residual_module(net, 64, 256, scope='fire9', activation_fn=tf.nn.relu)
                
                net = slim.dropout(net, keep_probability)
                net = slim.conv2d(net, 1000, [1, 1], activation_fn=None, normalizer_fn=None, scope='conv10')
                net = slim.avg_pool2d(net, net.get_shape()[1:3], scope='avgpool10')

                net = tf.squeeze(net, [1, 2], name='logits')
                net = slim.fully_connected(net, bottleneck_layer_size, activation_fn=None,
                        scope='Bottleneck', reuse=False)
    return net, None
