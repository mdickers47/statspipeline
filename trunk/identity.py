#!/usr/bin/python2.5

import pipelineblock


class IdentityBlock(pipelineblock.PipelineBlock):
  pass


if __name__ == '__main__':
  pipelineblock.main(IdentityBlock)
