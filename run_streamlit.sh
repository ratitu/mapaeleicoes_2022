#!/bin/bash
export LD_PRELOAD=/home/ratitu/miniconda3/envs/qgis_env/lib/libstdc++.so.6
exec streamlit run streamlit_app.py "$@"
