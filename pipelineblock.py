#!/usr/bin/python2.5

import cPickle
import gc
import MySQLdb
import os
import pyinotify
import signal
import sys
import time

from pyPgSQL import PgSQL


import flags

FLAGS = flags.FLAGS


flags.DefineString('db-type', 'mysql', 'Database type (mysql, pgsql)')
flags.DefineString('db-hostname', 'localhost', 'Database hostname to connect to')
flags.DefineString('db-username', os.getenv('USER'), 'Database username to connect with')
flags.DefineString('db-password', None, 'Database password to connect with')
flags.DefineString('db-name', None, 'Database name to use')

flags.DefineString('instance', None, 'Instance name for this instantiation of this block', required=True)
flags.DefineString('basedir', None, 'Base directory for input/output chunks', required=True)


class VirtualTable(object):
  """Store column names and row data; produce dictionaries on demand."""
  def __init__(self, fields, rows):
    """Constructor
    
    Args:
      fields: List of field names
      rows: List of rows, each of which is a list of field values
    """
    self._fields = fields
    self._rows = rows

  def __getitem__(self, i):
    return dict(zip(self._fields, self._rows[i]))

  def __len__(self):
    return len(self._rows)

  def __str__(self):
    ret = '============================================\n'
    for row in self:
      for field, value in row.iteritems():
        ret += '%s: %s\n' % (field, value)
      ret += '============================================\n'
    return ret

  def fields(self):
    return self._fields

  def rows(self):
    return self._rows

  def append(self, row):
    """Append a new row

    Args:
      row: A list of values (no field names)
    """
    self._rows.append(row)


class PipelineBlock(pyinotify.ProcessEvent):
  _dbh = None
  _stop = False

  def __init__(self, basedir, instance):
    """Constructor

    Args:
      basedir: Parent directory to create pipeline subdirs in
      instance: The unique-per-pipeline name for tihs instance
    """
    self._instance = instance
    self._input_dir = os.path.join(basedir, '%s-input' % self._instance)
    self._output_dir = os.path.join(basedir, '%s-output' % self._instance)
    self._completed_dir = os.path.join(basedir, '%s-completed' % self._instance)
    self._makedirs(self._input_dir)
    self._makedirs(self._output_dir)
    self._makedirs(self._completed_dir)

  def _makedirs(self, dir):
    try:
      os.makedirs(dir, 0755)
    except:
      pass

  def process_IN_MOVED_TO(self, event):
    """inotify event for a file moved here"""
    self.ProcessFile(event.name)

  def process_IN_CREATE(self, event):
    """inotify event for a newly created file"""
    self.ProcessFile(event.name)

  def StartTimer(self):
    self._start_time = time.time()

  def StopTimer(self):
    return time.time() - self._start_time

  def Log(self, msg, unused_priority=0):
    self.DBExecute("INSERT INTO Log (class, instance, event) VALUES (%s, %s, %s)",
                   self.__class__.__name__, self._instance, msg)
    print '%s/%s: %s' % (self.__class__.__name__, self._instance, msg)

  def WriteData(self, name, data):
    tempname = os.path.join(self._output_dir, '_%s' % name)
    handle = open(tempname, 'w')
    self.WriteFile(handle, data)
    handle.close()
    os.rename(tempname,
              os.path.join(self._output_dir, name))

  def ProcessFile(self, name):
    if name.startswith('_') or name.endswith('.tmp'):
      # Temporary file
      return

    if not os.path.exists(os.path.join(self._input_dir, name)):
      return

    self.Log('Processing %s' % name)

    self.StartTimer()

    handle = open(os.path.join(self._input_dir, name), 'r', 1024*1024)
    data = self.ParseFile(handle, name)
    handle.close()

    try:
      rows_in = len(data)
    except TypeError:
      rows_in = 0

    output = self.NewData(data)

    try:
      rows_out = len(output)
    except TypeError:
      rows_out = 0

    self.WriteData(name, output)

    elapsed_time = self.StopTimer()

    os.rename(os.path.join(self._input_dir, name),
              os.path.join(self._completed_dir, name))

    rps = rows_in / elapsed_time
    self.Log('%s: %ld -> %ld rows in %.2fs (%ld rps)' % (name, rows_in, rows_out, elapsed_time, rps))
    self.DBDisconnect()
    gc.collect()

  def Stop(self, *_):
    """Mark for stop after next completed file"""
    self.Log('Stopping...')
    self._stop = True

  def Run(self):
    """Main loop"""
    self.Log('Starting')

    signal.signal(signal.SIGTERM, self.Stop)
    wm = pyinotify.WatchManager()
    mask = pyinotify.EventsCodes.IN_CREATE | pyinotify.EventsCodes.IN_MOVED_TO
    notifier = pyinotify.Notifier(wm, self)
    wm.add_watch(self._input_dir, mask, rec=True)
    while True:
      if self._stop:
        self.Log('Stopped.')
        return
      notifier.process_events()
      # Catch anything here at startup or that inotify missed
      for path, dirs, files in os.walk(self._input_dir):
        for filename in files:
          if self._stop:
            self.Log('Stopped.')
            return
          self.ProcessFile(filename)
      try:
        if notifier.check_events():
          notifier.read_events()
      except KeyboardInterrupt:
        self.Log('So long')
        break

  def NewData(self, data):
    """Perform operation for this block

    Args:
      data: Output from parseFile
    Returns:
      Output to pass to writefile
    """
    return data

  def ParseFile(self, handle, name):
    """Unpickle, turn into virtual table

    Args:
      handle: File handle
      name: Source file name (without path)
    Returns:
      Parsed file contents
    """
    return cPickle.load(handle)

  def WriteFile(self, handle, data):
    """Pickle to file

    Args:
      handle: File handle
      data: Data to write
    """
    cPickle.dump(data, handle, cPickle.HIGHEST_PROTOCOL)

  def DBDisconnect(self):
    if self._dbh:
      self._dbh.close()
      self._dbh = None

  def DBExecute(self, query, *args):
    """Execute a query on the database, creating a connection if necessary

    Args:
      query: SQL string
    Returns:
      Full query result in virtual table
    """
    if not self._dbh:
      db_args = {
        'host': FLAGS['db-hostname'],
        'user': FLAGS['db-username'],
        'password': FLAGS['db-password'],
        'db': FLAGS['db-name'],
      }
      if FLAGS['db-type'] == 'mysql':
        self._dbh = MySQLdb.connect(host=FLAGS['db-hostname'],
                                    user=FLAGS['db-username'],
                                    passwd=FLAGS['db-password'],
                                    db=FLAGS['db-name'])
      elif FLAGS['db-type'] == 'pgsql':
        self._dbh = PgSQL.connect(host=FLAGS['db-hostname'],
                                  user=FLAGS['db-username'],
                                  password=FLAGS['db-password'],
                                  database=FLAGS['db-name'])
      else:
        print 'Invalid db-type: %s' % FLAGS['db-type']
        sys.exit(1)
      self._cursor = self._dbh.cursor()
    self._cursor.execute(query, args)
    self._dbh.commit()
    try:
      result = self._cursor.fetchall()
    except:
      return None
    if not result:
      return result
    fields = [i[0] for i in self._cursor.description]
    return VirtualTable(fields, result)


def main(block_class, *args, **kwargs):
  flags.ParseFlags()

  block = block_class(FLAGS['basedir'], FLAGS['instance'], *args, **kwargs)
  block.Run()
