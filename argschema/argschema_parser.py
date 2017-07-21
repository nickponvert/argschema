'''Module that contains the base class ArgSchemaParser which should be
subclassed when using this library
'''
import json
import logging
import copy
from . import schemas
from . import utils
import marshmallow as mm


def contains_non_default_schemas(schema, schema_list=[]):
    """returns true if this schema contains a schema which was not an instance of DefaultSchema"""
    if not isinstance(schema, schemas.DefaultSchema):
        return True
    for k, v in schema.declared_fields.items():
        if isinstance(v, mm.fields.Nested):
            if type(v.schema) in schema_list:
                return False
            else:
                schema_list.append(type(v.schema))
                if contains_non_default_schemas(v.schema, schema_list):
                    return True
    return False


def is_recursive_schema(schema, schema_list=[]):
    """returns true if this schema contains recursive elements"""
    for k, v in schema.declared_fields.items():
        if isinstance(v, mm.fields.Nested):
            if type(v.schema) in schema_list:
                return True
            else:
                schema_list.append(type(v.schema))
                if is_recursive_schema(v.schema, schema_list):
                    return True
    return False


def fill_defaults(schema, args):
    defaults = []

    # find all of the schema entries with default values
    schemata = [(schema, [])]
    while schemata:
        subschema, path = schemata.pop()
        for k, v in subschema.declared_fields.items():
            if isinstance(v, mm.fields.Nested):
                schemata.append((v.schema, path + [k]))
            elif v.default != mm.missing:
                defaults.append((path + [k], v.default))

    # put the default entries into the args dictionary
    args = copy.deepcopy(args)
    for path, val in defaults:
        d = args
        for path_item in path[:-1]:
            d = d.setdefault(path_item, {})
        if path[-1] not in d:
            d[path[-1]] = val
    return args


class ArgSchemaParser(object):
    """ArgSchemaParser(input_data=None, schema_type = schemas.ArgSchema,
    args = None, logger_name = 'argschema')
    inputs)
        input data = None, dictionary parameters as option
            instead of --input_json
        args = None, a list of command line arguments passed to the module,
        otherwise argparse will fill this from the command line, set to
            [] if you want to bypass command line parsing
        logger_name = 'argschema', name of logger from the logging
            module you want to instantiate
    """

    def __init__(self,
                 input_data=None,  # dictionary input as option instead of --input_json
                 schema_type=schemas.ArgSchema,  # schema for parsing arguments
                 args=None,
                 logger_name=__name__):

        schema = schema_type()

        # convert schema to argparse object
        p = utils.schema_argparser(schema)
        argsobj = p.parse_args(args)
        argsdict = utils.args_to_dict(argsobj)

        if argsobj.input_json is not None:
            result = schema.load(argsdict)
            if 'input_json' in result.errors:
                raise mm.ValidationError(result.errors['input_json'])
            with open(result.data['input_json'], 'r') as j:
                jsonargs = json.load(j)
        else:
            jsonargs = input_data if input_data else {}

        self.logger = self.initialize_logger(logger_name,'WARNING')
        # merge the command line dictionary into the input json
        args = utils.smart_merge(jsonargs, argsdict)

        # validate with load!
        result = self.load_schema_with_defaults(schema, args)
        if len(result.errors) > 0:
            raise mm.ValidationError(json.dumps(result.errors, indent=2))

        self.schema_args = result
        self.args = result.data

        self.logger = self.initialize_logger(
            logger_name, self.args.get('log_level'))

    def load_schema_with_defaults(self  ,schema, args):
        """load_schema_with_defaults(schema, args)
        method for deserializing the arguments dictionary (args)
        given the schema (schema) making sure that the default values have
        been filled in.
        inputs)
            args: a dictionary of input arguments
            schema: a marshmallow.Schema schema specifiying the schema the
                input should fit
        outputs)
            a deserialized dictionary of the parameters converted
                through marshmallow
        """
        is_recursive = is_recursive_schema(schema)
        is_non_default = contains_non_default_schemas(schema)
        if (not is_recursive) and is_non_default:
            # throw a warning
            self.logger.warning("""DEPRECATED:You are using a Schema which contains 
            a Schema which is not subclassed from argschema.DefaultSchema, 
            default values will not work correctly in this case, 
            this use is deprecated, and future versions will not fill in default 
            values when you use non-DefaultSchema subclasses""")
            args = fill_defaults(schema, args)
        if is_recursive and is_non_default:
            raise mm.ValidationError(
                'Recursive schemas need to subclass argschema.DefaultSchema else defaults will not work')

        # load the dictionary via the schema
        result = schema.load(args)

        return result

    @staticmethod
    def initialize_logger(name, log_level):
        """initializes the logger to a level with a name
        logger = initialize_logger(name, log_level)
        inputs)
            name) name of the logger
            log_level) log level of the logger
        outputs)
            logger: a logging.Logger set with the name and level specified
        """
        level = logging.getLevelName(log_level)

        logging.basicConfig()
        logger = logging.getLogger(name)
        logger.setLevel(level=level)
        return logger

    def run(self):
        """standin run method to illustrate what the arguments are after
        validation and parsing should overwrite in your subclass
        run() prints the arguments using json.dumps
        """
        print("running! with args")
        print(self.args)
