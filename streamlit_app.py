import os
import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import pyarrow.parquet as pq
import geobr
import folium
from streamlit_folium import st_folium
from branca.colormap import LinearColormap

st.set_page_config(page_title="Geografia Eleitoral 2022", layout="wide")

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

@st.cache_data
def load_dicionario():
    df = pd.read_csv(
        os.path.join(DATA_DIR, "municipio_tse_ibge.csv"),
        sep=";",
        encoding="ISO-8859-1",
        dtype={"CD_MUNICIPIO_IBGE": str, "CD_MUNICIPIO_TSE": str},
    )
    return df[["CD_MUNICIPIO_IBGE", "CD_MUNICIPIO_TSE"]]

@st.cache_data
def load_votos():
    cols = ["ANO_ELEICAO", "NR_TURNO", "CD_CARGO", "NR_CANDIDATO", "CD_MUNICIPIO", "QT_VOTOS_NOMINAIS"]
    df = (
        pq.read_table(os.path.join(DATA_DIR, "resultado_votacao_2022.parquet"), columns=cols)
        .to_pandas()
    )
    mask = (
        (df["ANO_ELEICAO"] == 2022)
        & (df["NR_TURNO"] == 2)
        & (df["CD_CARGO"] == 1)
        & (df["NR_CANDIDATO"].isin([13, 22]))
    )
    df = df[mask]
    agg = (
        df.groupby(["CD_MUNICIPIO", "NR_CANDIDATO"], as_index=False)["QT_VOTOS_NOMINAIS"]
        .sum()
    )
    agg["CD_MUNICIPIO"] = agg["CD_MUNICIPIO"].astype(str)
    return agg

@st.cache_data
def process_data(votos_agg, dicionario):
    dic = dicionario.drop_duplicates(subset="CD_MUNICIPIO_TSE")
    merged = votos_agg.merge(
        dic,
        left_on="CD_MUNICIPIO",
        right_on="CD_MUNICIPIO_TSE",
        how="left",
    )
    pivoted = (
        merged.groupby(["CD_MUNICIPIO_IBGE", "NR_CANDIDATO"], as_index=False)["QT_VOTOS_NOMINAIS"]
        .sum()
        .pivot(index="CD_MUNICIPIO_IBGE", columns="NR_CANDIDATO", values="QT_VOTOS_NOMINAIS")
        .reset_index()
    )
    pivoted.columns = ["CD_MUNICIPIO_IBGE", "cand_13", "cand_22"]
    pivoted = pivoted.dropna(subset=["cand_13", "cand_22"])
    total = pivoted["cand_13"] + pivoted["cand_22"]
    pivoted["dominancia"] = ((pivoted["cand_22"] - pivoted["cand_13"]) / total) * 100
    pivoted["vencedor"] = np.where(pivoted["cand_13"] > pivoted["cand_22"], "LULA", "BOLSONARO")
    pivoted["pct_lula"] = (pivoted["cand_13"] / total) * 100
    pivoted["pct_bolsonaro"] = (pivoted["cand_22"] / total) * 100
    return pivoted

@st.cache_data
def load_municipios():
    mun = geobr.read_municipality(year=2020)
    mun["code_muni"] = mun["code_muni"].astype(str)
    return mun

@st.cache_data
def load_estados():
    estados = geobr.read_state(year=2020)
    centros = estados.geometry.centroid
    estados["centroide_x"] = centros.x
    estados["centroide_y"] = centros.y
    return estados

@st.cache_data
def build_mapa_final(_mun_map, data):
    return mun_map.merge(data, left_on="code_muni", right_on="CD_MUNICIPIO_IBGE", how="left")


st.title("🗳️ Geografia Eleitoral 2022")
st.markdown("Vantagem de Bolsonaro vs Lula no 2º turno por município")

progress_bar = st.sidebar.progress(0, text="Inicializando...")

votos_agg = load_votos()
progress_bar.progress(20, text="Carregando dados de votação...")
st.sidebar.success(f"✓ {len(votos_agg):,} registros de votos carregados")

dicionario = load_dicionario()
progress_bar.progress(40, text="Carregando dicionário de municípios...")
st.sidebar.success(f"✓ {len(dicionario):,} municípios no dicionário")

data = process_data(votos_agg, dicionario)
progress_bar.progress(60, text="Processando dados eleitorais...")
st.sidebar.success(f"✓ {len(data):,} municípios processados")

mun_map = load_municipios()
estados = load_estados()
progress_bar.progress(80, text="Carregando malhas geográficas...")
st.sidebar.success(f"✓ {len(mun_map):,} municípios e {len(estados):,} estados carregados")

mapa_final = build_mapa_final(mun_map, data)
progress_bar.progress(100, text="Montando mapa final...")
progress_bar.empty()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Municípios com dados", f"{data['CD_MUNICIPIO_IBGE'].nunique():,}")
col2.metric("Vitórias Lula", f"{(data['vencedor'] == 'LULA').sum():,}")
col3.metric("Vitórias Bolsonaro", f"{(data['vencedor'] == 'BOLSONARO').sum():,}")
col4.metric("Dominância média", f"{data['dominancia'].mean():.1f} pp")

br_map = mapa_final.to_crs(epsg=4326)

dominancia = br_map["dominancia"]
vmin, vmax = -60, 60
clamp = dominancia.clip(lower=vmin, upper=vmax)

colormap = LinearColormap(
    colors=["#8B0000", "#f7f7f7", "#00008B"],
    vmin=vmin, vmax=vmax,
    caption="Vantagem (pp)",
)

m = folium.Map(location=[-14, -55], zoom_start=4, tiles="CartoDB positron", control_scale=True)

style_fn = lambda x: {
    "fillColor": colormap(clamp.get(x["properties"]["CD_MUNICIPIO_IBGE"], 0))
    if x["properties"]["CD_MUNICIPIO_IBGE"] in clamp.index and pd.notna(x["properties"]["dominancia"])
    else "#cccccc",
    "color": "white",
    "weight": 0.3,
    "fillOpacity": 0.85,
}

tooltip = folium.GeoJsonTooltip(
    fields=["name_muni", "cand_13", "cand_22", "dominancia", "vencedor"],
    aliases=["Município", "Votos Lula", "Votos Bolsonaro", "Vantagem (pp)", "Vencedor"],
    localize=True,
    style="font-size: 12px;",
)

gj = folium.GeoJson(
    br_map,
    style_function=style_fn,
    tooltip=tooltip,
    name="Municípios",
).add_to(m)

folium.GeoJson(
    estados.geometry,
    style_function=lambda x: {
        "fillColor": "transparent",
        "color": "grey30",
        "weight": 1.2,
    },
    name="Estados",
).add_to(m)

for _, row in estados.iterrows():
    folium.map.Marker(
        location=[row["centroide_y"], row["centroide_x"]],
        icon=folium.DivIcon(
            icon_size=(0, 0),
            icon_anchor=(0, 0),
            html=f'<div style="font-size: 10pt; font-weight: bold; color: #333; text-shadow: -1px -1px 0 white, 1px -1px 0 white, -1px 1px 0 white, 1px 1px 0 white;">{row["abbrev_state"]}</div>',
        ),
    ).add_to(m)

colormap.add_to(m)

folium.LayerControl().add_to(m)

st_folium(m, width=None, height=600)

with st.expander("Ver tabela de dados"):
    st.dataframe(
        data.sort_values("dominancia", ascending=False)
        .head(50)
        .style.format({
            "cand_13": "{:,.0f}", "cand_22": "{:,.0f}",
            "dominancia": "{:.1f}", "pct_lula": "{:.1f}%", "pct_bolsonaro": "{:.1f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )
