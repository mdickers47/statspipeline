#!/usr/bin/python2.4

import cPickle
import gc
import MySQLdb
import os
import signal
import sys
import time

from pyinotify import pyinotify


_DB_ARGS={
  'host':   'wells',
  'user':   'flamingcow',
  'passwd': '',
  'db':     'edaystats'
}


class MagicDict(object):
  """Pretends to be a dictionary cursor, takes less memory.  Magic!"""
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
    self.DBExecute('BEGIN')
    self.DBExecute("INSERT INTO PipelineEvents (class, instance, filename, rows_in, rows_out, elapsed_ms) VALUES ('%s', '%s', '%s', %d, %d, %d)" %
                   (self.__class__.__name__, self._instance, name, rows_in, rows_out, int(elapsed_time * 1000.0)))
    self.DBExecute('COMMIT')
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

  def NewData(self, _):
    """Perform operation for this block

    Args:
      data: Output from parseFile
    Returns:
      Output to pass to writefile
    """
    raise NotImplemented('Please implement NewData')

  def ParseFile(self, handle, name):
    """Unpickle, turn into magic dict

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
    self._dbh.close()
    self._dbh = None

  def DBExecute(self, query):
    """Execute a query on the database, creating a connection if necessary

    Args:
      query: SQL string
    Returns:
      Full query result in magic dict
    """
    if not self._dbh:
      self._dbh = MySQLdb.Connect(**_DB_ARGS)
      self._cursor = self._dbh.cursor()
    self._cursor.execute(query)
    result = self._cursor.fetchall()
    if not result:
      return result
    fields = [i[0] for i in self._cursor.description]
    return MagicDict(fields, result)


def main(block_class, *args, **kwargs):
  if len(sys.argv) < 3:
    print 'Usage: %s <instance> <basedir>' % sys.argv[0]
    sys.exit(1)

  instance = sys.argv[1]
  basedir = sys.argv[2]
  block = block_class(basedir, instance, *args, **kwargs)
  block.Run()
