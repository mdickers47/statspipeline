#!/usr/bin/python2.5
"""IdentityBlock binary"""

import pipelineblock


class IdentityBlock(pipelineblock.PipelineBlock):
  """Parse the block as VirtualTable input, output the exact same block"""
  pass


if __name__ == '__main__':
  pipelineblock.Main(IdentityBlock)
