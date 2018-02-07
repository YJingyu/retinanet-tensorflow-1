class Level(object):
  def __init__(self, number, anchor_size, anchor_aspect_ratios):
    self.number = number
    self.anchor_size = anchor_size
    self.anchor_aspect_ratios = anchor_aspect_ratios

  def __repr__(self):
    return 'Level(number={}, anchor_size={}, anchor_aspect_ratios={})'.format(
        self.number, self.anchor_size, self.anchor_aspect_ratios)


def make_levels():
  anchor_aspect_ratios = [(1, 2), (1, 1), (2, 1)]

  return [
      Level(3, 32, anchor_aspect_ratios),
      Level(4, 64, anchor_aspect_ratios),
      Level(5, 128, anchor_aspect_ratios),
      Level(6, 256, anchor_aspect_ratios),
      Level(7, 512, anchor_aspect_ratios),
  ]