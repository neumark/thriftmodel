from unimodel.backends.base import SchemaWriter
import copy
import json
from unimodel import types
from unimodel.backends.json.type_data import get_field_name
from unimodel.util import get_backend_type

"""
Useful: http://www.jsonschema.net/
Example: from http://json-schema.org/example2.html
"""


MAP_DEFINITION_TEMPLATE = {
    "description": "map",
    "additionalProperties": True,
}

STRUCT_DEFINITION_TEMPLATE = {
    "type": "object",
    "properties": {},  # Fill with field definitions
    "additionalProperties": True,
    "required": [],  # Fill with required field names
}

SCHEMA_TEMPLATE = dict(copy.deepcopy(
    STRUCT_DEFINITION_TEMPLATE).items() + {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": None,  # Replace with schema description
    "definitions": {}  # Fill struct and map type definitions
}.items())

LIST_TEMPLATE = {
    "type": "array",
    "items": {
        "type": None  # Replace with type reference to definition of elements
    },
    "uniqueItems": False  # set to True for sets
}

JSONDATA_TEMPLATE = {
    "description": "Generic JSONData field",
    "additionalProperties": True
}


class JSONSchemaWriter(SchemaWriter):

    def __init__(self, *args, **kwargs):
        super(JSONSchemaWriter, self).__init__(*args, **kwargs)

    def get_schema_ast(self, root_struct_class):
        # Collect struct dependencies of root struct (if any).
        struct_dependencies = self.get_dependencies_for_one_struct(
            root_struct_class)
        # Collect struct dependencies of manually added struct classes (if
        # any).
        for struct_class in self.struct_classes:
            self.get_dependencies_for_one_struct(
                struct_class,
                struct_dependencies)
        schema = copy.deepcopy(SCHEMA_TEMPLATE)
        schema['description'] = self.description
        # Note, the root class will be added to the definitions list
        # even if it is only used to desribe the top-level object.
        schema['definitions'] = dict(
            [self.get_struct_definition(s) for s in struct_dependencies])
        self.add_struct_properties(root_struct_class, schema)
        return schema

    def get_struct_definition(self, struct_class):
        """ returns (name, definition) pairs """
        struct_def = copy.deepcopy(STRUCT_DEFINITION_TEMPLATE)
        self.add_struct_properties(struct_class, struct_def)
        return (struct_class.get_name(), struct_def)

    def add_struct_properties(self, struct_class, struct_def):
        if struct_class.get_field_definitions():
            required = []
            for field in struct_class.get_field_definitions():
                field_name = get_field_name(field)
                struct_def['properties'][
                    field_name] = self.get_type_definition(field.field_type)
                if field.required:
                    required.append(field_name)
            struct_def['required'] = required
        if 'required' in struct_def and not struct_def['required']:
            del struct_def['required']

    def get_type_definition(self, type_definition):
        """ returns field (name, definition) pair """
        if isinstance(type_definition, types.Enum):
            return self.define_enum_field(type_definition)
        if isinstance(type_definition, types.NumberTypeMarker):
            return self.define_basic_field(type_definition)
        if isinstance(type_definition, types.StringTypeMarker):
            return self.define_basic_field(type_definition)
        if isinstance(type_definition, types.Bool):
            return self.define_basic_field(type_definition)
        if isinstance(type_definition, types.Struct):
            # Since all the structs were already collected, and are
            # defined in the definitions section, it's enough to refer
            # to the struct here.
            return self.reference_type(type_definition)
        if isinstance(type_definition, types.Map):
            return self.define_map_field(type_definition)
        if isinstance(type_definition, types.List):
            return self.define_array(type_definition)
        if isinstance(type_definition, types.JSONData):
            return copy.deepcopy(JSONDATA_TEMPLATE)
        if isinstance(type_definition, types.Tuple):
            return self.define_array(type_definition)
        raise Exception(
            "Cannot create schema for type %s" %
            str(type_definition))

    def define_basic_field(self, type_definition):
        return copy.deepcopy(get_backend_type("json", type_definition.type_id))

    def define_enum_field(self, type_definition):
        field_def = {'enum': type_definition.names()}
        return field_def

    def reference_type(self, type_definition):
        return {
            "$ref": "#/definitions/%s" %
            type_definition.get_python_type().get_name()}

    def define_map_field(self, type_definition):
        """
        A map looks something like this:
        (taken from:
        https://github.com/swagger-api/swagger-spec/blob/master/fixtures/v2.0/json/models/modelWithInt32Map.json)
        {
          "description": "This is a Map[String, Integer]",
          "additionalProperties": {
            "type": "integer",
            "format": "int32"
          }
        }"""

        field_def = copy.deepcopy(MAP_DEFINITION_TEMPLATE)
        field_def["description"] = type_definition.get_type_name()
        if not isinstance(type_definition.type_parameters[0], types.UTF8):
            raise Exception("JSONSchema can only handle maps with UTF8 keys")
        field_def['additionalProperties'] = self.get_type_definition(type_definition.type_parameters[1])
        return field_def

    def define_array(self, type_definition):
        field_def = copy.deepcopy(LIST_TEMPLATE)
        type_parameter_defs = [self.get_type_definition(t) for t in type_definition.type_parameters]
        field_def['items'] = type_parameters_def[0] if len(type_parameter_defs) == 0 else type_parameter_defs
        if isinstance(type_definition, types.Set):
            field_def['uniqueItems'] = True
        return field_def

    def get_dependencies_for_field_type(self, field_type, struct_dependencies):
        if isinstance(field_type, types.Struct):
            self.get_dependencies_for_one_struct(
                field_type.get_python_type(),
                struct_dependencies)
        if field_type.type_parameters:
            for type_parameter in field_type.type_parameters:
                self.get_dependencies_for_field_type(
                    type_parameter,
                    struct_dependencies)

    def get_dependencies_for_one_struct(self, cls, struct_dependencies=None):
        # It's possible that struct_class is actually an implementation class
        # In this case, we want the interface class
        struct_dependencies = struct_dependencies or set()
        struct_class = self.model_registry.lookup_interface(cls)
        if struct_class in struct_dependencies:
            # For recursive types, quit if type has already been encountered
            return struct_dependencies
        # recursively traverse the fields of the struct, looking for new
        # dependencies
        struct_dependencies.add(struct_class)
        if struct_class.get_field_definitions():
            for field in struct_class.get_field_definitions():
                self.get_dependencies_for_field_type(
                    field.field_type,
                    struct_dependencies)
        return struct_dependencies

    def get_schema_text(self, *args, **kwargs):
        return json.dumps(
            self.get_schema_ast(*args, **kwargs),
            sort_keys=True,
            indent=4,
            separators=(',', ': '))
