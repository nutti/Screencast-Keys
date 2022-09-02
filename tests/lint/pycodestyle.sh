#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: pycodestyle.sh <target>"
    exit 1
fi

tgt=${1}

files=`find ${tgt} -name "*.py"`

# pycodestyle
error=0
for file in ${files[@]}; do
    echo "======= pycodestyle test "${file}" ======="
    pycodestyle --config=.pycodestyle ${file}
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
