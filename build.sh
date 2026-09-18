#!/bin/bash
# Builds the C++ ticker matcher. SDK 27 has tbd files this linker can't parse.
set -e
SUFFIX=$(python -c 'import sysconfig;print(sysconfig.get_config_var("EXT_SUFFIX"))')
clang++ -O3 -Wall -shared -std=c++17 -fPIC -arch arm64 \
  -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX26.sdk \
  -undefined dynamic_lookup \
  $(python -m pybind11 --includes) \
  matcher/matcher.cpp -o "fastmatch${SUFFIX}"
echo "built fastmatch${SUFFIX}"
