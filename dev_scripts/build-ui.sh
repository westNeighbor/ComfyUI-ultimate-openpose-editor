#!/bin/bash
# build the code in openpose-editor before running this script

set -x
cd "$(dirname "$0")/../openpose-editor" || exit 1
npm run build