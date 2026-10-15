"""새 typed carrier의 직렬화 필드를 그대로 소비한다. 원형 strict 비교기는 변경하지 않는다."""
from dataclasses import fields, is_dataclass
import typing
from . import record_role_types as T
from .record_role_transport import validate_declared_shape, encode

def decode(annotation, value, pointer):
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin is typing.Union:
        if value is None and type(None) in args:
            return None
        choices = [a for a in args if a is not type(None)]
        if len(choices) != 1:
            raise TypeError('unsupported union at ' + pointer)
        return decode(choices[0], value, pointer)
    if origin is tuple:
        if type(value) is not list:
            raise TypeError('serialized tuple array at ' + pointer)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(decode(args[0], v, pointer + '/' + str(i)) for i, v in enumerate(value))
        if len(value) != len(args):
            raise ValueError('fixed tuple length at ' + pointer)
        return tuple(decode(a, v, pointer + '/' + str(i)) for i, (a, v) in enumerate(zip(args, value)))
    if isinstance(annotation, type) and is_dataclass(annotation):
        if type(value) is not dict:
            raise TypeError('serialized typed object at ' + pointer)
        names = tuple(f.name for f in fields(annotation))
        missing, extras = set(names) - value.keys(), value.keys() - set(names)
        if missing or extras:
            raise ValueError('required/extras at ' + pointer + ': missing=' + repr(sorted(missing)) + '; extras=' + repr(sorted(extras)))
        hints = typing.get_type_hints(annotation)
        return annotation(**{name: decode(hints[name], value[name], pointer + '/' + name) for name in names})
    if type(value) is not annotation:
        raise TypeError('annotation value at ' + pointer)
    return value

def leaf_copies(value, pointer, artifact_sha256):
    proofs = []
    if type(value) is dict:
        for key, item in value.items():
            escaped = key.replace('~', '~0').replace('/', '~1')
            proofs.extend(leaf_copies(item, pointer + '/' + escaped, artifact_sha256))
    elif type(value) is list:
        for index, item in enumerate(value):
            proofs.extend(leaf_copies(item, pointer + '/' + str(index), artifact_sha256))
    else:
        proofs.append({'operation': 'copy', 'pointer': pointer, 'value': value,
            'actual_type': type(value).__name__, 'artifact_sha256': artifact_sha256})
    return proofs

def normalize_record_roles(serialized_relation, artifact_sha256, prefix='/relation'):
    if type(serialized_relation) is not dict:
        return {'status': 'UNSUPPORTED', 'reason': 'relation mapping absent', 'required_joint': False}
    if 'record_role_provenance' not in serialized_relation:
        return {'status': 'NOT_OBSERVED', 'reason': 'carrier_key_missing', 'key_present': False, 'required_joint': False}
    raw = serialized_relation['record_role_provenance']
    if raw is None:
        return {'status': 'NOT_OBSERVED', 'reason': 'carrier_key_present_null', 'key_present': True, 'raw_value': None, 'required_joint': False}
    if type(raw) is not list:
        return {'status': 'UNSUPPORTED', 'reason': 'carrier_array_annotation', 'raw_value': raw, 'required_joint': False}
    results = []
    for index, value in enumerate(raw):
        pointer = prefix + '/record_role_provenance/' + str(index)
        try:
            carrier = decode(T.RecordRoleProvenanceDraft, value, pointer)
            validate_declared_shape(carrier)
            if encode(carrier) != value:
                raise ValueError('all typed fields changed on decode/re-encode')
            results.append({'status': 'SERIALIZED_CARRIER_COPIED', 'record_reference': value['record_reference'],
                'typed_value': carrier, 'raw_value': value, 'record_pointer': pointer,
                'all_leaf_copy_proofs': leaf_copies(value, pointer, artifact_sha256),
                'semantic_status': 'NOT_OBSERVED', 'required_joint': False,
                'reason': 'source/record edges and applicability authority require independent producer evidence'})
        except (TypeError, ValueError) as error:
            results.append({'status': 'PROVENANCE_FAILURE', 'raw_value': value, 'record_pointer': pointer,
                'reason': str(error), 'required_joint': False})
    return {'status': 'CARRIER_ARRAY_CONSUMED', 'records': results, 'count': len(results),
        'empty_array_is_semantic_PASS': False, 'all_extras_and_null_values_retained_in_raw': True,
        'artifact_sha_binding': 'CALLER_SUPPLIED_NOT_VERIFIED_HERE', 'required_joint': False,
        'original_strict_comparator_replaced': False, 'field_values_from_gold': False}
