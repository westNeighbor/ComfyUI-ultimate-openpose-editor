#!/bin/bash
# build the code in openpose-editor before running this script

set -x
cd "$(dirname "$0")/.." || exit 1

rm -rf ./js/ui/*
cp -r ./openpose-editor/dist/assets ./js/ui
cp ./openpose-editor/dist/index.html ./js/ui/OpenposeEditor.html