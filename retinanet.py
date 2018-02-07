import tensorflow as tf
import tensorflow.contrib.slim as slim
import tensorflow.contrib.slim.nets as nets
import math


def conv(x, filters, kernel_size, strides, kernel_initializer,
         kernel_regularizer):
  return tf.layers.conv2d(
      x,
      filters,
      kernel_size,
      strides,
      padding='same',
      kernel_initializer=kernel_initializer,
      kernel_regularizer=kernel_regularizer)


def conv_bn_relu(x, filters, kernel_size, strides, dropout, kernel_initializer,
                 kernel_regularizer, training):
  x = conv(
      x,
      filters,
      kernel_size,
      strides,
      kernel_initializer=kernel_initializer,
      kernel_regularizer=kernel_regularizer)
  x = tf.layers.batch_normalization(x, training=training)
  x = tf.nn.relu(x)
  x = tf.layers.dropout(x, rate=dropout, training=training)

  return x


def classification_subnet(x, num_classes, num_anchors, dropout,
                          kernel_initializer, kernel_regularizer, training):
  filters = x.shape[-1]
  for _ in range(4):
    x = conv_bn_relu(
        x,
        filters,
        3,
        1,
        dropout=dropout,
        kernel_initializer=kernel_initializer,
        kernel_regularizer=kernel_regularizer,
        training=training)

  x = conv(
      x,
      num_classes * num_anchors,
      3,
      1,
      kernel_initializer=kernel_initializer,
      kernel_regularizer=kernel_regularizer)

  return x


def regresison_subnet(x, num_anchors, dropout, kernel_initializer,
                      kernel_regularizer, training):
  filters = x.shape[-1]
  for _ in range(4):
    x = conv_bn_relu(
        x,
        filters,
        3,
        1,
        dropout=dropout,
        kernel_initializer=kernel_initializer,
        kernel_regularizer=kernel_regularizer,
        training=training)

  x = conv(
      x,
      num_anchors * 4,
      3,
      1,
      kernel_initializer=kernel_initializer,
      kernel_regularizer=kernel_regularizer)

  return x


def validate_level_shape(x, output, l):
  x_shape = tf.shape(x, out_type=tf.int32)
  output_shape = tf.shape(output, out_type=tf.int32)
  return tf.assert_equal(
      tf.to_float(output_shape[1:3]),
      tf.to_float(tf.ceil(x_shape[1:3] / 2**l)),
  )


def backbone(x, levels, training):
  level_to_layer = [
      None,
      'resnet_v2_50/conv1',
      'resnet_v2_50/block1/unit_3/bottleneck_v2/conv1',
      'resnet_v2_50/block2/unit_4/bottleneck_v2/conv1',
      'resnet_v2_50/block3/unit_6/bottleneck_v2/conv1',
      'resnet_v2_50/block4',
  ]

  _, outputs = nets.resnet_v2.resnet_v2_50(
      x,
      num_classes=None,
      global_pool=False,
      output_stride=None,
      is_training=training)

  bottom_up = []

  for l in levels:
    output = outputs[level_to_layer[l.number]]
    with tf.control_dependencies([validate_level_shape(x, output, l.number)]):
      bottom_up.append(tf.identity(output))

  return bottom_up


def validate_lateral_shape(x, lateral):
  x_shape = tf.shape(x, out_type=tf.int32)
  lateral_shape = tf.shape(lateral, out_type=tf.int32)
  return tf.assert_equal(
      tf.to_float(tf.round(lateral_shape[1:3] / x_shape[1:3])),
      tf.to_float(2.0),
  )


def fpn(bottom_up, extra_levels, dropout, kernel_initializer,
        kernel_regularizer, training):
  def conv(x, kernel_size, strides):
    return conv_bn_relu(
        x,
        256,
        kernel_size,
        strides,
        dropout=dropout,
        kernel_initializer=kernel_initializer,
        kernel_regularizer=kernel_regularizer,
        training=training)

  def upsample_merge(x, lateral):
    with tf.control_dependencies([validate_lateral_shape(x, lateral)]):
      lateral = conv(lateral, 1, 1)
      x = tf.image.resize_images(
          x, tf.shape(lateral)[1:3], method=tf.image.ResizeMethod.BILINEAR)

      return x + lateral

  x = bottom_up[-1]
  top_down = []

  for l in extra_levels:
    x = conv(x, 3, 2)
    top_down.insert(0, x)

  x = conv(bottom_up.pop(), 1, 1)
  top_down.append(x)

  for _ in range(len(bottom_up)):
    x = upsample_merge(x, bottom_up.pop())
    x = conv(x, 3, 1)
    top_down.append(x)

  return top_down


def retinanet_base(x, num_classes, levels, dropout, kernel_initializer,
                   kernel_regularizer, training):
  backbone_levels = [l for l in levels if l.number <= 5]
  extra_levels = [l for l in levels if l.number > 5]

  bottom_up = backbone(x, levels=backbone_levels, training=training)

  top_down = fpn(
      bottom_up,
      extra_levels=extra_levels,
      dropout=dropout,
      kernel_initializer=kernel_initializer,
      kernel_regularizer=kernel_regularizer,
      training=training)

  assert len(top_down) == len(levels)

  classifications = [
      classification_subnet(
          x,
          num_classes=num_classes,
          num_anchors=len(l.anchor_aspect_ratios),
          dropout=dropout,
          kernel_initializer=kernel_initializer,
          kernel_regularizer=kernel_regularizer,
          training=training) for x, l in zip(top_down, reversed(levels))
  ]

  regressions = [
      regresison_subnet(
          x,
          num_anchors=len(l.anchor_aspect_ratios),
          dropout=dropout,
          kernel_initializer=kernel_initializer,
          kernel_regularizer=kernel_regularizer,
          training=training) for x, l in zip(top_down, reversed(levels))
  ]

  return classifications, regressions


def retinaneet(x, num_classes, levels, dropout, weight_decay, training):
  kernel_initializer = tf.contrib.layers.xavier_initializer_conv2d()
  kernel_regularizer = tf.contrib.layers.l2_regularizer(scale=weight_decay)

  return retinanet_base(
      x,
      num_classes=num_classes,
      levels=levels,
      dropout=dropout,
      kernel_initializer=kernel_initializer,
      kernel_regularizer=kernel_regularizer,
      training=training)