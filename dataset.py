import os
import numpy as np
import tensorflow as tf
import pycocotools.coco as pycoco


class COCO(object):
  class Image(object):
    def __init__(self, img):
      self.id = img['id']
      self.filename = img['file_name']
      self.size = (img['height'], img['width'])

  class Annotation(object):
    def __init__(self, ann, category_ids):
      self.bbox = ann['bbox']
      self.category_id = category_ids.index(ann['category_id'])

  def __init__(self, ann_path, dataset_path, download):
    self.coco = pycoco.COCO(ann_path)
    self.category_ids = sorted(self.coco.getCatIds())
    self.num_classes = len(self.category_ids)

    if download:
      self.coco.download(tarDir=dataset_path)

  def get_img_ids(self):
    return self.coco.getImgIds()

  def load_imgs(self, ids):
    return [self.Image(img) for img in self.coco.loadImgs(ids=ids)]

  def get_ann_ids(self, img_ids):
    return self.coco.getAnnIds(imgIds=img_ids)

  def load_anns(self, ids):
    return [
        self.Annotation(ann, self.category_ids)
        for ann in self.coco.loadAnns(ids=ids)
    ]


def box_size(base_size, ratio):
  return (np.sqrt(base_size**2 / (ratio[0] * ratio[1])) * ratio[0],
          np.sqrt(base_size**2 / (ratio[0] * ratio[1])) * ratio[1])


def make_level_labels(image, anns, level, num_classes):
  image_size = np.array(image.size)

  # for item in anns:
  #   print(item.bbox, item.category_id)

  anchor_boxes = [
      box_size(level.anchor_size, ratio)
      for ratio in level.anchor_aspect_ratios
  ]

  classification = np.zeros((*np.int32(np.floor(image_size / 2**level.number)),
                             num_classes * len(level.anchor_aspect_ratios)))
  regression = np.zeros((*np.int32(np.floor(image_size / 2**level.number)),
                         4 * len(level.anchor_aspect_ratios)))

  return classification, regression


def make_labels(image, anns, levels, num_classes):
  labels = [
      make_level_labels(image, anns, l, num_classes=num_classes)
      for l in reversed(levels)
  ]

  classifications, regressions = list(zip(*labels))

  return classifications, regressions


def gen(coco, dataset_path, levels, download):

  # for img_
  # ann_ids = coco.getAnnIds()
  # print(len(ann_ids))

  # print(len(cats))

  # cat_ids = coco.getCatIds()
  # assert len(cat_ids) == 80
  # coco.loadCats(cat_ids)
  # img_ids = coco.getImgIds(catIds=cat_ids)

  imgs = coco.load_imgs(coco.get_img_ids())
  assert len(imgs) == 118287

  for img in imgs:
    image_path = os.path.join(dataset_path, img.filename)
    anns = coco.load_anns(coco.get_ann_ids(img_ids=img.id))
    classifications, regressions = make_labels(
        img, anns, levels=levels, num_classes=coco.num_classes)

    yield image_path, classifications, regressions

  # print(len(imgs))

  # assert len(imgs) == 118287
  # print(imgs[0])
  # # print(imgs[0])
  # anns = coco.loadAnns()
  # print(len(anns))
  # print(anns[:5])
  #
  # ann_ids = coco.getAnnIds()
  # print(len(ann_ids))
  # anns = coco.loadAnns(ann_ids)
  # print(len(anns))
  # print(anns[0].keys())

  # print(len(img_ids))

  # print(len(img_ids))

  # img = imgs[0]
  # ann_ids = coco.getAnnIds(imgIds=img['id'])
  # anns = coco.loadAnns(ann_ids)
  #
  # image = Image.open(os.path.join(args.dataset_path, img['file_name']))
  # image = (np.array(image) / 255).astype(np.float32)

  # print(len(cat_ids))
  # print()
  # print(cat_ids)
  # print(cats)

  # nms = [cat['name'] for cat in cats]
  # print('COCO categories: \n{}\n'.format(' '.join(nms)))
  #
  # nms = set([cat['supercategory'] for cat in cats])
  # print('COCO supercategories: \n{}'.format(' '.join(nms)))

  # assert image.shape[0] == img['height'], image.shape[1] == img['width']
  #
  # print(anns[0])
  # boxes = [[
  #     ann['bbox'][0] / img['width'], ann['bbox'][1] / img['height'],
  #     ann['bbox'][2] / img['width'], ann['bbox'][3] / img['height']
  # ] for ann in anns]
  #
  # boxmap_true = np.array(boxes, dtype=np.float32)
  #
  # boxmap_true = tf.stack([
  #     boxmap_true[:, 1],
  #     boxmap_true[:, 0],
  #     boxmap_true[:, 3] + boxmap_true[:, 1],
  #     boxmap_true[:, 2] + boxmap_true[:, 0],
  # ], -1)


def make_dataset(ann_path, dataset_path, levels, download):
  def make_gen():
    return gen(
        coco=coco, dataset_path=dataset_path, levels=levels, download=download)

  def load_image(filename):
    image = tf.read_file(filename)
    image = tf.image.decode_png(image, channels=3)
    image = tf.image.convert_image_dtype(image, tf.float32)
    return image

  coco = COCO(ann_path, dataset_path, download)

  ds = tf.data.Dataset.from_generator(
      make_gen,
      output_types=(
          tf.string,
          tuple(tf.float32 for _ in levels),
          tuple(tf.float32 for _ in levels),
      ),
      output_shapes=(
          [],
          tuple([None, None,
                 len(l.anchor_aspect_ratios) * coco.num_classes]
                for l in levels),
          tuple([None, None, len(l.anchor_aspect_ratios) * 4] for l in levels),
      ))

  ds = ds.map(lambda filename, *rest: (load_image(filename), *rest))

  return ds, coco.num_classes