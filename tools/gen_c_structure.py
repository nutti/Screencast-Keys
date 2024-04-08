##############################################################################
# gen_c_structure.py
#
# Description:
#   gen_c_structure.py generates struct/enum definitions from the Blender C
#   source code to access the internal structure via ctypes module.
#
# Note:
#   This script requires the network access to Blender's GitHub repository.
#
# Usage:
#   python gen_c_structure.py -o <output-file> -t <target>
#
#     output-file:
#       Output file path.
#     target:
#       Target branch/tag to generates the definition file.
#       (ex. v3.0.0 -> Version 3.0.0, main -> Latest)
##############################################################################

import re
import sys
import argparse
import requests

SOURCE_BASE_URL = "https://raw.githubusercontent.com/blender/blender/"


def write_import(file):
    body = '''from ctypes import (
    c_void_p, c_char, c_short, c_int, c_int8, c_uint64,
    addressof, cast, pointer,
    Structure,
    POINTER,
)
'''

    print(f"{body}\n", file=file)


def parse_struct_variables(code_body):
    lines = code_body.split("\n")
    variables = []
    for line in lines:
        line = re.sub(r"^\s*const ", "", line)  # Remove const specifier.
        m = re.search(r"^\s*(enum\s+|struct\s+)*([a-zA-Z_][a-zA-Z0-9_]*)\s+"
                      r"([a-zA-Z0-9_\[\],\s*]*?)(\s+DNA_DEPRECATED)*;", line)
        if m:
            var_names = m.group(3).split(",")
            for name in var_names:
                name = name.strip()

                var = {}
                var["is_pointer"] = name.startswith("*")
                var["type"] = m.group(2)

                name = name[1:] if var["is_pointer"] else name
                m2 = re.search(r"^([a-zA-Z0-9_]+)(\[([0-9]+)\])*$", name)
                if not m2:
                    raise Exception(f"Unexpected line: {line}")
                var["name"] = m2.group(1)
                if m2.group(2):
                    var["array_element_num"] = int(m2.group(3))
                else:
                    var["array_element_num"] = None
                variables.append(var)

    return variables


def parse_enum_items(code_body):
    lines = code_body.split("\n")
    items = []
    value = 0
    for line in lines:
        m = re.search(r"^\s*([A-Z_]+)\s*(=*)\s*([0-9]*),", line)
        if m:
            item = {}
            item["name"] = m.group(1)
            if m.group(2) == "=":
                item["value"] = int(m.group(3))
                value = item["value"] + 1
            else:
                item["value"] = value
                value += 1
            items.append(item)

    return items


def type_to_ctype(type_, is_pointer):
    known_struct = (
        "Link",
        "ListBase",
        "ScrAreaMap",
        "wmWindow",
        "wmOperator",
        "wmEventHandler",
    )
    known_enum = (
        "eWM_EventHandlerType",
        "eWM_EventHandlerFlag",
    )
    known_func = (
        "EventHandlerPoll",
    )
    builtin_types = (
        "void",
        "char",
        "short",
        "int",
        "int8",
    )
    builtin_types_with_t = (
        "uint64_t",
    )

    if type_ in known_struct:
        if is_pointer:
            return True, f"POINTER({type_})"
        return True, type_
    if type_ in known_enum:
        return False, "c_int8"
    if type_ in known_func:
        return False, "c_void_p"
    if type_ in builtin_types:
        if is_pointer:
            return True, f"c_{type_}_p"
        return True, f"c_{type_}"
    if type_ in builtin_types_with_t:
        return True, f"c_{type_[:-2]}"

    assert is_pointer
    return False, "c_void_p"


def parse_struct(target, source_file_path, struct_name):
    url = f"{SOURCE_BASE_URL}/{target}/{source_file_path}"
    response = requests.get(url)
    response.raise_for_status()

    code_body = response.text
    lines = code_body.split("\n")
    in_struct = False
    struct_code_body = ""
    for line in lines:
        if not in_struct:
            m = re.search(r"struct\s+" + struct_name + r"\s+{$", line)
            if m:
                in_struct = True
        else:
            struct_code_body += line + "\n"
            m = re.search("^}", line)
            if m:
                break
    else:
        raise Exception(f"Struct {struct_name} is not found.")

    variables = parse_struct_variables(struct_code_body)

    return struct_name, variables


def write_struct(file, source_file_path, struct_name, variables,
                 add_method_func, add_variable_func, *, last=False):
    def print_variable(file, var):
        known_type, type_name = type_to_ctype(var["type"], var["is_pointer"])
        if var["array_element_num"]:
            type_name = f'{type_name} * {var["array_element_num"]}'
        if known_type:
            print(f'    ("{var["name"]}", {type_name}),', file=file)
        else:
            print(f'    # {var["type"]}', file=file)
            print(f'    ("{var["name"]}", {type_name}),', file=file)

    print("# pylint: disable=W0201", file=file)
    print(f"class {struct_name}(Structure):", file=file)
    print(f'    """Defined in ${source_file_path}"""', file=file)
    if callable(add_method_func):
        print(add_method_func(), file=file)
    print("\n", file=file)
    print("# pylint: disable=W0212", file=file)
    print(f"{struct_name}._fields_ = [", file=file)
    for var in variables:
        print_variable(file, var)
    if callable(add_variable_func):
        variables_to_add = add_variable_func()
        for var in variables_to_add:
            print_variable(file, var)
    print("]", file=file)
    if not last:
        print("\n", file=file)


def write_enum(file, source_file_path, enum_name, items):
    print("# pylint: disable=C0103", file=file)
    print(f"class {enum_name}:", file=file)
    print(f'    """Defined in ${source_file_path}"""\n', file=file)
    for item in items:
        print(f'    {item["name"]} = {item["value"]}', file=file)
    print("\n", file=file)


def parse_enum(target, source_file_path, enum_name):
    url = f"{SOURCE_BASE_URL}/{target}/{source_file_path}"
    response = requests.get(url)
    response.raise_for_status()

    code_body = response.text
    lines = code_body.split("\n")
    in_enum = False
    enum_code_body = ""
    for line in lines:
        if not in_enum:
            m = re.search(r"enum\s+" + enum_name + r"\s+{$", line)
            if m:
                in_enum = True
        else:
            enum_code_body += line + "\n"
            m = re.search("^}", line)
            if m:
                break
    else:
        raise Exception(f"Enumerator {enum_name} is not found.")

    items = parse_enum_items(enum_code_body)

    return enum_name, items


# pylint: disable=C0103
def add_method_for_ListBase():
    body = '''
    def remove(self, vlink):
        """Ref: BLI_remlink"""

        link = vlink
        if not vlink:
            return

        if link.next:
            link.next.contents.prev = link.prev
        if link.prev:
            link.prev.contents.next = link.next

        if self.last == addressof(link):
            self.last = cast(link.prev, c_void_p)
        if self.first == addressof(link):
            self.first = cast(link.next, c_void_p)

    def find(self, number):
        """Ref: BLI_findlink"""

        link = None
        if number >= 0:
            link = cast(c_void_p(self.first), POINTER(Link))
            while link and number != 0:
                number -= 1
                link = link.contents.next
        return link.contents if link else None

    def insert_after(self, vprevlink, vnewlink):
        """Ref: BLI_insertlinkafter"""

        prevlink = vprevlink
        newlink = vnewlink

        if not newlink:
            return

        def gen_ptr(link):
            if isinstance(link, (int, type(None))):
                return cast(c_void_p(link), POINTER(Link))
            else:
                return pointer(link)

        if not self.first:
            self.first = self.last = addressof(newlink)
            return

        if not prevlink:
            newlink.prev = None
            newlink.next = gen_ptr(self.first)
            newlink.next.contents.prev = gen_ptr(newlink)
            self.first = addressof(newlink)
            return

        if self.last == addressof(prevlink):
            self.last = addressof(newlink)

        newlink.next = prevlink.next
        newlink.prev = gen_ptr(prevlink)
        prevlink.next = gen_ptr(newlink)
        if newlink.next:
            newlink.next.prev = gen_ptr(newlink)'''

    return body


# pylint: disable=C0103
def add_variable_for_wmEventHandler():
    variables = [
        {
            "name": "op",
            "type": "wmOperator",
            "is_pointer": True,
            "array_element_num": None,
        },
    ]

    return variables


def parse_argument():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", nargs="?",
                        type=argparse.FileType("w"), default=sys.stdout)
    parser.add_argument("-t", "--target", nargs="?", type=str, default="main")

    args = parser.parse_args()
    return args


def compare_version(target, ref):
    if target[0] != "v" or ref[0] != "v":
        raise ValueError(f"Version must start from 'v' "
                         f"(target: {target}, ref: {ref})")

    if target == ref:
        return 0

    s = sorted([target, ref])
    if s[0] == target:
        return -1
    return 1


def main():
    args = parse_argument()

    output_file = args.output
    target = args.target

    gen_info = [
        [
            "enum",
            "source/blender/windowmanager/wm_event_system.h",
            "eWM_EventHandlerType"
        ],

        [
            "struct",
            "source/blender/makesdna/DNA_listBase.h",
            "Link",
            None,
            None
        ],
        [
            "struct",
            "source/blender/makesdna/DNA_listBase.h",
            "ListBase",
            add_method_for_ListBase,
            None
        ],
        [
            "struct",
            "source/blender/makesdna/DNA_screen_types.h",
            "ScrAreaMap",
            None,
            None
        ],
        [
            "struct",
            "source/blender/makesdna/DNA_windowmanager_types.h",
            "wmWindow",
            None,
            None
        ],
        [
            "struct",
            "source/blender/makesdna/DNA_windowmanager_types.h",
            "wmOperator",
            None,
            None
        ],
        [
            "struct",
            "source/blender/windowmanager/wm_event_system.h",
            "wmEventHandler",
            None,
            add_variable_for_wmEventHandler
        ],
    ]

    # From v4.1.0, the extension of some header files is ".hh".
    if compare_version(target, "v4.1.0") >= 0:
        for info in gen_info:
            if info[2] in ("wmEventHandler", "eWM_EventHandlerType"):
                info[1] += "h"

    # Parse struct/enum.
    struct_info = []
    enum_info = []
    for info in gen_info:
        if info[0] == "enum":
            enum_name, items = parse_enum(target, info[1], info[2])
            enum_info.append({
                "file": output_file,
                "source_file_path": info[1],
                "enum_name": enum_name,
                "items": items,
            })
        elif info[0] == "struct":
            struct_name, variables = parse_struct(target, info[1], info[2])
            struct_info.append({
                "file": output_file,
                "source_file_path": info[1],
                "struct_name": struct_name,
                "variables": variables,
                "add_method_func": info[3],
                "add_variable_func": info[4],
            })

    # Write file.
    write_import(output_file)
    for enum in enum_info:
        write_enum(**enum)
    for index, struct in enumerate(struct_info):
        last = index == (len(struct_info) - 1)
        write_struct(**struct, last=last)


if __name__ == "__main__":
    main()
