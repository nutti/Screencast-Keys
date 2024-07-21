#!/usr/bin/env bash
# require: bash version >= 4
# usage example: bash download_blender.sh 2.79 out
set -eEu

SUPPORTED_VERSIONS=(
    "2.78" "2.79" "2.80" "2.81" "2.82" "2.83"
    "2.90" "2.91" "2.92" "2.93"
    "3.0" "3.1" "3.2" "3.3" "3.4" "3.5" "3.6"
    "4.0" "4.1" "4.2"
)

declare -A BLENDER_DOWNLOAD_URL_LINUX_PATTERN=(
    ["v2.78"]="blender-2\\.78([a-z])-linux.*?\\.tar\\.bz2"
    ["v2.79"]="blender-2\\.79([a-z])-linux.*?\\.tar\\.bz2"
    ["v2.80"]="blender-2\\.80-linux.*?\\.tar\\.bz2"
    ["v2.81"]="blender-2\\.81([a-z])-linux.*?\\.tar\\.bz2"
    ["v2.82"]="blender-2\\.82([a-z])-linux.*?\\.tar\\.xz"
    ["v2.83"]="blender-2\\.83\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v2.90"]="blender-2\\.90\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v2.91"]="blender-2\\.91\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v2.92"]="blender-2\\.92\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v2.93"]="blender-2\\.93\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v3.0"]="blender-3\\.0\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v3.1"]="blender-3\\.1\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v3.2"]="blender-3\\.2\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v3.3"]="blender-3\\.3\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v3.4"]="blender-3\\.4\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v3.5"]="blender-3\\.5\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v3.6"]="blender-3\\.6\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v4.0"]="blender-4\\.0\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v4.1"]="blender-4\\.1\\.([0-9]+)-linux.*?\\.tar\\.xz"
    ["v4.2"]="blender-4\\.2\\.([0-9]+)-linux.*?\\.tar\\.xz"
)

declare -A BLENDER_CHECKSUM_URL_PATTERN=(
    ["v2.78"]="release278([a-z])\\.md5"
    ["v2.79"]="release279([a-z])\\.md5"
    ["v2.80"]="release280\\.md5"
    ["v2.81"]="release281([a-z])\\.md5"
    ["v2.82"]="release282([a-z])\\.md5"
    ["v2.83"]="blender-2\\.83\\.([0-9]+)\\.md5"
    ["v2.90"]="blender-2\\.90\\.([0-9]+)\\.md5"
    ["v2.91"]="blender-2\\.91\\.([0-9]+)\\.md5"
    ["v2.92"]="blender-2\\.92\\.([0-9]+)\\.md5"
    ["v2.93"]="blender-2\\.93\\.([0-9]+)\\.md5"
    ["v3.0"]="blender-3\\.0\\.([0-9]+)\\.md5"
    ["v3.1"]="blender-3\\.1\\.([0-9]+)\\.md5"
    ["v3.2"]="blender-3\\.2\\.([0-9]+)\\.md5"
    ["v3.3"]="blender-3\\.3\\.([0-9]+)\\.md5"
    ["v3.4"]="blender-3\\.4\\.([0-9]+)\\.md5"
    ["v3.5"]="blender-3\\.5\\.([0-9]+)\\.md5"
    ["v3.6"]="blender-3\\.6\\.([0-9]+)\\.md5"
    ["v4.0"]="blender-4\\.0\\.([0-9]+)\\.md5"
    ["v4.1"]="blender-4\\.1\\.([0-9]+)\\.md5"
    ["v4.2"]="blender-4\\.2\\.([0-9]+)\\.md5"
)

function get_extractor() {
    local file_extension=${1}
    local extractor=""

    if [ "${file_extension}" = "zip" ]; then
        extractor="unzip"
    elif [[ "${file_extension}" = "bz2" || "${file_extension}" = "xz" ]]; then
        extractor="tar xf"
    fi
    echo "${extractor}"
}

function verify_download_integrity() {
    local version=${1}
    local target_filepath=${2}
    local checksum_download_url=${3}

    if [ ! -f "${target_filepath}" ]; then
        return 1
    fi

    echo "Found Blender ${version} download. Verifying the integrity."

    local target_filename download_dir checksum_url checksum_filename
    target_filename="$(basename "${target_filepath}")"
    download_dir="$(dirname "${target_filepath}")"
    checksum_url="${checksum_download_url}"
    checksum_filename="$(basename "${checksum_url}")"

    pushd "${download_dir}" 1> /dev/null

    curl --location --fail -s "${checksum_url}" -o "${checksum_filename}"

    if ! grep -q "${target_filename}" "${checksum_filename}"; then
        echo "Error: Unable to find \"${target_filename}\" in \"${checksum_filename}\""
        cat "${checksum_filename}"
        return 1
    fi

    local checksum
    checksum="$(grep "${target_filename}" "${checksum_filename}")"

    md5sum --check --status <<< "${checksum}"
    local returncode=$?

    if [ $returncode -ne 0 ]; then
        echo "Checksum verification of Blender ${version} failed:"
        echo "  Expected: ${checksum}"
        echo "  Received: $(md5sum "${target_filename}")"
    else
        echo "Checksum of Blender ${version} verified."
    fi

    # if function had no critical errors, remove checksum file again.
    rm "${checksum_filename}"

    popd 1> /dev/null
    return ${returncode}
}

# download Blender binary
function download_blender() {
    ver=${1}
    blender_download_url=${2}
    checksum_download_url=${3}
    move_from=${4}

    local download_dir target
    download_dir="$(pwd)/downloads"
    target=blender-${ver}-bin

    local url file_extension filename filepath
    url=${blender_download_url}
    file_extension=${url##*.}
    filename="$(basename "${url}")"
    filepath="${download_dir}/${filename}"

    local extractor=""
    extractor=$(get_extractor "${file_extension}")
    if [ -z "${extractor}" ]; then
        echo "Error: Unknown file extension '${file_extension}'"
        exit 1
    fi

    # check if file already has been download and verify its signature
    if ! verify_download_integrity "${ver}" "${filepath}" "${checksum_download_url}";  then
        # create download folder
        mkdir -p "${download_dir}"

        # fetch file
        echo "Downloading Blender ${ver}: ${blender_download_url}"
        curl --location --fail -s "${url}" -o "${filepath}"

        # verify integrity of the download
        if ! verify_download_integrity "${ver}" "${filepath}" "${checksum_download_url}"; then
            echo "Error: Blender ${ver} download failed, please retry. If this happens again, please open a bug report."
            echo "  URL: ${url}"
            exit 1
        fi
    else
        echo "Found verified Blender ${ver} download: \"${filepath}\""
    fi

    local targetpath="${output_dir}/${target}"

    # cleanup existing files
    if [ -d "${targetpath}" ]; then
        echo "Removing old target folder \"${targetpath}\"."
        rm -r "${targetpath}"
    fi
    mkdir -p "${targetpath}"

    # change working directory
    pushd "${targetpath}" 1> /dev/null

    # extract file
    echo "Extracting Blender ${ver} using \"${extractor%% *}\"."
    ${extractor} "${filepath}"

    if [ ! "${move_from}" = "" ]; then
        echo "Moving downloaded Blender ${ver} files from \"${move_from}\" to \"${targetpath}\"."
        mv "${move_from}"/* .
    fi

    # go back to download folder
    popd 1> /dev/null
}

# check arguments
if [ $# -ne 2 ]; then
    echo "Usage: sh download_blender.sh <version> <output-dir>"
    exit 1
fi

version=${1}
output_dir=${2}

if [ -z "${output_dir}" ]; then
    echo "Error: <output-dir> cannot be empty. Use \".\" if you wannt to use the current folder."
    exit 1
fi

# check if the specified version is supported
supported=0
for v in "${SUPPORTED_VERSIONS[@]}"; do
    if [ "${v}" = "${version}" ]; then
        supported=1
    fi
done
if [ ${supported} -eq 0 ]; then
    echo "${version} is not supported."
    echo "Supported version is ${SUPPORTED_VERSIONS[*]}."
    exit 1
fi

ver="v${version}"
url="https://download.blender.org/release/Blender${version}/"

pattern=${BLENDER_DOWNLOAD_URL_LINUX_PATTERN["${ver}"]}
url_regex="s/.*?<a href=\"(${pattern})\">.+?<\\/a>.*/\\1/"
if [[ "${version}" =~ ^2.7[89]$ || "${version}" =~ ^2.8[0-2]$ ]]; then
    target_blender_file=$(curl -s -L "${url}" | grep -E "${pattern}" | grep -v "i686" | sed -r "${url_regex}" | sort | tail -n 1)
else
    target_blender_file=$(curl -s -L "${url}" | grep -E "${pattern}" | grep -v "i686" | sed -r "${url_regex}" | sort -n -t . -k 3 | tail -n 1)
fi
download_url="${url}${target_blender_file}"

pattern=${BLENDER_CHECKSUM_URL_PATTERN["${ver}"]}
url_regex="s/.*?<a href=\"(${pattern})\">.+?<\\/a>.*/\\1/"
if [[ "${version}" =~ ^2.7[89]$ || "${version}" =~ ^2.8[0-2]$ ]]; then
    target_checksum_file=$(curl -s -L "${url}" | grep -E "${pattern}" | sed -r "${url_regex}" | sort | tail -n 1)
else
    target_checksum_file=$(curl -s -L "${url}" | grep -E "${pattern}" | sed -r "${url_regex}" | sort -n -t . -k 3 | tail -n 1)
fi
checksum_url="${url}${target_checksum_file}"

move_from=$(basename "${target_blender_file}")
move_from=${move_from%.tar.xz}
move_from=${move_from%.tar.bz2}
download_blender "${ver}" "${download_url}" "${checksum_url}" "${move_from}"
