"""Fetch and convert the official BGE-M3 sparse head without Torch."""
import argparse
import hashlib
from pathlib import Path
import zipfile

from huggingface_hub import hf_hub_download
import mlx.core as mx
import numpy as np

REPO_ID = "BAAI/bge-m3"
REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SHA256 = "45c93804d2142b8f6d7ec6914ae23a1eee9c6a1d27d83d908a20d2afb3595ad9"
FILENAME = "sparse_linear.pt"


def read_head(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Unexpected sparse head checksum.")
    with zipfile.ZipFile(path) as archive:
        weight = np.frombuffer(archive.read("sparse_linear/data/0"), dtype="<f2")
        bias = np.frombuffer(archive.read("sparse_linear/data/1"), dtype="<f2")
    if weight.size != 1024 or bias.size != 1:
        raise ValueError("Unexpected sparse head shape.")
    return weight.reshape(1, 1024).astype(np.float32), bias.reshape(1).astype(np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="models/bge-m3-mlx-8bit")
    parser.add_argument("--pt", help="Use an existing sparse_linear.pt instead of downloading")
    args = parser.parse_args()
    source = Path(args.pt) if args.pt else Path(
        hf_hub_download(REPO_ID, FILENAME, revision=REVISION))
    weight, bias = read_head(source)
    target = Path(args.model_dir).expanduser() / "sparse_linear.safetensors"
    target.parent.mkdir(parents=True, exist_ok=True)
    mx.save_safetensors(str(target), {"weight": mx.array(weight), "bias": mx.array(bias)})
    print(f"Wrote {target} ({target.stat().st_size} bytes).")


if __name__ == "__main__":
    main()
