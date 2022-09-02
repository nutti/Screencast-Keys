#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: pylint.sh <target>"
    exit 1
fi

tgt=${1}

files=`find ${tgt} -name "*.py"`

# pylint
error=0
for file in ${files[@]}; do
    echo "======= pylint test "${file}" ======="
    pylint ${file}
    ret=`echo $?`
    if [ ${ret} -ne 0 ]; then
        ((error+=1))
    fi
done

if ((error > 0)); then
    echo "Error: ${error} files have errors."
    exit 1
fi

exit 0
