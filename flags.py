#!/usr/bin/python2.5

import getopt
import os
import sys


FLAGS = {}
_SEEN = {}
_CAST = {}
_LONG_OPTIONS = []
_USAGE = []


def DefineInteger(name, default_value, description, required=False):
  FLAGS[name] = int(default_value)
  _CAST[name] = int
  _LONG_OPTIONS.append('%s=' % name)
  if required:
    _SEEN[name] = False
  _USAGE.append('--%s: %s (integer)%s' % (name, description, {True: ' [REQUIRED]', False: ''}[required]))


def DefineString(name, default_value, description, required=False):
  FLAGS[name] = str(default_value)
  _CAST[name] = str
  _LONG_OPTIONS.append('%s=' % name)
  if required:
    _SEEN[name] = False
  _USAGE.append('--%s: %s (string)%s' % (name, description, {True: ' [REQUIRED]', False: ''}[required]))


def DefineFloat(name, default_value, description, required=False):
  FLAGS[name] = float(default_value)
  _CAST[name] = float
  _LONG_OPTIONS.append('%s=' % name)
  if required:
    _SEEN[name] = False
  _USAGE.append('--%s: %s (float)%s' % (name, description, {True: ' [REQUIRED]', False: ''}[required]))


def DefineBoolean(name, default_value, description, required=False):
  FLAGS[name] = bool(default_value)
  _CAST[name] = bool
  _LONG_OPTIONS.append(name)
  _LONG_OPTIONS.append('no-%s' % name)
  if required:
    _SEEN[name] = False
  _USAGE.append('--[no-]%s: %s (boolean)%s' % (name, description, {True: ' [REQUIRED]', False: ''}[required]))


def ParseFlags():
  env = os.environ
  for option in _LONG_OPTIONS:
    if option.endswith('='):
      option = option[:-1]
    key = 'FLAG_%s' % option.replace('-', '_')
    if key in env:
      value = env[key]
      if option.startswith('no-') and _CAST[option[3:]] == bool:
        option = option[3:]
        value = False
      elif _CAST[option] == bool:
        value = True
      FLAGS[option] = _CAST[option](value)
      _SEEN[option] = True

  options = getopt.gnu_getopt(sys.argv[1:], '', _LONG_OPTIONS)[0]
  for option, value in options:
    option = option[2:]
    if option.startswith('no-') and option[3:] in FLAGS and _CAST[option[3:]] == bool:
      option = option[3:]
      value = False
    elif _CAST[option] == bool:
      value = True
    FLAGS[option] = _CAST[option](value)
    _SEEN[option] = True

  if FLAGS['help']:
    Usage()

  for key in [key for key, value in _SEEN.iteritems() if value == False]:
    print 'Missing value for %s' % key
    print
    Usage()


def Usage(exitcode=1):
  print 'Usage: %s [options]' % sys.argv[0]
  print
  print '\n'.join(['  %s' % x for x in _USAGE])
  if exitcode != 0:
    sys.exit(exitcode)


DefineBoolean('help', False, 'Display help')
