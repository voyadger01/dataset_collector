#!/usr/bin/env bash
set -uo pipefail

APP_DIR="/app"
SRC_DIR="$APP_DIR/dataset_sources"
WORK_DIR="$APP_DIR/work"
OUT_DIR="$APP_DIR/output"

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR" "$OUT_DIR"

for lang in c cpp mixed; do
  LANG_DIR="$SRC_DIR/$lang"
  [ -d "$LANG_DIR" ] || continue

  for proj_path in "$LANG_DIR"/*/; do
    [ -d "$proj_path" ] || continue
    proj_name=$(basename "$proj_path")

    work_proj="$WORK_DIR/$proj_name"
    mkdir -p "$work_proj"
    cp -r "$proj_path"* "$work_proj/" 2>/dev/null || continue
    cd "$work_proj" || continue

    rm -rf build bin .git 2>/dev/null || true
    find . -name "*.o" -delete 2>/dev/null || true

    git submodule update --init --recursive 2>/dev/null || true

    build_ok=false
    if [ -f Makefile ]; then
      make -j"$(nproc)" >/dev/null 2>&1 && build_ok=true
    elif [ -f CMakeLists.txt ]; then
      cmake -B build -S . >/dev/null 2>&1 && cmake --build build >/dev/null 2>&1 && build_ok=true
    fi

    if [ "$build_ok" = false ]; then
      cd "$APP_DIR"
      continue
    fi

    out_proj="$OUT_DIR/$proj_name"
    mkdir -p "$out_proj"
    cp -r "$work_proj/"* "$out_proj/" 2>/dev/null || continue

    if [ ! -f "$out_proj/info.txt" ]; then
      build_type="auto"
      [ -f "$work_proj/Makefile" ] && build_type="make"
      [ -f "$work_proj/CMakeLists.txt" ] && build_type="cmake"

      cat > "$out_proj/info.txt" <<EOF
Name: $proj_name
Language: $lang
Build: $build_type
Output: auto
Description: Auto-compiled project
EOF
    fi

    cd "$APP_DIR"
  done
done