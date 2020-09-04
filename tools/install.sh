#!/bin/sh

if [ $# -ne 2 ]; then
    echo "Usage: tools/install.sh <os> <version>"
    exit 1
fi

os=${1}
version=${2}
target=""

if [ ${os} = "mac" ]; then
    target="${HOME}/Library/Application Support/Blender/${version}/scripts/addons/screencast_keys"
elif [ ${os} = "linux" ]; then
    target="${HOME}/.config/blender/${version}/scripts/addons/screencast_keys"
else
    echo "Invalid operating system."
    exit 1
fi

rm -rf "${target}"
cp -r src/screencast_keys "${target}"
