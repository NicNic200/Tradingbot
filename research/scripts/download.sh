#!/usr/bin/env bash
# Download all archive files listed in data/urls.txt into data/raw/<market>/<kind>/... (missing months are simply skipped: 404)
set -u
cd "$(dirname "$0")/.."
dl() {
  url="$1"; rel="${url#https://data.binance.vision/data/}"; dest="data/raw/$rel"
  [ -s "$dest" ] && return 0
  mkdir -p "$(dirname "$dest")"
  for i in 1 2 3; do
    code=$(curl -s -w "%{http_code}" --max-time 60 -o "$dest.part" "$url")
    if [ "$code" = "200" ]; then mv "$dest.part" "$dest"; return 0; fi
    rm -f "$dest.part"; [ "$code" = "404" ] && { echo "404 $rel" >> data/missing.txt; return 0; }
    sleep $i
  done
  echo "FAIL $code $rel" >> data/failed.txt
}
export -f dl
: > data/missing.txt; : > data/failed.txt
xargs -P 24 -I{} bash -c 'dl "$@"' _ {} < data/urls.txt
echo "done: $(find data/raw -name '*.zip' | wc -l) zips, $(wc -l < data/missing.txt) missing, $(wc -l < data/failed.txt) failed"
