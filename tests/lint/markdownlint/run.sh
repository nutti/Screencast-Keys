#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: run.sh <target>"
    exit 1
fi

readonly SCRIPT_DIR=$(cd $(dirname $0); pwd)
readonly MARKDOWN_DIRECTORY=${1}
readonly TMP_DIR=$(mktemp -d)
readonly MARKDOWN_CMD="markdownlint"

error=0
for file in `find ${MARKDOWN_DIRECTORY} -name "*.md" | sort`; do
    MARKDOWN_INPUT_FILE="${TMP_DIR}/${file}"
    mkdir -p $(dirname ${MARKDOWN_INPUT_FILE})

    SKIP_FILES=()

    skip=0
    for f in "${SKIP_FILES[@]}"; do
        if [[ ${file} =~ "${f}" ]]; then
            skip=1
        fi
    done
    if [ ${skip} -eq 1 ]; then
        echo "'${file}' was skipped."
        continue
    fi

    cat ${file} > ${MARKDOWN_INPUT_FILE}

    echo "======= markdownlint "${file}" ======="

    ${MARKDOWN_CMD} ${MARKDOWN_INPUT_FILE}
    if [ $? -ne 0 ]; then
        ((error+=1))
    fi

    rm -rf ${TMP_DIR}
done

if ((error > 0)); then
    echo "Error: ${error} files have errors."
    exit 1
fi

exit ${error}
