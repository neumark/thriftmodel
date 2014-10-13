#
# Autogenerated by Thrift Compiler (1.0.0-dev)
#
# DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
#
#  options string: py:new_style,utf8strings,dynamic
#

from thrift.Thrift import TType, TMessageType, TException, TApplicationException
from ttypes import *
from thrift.Thrift import TProcessor
from thrift.protocol.TBase import TBase, TExceptionBase


class Iface(object):
  def ping(self):
    pass

  def merge(self, parent1, parent2):
    """
    Parameters:
     - parent1
     - parent2
    """
    pass

  def zip(self):
    pass


class Client(Iface):
  def __init__(self, iprot, oprot=None):
    self._iprot = self._oprot = iprot
    if oprot is not None:
      self._oprot = oprot
    self._seqid = 0

  def ping(self):
    self.send_ping()
    self.recv_ping()

  def send_ping(self):
    self._oprot.writeMessageBegin('ping', TMessageType.CALL, self._seqid)
    args = ping_args()
    args.write(self._oprot)
    self._oprot.writeMessageEnd()
    self._oprot.trans.flush()

  def recv_ping(self):
    iprot = self._iprot
    (fname, mtype, rseqid) = iprot.readMessageBegin()
    if mtype == TMessageType.EXCEPTION:
      x = TApplicationException()
      x.read(iprot)
      iprot.readMessageEnd()
      raise x
    result = ping_result()
    result.read(iprot)
    iprot.readMessageEnd()
    return

  def merge(self, parent1, parent2):
    """
    Parameters:
     - parent1
     - parent2
    """
    self.send_merge(parent1, parent2)
    return self.recv_merge()

  def send_merge(self, parent1, parent2):
    self._oprot.writeMessageBegin('merge', TMessageType.CALL, self._seqid)
    args = merge_args()
    args.parent1 = parent1
    args.parent2 = parent2
    args.write(self._oprot)
    self._oprot.writeMessageEnd()
    self._oprot.trans.flush()

  def recv_merge(self):
    iprot = self._iprot
    (fname, mtype, rseqid) = iprot.readMessageBegin()
    if mtype == TMessageType.EXCEPTION:
      x = TApplicationException()
      x.read(iprot)
      iprot.readMessageEnd()
      raise x
    result = merge_result()
    result.read(iprot)
    iprot.readMessageEnd()
    if result.success is not None:
      return result.success
    if result.ex1 is not None:
      raise result.ex1
    raise TApplicationException(TApplicationException.MISSING_RESULT, "merge failed: unknown result");

  def zip(self):
    self.send_zip()

  def send_zip(self):
    self._oprot.writeMessageBegin('zip', TMessageType.ONEWAY, self._seqid)
    args = zip_args()
    args.write(self._oprot)
    self._oprot.writeMessageEnd()
    self._oprot.trans.flush()

class Processor(Iface, TProcessor):
  def __init__(self, handler):
    self._handler = handler
    self._processMap = {}
    self._processMap["ping"] = Processor.process_ping
    self._processMap["merge"] = Processor.process_merge
    self._processMap["zip"] = Processor.process_zip

  def process(self, iprot, oprot):
    (name, type, seqid) = iprot.readMessageBegin()
    if name not in self._processMap:
      iprot.skip(TType.STRUCT)
      iprot.readMessageEnd()
      x = TApplicationException(TApplicationException.UNKNOWN_METHOD, 'Unknown function %s' % (name))
      oprot.writeMessageBegin(name, TMessageType.EXCEPTION, seqid)
      x.write(oprot)
      oprot.writeMessageEnd()
      oprot.trans.flush()
      return
    else:
      self._processMap[name](self, seqid, iprot, oprot)
    return True

  def process_ping(self, seqid, iprot, oprot):
    args = ping_args()
    args.read(iprot)
    iprot.readMessageEnd()
    result = ping_result()
    self._handler.ping()
    oprot.writeMessageBegin("ping", TMessageType.REPLY, seqid)
    result.write(oprot)
    oprot.writeMessageEnd()
    oprot.trans.flush()

  def process_merge(self, seqid, iprot, oprot):
    args = merge_args()
    args.read(iprot)
    iprot.readMessageEnd()
    result = merge_result()
    try:
      result.success = self._handler.merge(args.parent1, args.parent2)
    except InvalidOperation, ex1:
      result.ex1 = ex1
    oprot.writeMessageBegin("merge", TMessageType.REPLY, seqid)
    result.write(oprot)
    oprot.writeMessageEnd()
    oprot.trans.flush()

  def process_zip(self, seqid, iprot, oprot):
    args = zip_args()
    args.read(iprot)
    iprot.readMessageEnd()
    self._handler.zip()
    return


# HELPER FUNCTIONS AND STRUCTURES

class ping_args(TBase):

  thrift_spec = (
  )

  def __hash__(self):
    value = 17
    return value

  def __repr__(self):
    L = ['%s=%r' % (key, value)
      for key, value in self.__dict__.iteritems()]
    return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

  def __eq__(self, other):
    return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

  def __ne__(self, other):
    return not (self == other)

class ping_result(TBase):

  thrift_spec = (
  )

  def __hash__(self):
    value = 17
    return value

  def __repr__(self):
    L = ['%s=%r' % (key, value)
      for key, value in self.__dict__.iteritems()]
    return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

  def __eq__(self, other):
    return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

  def __ne__(self, other):
    return not (self == other)

class merge_args(TBase):
  """
  Attributes:
   - parent1
   - parent2
  """

  thrift_spec = (
    None, # 0
    (1, TType.LIST, 'parent1', (TType.MAP,(TType.STRING,None,TType.LIST,(TType.STRUCT,(SomeStruct, SomeStruct.thrift_spec)))), None, ), # 1
    (2, TType.LIST, 'parent2', (TType.MAP,(TType.STRING,None,TType.LIST,(TType.STRUCT,(SomeStruct, SomeStruct.thrift_spec)))), None, ), # 2
  )

  def __init__(self, parent1=None, parent2=None,):
    self.parent1 = parent1
    self.parent2 = parent2

  def __hash__(self):
    value = 17
    value = (value * 31) ^ hash(self.parent1)
    value = (value * 31) ^ hash(self.parent2)
    return value

  def __repr__(self):
    L = ['%s=%r' % (key, value)
      for key, value in self.__dict__.iteritems()]
    return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

  def __eq__(self, other):
    return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

  def __ne__(self, other):
    return not (self == other)

class merge_result(TBase):
  """
  Attributes:
   - success
   - ex1
  """

  thrift_spec = (
    (0, TType.LIST, 'success', (TType.MAP,(TType.STRING,None,TType.LIST,(TType.STRUCT,(SomeStruct, SomeStruct.thrift_spec)))), None, ), # 0
    (1, TType.STRUCT, 'ex1', (InvalidOperation, InvalidOperation.thrift_spec), None, ), # 1
  )

  def __init__(self, success=None, ex1=None,):
    self.success = success
    self.ex1 = ex1

  def __hash__(self):
    value = 17
    value = (value * 31) ^ hash(self.success)
    value = (value * 31) ^ hash(self.ex1)
    return value

  def __repr__(self):
    L = ['%s=%r' % (key, value)
      for key, value in self.__dict__.iteritems()]
    return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

  def __eq__(self, other):
    return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

  def __ne__(self, other):
    return not (self == other)

class zip_args(TBase):

  thrift_spec = (
  )

  def __hash__(self):
    value = 17
    return value

  def __repr__(self):
    L = ['%s=%r' % (key, value)
      for key, value in self.__dict__.iteritems()]
    return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

  def __eq__(self, other):
    return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

  def __ne__(self, other):
    return not (self == other)