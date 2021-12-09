import os.path
import json


def open_json(path):
    if os.path.isfile(path):
        with open(path, 'r') as file:
            return json.load(file)
    else:
        return None


def save_json(path, json_object):
    if os.path.dirname(path) != '':
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as out:
        out.write(json.dumps(json_object))
        out.flush()


def get_path_in_dict(dictionary, path, separator="."):
    key_path = path.split(separator)
    value = dictionary
    for key_item in key_path:
        if value is not None and key_item in value:
            value = value[key_item]
        else:
            value = None
            break
    return value


def insert_path_in_dict(dictionary, path, value, append=True, separator="."):
    key_path = path.split(separator)
    sub_dir = dictionary
    for key_item in key_path[:-1]:
        if key_item not in sub_dir:
            new_dir = {}
            sub_dir[key_item] = new_dir
            sub_dir = new_dir
        else:
            sub_dir = sub_dir[key_item]

    last_key = key_path[-1]
    if append:
        sub_dir.setdefault(last_key, []).append(value)
    else:
        sub_dir[last_key] = value
    return dictionary


def extract_keys_in_dict(dictionary, dict_template):
    new_dict = {}
    for key in dict_template:
        new_dict[key] = get_path_in_dict(dictionary, dict_template[key])
    return new_dict
