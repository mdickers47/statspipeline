#!/usr/bin/python2.5
"""Commandline and environment flag parsing"""

import getopt
import os
import sys


FLAGS = {}
_SEEN = {}
_CAST = {}
_LONG_OPTIONS = []
_USAGE = []


def DefineInteger(name, default_value, description, required=False):
  """Define a flag that takes an integer value

  Args:
    name: Flag name; command line use is --<name>
    default_value: Value if not specified
    description: Flag description shown in help text
    required: If true, it is an error if this flag isn't specified
  """
  FLAGS[name] = int(default_value)
  _CAST[name] = int
  _LONG_OPTIONS.append('%s=' % name)
  if required:
    _SEEN[name] = False
  _USAGE.append('--%s: %s (integer)%s' % (name, description, {True: ' [REQUIRED]', False: ''}[required]))


def DefineString(name, default_value, description, required=False):
  """Define a flag that takes a string value
  
  Args:
    See DefineInteger()
  """
  FLAGS[name] = str(default_value)
  _CAST[name] = str
  _LONG_OPTIONS.append('%s=' % name)
  if required:
    _SEEN[name] = False
  _USAGE.append('--%s: %s (string)%s' % (name, description, {True: ' [REQUIRED]', False: ''}[required]))


def DefineFloat(name, default_value, description, required=False):
  """Define a flag that takes a floating-point value

  Args:
    See DefineInteger()
  """
  FLAGS[name] = float(default_value)
  _CAST[name] = float
  _LONG_OPTIONS.append('%s=' % name)
  if required:
    _SEEN[name] = False
  _USAGE.append('--%s: %s (float)%s' % (name, description, {True: ' [REQUIRED]', False: ''}[required]))


def DefineBoolean(name, default_value, description, required=False):
  """Define a flag that is enabled or disabled by name

  Args:
    See DefineInteger()
  """
  FLAGS[name] = bool(default_value)
  _CAST[name] = bool
  _LONG_OPTIONS.append(name)
  _LONG_OPTIONS.append('no-%s' % name)
  if required:
    _SEEN[name] = False
  _USAGE.append('--[no-]%s: %s (boolean)%s' % (name, description, {True: ' [REQUIRED]', False: ''}[required]))


def ParseFlags():
  """Parse environment and commandline flags into FLAGS"""
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
  """Print usage information generated from defined flags

  Args:
    exitcode: If nonzero, exit with this return value after printing usage
  """
  print 'Usage: %s [options]' % sys.argv[0]
  print
  print '\n'.join(['  %s' % x for x in _USAGE])
  if exitcode != 0:
    sys.exit(exitcode)


DefineBoolean('help', False, 'Display help')
