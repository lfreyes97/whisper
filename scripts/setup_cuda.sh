#!/usr/bin/env bash
set -euo pipefail

VENV="$(dirname "$(dirname "$(readlink -f "$0")")")/.venv"
CTLIB="$VENV/lib/python3.12/site-packages/ctranslate2.libs"
NVIDIA="$VENV/lib/python3.12/site-packages/nvidia"

if [ ! -d "$CTLIB" ]; then
  echo "No se encontró ctranslate2.libs. Ejecuta primero: uv sync"
  exit 1
fi

for f in \
  cublas/lib/libcublas.so.12 \
  cublas/lib/libcublasLt.so.12 \
  cudnn/lib/libcudnn.so.9 \
  cudnn/lib/libcudnn_adv_infer.so.9 \
  cudnn/lib/libcudnn_adv_train.so.9 \
  cudnn/lib/libcudnn_cnn.so.9 \
  cudnn/lib/libcudnn_cnn_infer.so.9 \
  cudnn/lib/libcudnn_cnn_train.so.9 \
  cudnn/lib/libcudnn_engines_precompiled.so.9 \
  cudnn/lib/libcudnn_engines_runtime_compiled.so.9 \
  cudnn/lib/libcudnn_graph.so.9 \
  cudnn/lib/libcudnn_heuristic.so.9 \
  cudnn/lib/libcudnn_ops_infer.so.9 \
  cudnn/lib/libcudnn_ops_train.so.9; do
  ln -sf "$NVIDIA/$f" "$CTLIB/$(basename "$f")"
done

echo "Symlinks CUDA creados en $CTLIB"
