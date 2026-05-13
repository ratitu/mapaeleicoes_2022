#!/usr/bin/env python3
"""Download the required parquet dataset from a remote URL."""

import os
import urllib.request
import sys

URL = "https://github.com/ratitu/mapaeleicoes_2022/releases/download/v1.0/resultado_votacao_2022.parquet"
DEST = os.path.join(os.path.dirname(__file__), "resultado_votacao_2022.parquet")


def download(url, dest):
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, dest)
    size_mb = os.path.getsize(dest) / 1e6
    print(f"Done: {size_mb:.1f} MB saved to {dest}")


if __name__ == "__main__":
    download(URL, DEST)
