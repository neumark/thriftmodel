import sys
import types
import itertools
import inspect
from functools import wraps
from thrift.Thrift import TType, TMessageType, TException, TApplicationException
from thrift.protocol.TBase import TBase, TExceptionBase
from thrift.transport import TTransport
from thriftmodel.protocol import default_protocol_factory

class ValidationException(Exception):
    pass

class UndefinedFieldException(Exception):
    pass

class ThriftFieldMergeException(Exception):
    def __init__(self, msg,
            to_merge_py_name=None, to_merge_field=None,
            original_py_name=None, original_field=None):
        Exception.__init__(self, msg)
        self.to_merge_py_name=to_merge_py_name
        self.to_merge_field=to_merge_field
        self.original_py_name=original_py_name
        self.original_field=original_field

def thrift_field_id_to_name(field_type_id):
    return TType._VALUES_TO_NAMES[field_type_id].lower()

def collect_field_type_constructors():
    cons_list = {}
    for key in dir(sys.modules[__name__]):
        value = getattr(sys.modules[__name__], key)
        if value == UnionField:
            continue  # don't save unionfield, use StructField instead.
        if inspect.isclass(value) and\
            issubclass(value, ThriftField) and\
            hasattr(value, "field_type_id"):
            cons_list[value.field_type_id] = value
    return cons_list

class FieldMerger(object):
    """
    Based on field id, or thrift field name, replaces each
    field in the original list with the field in the list_to_merge
    ith the same thrift_field_name. If the field types + ids do not match
    there is a conflict. In this case either an exception is thrown or
    the field def from list_to_merge wins.
    both original_list and list_to_merge should be lists of 
    (python_field_name, field_object) tuples.

    The assumption is that both original_list and list_to_merge are
    valid in themselves (no duplicate, no duplicate thrift of
    python field names). It is assumed that original_list has no
    non-positive field_ids, but this is not a requirement for
    list_to_merge.

    Possible conflicts introduced by the merge:
    * Duplicate field id
    * Duplicate field name (thrift or python)
    * Field id / name mismatch (different name for same id in the two lists)
    * Field type mismatch (same id, name in both lists, but different type)
      NOTE: types are not currently checked.
    """
 
    def __init__(
            self,
            original_fields,
            to_merge_fields,
            overwrite_if_conflict=False):
        self.original_fields = original_fields
        self.to_merge_fields = to_merge_fields
        self.overwrite_if_conflict = overwrite_if_conflict
        self.merged_field_ids = []
        self.conflicting_field_ids = []
        self.assert_fields_valid(original_fields, error_source="original")
        self.assert_fields_valid(to_merge_fields, allow_nonpositive_field_ids=True, error_source="to_merge")
        self.assert_no_duplicates(original_fields, error_source="original")
        self.assert_no_duplicates(to_merge_fields, allow_default_field_id_duplicates=True, error_source="to merge")

    def assert_fields_valid(
            self,
            fields,
            allow_nonpositive_field_ids=False,
            error_source=None):
        # fields is a list of (field_name, field_def) pairs
        def err(field_ix, message):
            msg = "field number %(field_ix)s: %(message)s" % {
                'field_ix': field_ix,
                'message': message}
            if error_source is not None:
                msg = "%s %s" % (error_source, msg)
            raise ThriftFieldMergeException(msg)
        def err_invalid_attr(field_ix, invalid_attr):
            msg = "invalid %(invalid_attr)s attribute (the value is %(invalid_value)s)." % {
                'invalid_attr': invalid_attr,
                'invalid_value': str(getattr(fields[field_ix][1], invalid_attr))}
            err(field_ix, msg)
        for field_ix in xrange(0, len(fields)):
            python_field_name, field_definition = fields[field_ix]
            if not python_field_name:
                err(field_ix, 'python_field_name has bad value: %s' % str(python_field_name))
            for attr_name in ['field_id', 'thrift_field_name']:
                if hasattr(field_definition, attr_name):
                    if getattr(field_definition, attr_name) is None:
                        err_invalid_attr(field_ix, attr_name)
            if field_definition.field_id < 1 and (not allow_nonpositive_field_ids):
                err_invalid_attr(field_ix, 'field_id')


 
    def assert_no_duplicates(self, fields, allow_default_field_id_duplicates=False, error_source=None):
        # fields is a list of (field_name, field_def) pairs
        def err(duplicate_attr, duplicate_value):
            original_field_ix = duplicates[duplicate_attr][duplicate_value]
            msg = "field %(duplicate_field_ix)s (%(duplicate_field_name)s) is duplicate of %(original_field_ix)s (%(original_field_name)s) by attribute %(duplicate_attr)s (both are %(duplicate_value)s)." % {
                'duplicate_attr': duplicate_attr,
                'duplicate_value': duplicate_value,
                'duplicate_field_ix': field_ix,
                'duplicate_field_name': fields[field_ix][0],
                'original_field_ix': original_field_ix,
                'original_field_name': fields[original_field_ix][0]
                }
            if error_source is not None:
                msg = "%s %s" % (error_source, msg)
            raise ThriftFieldMergeException(msg)
        duplicates = {
            'python_field_name': {},
            'thrift_field_name': {},
            'field_id': {}}
        
        for field_ix in xrange(0, len(fields)):
            python_field_name, field_definition = fields[field_ix]
            attrs = {
                'thrift_field_name': field_definition.thrift_field_name,
                'python_field_name': python_field_name
            }
            if not (allow_default_field_id_duplicates and field_definition.field_id < 0):
                attrs['field_id'] = field_definition.field_id
            for attr_name, value in attrs.items():
                if value in duplicates[attr_name]:
                    err(attr_name, value)
                else:
                    duplicates[attr_name][value] = field_ix


    def original_field_ix_by_name(self, thrift_field_name):
        candidate_list = []
        for original_field_ix in xrange(0, len(self.original_fields)):
            original_py_name, original_field = self.original_fields[original_field_ix]
            if thrift_field_name == original_field.thrift_field_name:
                candidate_list.append(original_field_ix)
        return candidate_list

    def attempt_merge(self, original_field_ix, to_merge_field_ix):
        # the merge is successful if:
        # 1. both fields have the same field id (or
        #    to_merge_field.field_id is -1).
        # 2. both fields have the same thrift_field_name.
        # 3. both fields have the same python field name.
        # 4. TODO: check that the types of the fields match.
        field_indexes = (original_field_ix, to_merge_field_ix)
        to_merge_py_name, to_merge_field = self.to_merge_fields[to_merge_field_ix]
        original_py_name, original_field = self.original_fields[original_field_ix]
        if not to_merge_field.field_id in [original_field.field_id, -1]:
            self.handle_conflict("field_id mismatch", *field_indexes)
        elif to_merge_field.thrift_field_name != original_field.thrift_field_name:
            self.handle_conflict("thrift_field_name mismatch", *field_indexes)
        elif to_merge_py_name != original_py_name:
            self.handle_conflict("python field name mismatch", *field_indexes)
        self.mark_fields_merged(*field_indexes)

    def handle_conflict(self, msg, original_field_ix, to_merge_field_ix):
        self.conflicting_field_ids.append((original_field_ix, to_merge_field_ix))
        if not self.overwrite_if_conflict:
            to_merge_py_name, to_merge_field = self.to_merge_fields[to_merge_field_ix]
            original_py_name, original_field = self.original_fields[original_field_ix]
            raise ThriftFieldMergeException(msg,
                to_merge_py_name, to_merge_field,
                original_py_name, original_field)

    def mark_fields_merged(self, original_field_ix, to_merge_field_ix):
        self.merged_field_ids.append((original_field_ix, to_merge_field_ix))

    def get_merge_result(self):
        merge_result = []
        merge_map = dict(self.merged_field_ids)
        # add original fields, substituting in merged fields from
        # to_merge_fields.
        for original_field_ix in xrange(0, len(self.original_fields)):
            if original_field_ix in merge_map:
                field_data = self.to_merge_fields[merge_map[original_field_ix]]
            else:
                field_data = self.original_fields[original_field_ix]
            merge_result.append(field_data)
        # Add fields form to_merge_fields which weren't merged with anything
        # in original_fields
        merged_field_ix_set = set([pair[1] for pair in self.merged_field_ids])
        for to_merge_field_ix in xrange(0, len(self.to_merge_fields)):
            if to_merge_field_ix not in merged_field_ix_set:
                merge_result.append(self.to_merge_fields[to_merge_field_ix])
        return merge_result

    def merge(self):
        for to_merge_field_ix in xrange(0, len(self.to_merge_fields)):
            to_merge_py_name, to_merge_field = self.to_merge_fields[to_merge_field_ix]
            # match by thrift_field_name
            merge_candidates = self.original_field_ix_by_name(to_merge_field.thrift_field_name)
            # two fields should not have the same id in the original field list
            if len(merge_candidates) > 1:
                raise ThriftFieldMergeException("The original field list "+\
                    "has duplicate thrift_field_names: %s" % ", ".join([str(c) for c in merge_candidates]))
            if merge_candidates:
                self.attempt_merge(merge_candidates[0], to_merge_field_ix)
        return self.get_merge_result()

class ThriftFieldFactory(object):

    def __init__(self, field_merger_class=FieldMerger):
        self.field_merger_class = field_merger_class

    def create_thriftmodel_field(self, field_type_id, type_parameter, **init_kwargs): 
        # If possible get value from constructor dict
        cons = collect_field_type_constructors().get(field_type_id, None)
        if cons is None:
            # Default to ThriftField
            cons = ThriftField
        init_args = []
        init_kwargs['field_type_id'] = field_type_id
        if type_parameter is not None:
            if field_type_id == TType.MAP:
                # key type
                init_args.append(
                    self.create_thriftmodel_field(type_parameter[0], type_parameter[1]))
                # value type
                init_args.append(
                    self.create_thriftmodel_field(type_parameter[2], type_parameter[3]))
            elif field_type_id in [TType.LIST, TType.SET]:
                init_args.append(
                    self.create_thriftmodel_field(
                        type_parameter[0], type_parameter[1]))
            elif field_type_id == TType.STRUCT:
                init_args.append(type_parameter[0])
        return cons(*init_args, **init_kwargs)

    def convert_field_spec_to_field(self, thrift_spec):
        # verify that the id and name of the field is set
        field_id = thrift_spec[0]
        field_type_id = thrift_spec[1]
        thrift_field_name = thrift_spec[2]
        type_parameter = thrift_spec[3]
        default = thrift_spec[4]
        return self.create_thriftmodel_field(
                field_type_id,
                type_parameter,
                thrift_field_name=thrift_field_name,
                field_id=field_id,
                default=default)

    def get_inherited_fields_from_thrift_spec(self, thrift_spec):
        fields = []
        for field_thrift_spec in thrift_spec[1:]:
            converted_field = self.convert_field_spec_to_field(field_thrift_spec)
            fields.append((converted_field.thrift_field_name, converted_field))
        return fields

    def get_inherited_fields(self, bases):
        # Inherited fields can come from cls.thrift_spec or
        # cls._fields_by_name
        # note that once get_field_definition() has run, this
        # will also return the fields of the current class.
        inherited_fields = []
        for cls in bases:
            thrift_spec = []
            if hasattr(cls, 'thrift_spec'):
                thrift_spec = cls.thrift_spec
            cls_fields = self.get_inherited_fields_from_thrift_spec(thrift_spec)
            if hasattr(cls, '_fields_by_name'):
                thriftmodel_fields = list(cls._fields_by_name.iteritems())
                merger = self.field_merger_class(cls_fields, thriftmodel_fields)
                cls_fields = merger.merge()
            # Merge inherited_fields with the fields of the current class
            merger = self.field_merger_class(inherited_fields, cls_fields)
            inherited_fields = merger.merge()
        return inherited_fields

    def field_dict_to_field_list(self, field_dict):
        # Then, we process the contents of field_dict
        fields = [(k,v) for k,v in field_dict.iteritems()]
        # set missing field names
        for name, field_data in fields:
            if field_data.thrift_field_name is None:
                field_data.thrift_field_name = name
        return fields

    def apply_thrift_spec(self, cls, fields=None, bases=None):
        thrift_spec_attr = self.get_field_definition(cls, fields, bases)
        for attr_name, attr_value in thrift_spec_attr.items():
            if attr_value:  # do not set empty values
                setattr(cls, attr_name, attr_value)
        cls._thrift_spec = None

    def replace_default_field_ids(self, fields):
        # replace -1 field ids with the next available positive integer
        # fields is a list of (python_field_name, field_def) pairs.
        taken_field_ids = set([f[1].field_id for f in fields])
        next_field_id = 1
        # sort fields by creation count
        fields = sorted(fields, key=lambda x:x[1].creation_count)
        for field_name, field in fields:
            if field.field_id < 1:
                while next_field_id in taken_field_ids:
                    next_field_id += 1
                taken_field_ids.add(next_field_id)
                field.field_id = next_field_id
        return fields
 
    def get_field_definition(self, cls, field_dict=None, bases=None):
        """ Returns a dictionary of attributes which will
            be set on the class by the metaclass. These
            attributes are:
            _fields_by_id
            _fields_by_name
        """
        inherited_fields = self.get_inherited_fields(bases or [])
        current_class_fields = self.field_dict_to_field_list(field_dict or {})
        fields = self.field_merger_class(inherited_fields, current_class_fields).merge()
        self.replace_default_field_ids(fields)
        # thrift_spec can be a list or a tuple
        # we only need to set it here in the latter case
        # because a list thrift_spec is already an attr of cls.
        attr_dict = {
            '_fields_by_id': dict([(v.field_id, (k,v)) for k,v in fields]),
            '_fields_by_name': dict([(k,v) for k,v in fields])}
        return attr_dict

class ThriftField(object):
    _field_creation_counter = 0

    def __init__(self,
            thrift_field_name=None,
            field_id=-1,
            field_type_id=-1,
            default=None,
            required=False,
            validators=None):
        self.creation_count = ThriftField._field_creation_counter
        ThriftField._field_creation_counter += 1
        self.field_id = field_id
        self.thrift_field_name = thrift_field_name
        self.default = default
        # if the field_type_id argument is invalid, we can use the
        # default value set on the class (when it exists).
        if field_type_id < 0 and hasattr(self.__class__, 'field_type_id'):
            self.field_type_id = self.__class__.field_type_id
        else:
            # TODO: we should probably throw an exception here
            # if field_type_id is < 0
            self.field_type_id = field_type_id
        self.required = required
        self.validators = validators

    def type_equals(self, other):
        return self.field_type_id == other.field_type_id and\
               (self.type_parameter == other.type_parameter) or\
               self.type_parameter is not None and self.type_parameter.type_equals(other.type_parameter)

    def validate(self, value):
        for validator in (self.validators or []):
            # TODO: we may want to save the output of validators for warnings and messages
            validator.validate(value)

    def thrift_type_name(self):
        return thrift_field_id_to_name(self.field_type_id)

    def to_tuple(self):
        return (self.field_id, self.field_type_id, self.thrift_field_name, None, self.default,)


class ParametricThriftField(ThriftField):
    def __init__(self, type_parameter, **kwargs):
        super(ParametricThriftField, self).__init__(**kwargs)
        self.type_parameter = type_parameter

    def get_type_parameter(self):
        tp = self.type_parameter.to_tuple()
        return (tp[1], tp[3])

    def _validate_elements(self, collection, field_or_model):
        if field_or_model is not None:
            if isinstance(field_or_model, ThriftField):
                for elem in collection:
                    field_or_model.validate(elem)
            if isinstance(field_or_model, ThriftModel):
                for elem in collection:
                    elem.validate()

    def validate(self, container):
        # Run an validators on the container type itself.
        # Eg: if we want to chech that a list has 4 elements,
        # the validator would be on the list itself.
        super(ParametricThriftField, self).validate(container)
        # Validate the elements of the container if there are validators defined.
        self._validate_elements(container, self.type_parameter)

    def thrift_type_name(self):
        return "%s<%s>" % (
            thrift_field_id_to_name(self.field_type_id),
            self.type_parameter.thrift_type_name())

    def to_tuple(self):
        return (self.field_id, self.field_type_id, self.thrift_field_name, self.get_type_parameter(), self.default,)

class IntField(ThriftField):
    field_type_id = TType.I64

class DoubleField(ThriftField):
    field_type_id = TType.DOUBLE

class BoolField(ThriftField):
    field_type_id = TType.BOOL

class UTF8Field(ThriftField):
    field_type_id = TType.UTF8

class StringField(ThriftField):
    field_type_id = TType.STRING

class BinaryField(StringField):
    is_binary = True

class StructField(ParametricThriftField):
    field_type_id = TType.STRUCT

    def thrift_type_name(self):
        return self.type_parameter.thrift_type_name()

    def get_type_parameter(self):
        return self.type_parameter.to_tuple()[3]

class UnionField(StructField):
    is_union = True
    def __init__(self, type_parameter, **kwargs):
        super(UnionField, self).__init__(type_parameter, is_boxed=False, **kwargs)
        self.is_boxed = is_boxed

class ListField(ParametricThriftField):
    field_type_id = TType.LIST

    def get_type_parameter(self):
        tp = self.type_parameter.to_tuple()
        return (tp[1], tp[3])

class SetField(ListField):
    field_type_id = TType.SET

class MapField(ParametricThriftField):
    field_type_id = TType.MAP

    def __init__(self, key_type_parameter, value_type_parameter, **kwargs):
        super(MapField, self).__init__(None, **kwargs)
        self.key_type_parameter = key_type_parameter
        self.value_type_parameter = value_type_parameter

    def get_type_parameter(self):
        key_spec = self.key_type_parameter.to_tuple()
        value_spec = self.value_type_parameter.to_tuple()
        return (key_spec[1],
                key_spec[3],
                value_spec[1],
                value_spec[3])

    def validate(self, dictionary):
        # Run an validators on the container type itself.
        # Eg: if we want to chech that a list has 4 elements,
        # the validator would be on the list itself.
        super(MapField, self).validate(dictionary)
        # Validate the elements of the container if there are validators defined.
        if dictionary:
            self._validate_elements(dictionary.keys(), self.key_type_parameter)
            self._validate_elements(dictionary.values(), self.value_type_parameter)

    def thrift_type_name(self):
        return "%s<%s, %s>" % (
            thrift_field_id_to_name(self.field_type_id),
            self.key_type_parameter.thrift_type_name(),
            self.value_type_parameter.thrift_type_name())

def serialize(obj, protocol_factory=default_protocol_factory, protocol_options=None):
    transport = TTransport.TMemoryBuffer()
    protocol = protocol_factory.getProtocol(transport)
    if protocol_options is not None and hasattr(protocol, 'set_options'):
        protocol.set_options(protocol_options)
    write_to_stream(obj, protocol)
    transport._buffer.seek(0)
    return transport._buffer.getvalue()

def deserialize(cls, stream, protocol_factory=default_protocol_factory, protocol_options=None):
    obj = cls()
    transport = TTransport.TMemoryBuffer()
    transport._buffer.write(stream)
    transport._buffer.seek(0)
    protocol = protocol_factory.getProtocol(transport)
    if protocol_options is not None and hasattr(protocol, 'set_options'):
        protocol.set_options(protocol_options)
    read_from_stream(obj, protocol)
    return obj

def write_to_stream(obj, protocol):
    return protocol.writeStruct(obj, obj.thrift_spec)

def read_from_stream(obj, protocol):
    protocol.readStruct(obj, obj.thrift_spec)

class ThriftModelMetaclass(type):
    def __init__(cls, name, bases, dct):
        super(ThriftModelMetaclass, cls).__init__(name, bases, dct)
        fields = dict([(k,v) for k,v in dct.iteritems() if isinstance(v, ThriftField)])
        # Note: we could optionally pass a custom FieldMerger here if needed.
        field_factory = ThriftFieldFactory(field_merger_class=FieldMerger)
        field_factory.apply_thrift_spec(cls, fields, bases)

    @property
    def thrift_spec(cls):
        return cls._make_thrift_spec()


class ThriftModel(TBase):

    __metaclass__ = ThriftModelMetaclass

    def __init__(self, *args, **kwargs):
        self._model_data = {}

        for field_name, value in kwargs.iteritems():
            setattr(self, field_name, value)

        for i in xrange(0, len(args)):
            field_id = self.thrift_spec[i+1][0]
            self._model_data[field_id] = args[i]

    def __repr__(self):
        L = ['%s=%r' % (self._fields_by_id[field_id][0], value)
            for field_id, value in self._model_data.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def iterkeys(self):
        return itertools.imap(
                lambda pair: self._fields_by_id[pair[0]][1].thrift_field_name,
                itertools.ifilter(lambda pair: pair[1] is not None, self._model_data.iteritems()))

    def _thrift_field_name_to_field_id(self, thrift_field_name):
        field = [f[1] for f in self._fields_by_id.values() if f[1].thrift_field_name == thrift_field_name]
        if len(field) < 1:
            raise KeyError(thrift_field_name)
        return field[0].field_id

    def __getitem__(self, thrift_field_name):
        return self._model_data[self._thrift_field_name_to_field_id(thrift_field_name)]

    def __setitem__(self, thrift_field_name, value):
        self._model_data[self._thrift_field_name_to_field_id(thrift_field_name)] = value

    def __delitem__(self, thrift_field_name):
        self._model_data.__delitem__(
                self._thrift_field_name_to_field_id(thrift_field_name))

    def __iter__(self):
        return self.iterkeys()


    def __getattribute__(self, name):
        # check in model_data first
        fields_by_name = object.__getattribute__(self, '_fields_by_name')
        # Note: In a try ... raise block because reading of _model_data
        # raises an AttributeError in ThriftModel.__init__, when the
        # attribute is initialized.
        try:
            model_data = object.__getattribute__(self, '_model_data')
            # If a model field name matches, return its value
            if name in fields_by_name:
                return model_data.get(fields_by_name[name].field_id, None)
        except AttributeError:
            pass
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if hasattr(self, '_model_data') and name in self._fields_by_name:
            self._model_data[self._fields_by_name[name].field_id] = value
            return
        super(ThriftModel, self).__setattr__(name, value)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not (self == other)

    def serialize(self, protocol_factory=default_protocol_factory, protocol_options=None):
        return serialize(self, protocol_factory, protocol_options)

    def _set_value_by_thrift_field_id(self, field_id, value):
        self._model_data[field_id] = value

    def _get_value_by_thrift_field_id(self, field_id):
        return self._model_data.get(field_id, None)

    @property
    def thrift_spec(self):
        return self._make_thrift_spec()
    
    @classmethod
    def _make_thrift_spec(cls):
        if not hasattr(cls, '_thrift_spec') or cls._thrift_spec is None:
            cls._thrift_spec = [None]
            if hasattr(cls, '_fields_by_name'):
                field_list = sorted(cls._fields_by_name.values(), key=lambda x: x.field_id)
                for f in field_list:
                    cls._thrift_spec.append(f.to_tuple())
        return cls._thrift_spec

    @classmethod
    def deserialize(cls, stream, protocol_factory=default_protocol_factory, protocol_options=None):
        return deserialize(cls, stream, protocol_factory, protocol_options)

    
    @classmethod
    def to_tuple(cls):
        return (-1, TType.STRUCT, cls.__name__, (cls, cls.thrift_spec), None,)

    def validate(self):
        # check to make sure required fields are set
        for k, v in self._fields_by_name.iteritems():
            if v.required and self._model_data.get(v.field_id, None) is None:
                raise ValidationException("Required field %s (id %s) not set" % (k, v.field_id))
            # Run any field validators
            v.validate(self._model_data.get(v.field_id, None))
        # Run the validator for the model itself (if it is set)
        if hasattr(self, 'validators'):
            for validator in (self.validators or []):
                validator.validate(self)

class UnboxedUnion(object):
    is_unboxed_union = True


