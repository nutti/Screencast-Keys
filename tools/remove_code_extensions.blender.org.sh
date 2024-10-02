#!/usr/bin/env bash
# require: bash version >= 4
# usage example: bash remove_code_extensions.blender.org.sh src output
set -eEu


function usage() {
    echo "Usage: bash remove_code_extensions.blender.org.sh <source-directory> <output-directory>"
}

if [ $# -ne 2 ]; then
    usage
    exit 1
fi

SOURCE_DIR=${1}
OUTPUT_DIR=${2}
TMP_DIR=$(mktemp -d)

REMOVE_FILES=(
    "screencast_keys/utils/addon_updater.py"
    "screencast_keys/c_structure/.*.py"
)

mkdir -p "${OUTPUT_DIR}"

delete_block_start_regex="[^\S]*#[^\S]*extensions.blender.org: Delete block start"
delete_block_end_regex="[^\S]*#[^\S]*extensions.blender.org: Delete block end"
delete_line_regex="[^\S]*#[^\S]*extensions.blender.org: Delete line"
# shellcheck disable=SC2044
for file in $(find "${SOURCE_DIR}" -name "*.py" -or -name "*.glsl" -or -name "*.toml"); do
    in_dir_path=$(dirname "${file}")
    tmp_dir_path="${TMP_DIR}/${in_dir_path}"
    mkdir -p "${tmp_dir_path}"

    remove_file=0
    for f in "${REMOVE_FILES[@]}"; do
        if [[ "${file}" =~ $f ]]; then
            remove_file=1
        fi
    done
    if [ ${remove_file} -eq 1 ]; then
        echo "${file} is removed."
        continue
    fi

    enable_delete=0
    tmp_file_path="${TMP_DIR}/${file}"
    while IFS= read -r line || [ -n "${line}" ]; do
        # Delete by line.
        if [[ "${line}" =~ $delete_line_regex ]]; then
            continue
        fi

        # Delete by block.
        if [[ "${line}" =~ $delete_block_start_regex ]]; then
            enable_delete=1
            continue
        elif [[ "${line}" =~ $delete_block_end_regex ]]; then
            enable_delete=0
            continue
        fi
        if [[ ${enable_delete} -eq 1 ]]; then
            continue
        fi
 
        echo "${line}" >> "${tmp_file_path}"
    done < "${file}"

    echo "Remove code in ${file} >> ${tmp_file_path}"
done

# shellcheck disable=SC2044
for file in $(find "${TMP_DIR}" -name "*.py" -name "*.py" -or -name "*.glsl" -or -name "*.toml"); do
    out_file_path=${file/${TMP_DIR}/${OUTPUT_DIR}}

    out_dir_path=$(dirname "${out_file_path}")
    mkdir -p "${out_dir_path}"

    cp "${file}" "${out_file_path}"
    echo "Copy file ${file} -> ${out_file_path}"
done
