"""
Dashboard Monitoring dan Simulasi Ekonomi Nasional - DJSEF Kemenkeu
Tampilan mengikuti Dashboard_Simulasi_DJSEF_Kemenkeu_v6.html
Jalankan: streamlit run app_tab_menu.py   (butuh streamlit >= 1.40)
"""
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.request import Request, urlopen
from urllib.parse import quote_plus, urlparse
import difflib
import html
import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
import math
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Dashboard Ekonomi Nasional - Kementerian Keuangan RI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================
# Konfigurasi umum
# =========================
TAHUN = 2026                 # tahun analisis (outlook / simulasi)
JUMLAH_Q_REALISASI = 2       # Q1 dan Q2 sudah realisasi, Q3-Q4 proyeksi

# Nama file yang dicari di root repo (dua varian: spasi atau underscore)
PDB_FILE_CANDIDATES = ["dashboard PDB.xlsx", "dashboard_PDB.xlsx"]
INDICATOR_FILE_CANDIDATES = ["dashboard indikator.xlsx", "dashboard_indikator.xlsx"]
TRIWULAN_FILE_CANDIDATES = [
    "Database_Dashboard_triwulanan.xlsx", "Database Dashboard triwulanan.xlsx",
    "database_dashboard_triwulanan.xlsx", "database dashboard triwulanan.xlsx",
]
try:
    GITHUB_RAW_XLSX_URL = st.secrets.get("github_raw_xlsx_url", "")
except Exception:
    GITHUB_RAW_XLSX_URL = ""

# Palet warna (sama dengan variabel CSS di HTML)
C_PRIMARY = "#1A3A6B"
C_PRIMARY_LIGHT = "#2B5AA8"
C_ACCENT = "#E8A020"
C_GREEN = "#1A8A4A"
C_RED = "#C0392B"
C_ORANGE = "#D4700A"
C_TEAL = "#0891B2"
C_PURPLE = "#7C3AED"
C_TEXT3 = "#8898AA"
C_GRID = "#EEF1F6"

PERIOD_MAP = {
    "out_tw1": "Q1",
    "out_tw2": "Q2",
    "out_tw3": "Q3",
    "out_tw4": "Q4",
    "full_year": "Full Year",
}
PERIOD_ORDER = list(PERIOD_MAP.keys())

SIMULASI_FISKAL_ROWS = [
    "Bantuan Pangan",
    "Bantuan Langsung Tunai",
    "Kenaikan Gaji",
    "Pembayaran Gaji 14",
    "Diskon Transportasi",
    "Investasi",
]
SIMULASI_FISKAL_COLS = ["out_tw1", "out_tw2", "out_tw3", "out_tw4"]

SIMULASI_MAKRO_DEFAULTS = [
    ("Pertumbuhan ekonomi (%)", 5.4),
    ("Inflasi (%)", 2.5),
    ("Tingkat bunga SUN 10 tahun", 6.9),
    ("Nilai tukar (Rp100/US$1)", 16500.0),
    ("Harga minyak (US$/barel)", 70.0),
    ("Lifting minyak (ribu barel per hari)", 610.0),
    ("Lifting Gas Bumi (ribu barel setara minyak per hari)", 984.0),
]

SIMULASI_MAKRO_LABEL_PENDEK = [
    "Pertumbuhan ekonomi (%)",
    "Inflasi (%)",
    "Bunga SUN 10 tahun (%)",
    "Nilai tukar (Rp/US$)",
    "Harga minyak (US$/barel)",
    "Lifting minyak (ribu bph)",
    "Lifting gas (ribu BOEPD)",
]

PDB_COMPONENTS = [
    "Konsumsi RT",
    "Konsumsi LNPRT",
    "PKP",
    "PMTB",
    "Change in Stocks",
    "Ekspor",
    "Impor",
    "PDB Aggregate",
]
PDB_MAIN_ROWS = ["Konsumsi RT", "PKP", "PMTB", "Ekspor", "Impor", "PDB Aggregate"]
EXCLUDE_GROWTH_ROWS = ["Change in Stocks"]
DEFAULT_ROWS = {"pdb": PDB_COMPONENTS}

# APBN 2026 (miliar rupiah) untuk halaman Sensitivitas APBN
APBN_BASE = {"pp": 2693714, "pnbp": 459200, "hibah": 666, "bpp": 3149733, "tkd": 692995}
APBN_DEFISIT_PDB_PCT = -2.68  # defisit APBN 2026 terhadap PDB (%), dipakai menurunkan PDB nominal
BULAN_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

# =========================
# CSS (diterjemahkan dari HTML referensi)
# =========================
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
:root{
  --bg:#F5F7FA; --surface:#FFFFFF; --surface2:#EEF1F6; --border:#DDE2EC;
  --text:#0F1C35; --text2:#4A5568; --text3:#8898AA;
  --primary:#1A3A6B; --primary-light:#2B5AA8; --accent:#E8A020;
  --green:#1A8A4A; --green-bg:#E8F7EE; --red:#C0392B; --red-bg:#FDECEA;
  --orange:#D4700A; --orange-bg:#FEF3E2; --blue-bg:#EBF2FF;
  --shadow:0 1px 3px rgba(15,28,53,.08),0 4px 12px rgba(15,28,53,.04);
  --shadow-md:0 4px 16px rgba(15,28,53,.10),0 1px 4px rgba(15,28,53,.06);
  --radius:10px; --radius-sm:6px;
}
html, body, .stApp, [class*="st-"], button, input, textarea, select{font-family:'Inter',sans-serif;}
.stApp{background:var(--bg); color:var(--text);}

/* Header bawaan Streamlit disembunyikan, diganti topnav */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
[data-testid="stExpandSidebarButton"], header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"]{display:none !important;}
#MainMenu, footer{visibility:hidden;}
.block-container{padding:124px 24px 40px 24px !important; max-width:none !important;}

/* TOPNAV */
.topnav{height:60px;background:var(--primary);display:flex;align-items:center;padding:0 24px;gap:16px;
  position:fixed;top:0;left:0;right:0;z-index:999990;box-shadow:0 2px 8px rgba(0,0,0,.18);}
.logo-area{display:flex;align-items:center;gap:12px;min-width:240px;}
.logo-box{display:flex;align-items:center;flex-shrink:0;}
.logo-box img{height:42px;width:auto;display:block;}
.logo-text{display:flex;flex-direction:column;}
.logo-text span:first-child{font-size:10px;color:#AFC6E9;font-weight:500;letter-spacing:.5px;text-transform:uppercase;}
.logo-text span:last-child{font-size:12px;color:#fff;font-weight:700;line-height:1.2;}
.topnav-title{flex:1;display:flex;align-items:center;justify-content:center;gap:10px;color:#fff;font-size:15px;font-weight:700;letter-spacing:.3px;}
.topnav-title img{height:28px;width:auto;display:block;}
.topnav-spacer{min-width:240px;}

/* MENU HORIZONTAL (tepat di bawah topnav, selalu terlihat) */
.st-key-navbar{position:fixed !important;top:60px;left:0;right:0;width:100% !important;z-index:999989;
  background:var(--surface);border-bottom:1px solid var(--border);box-shadow:0 2px 6px rgba(15,28,53,.06);padding:0 24px;}
.st-key-navbar [data-testid="stVerticalBlock"]{gap:0 !important;}
.st-key-navbar [data-testid="stHorizontalBlock"]{gap:2px !important;align-items:flex-end;}
.st-key-navbar .stButton > button{width:100%;border-radius:0;background:transparent !important;color:var(--text2) !important;
  border:none;border-bottom:3px solid transparent;padding:13px 10px 10px;font-size:13px;font-weight:600;white-space:nowrap;
  justify-content:center;}
.st-key-navbar .stButton > button p{color:inherit !important;font-size:13px;font-weight:inherit;white-space:nowrap;}
.st-key-navbar .stButton > button:hover{background:var(--bg) !important;color:var(--text) !important;opacity:1;}
.st-key-navbar .stButton > button[kind="primary"], .st-key-navbar .stButton > button[data-testid="stBaseButton-primary"]{
  color:var(--primary) !important;border-bottom-color:var(--primary);background:var(--blue-bg) !important;font-weight:700;}

/* PAGE HEADER */
.page-title{font-size:18px;font-weight:700;color:var(--text);padding:4px 0 8px;}
.page-title span{color:var(--text3);font-weight:400;font-size:14px;margin-left:8px;}
.section-header{font-size:13px;font-weight:700;color:var(--primary);margin:6px 0 10px;display:flex;align-items:center;gap:8px;}
.section-header::after{content:'';flex:1;height:1px;background:var(--border);}
.section-header small{font-size:11px;font-weight:400;color:var(--text3);}

/* CARD (st.container(key="card-...")) */
[class*="st-key-card"]{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:18px 20px;box-shadow:var(--shadow);position:relative;overflow:hidden;min-width:0;}
[class*="st-key-card"] [data-testid="stVerticalBlock"]{gap:.5rem;}
.cardbar{position:absolute;top:0;left:0;right:0;height:3px;}
.card-title{font-size:14px;font-weight:700;color:var(--text);}
.card-title small{font-weight:400;color:var(--text3);font-size:12px;}
.card-subtitle{font-size:11px;color:var(--text3);font-weight:400;margin-top:2px;}
.sub-title{font-size:13px;font-weight:700;color:var(--text);margin-bottom:4px;}
.hint{font-size:11px;color:var(--text3);margin-top:2px;}
.mini-label{font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.3px;margin:8px 0 2px;}

/* KPI ADEM */
.adem-kpi-label{font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.4px;margin:4px 0 6px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.adem-kpi-value{font-size:22px;font-weight:800;color:var(--text);line-height:1.1;margin-bottom:2px;}
.adem-kpi-value small{font-size:11px;font-weight:500;color:var(--text3);margin-left:4px;}
.adem-kpi-target{font-size:10px;color:var(--text3);margin-bottom:6px;}
.adem-kpi-delta{display:inline-flex;align-items:center;gap:3px;font-size:11px;font-weight:600;padding:2px 7px;border-radius:10px;margin-bottom:4px;}
.adem-kpi-delta.up{color:var(--green);background:var(--green-bg);}
.adem-kpi-delta.down{color:var(--red);background:var(--red-bg);}
.adem-kpi-delta.flat{color:var(--orange);background:var(--orange-bg);}
.adem-kpi-date{font-size:10px;color:var(--text3);font-weight:500;}

/* LEI */
.lei-title{font-size:12px;font-weight:700;color:var(--text);margin-bottom:1px;line-height:1.3;}
.lei-sub{font-size:10px;color:var(--text3);margin-bottom:6px;}
.lei-value-row{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap;}
.lei-value{font-size:21px;font-weight:800;color:var(--text);}
.lei-unit{font-size:10px;color:var(--text3);}

/* KOMODITAS */
.komoditas-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:20px;}
.komoditas-card{background:var(--primary);border-radius:var(--radius);padding:16px;color:#fff;box-shadow:var(--shadow-md);position:relative;overflow:hidden;}
.komoditas-card::after{content:'';position:absolute;right:-20px;top:-20px;width:80px;height:80px;border-radius:50%;background:#FFFFFF08;}
.komoditas-name{font-size:12px;font-weight:500;color:#AFC6E9;margin-bottom:2px;}
.komoditas-unit{font-size:10px;color:#7A9CC8;margin-bottom:2px;}
.komoditas-date{font-size:10px;color:#AFC6E9;margin-bottom:8px;}
.komoditas-value{font-size:22px;font-weight:800;color:#fff;line-height:1;margin-bottom:10px;}
.komoditas-rows{display:flex;flex-direction:column;gap:4px;}
.komoditas-row{display:flex;align-items:center;justify-content:space-between;}
.komoditas-row-label{font-size:10px;color:#AFC6E9;font-weight:500;}
.komoditas-row-val{font-size:11px;font-weight:700;display:flex;align-items:center;gap:3px;}
.kom-up{color:#4ADE80;} .kom-down{color:#F87171;}
.kom-dot-up{width:7px;height:7px;border-radius:50%;background:#4ADE80;display:inline-block;}
.kom-dot-down{width:7px;height:7px;border-radius:50%;background:#F87171;display:inline-block;}

/* TABEL DAMPAK PDB */
.impact-wrap{overflow-x:auto;}
.impact-tbl{width:100%;border-collapse:collapse;font-size:12px;}
.impact-tbl th{padding:7px 9px;text-align:center;font-size:11px;font-weight:700;color:var(--text3);border-bottom:1px solid var(--border);white-space:nowrap;}
.impact-tbl .grp-hdr{background:var(--surface2);color:var(--text2);border-left:1px solid var(--border);}
.impact-tbl .sub-hdr{background:var(--bg);font-size:10px;font-weight:600;padding:5px 9px;}
.impact-tbl td{padding:8px 9px;border-bottom:1px solid var(--border);text-align:right;font-size:12px;color:var(--text2);font-variant-numeric:tabular-nums;white-space:nowrap;}
.impact-tbl td:first-child{text-align:left;color:var(--text);font-weight:500;padding-left:12px;}
.impact-tbl tr.ttl-row td{font-weight:700;color:var(--text);background:var(--surface2);}
.impact-tbl tr:hover td{background:var(--bg);}
.cell-hi{background:#E8F7EE !important;color:#1A8A4A !important;font-weight:600 !important;}
.cell-lo{background:#FDECEA !important;color:#C0392B !important;font-weight:600 !important;}
.cell-eq{background:var(--surface2) !important;}
.legend-row{display:flex;gap:16px;margin-top:12px;font-size:11px;color:var(--text3);flex-wrap:wrap;}
.legend-row span{display:flex;align-items:center;gap:5px;}
.legend-row i{width:12px;height:12px;display:inline-block;border-radius:2px;}

/* TABEL SENSITIVITAS APBN */
.sadem-apbn-tbl{width:100%;border-collapse:collapse;font-size:13px;}
.sadem-apbn-tbl th{padding:10px 14px;text-align:right;font-size:11px;font-weight:700;color:var(--text3);border-bottom:2px solid var(--border);text-transform:uppercase;letter-spacing:.4px;white-space:nowrap;line-height:1.5;}
.sadem-apbn-tbl th:first-child{text-align:left;}
.sadem-apbn-tbl th.c{text-align:center;}
.sadem-apbn-tbl th em{font-weight:400;font-size:10px;text-transform:none;}
.sadem-apbn-tbl td{padding:9px 14px;border-bottom:1px solid var(--border);color:var(--text2);font-size:13px;vertical-align:middle;}
.sadem-apbn-tbl td.nc{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}
.sadem-apbn-tbl td:first-child{color:var(--text);}
.sadem-apbn-tbl tr.grp td{font-weight:700;color:var(--primary);padding-top:14px;border-top:1px solid var(--border);}
.sadem-apbn-tbl tr.sub td:first-child{padding-left:24px;color:var(--text2);font-size:12px;}
.sadem-apbn-tbl tr.spec td:first-child{padding-left:36px;font-style:italic;color:var(--text3);font-size:12px;}
.sadem-apbn-tbl tr:hover td{background:var(--bg);}
.sa-pos{color:var(--green) !important;font-weight:600;}
.sa-neg{color:var(--red) !important;font-weight:600;}

/* TOMBOL (Mulai = tosca, Reset = pink) */
.stButton > button{border:none;border-radius:20px;padding:6px 26px;font-size:13px;font-weight:700;color:#fff;width:100%;}
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"]{background:#0891B2;}
.stButton > button[kind="secondary"], .stButton > button[data-testid="stBaseButton-secondary"]{background:#E83E8C;}
.stButton > button:hover{opacity:.88;color:#fff;border:none;}
.stButton > button p{color:#fff;font-weight:700;}

/* Tombol Asisten AI */
[class*="st-key-aibtn"] .stButton > button{background:linear-gradient(135deg,#7C3AED,#2B5AA8) !important;border-radius:20px;
  padding:7px 12px;font-weight:700;white-space:nowrap;box-shadow:0 2px 8px rgba(124,58,237,.30);}

/* TAB gaya sim-tabs-row */
[data-baseweb="tab-list"]{gap:0;border-bottom:2px solid var(--border);}
[data-baseweb="tab"]{padding:9px 18px;font-size:13px;font-weight:500;color:var(--text3);}
[data-baseweb="tab"][aria-selected="true"]{color:var(--primary);font-weight:700;}
[data-baseweb="tab-highlight"]{background-color:var(--primary) !important;height:3px;}

/* Selectbox / multiselect agar mirip select-filter */
[data-baseweb="select"] > div{background:var(--surface);border-color:var(--border);border-radius:var(--radius-sm);font-size:13px;}
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)


def compact(markup: str) -> str:
    """Rapatkan HTML jadi satu baris (hindari code-block markdown) dan amankan tanda $ (LaTeX)."""
    return "".join(line.strip() for line in markup.splitlines()).replace("$", "&#36;")


def md(markup: str):
    st.markdown(compact(markup), unsafe_allow_html=True)


def esc(text: object) -> str:
    return html.escape(str(text))



# =========================
# Helper formatting
# =========================
def normalize_col_name(name: object) -> str:
    return str(name).strip().lower().replace(" ", "_").replace(".", "").replace("-", "_")


def fmt_id0(val):
    if pd.isna(val) or val is None:
        return "—"
    try:
        s = f"{float(val):,.0f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(val)


def fmt_pct(val):
    if pd.isna(val) or val is None:
        return "—"
    try:
        s = f"{float(val):,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s + "%"
    except Exception:
        return str(val)



# =========================
# Default DF utilities
# =========================
def empty_df(block: str) -> pd.DataFrame:
    rows = DEFAULT_ROWS.get(block, [])
    payload = {"indikator": rows}
    for c in PERIOD_ORDER:
        payload[c] = [None] * len(rows)
    return pd.DataFrame(payload)


def ensure_schema(df: pd.DataFrame, block: str) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_df(block)

    work = df.copy()
    work.columns = [normalize_col_name(c) for c in work.columns]

    if "indikator" not in work.columns and len(work.columns) > 0:
        work = work.rename(columns={work.columns[0]: "indikator"})

    for col in ["indikator", *PERIOD_ORDER]:
        if col not in work.columns:
            work[col] = None

    work = work[["indikator", *PERIOD_ORDER]].copy()

    if block in DEFAULT_ROWS:
        wanted = DEFAULT_ROWS[block]
        work["indikator"] = work["indikator"].astype(str).str.strip()
        rows = []
        for ind in wanted:
            found = work.loc[work["indikator"] == ind]
            if not found.empty:
                rows.append(found.iloc[0].to_dict())
            else:
                rows.append({"indikator": ind, **{c: None for c in PERIOD_ORDER}})
        work = pd.DataFrame(rows)

    for c in PERIOD_ORDER:
        work[c] = pd.to_numeric(work[c], errors="coerce")
    return work


def ensure_full_year_from_quarters(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_df("pdb")
    work = df.copy()
    for c in SIMULASI_FISKAL_COLS:
        if c not in work.columns:
            work[c] = None
        work[c] = pd.to_numeric(work[c], errors="coerce")
    work["full_year"] = work[SIMULASI_FISKAL_COLS].sum(axis=1, min_count=1)
    return work



# =========================
# Excel source loaders
# =========================
def load_excel_bytes_from_url(url: str) -> bytes:
    with urlopen(url) as resp:
        return resp.read()


def open_excel_source(source: Union[str, bytes, bytearray]):
    if isinstance(source, (bytes, bytearray)):
        return pd.ExcelFile(BytesIO(source), engine="openpyxl")
    return pd.ExcelFile(source, engine="openpyxl")



# =========================
# PDB builder from 'realisasi'
# =========================
def _pick_col(columns, candidate: str):
    target = normalize_col_name(candidate)
    for c in columns:
        if normalize_col_name(c) == target:
            return c
    return None


def _build_period_table_from_realisasi(raw: pd.DataFrame) -> pd.DataFrame:
    row_map = {
        "Konsumsi RT": _pick_col(raw.columns, "Konsumsi RT"),
        "Konsumsi LNPRT": _pick_col(raw.columns, "Konsumsi LNPRT"),
        "PKP": _pick_col(raw.columns, "PKP"),
        "PMTB": _pick_col(raw.columns, "PMTB"),
        "Ekspor": _pick_col(raw.columns, "Ekspor"),
        "Impor": _pick_col(raw.columns, "Impor"),
        "Change in Stocks": _pick_col(raw.columns, "Change in Stocks"),
        "Statistical Discrepancy": _pick_col(raw.columns, "Statistical Discrepancy"),
    }

    work = raw.copy().sort_values("tanggal")
    work["tahun"] = work["tanggal"].dt.year
    work["quarter"] = work["tanggal"].dt.quarter

    rows = []
    for indikator, src in row_map.items():
        if src is None:
            continue
        s2026 = work.loc[work["tahun"] == TAHUN, ["quarter", src]].copy()
        quarter_values = {}
        for q in [1, 2, 3, 4]:
            sel = s2026.loc[s2026["quarter"] == q, src]
            quarter_values[f"out_tw{q}"] = float(sel.iloc[-1]) if not sel.empty else None
        fy = s2026[src].sum() if not s2026.empty else None
        rows.append({"indikator": indikator, **quarter_values, "full_year": fy})

    out = pd.DataFrame(rows)

    if not out.empty:
        idx = out.set_index("indikator")
        agg_vals = {}

        def gv(name, col):
            try:
                return pd.to_numeric(idx.loc[name, col], errors="coerce")
            except Exception:
                return 0.0

        for c in PERIOD_ORDER:
            agg_vals[c] = (
                (0 if pd.isna(gv("Konsumsi RT", c)) else float(gv("Konsumsi RT", c)))
                + (0 if pd.isna(gv("Konsumsi LNPRT", c)) else float(gv("Konsumsi LNPRT", c)))
                + (0 if pd.isna(gv("PKP", c)) else float(gv("PKP", c)))
                + (0 if pd.isna(gv("PMTB", c)) else float(gv("PMTB", c)))
                + (0 if pd.isna(gv("Change in Stocks", c)) else float(gv("Change in Stocks", c)))
                + (0 if pd.isna(gv("Ekspor", c)) else float(gv("Ekspor", c)))
                - (0 if pd.isna(gv("Impor", c)) else float(gv("Impor", c)))
                + (0 if pd.isna(gv("Statistical Discrepancy", c)) else float(gv("Statistical Discrepancy", c)))
            )

        out = pd.concat(
            [
                out[out["indikator"] != "Statistical Discrepancy"],
                pd.DataFrame([{"indikator": "PDB Aggregate", **agg_vals}]),
            ],
            ignore_index=True,
        )

    return ensure_schema(out, "pdb")


def _build_level_history(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy().sort_values("tanggal")

    col_rt = _pick_col(work.columns, "Konsumsi RT")
    col_lnprt = _pick_col(work.columns, "Konsumsi LNPRT")
    col_pkp = _pick_col(work.columns, "PKP")
    col_pmtb = _pick_col(work.columns, "PMTB")
    col_exp = _pick_col(work.columns, "Ekspor")
    col_imp = _pick_col(work.columns, "Impor")
    col_stocks = _pick_col(work.columns, "Change in Stocks")
    col_disc = _pick_col(work.columns, "Statistical Discrepancy")

    wide = pd.DataFrame(
        {
            "tanggal": work["tanggal"],
            "Konsumsi RT": pd.to_numeric(work[col_rt], errors="coerce") if col_rt else None,
            "Konsumsi LNPRT": pd.to_numeric(work[col_lnprt], errors="coerce") if col_lnprt else None,
            "PKP": pd.to_numeric(work[col_pkp], errors="coerce") if col_pkp else None,
            "PMTB": pd.to_numeric(work[col_pmtb], errors="coerce") if col_pmtb else None,
            "Change in Stocks": pd.to_numeric(work[col_stocks], errors="coerce") if col_stocks else None,
            "Ekspor": pd.to_numeric(work[col_exp], errors="coerce") if col_exp else None,
            "Impor": pd.to_numeric(work[col_imp], errors="coerce") if col_imp else None,
        }
    )

    discrepancy = pd.to_numeric(work[col_disc], errors="coerce") if col_disc else 0.0

    wide["PDB Aggregate"] = (
        wide["Konsumsi RT"].fillna(0)
        + wide["Konsumsi LNPRT"].fillna(0)
        + wide["PKP"].fillna(0)
        + wide["PMTB"].fillna(0)
        + wide["Change in Stocks"].fillna(0)
        + wide["Ekspor"].fillna(0)
        - wide["Impor"].fillna(0)
        + pd.to_numeric(discrepancy, errors="coerce").fillna(0)
    )
    return wide


def _build_growth_tables_from_wide(wide: pd.DataFrame):
    long_rows = []
    growth_rows = []
    yoy_rows = []
    qtq_rows = []
    date_map = {1: "out_tw1", 2: "out_tw2", 3: "out_tw3", 4: "out_tw4"}

    for comp in PDB_COMPONENTS:
        s = wide[["tanggal", comp]].copy().sort_values("tanggal")
        s["nilai"] = pd.to_numeric(s[comp], errors="coerce")
        s["komponen"] = comp
        s["nilai_fmt"] = s["nilai"].apply(fmt_id0)
        s["yoy"] = s["nilai"].pct_change(4) * 100
        s["qtq"] = s["nilai"].pct_change(1) * 100

        long_rows.append(s[["tanggal", "komponen", "nilai", "nilai_fmt"]])
        growth_rows.append(s[["tanggal", "komponen", "yoy", "qtq"]])

        s["tahun"] = s["tanggal"].dt.year
        s["quarter"] = s["tanggal"].dt.quarter
        s26 = s[s["tahun"] == TAHUN]

        yoy_row = {"indikator": comp}
        qtq_row = {"indikator": comp}
        for q in [1, 2, 3, 4]:
            sel = s26[s26["quarter"] == q]
            yoy_row[date_map[q]] = (
                float(sel["yoy"].iloc[-1]) if not sel.empty and pd.notna(sel["yoy"].iloc[-1]) else None
            )
            qtq_row[date_map[q]] = (
                float(sel["qtq"].iloc[-1]) if not sel.empty and pd.notna(sel["qtq"].iloc[-1]) else None
            )

        annual = s.groupby("tahun", as_index=False)["nilai"].sum()
        annual["yoy"] = annual["nilai"].pct_change(1) * 100
        annual26 = annual.loc[annual["tahun"] == TAHUN, "yoy"]

        yoy_row["full_year"] = (
            float(annual26.iloc[-1]) if not annual26.empty and pd.notna(annual26.iloc[-1]) else None
        )
        qtq_row["full_year"] = (
            float(s["qtq"].dropna().iloc[-1]) if not s["qtq"].dropna().empty else None
        )

        yoy_rows.append(yoy_row)
        qtq_rows.append(qtq_row)

    return (
        pd.concat(long_rows, ignore_index=True),
        pd.concat(growth_rows, ignore_index=True),
        ensure_schema(pd.DataFrame(yoy_rows), "pdb"),
        ensure_schema(pd.DataFrame(qtq_rows), "pdb"),
    )


def derive_pdb_from_realisasi(source: Union[str, bytes]):
    xls = open_excel_source(source)
    sheet_map = {s.lower().strip(): s for s in xls.sheet_names}
    if "realisasi" not in sheet_map:
        return empty_df("pdb"), None, None

    raw = pd.read_excel(xls, sheet_name=sheet_map["realisasi"], engine="openpyxl")
    raw = raw.rename(columns={raw.columns[0]: "tanggal"}).copy()
    raw["tanggal"] = pd.to_datetime(raw["tanggal"], errors="coerce")
    raw = raw.dropna(subset=["tanggal"]).sort_values("tanggal").reset_index(drop=True)

    pdb_df = _build_period_table_from_realisasi(raw)
    wide = _build_level_history(raw)
    level_long, growth_long, yoy_df, qtq_df = _build_growth_tables_from_wide(wide)

    return pdb_df, {"level": level_long, "growth": growth_long, "wide": wide}, {"yoy": yoy_df, "qtq": qtq_df}



# =========================
# Simulasi Fiskal
# =========================
def build_simulasi_fiskal_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "indikator": SIMULASI_FISKAL_ROWS,
            "out_tw1": [0.0] * len(SIMULASI_FISKAL_ROWS),
            "out_tw2": [0.0] * len(SIMULASI_FISKAL_ROWS),
            "out_tw3": [0.0] * len(SIMULASI_FISKAL_ROWS),
            "out_tw4": [0.0] * len(SIMULASI_FISKAL_ROWS),
        }
    )


def get_simulasi_fiskal_df() -> pd.DataFrame:
    if "simulasi_fiskal_df" not in st.session_state:
        st.session_state["simulasi_fiskal_df"] = build_simulasi_fiskal_df()
    df = st.session_state["simulasi_fiskal_df"].copy()
    df["indikator"] = SIMULASI_FISKAL_ROWS
    for c in SIMULASI_FISKAL_COLS:
        df[c] = pd.to_numeric(df.get(c, 0.0), errors="coerce").fillna(0.0)
    # Q1 dan Q2 sudah realisasi, sehingga shock fiskal dinonaktifkan.
    df["out_tw1"] = 0.0
    df["out_tw2"] = 0.0
    st.session_state["simulasi_fiskal_df"] = df.copy()
    return df[["indikator", *SIMULASI_FISKAL_COLS]]


# =========================
# Simulasi Makro
# =========================
def build_simulasi_makro_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "indikator": [row[0] for row in SIMULASI_MAKRO_DEFAULTS],
            "apbn_2026": [row[1] for row in SIMULASI_MAKRO_DEFAULTS],
            "shock": [None] * len(SIMULASI_MAKRO_DEFAULTS),
        }
    )


def get_simulasi_makro_df() -> pd.DataFrame:
    if "simulasi_makro_df" not in st.session_state:
        st.session_state["simulasi_makro_df"] = build_simulasi_makro_df()

    df = st.session_state["simulasi_makro_df"].copy()
    df["indikator"] = [row[0] for row in SIMULASI_MAKRO_DEFAULTS]
    df["apbn_2026"] = [row[1] for row in SIMULASI_MAKRO_DEFAULTS]
    df["shock"] = pd.to_numeric(df.get("shock"), errors="coerce")

    return df[["indikator", "apbn_2026", "shock"]]


def get_simulasi_makro_delta(simulasi_makro_df: Optional[pd.DataFrame], indikator: str) -> Optional[float]:
    if simulasi_makro_df is None or simulasi_makro_df.empty:
        return None
    work = simulasi_makro_df.copy()
    work["indikator"] = work["indikator"].astype(str).str.strip()
    row = work.loc[work["indikator"] == indikator]
    if row.empty:
        return None

    apbn_val = pd.to_numeric(row.iloc[0].get("apbn_2026"), errors="coerce")
    shock_val = pd.to_numeric(row.iloc[0].get("shock"), errors="coerce")
    if pd.isna(apbn_val) or pd.isna(shock_val):
        return None
    return float(shock_val) - float(apbn_val)


def calculate_pertumbuhan_ekonomi_tax_impact(simulasi_makro_df: Optional[pd.DataFrame]) -> Optional[float]:
    delta = get_simulasi_makro_delta(simulasi_makro_df, "Pertumbuhan ekonomi (%)")
    if delta is None:
        return None
    dampak = (delta / 0.1) * 2080.30
    return round(dampak, 2)


def calculate_inflasi_tax_impact(simulasi_makro_df: Optional[pd.DataFrame]) -> Optional[float]:
    """Hitung sensitivitas inflasi terhadap Penerimaan Perpajakan.

    Setiap kenaikan 0,1 poin persentase, misalnya dari 2,5% menjadi
    2,6%, meningkatkan Penerimaan Perpajakan sebesar 1.862,99.
    Penurunan inflasi dihitung secara linear dan memberi dampak negatif.
    """
    delta = get_simulasi_makro_delta(simulasi_makro_df, "Inflasi (%)")
    if delta is None:
        return None
    dampak = (delta / 0.1) * 1862.99
    return round(dampak, 2)


def calculate_sun_10y_bpp_impact(simulasi_makro_df: Optional[pd.DataFrame]) -> Optional[float]:
    """Hitung sensitivitas SUN 10 tahun terhadap Belanja Pemerintah Pusat.

    Setiap kenaikan 0,1 poin persentase, misalnya dari 6,9 menjadi
    7,0, meningkatkan Belanja Pemerintah Pusat sebesar 1.899,98.
    Penurunan tingkat bunga dihitung secara linear dan memberi dampak negatif.
    """
    delta = get_simulasi_makro_delta(
        simulasi_makro_df,
        "Tingkat bunga SUN 10 tahun",
    )
    if delta is None:
        return None
    dampak = (delta / 0.1) * 1899.98
    return round(dampak, 2)


def calculate_nilai_tukar_impacts(simulasi_makro_df: Optional[pd.DataFrame]) -> dict:
    delta = get_simulasi_makro_delta(simulasi_makro_df, "Nilai tukar (Rp100/US$1)")
    if delta is None:
        return {"pp": 0.0, "pnbp": 0.0, "bpp": 0.0}
    factor = delta / 100.0
    return {"pp": round(factor * 3481.10, 2), "pnbp": round(factor * 1831.36, 2), "bpp": round(factor * 6094.48, 2)}


def calculate_harga_minyak_impacts(simulasi_makro_df: Optional[pd.DataFrame]) -> dict:
    delta = get_simulasi_makro_delta(simulasi_makro_df, "Harga minyak (US$/barel)")
    if delta is None:
        return {"pp": 0.0, "pnbp": 0.0, "bpp": 0.0}
    factor = delta
    return {"pp": round(factor * 1911.93, 2), "pnbp": round(factor * 1576.88, 2), "bpp": round(factor * 10286.40, 2)}


def calculate_lifting_minyak_impacts(simulasi_makro_df: Optional[pd.DataFrame]) -> dict:
    delta = get_simulasi_makro_delta(simulasi_makro_df, "Lifting minyak (ribu barel per hari)")
    if delta is None:
        return {"pp": 0.0, "pnbp": 0.0}
    factor = delta / 10.0
    return {"pp": round(factor * 265.64, 2), "pnbp": round(factor * 1518.17, 2)}


def calculate_lifting_gas_bumi_impacts(simulasi_makro_df: Optional[pd.DataFrame]) -> dict:
    """
    Rule baru sesuai permintaan:
    - Jika shock Lifting Gas Bumi = APBN + 10:
      pp   += 390.99
      pnbp += 870.10
    - Jika shock Lifting Gas Bumi = APBN - 10:
      pp   -= 390.99
      pnbp -= 870.10

    Formula linear:
      factor = (shock - apbn) / 10
      pp     = factor * 390.99
      pnbp   = factor * 870.10
    """
    delta = get_simulasi_makro_delta(
        simulasi_makro_df,
        "Lifting Gas Bumi (ribu barel setara minyak per hari)"
    )
    if delta is None:
        return {"pp": 0.0, "pnbp": 0.0}

    factor = delta / 10.0
    return {
        "pp": round(factor * 390.99, 2),
        "pnbp": round(factor * 870.10, 2),
    }


# =========================
# Simulasi fiskal ke PDB nominal
# =========================
def apply_simulasi_fiskal_to_pdb_nominal(pdb_df: pd.DataFrame, simulasi_df: pd.DataFrame) -> pd.DataFrame:
    if pdb_df is None or pdb_df.empty:
        return pdb_df

    work = ensure_full_year_from_quarters(pdb_df.copy())
    sim = simulasi_df.copy()
    sim["indikator"] = sim["indikator"].astype(str).str.strip()

    rules = [
        {
            "sim_indicator": "Bantuan Pangan",
            "target_indicator": "PKP",
            "divisors": {"out_tw1": 1.82, "out_tw2": 1.86, "out_tw3": 1.88, "out_tw4": 1.91},
        },
        {
            "sim_indicator": "Bantuan Langsung Tunai",
            "target_indicator": "Konsumsi RT",
            "divisors": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86},
        },
        {
            "sim_indicator": "Kenaikan Gaji",
            "target_indicator": "Konsumsi RT",
            "divisors": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86},
        },
        {
            "sim_indicator": "Pembayaran Gaji 14",
            "target_indicator": "Konsumsi RT",
            "divisors": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86},
        },
        {
            "sim_indicator": "Diskon Transportasi",
            "target_indicator": "Konsumsi RT",
            "divisors": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86},
        },
        {
            "sim_indicator": "Investasi",
            "target_indicator": "PMTB",
            "divisors": {"out_tw1": 1.66, "out_tw2": 1.66, "out_tw3": 1.67, "out_tw4": 1.67},
        },
    ]

    agg_mask = work["indikator"].astype(str).str.strip() == "PDB Aggregate"

    for rule in rules:
        sim_row = sim.loc[sim["indikator"] == rule["sim_indicator"]]
        if sim_row.empty:
            continue

        target_mask = work["indikator"].astype(str).str.strip() == rule["target_indicator"]
        if not target_mask.any():
            continue

        for col, div in rule["divisors"].items():
            input_val = pd.to_numeric(sim_row.iloc[0].get(col, 0.0), errors="coerce")
            input_val = 0.0 if pd.isna(input_val) else float(input_val)
            addition = input_val / div if div else 0.0

            work.loc[target_mask, col] = (
                pd.to_numeric(work.loc[target_mask, col], errors="coerce").fillna(0.0) + addition
            )
            if agg_mask.any():
                work.loc[agg_mask, col] = (
                    pd.to_numeric(work.loc[agg_mask, col], errors="coerce").fillna(0.0) + addition
                )

    return ensure_full_year_from_quarters(work)


def apply_simulasi_makro_to_pdb_nominal(
    shock_fiskal_df: pd.DataFrame,
    simulasi_makro_pdb_df: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """Terapkan shock ICP dan inflasi hanya pada Full Year.

    Acuan seluruh dampak makro adalah nominal Full Year Shock Fiskal.
    Nilai Q1, Q2, Q3, dan Q4 tidak diubah oleh Shock Makro.

    Aturan ICP:
    - Kenaikan 1% relatif terhadap Target APBN mengubah Ekspor +323,97.
    - Kenaikan 1% relatif terhadap Target APBN mengubah Impor +1.449,95.

    Aturan inflasi:
    - Kenaikan 1 poin persentase, misalnya 2,5% menjadi 3,5%,
      menurunkan Konsumsi RT sebesar 0,053% dari nominal Full Year
      Konsumsi RT pada kolom Shock Fiskal.

    Dampak PDB Aggregate mengikuti identitas pengeluaran:
    delta PDB = delta Konsumsi RT + delta Ekspor - delta Impor.
    """
    if shock_fiskal_df is None or shock_fiskal_df.empty:
        return shock_fiskal_df

    # Full Year awal selalu dihitung dari Q1-Q4 hasil Shock Fiskal.
    work = ensure_full_year_from_quarters(shock_fiskal_df.copy())
    if simulasi_makro_pdb_df is None or simulasi_makro_pdb_df.empty:
        return work

    sim = simulasi_makro_pdb_df.copy()
    sim["indikator"] = sim["indikator"].astype(str).str.strip()
    indikator = work["indikator"].astype(str).str.strip()

    def get_target_and_shock(nama_indikator: str):
        row = sim.loc[sim["indikator"] == nama_indikator]
        if row.empty:
            return None, None
        target = pd.to_numeric(row.iloc[0].get("target_apbn"), errors="coerce")
        shock = pd.to_numeric(row.iloc[0].get("shock_makro"), errors="coerce")
        if pd.isna(target) or pd.isna(shock):
            return None, None
        return float(target), float(shock)

    def get_full_year(nama_indikator: str) -> Optional[float]:
        row = work.loc[indikator == nama_indikator, "full_year"]
        if row.empty:
            return None
        value = pd.to_numeric(row.iloc[0], errors="coerce")
        return None if pd.isna(value) else float(value)

    def add_full_year(nama_indikator: str, delta: float):
        mask = indikator == nama_indikator
        if mask.any():
            current = pd.to_numeric(
                work.loc[mask, "full_year"], errors="coerce"
            ).fillna(0.0)
            work.loc[mask, "full_year"] = current + float(delta)

    total_delta_pdb = 0.0

    # 1. Shock ICP. Contoh 70 menjadi 70,7 = kenaikan relatif 1%.
    target_icp, shock_icp = get_target_and_shock("ICP (USD/barrel)")
    if target_icp is not None and shock_icp is not None and target_icp != 0:
        perubahan_icp_persen = ((shock_icp / target_icp) - 1.0) * 100.0
        delta_ekspor = perubahan_icp_persen * 323.97
        delta_impor = perubahan_icp_persen * 1449.95
        add_full_year("Ekspor", delta_ekspor)
        add_full_year("Impor", delta_impor)
        total_delta_pdb += delta_ekspor - delta_impor

    # 2. Shock inflasi. Contoh 2,5 menjadi 3,5 = +1 poin persentase.
    target_inflasi, shock_inflasi = get_target_and_shock("Inflasi (%)")
    konsumsi_rt_fiskal = get_full_year("Konsumsi RT")
    if (
        target_inflasi is not None
        and shock_inflasi is not None
        and konsumsi_rt_fiskal is not None
    ):
        perubahan_inflasi_poin = shock_inflasi - target_inflasi
        # Setiap +1 poin persentase inflasi menurunkan konsumsi sebesar 0,053%.
        delta_konsumsi_rt = -(
            konsumsi_rt_fiskal
            * 0.00053
            * perubahan_inflasi_poin
        )
        add_full_year("Konsumsi RT", delta_konsumsi_rt)
        total_delta_pdb += delta_konsumsi_rt

    # PDB Aggregate hanya berubah pada Full Year. Q1-Q4 tetap Shock Fiskal.
    add_full_year("PDB Aggregate", total_delta_pdb)

    # Jangan menjalankan ensure_full_year_from_quarters lagi setelah ini,
    # karena fungsi tersebut akan menghapus dampak makro Full Year.
    return work


def build_full_year_yoy_from_nominal(
    pdb_history: Optional[dict],
    nominal_df: pd.DataFrame,
    quarter_growth_reference: pd.DataFrame,
) -> pd.DataFrame:
    """Bangun tabel YoY dengan Q1-Q4 tetap dari Shock Fiskal.

    Hanya Full Year YoY yang dihitung ulang menggunakan:
    ((nominal FY 2026 setelah shock makro / nominal FY 2025) - 1) * 100.
    """
    result = ensure_schema(quarter_growth_reference.copy(), "pdb")
    if (
        not pdb_history
        or pdb_history.get("wide") is None
        or nominal_df is None
        or nominal_df.empty
    ):
        return result

    wide = pdb_history["wide"].copy()
    wide["tahun"] = pd.to_datetime(wide["tanggal"], errors="coerce").dt.year
    nominal = nominal_df.copy()
    nominal["indikator"] = nominal["indikator"].astype(str).str.strip()

    for comp in PDB_COMPONENTS:
        if comp not in wide.columns:
            continue
        base_2025 = pd.to_numeric(
            wide.loc[wide["tahun"] == TAHUN - 1, comp], errors="coerce"
        ).sum(min_count=1)
        row = nominal.loc[nominal["indikator"] == comp, "full_year"]
        if row.empty or pd.isna(base_2025) or float(base_2025) == 0:
            continue
        value_2026 = pd.to_numeric(row.iloc[0], errors="coerce")
        if pd.isna(value_2026):
            continue
        yoy_fy = ((float(value_2026) / float(base_2025)) - 1.0) * 100.0
        result.loc[result["indikator"] == comp, "full_year"] = yoy_fy

    return result


def build_adjusted_top_growth_tables(pdb_history: Optional[dict], adjusted_nominal: pd.DataFrame):
    if not pdb_history or pdb_history.get("wide") is None or adjusted_nominal is None or adjusted_nominal.empty:
        return {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}

    wide = pdb_history["wide"].copy()
    date_map = {
        "out_tw1": pd.Timestamp(TAHUN, 3, 31),
        "out_tw2": pd.Timestamp(TAHUN, 6, 30),
        "out_tw3": pd.Timestamp(TAHUN, 9, 30),
        "out_tw4": pd.Timestamp(TAHUN, 12, 31),
    }

    adj = adjusted_nominal.copy()
    adj["indikator"] = adj["indikator"].astype(str).str.strip()

    for _, row in adj.iterrows():
        indikator = row["indikator"]
        if indikator not in PDB_COMPONENTS:
            continue
        for col, dt in date_map.items():
            val = pd.to_numeric(row.get(col), errors="coerce")
            if pd.notna(val):
                wide.loc[wide["tanggal"] == dt, indikator] = float(val)

    _, _, yoy_df, qtq_df = _build_growth_tables_from_wide(wide)
    return {"yoy": yoy_df, "qtq": qtq_df}




# =========================
# Loader sumber data (dengan cache)
# =========================
def _norm_filename(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(name).lower())


def _search_dirs() -> list:
    """Folder yang diperiksa: lokasi skrip, folder kerja, dan induknya (tanpa duplikat)."""
    script_dir = Path(__file__).resolve().parent
    dirs, seen = [], set()
    for d in (script_dir, Path.cwd(), script_dir.parent, Path.cwd().parent):
        if d not in seen and d.exists():
            seen.add(d)
            dirs.append(d)
    return dirs


def _list_xlsx_files() -> list:
    found = []
    for base in _search_dirs():
        try:
            for p in base.rglob("*.xlsx"):
                if not any(part.startswith(".") or part in {"node_modules", "__pycache__"} for part in p.parts):
                    found.append(p)
        except Exception:
            continue
    return list(dict.fromkeys(found))


def _find_local_file(candidates, keyword: Optional[str] = None) -> Optional[Path]:
    """Cari file Excel: nama persis dulu, lalu cocok tanpa memedulikan huruf besar/kecil, spasi, underscore;
    terakhir (opsional) file .xlsx mana pun yang namanya mengandung `keyword`."""
    targets = {_norm_filename(c) for c in candidates}
    files = _list_xlsx_files()
    for base in _search_dirs():
        for name in candidates:
            if (base / name).is_file():
                return base / name
    for p in files:
        if _norm_filename(p.name) in targets:
            return p
    if keyword:
        for p in files:
            if keyword.lower() in p.name.lower() and not p.name.startswith("~$"):
                return p
    return None


def _describe_xlsx_found() -> str:
    names = sorted({str(p.name) for p in _list_xlsx_files()})
    return ("File .xlsx yang terdeteksi di repo: " + ", ".join(names)) if names else "Tidak ada file .xlsx yang terdeteksi di repo."


def detect_excel_source() -> Tuple[Optional[Union[str, bytes]], str]:
    local_path = _find_local_file(PDB_FILE_CANDIDATES, keyword="pdb")
    if local_path is not None:
        return str(local_path), "Data tersedia."
    if GITHUB_RAW_XLSX_URL:
        return load_excel_bytes_from_url(GITHUB_RAW_XLSX_URL), "Data tersedia."
    return (
        None,
        "File Excel belum ditemukan. Simpan 'dashboard PDB.xlsx' (atau 'dashboard_PDB.xlsx') di root repo "
        "yang sama dengan app.py, atau isi st.secrets['github_raw_xlsx_url'].",
    )


@st.cache_data(show_spinner=False, ttl=3600)
def load_dashboard_data():
    """Return: (pdb_nominal_df, pdb_history, pdb_tables, status)."""
    pdb_df = empty_df("pdb")
    pdb_history = None
    pdb_tables = None

    source, status = detect_excel_source()
    if source is None:
        return pdb_df, pdb_history, pdb_tables, status

    try:
        xls = open_excel_source(source)
        sheet_map = {s.lower().strip(): s for s in xls.sheet_names}
        if "realisasi" in sheet_map:
            pdb_df, pdb_history, pdb_tables = derive_pdb_from_realisasi(source)
        elif "pdb" in sheet_map:
            pdb_df = ensure_schema(
                pd.read_excel(xls, sheet_name=sheet_map["pdb"], engine="openpyxl"), "pdb"
            )
        return pdb_df, pdb_history, pdb_tables, status
    except Exception as exc:
        return pdb_df, pdb_history, pdb_tables, f"Gagal membaca sumber Excel: {exc}"


@st.cache_data(show_spinner=False, ttl=3600)
def load_indicator_data() -> Tuple[Optional[pd.DataFrame], str]:
    local_path = _find_local_file(INDICATOR_FILE_CANDIDATES, keyword="indikator")
    if local_path is None:
        return None, "File 'dashboard indikator.xlsx' belum ditemukan di root repository."
    try:
        df = pd.read_excel(local_path, sheet_name="Data_Wide", engine="openpyxl")
        df.columns = [str(c).strip() for c in df.columns]
        df["Periode"] = pd.to_datetime(df["Periode"], errors="coerce")
        df = df.dropna(subset=["Periode"]).sort_values("Periode").reset_index(drop=True)
        for col in df.columns[1:]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df, "Data indikator tersedia."
    except Exception as exc:
        return None, f"Gagal membaca {local_path.name}: {exc}"


def parse_quarter_label(text) -> Optional[pd.Timestamp]:
    """'Q12020' / 'Q1 2020' / 'Q1-2020' -> tanggal akhir kuartal (2020-03-31)."""
    m = re.match(r"^\s*Q([1-4])\s*[-/ ]?\s*(\d{4})\s*$", str(text), flags=re.IGNORECASE)
    if not m:
        return None
    return pd.Period(year=int(m.group(2)), quarter=int(m.group(1)), freq="Q").end_time.normalize()


def _canon_name(name: str) -> str:
    text = re.sub(r"\s+", " ", str(name)).strip()
    return text[:1].upper() + text[1:]


def _sector_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


SECTOR_SYNONYMS = {"industripengolahan": "manufaktur", "industri": "manufaktur", "pertanianperikanandankehutanan": "pertanian"}


def _match_sector_name(name: str, targets: list) -> str:
    """Samakan nama sektor kolom nom_ dengan nama pada kolom distribusi_/share to growth_ (abaikan huruf/spasi/simbol)."""
    key = SECTOR_SYNONYMS.get(_sector_key(name), _sector_key(name))
    by_key = {_sector_key(t): t for t in targets}
    if key in by_key:
        return by_key[key]
    close = difflib.get_close_matches(key, list(by_key), n=1, cutoff=0.8)
    return by_key[close[0]] if close else name


@st.cache_data(show_spinner=False)
def _read_triwulan_excel(path_str: str, mtime: float) -> dict:
    """Baca sheet PDB dengan pandas. `mtime` hanya agar cache diperbarui saat file berubah."""
    xls = pd.ExcelFile(path_str, engine="openpyxl")
    sheet = next((s for s in xls.sheet_names if s.strip().lower() == "pdb"), xls.sheet_names[0])
    raw = pd.read_excel(xls, sheet_name=sheet)
    raw = raw.rename(columns={raw.columns[0]: "periode"})
    raw["tanggal"] = raw["periode"].map(parse_quarter_label)
    raw = raw.dropna(subset=["tanggal"]).sort_values("tanggal").set_index("tanggal")

    prefixes = {"dist": "distribusi_", "stg": "share to growth_", "growth": "pertumbuhan_"}
    out = {}
    for key, prefix in prefixes.items():
        mapping = {}
        for col in raw.columns:
            text = str(col).strip()
            if text.lower().startswith(prefix):
                mapping[col] = _canon_name(text[len(prefix):])
        out[key] = raw[list(mapping)].apply(pd.to_numeric, errors="coerce").rename(columns=mapping)

    # Pertumbuhan yoy (%) lapangan usaha diturunkan dari nilai level terhadap kuartal yang sama tahun lalu.
    # Prioritas sumber: kolom 'pertumbuhan_<sektor>' > 'kons_<sektor>' (harga konstan, pertumbuhan riil) > 'nom_<sektor>' (nominal).
    known_names = list(out["dist"].columns) + list(out["stg"].columns)

    def level_frame(prefix: str) -> pd.DataFrame:
        mapping = {}
        for col in raw.columns:
            text = str(col).strip()
            if text.lower().startswith(prefix):
                mapping[col] = _match_sector_name(_canon_name(text[len(prefix):]), known_names)
        frame = raw[list(mapping)].apply(pd.to_numeric, errors="coerce").rename(columns=mapping)
        return frame.loc[:, ~frame.columns.duplicated()].sort_index()

    skip = set(EXP_NAMES) | {"PDB"}  # pengeluaran tetap memakai sheet 'realisasi'
    growth = out["growth"]
    source = {}
    for prefix, label in (("kons_", "konstan"), ("nom_", "nominal")):
        level = level_frame(prefix)
        yoy = level.pct_change(periods=4, fill_method=None) * 100.0
        new_cols = [c for c in yoy.columns if c not in skip and c not in growth.columns]
        growth = pd.concat([growth, yoy[new_cols]], axis=1)
        source.update({c: label for c in new_cols})
        out["nom" if prefix == "nom_" else "kons"] = level
    out["growth"] = growth
    out["growth_source"] = source
    return out


def load_triwulan_data():
    """Return (dict[dist|stg|growth] -> DataFrame, status) dari Database_Dashboard_triwulanan.xlsx."""
    path = _find_local_file(TRIWULAN_FILE_CANDIDATES, keyword="triwulan")
    if path is None:
        return None, (
            "File 'Database_Dashboard_triwulanan.xlsx' belum ditemukan. Pastikan file di-commit ke GitHub "
            "(di folder yang sama dengan app_tab_menu.py atau di root repo) lalu reboot app. "
            + _describe_xlsx_found()
        )
    try:
        data = _read_triwulan_excel(str(path), path.stat().st_mtime)
    except Exception as exc:
        return None, f"Gagal membaca {path.name} dengan pandas: {exc}"
    if data["dist"].empty and data["stg"].empty:
        return None, (f"{path.name} terbaca, tetapi kolom 'distribusi_...' / 'share to growth_...' "
                      "atau kolom periode (contoh: Q12020) tidak ditemukan.")
    return data, "Data triwulanan tersedia."


# =========================
# Helper tampilan umum
# =========================
def card(key: str):
    """Container bergaya .card (butuh streamlit >= 1.40 untuk st.container(key=...))."""
    try:
        return st.container(key=f"card-{key}")
    except TypeError:
        return st.container()


def show_chart(fig, key: str):
    config = {"displayModeBar": False}
    try:
        st.plotly_chart(fig, width="stretch", config=config, key=key)
    except Exception:
        st.plotly_chart(fig, use_container_width=True, config=config, key=key)


def editor_stretch(df: pd.DataFrame, **kwargs):
    try:
        return st.data_editor(df, width="stretch", **kwargs)
    except Exception:
        return st.data_editor(df, use_container_width=True, **kwargs)


def _idn(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def periode_label(ts) -> str:
    ts = pd.Timestamp(ts)
    return f"{BULAN_ID[ts.month - 1]} {ts.year}"


def quarter_label(ts) -> str:
    ts = pd.Timestamp(ts)
    return f"Q{ts.quarter} {ts.year}"


def last_realized_date() -> pd.Timestamp:
    return pd.Period(f"{TAHUN}Q{JUMLAH_Q_REALISASI}").end_time.normalize()


def page_title(title: str, subtitle: str = ""):
    sub = f"<span>{subtitle}</span>" if subtitle else ""
    md(f'<div class="page-title">{title}{sub}</div>')


def section_header(title: str, note: str = ""):
    small = f"<small>{note}</small>" if note else ""
    md(f'<div class="section-header">{title}{small}</div>')


def style_figure(fig, height: int, legend: bool = False):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=11, color="#4A5568"),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, font=dict(size=11)),
        hoverlabel=dict(font_size=11),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor=C_GRID, zeroline=False)
    return fig


def sparkline_range(values) -> Optional[list]:
    """Rentang sumbu Y yang dipersempit mengikuti data (tidak dipaksa mulai dari nol),
    supaya perubahan kecil pada data yang bergerak landai tetap terlihat."""
    series = pd.Series(values, dtype="float64").dropna()
    if series.empty:
        return None
    y_min, y_max = float(series.min()), float(series.max())
    span = y_max - y_min
    if span <= abs(y_max) * 1e-6:  # data hampir konstan
        span = max(abs(y_max) * 0.02, 0.5)
    return [y_min - span * 0.25, y_max + span * 0.35]


def sparkline_figure(x, y, color: str, height: int = 90):
    values = pd.to_numeric(pd.Series(list(y)), errors="coerce")
    fig = go.Figure(
        go.Scatter(
            x=x, y=y, mode="lines", connectgaps=True,
            line=dict(color=color, width=2.4, shape="spline", smoothing=0.45),
            fill="tozeroy", fillcolor=color + "1A",
            hovertemplate="%{x|%b %Y}<br>%{y:,.2f}<extra></extra>",
        )
    )
    # Titik data terakhir diberi penanda
    last_idx = values.last_valid_index()
    if last_idx is not None:
        fig.add_trace(go.Scatter(
            x=[list(x)[last_idx]], y=[float(values.iloc[last_idx])], mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(size=7, color=color, line=dict(color="#FFFFFF", width=2)),
        ))
    style_figure(fig, height)
    fig.update_layout(margin=dict(l=2, r=6, t=6, b=2))
    fig.update_xaxes(tickformat="%b'%y", nticks=4, fixedrange=True, tickfont=dict(size=9, color=C_TEXT3))
    fig.update_yaxes(showgrid=False, showticklabels=False, range=sparkline_range(values), fixedrange=True)
    return fig


# =========================
# Halaman: Ringkasan Ekonomi
# =========================
ADEM_CARDS = [
    dict(key="PDB", label="Pertumbuhan PDB", unit="%", color=C_GREEN, target_text="Target APBN: 5,4%"),
    dict(key="Inflasi", label="Inflasi CPI (YoY)", unit="%", color=C_ORANGE, target_text="Target APBN: 2,5%"),
    dict(key="Nilai Tukar", label="Nilai Tukar USD/IDR", unit="Rp/US$", color=C_ACCENT, target_text="Target APBN: 16.500"),
    dict(key="Yield SBN 10 Tahun", label="Yield SBN 10 Tahun", unit="%", color=C_PRIMARY_LIGHT, target_text="Target APBN: 6,9%"),
    dict(key="Harga ICP", label="Harga ICP", unit="USD/barel", color=C_TEAL, target_text="Target APBN: USD70/barel"),
    dict(key="Lifting Minyak", label="Lifting Minyak", unit="ribu barel/hari", color=C_PURPLE, target_text="Target APBN: 610 ribu barel/hari"),
    dict(key="Lifting Gas", label="Lifting Gas", unit="ribu BOEPD", color=C_RED, target_text="Target APBN: 984 ribu BOEPD"),
]


def format_macro_value(value, key: str) -> str:
    if value is None or pd.isna(value):
        return "—"
    if key in {"PDB", "Inflasi", "Yield SBN 10 Tahun"}:
        return _idn(value, 2) + "%"
    if key == "Harga ICP":
        return "USD" + _idn(value, 1)
    return _idn(value, 0 if key == "Nilai Tukar" else 1)


def format_macro_delta(delta, key: str) -> str:
    if delta is None or pd.isna(delta):
        return "Data pembanding belum tersedia"
    arrow = "▲" if delta > 0 else "▼" if delta < 0 else "→"
    if key == "Nilai Tukar":
        value, suffix = _idn(abs(delta), 0), "vs bulan lalu"
    elif key in {"Inflasi", "Yield SBN 10 Tahun"}:
        value, suffix = _idn(abs(delta), 2), "p.p. vs bulan lalu"
    elif key == "PDB":
        value, suffix = _idn(abs(delta), 2), "p.p. vs kuartal lalu"
    elif key == "Harga ICP":
        value, suffix = "USD" + _idn(abs(delta), 1), "vs bulan lalu"
    else:
        value, suffix = _idn(abs(delta), 1), "vs bulan lalu"
    return f"{arrow} {value} {suffix}"


def _delta_class(delta) -> str:
    if delta is None or pd.isna(delta) or delta == 0:
        return "flat"
    return "up" if delta > 0 else "down"


def adem_series(key: str, ind_df: pd.DataFrame, as_of_end: pd.Timestamp, pdb_history: Optional[dict]):
    """Return (tanggal, nilai, teks_periode) untuk satu kartu ADEM; None jika data kosong."""
    if key == "PDB":
        if not pdb_history or pdb_history.get("growth") is None:
            return None
        g = pdb_history["growth"]
        g = g[(g["komponen"] == "PDB Aggregate") & (g["tanggal"] <= min(as_of_end, last_realized_date()))]
        g = g.dropna(subset=["yoy"]).tail(8)
        if g.empty:
            return None
        return g["tanggal"], g["yoy"], quarter_label(g["tanggal"].iloc[-1])
    if key not in ind_df.columns:
        return None
    data = ind_df.loc[ind_df["Periode"] <= as_of_end, ["Periode", key]].dropna().tail(24)
    if data.empty:
        return None
    return data["Periode"], data[key], periode_label(data["Periode"].iloc[-1])


def render_adem_card(meta: dict, series, idx: int):
    with card(f"adem-{idx}"):
        if series is None:
            md(f'<div class="cardbar" style="background:{meta["color"]}"></div>'
               f'<div class="adem-kpi-label">{esc(meta["label"])}</div>'
               f'<div class="adem-kpi-target">Data belum tersedia</div>')
            return
        x, y, period_text = series
        values = pd.to_numeric(y, errors="coerce").tolist()
        current = values[-1]
        previous = values[-2] if len(values) > 1 else None
        delta = None if previous is None else current - previous
        md(
            f'<div class="cardbar" style="background:{meta["color"]}"></div>'
            f'<div class="adem-kpi-label">{esc(meta["label"])}</div>'
            f'<div class="adem-kpi-value">{format_macro_value(current, meta["key"])}<small>{esc(meta["unit"])}</small></div>'
            f'<div class="adem-kpi-target">{esc(meta["target_text"])}</div>'
            f'<span class="adem-kpi-delta {_delta_class(delta)}">{esc(format_macro_delta(delta, meta["key"]))}</span>'
        )
        show_chart(sparkline_figure(x, y, meta["color"]), key=f"spk_adem_{idx}")
        md(f'<div class="adem-kpi-date">Data: {esc(period_text)}</div>')


def pdb_growth_chart(growth: pd.DataFrame, cut: pd.Timestamp, height: int = 300):
    g = growth[(growth["komponen"] == "PDB Aggregate") & (growth["tanggal"] <= cut)].dropna(subset=["yoy"]).tail(12)
    values = [float(v) for v in g["yoy"]]
    labels = [f"Q{t.quarter}<br>{t.year}" for t in g["tanggal"]]
    target = SIMULASI_MAKRO_DEFAULTS[0][1]  # target pertumbuhan APBN

    # Sumbu Y dipersempit mengikuti data (tidak dimulai dari nol), kelipatan 0,5
    lo = math.floor((min(values + [target]) - 0.5) * 2) / 2
    hi = math.ceil((max(values + [target]) + 0.5) * 2) / 2

    fig = go.Figure()
    fig.add_hline(
        y=target, line_dash="dash", line_color=C_ACCENT, line_width=1.6,
        annotation_text=f"Target APBN {_idn(target, 1)}%", annotation_position="top left",
        annotation_font=dict(size=10, color=C_ACCENT),
    )
    fig.add_trace(go.Scatter(
        x=labels, y=values, mode="lines+markers+text", name="PDB (yoy)",
        line=dict(color=C_PRIMARY_LIGHT, width=3.2, shape="spline", smoothing=0.6),
        marker=dict(size=8, color="#FFFFFF", line=dict(color=C_PRIMARY_LIGHT, width=2.4)),
        fill="tozeroy", fillcolor="rgba(43,90,168,0.10)",
        text=[_idn(v, 2) for v in values[:-1]] + [""], textposition="top center",
        textfont=dict(size=10, color=C_PRIMARY),
        hovertemplate="%{x}<br><b>%{y:.2f}%</b><extra></extra>",
    ))
    # Titik terakhir disorot
    fig.add_trace(go.Scatter(
        x=labels[-1:], y=values[-1:], mode="markers+text", showlegend=False,
        marker=dict(size=14, color=C_ACCENT, line=dict(color="#FFFFFF", width=3)),
        text=[f"<b>{_idn(values[-1], 2)}%</b>"], textposition="top center",
        textfont=dict(size=13, color=C_PRIMARY),
        hovertemplate="%{x}<br><b>%{y:.2f}%</b><extra></extra>",
    ))
    style_figure(fig, height)
    fig.update_layout(margin=dict(l=8, r=16, t=22, b=8))
    fig.update_yaxes(range=[lo, hi], dtick=0.5, tickformat=".1f", ticksuffix="%", tickfont=dict(size=10, color=C_TEXT3))
    fig.update_xaxes(tickfont=dict(size=10, color="#4A5568"), showline=True, linecolor="#DDE2EC")
    return fig


# ---- Kartu komposisi PDB (data: Database_Dashboard_triwulanan.xlsx) ----
EXP_NAMES = ["Konsumsi RT", "Konsumsi Pemerintah", "PMTB", "Ekspor", "Impor"]
# Nama komponen di Excel triwulanan -> nama komponen pada sheet 'realisasi' (untuk pertumbuhan yoy pengeluaran)
EXP_TO_REALISASI = {"Konsumsi RT": "Konsumsi RT", "Konsumsi Pemerintah": "PKP", "PMTB": "PMTB", "Ekspor": "Ekspor", "Impor": "Impor"}
PROD_SHORT = {"Manufaktur": "Ind. Pengolahan"}
SHARE_COLORS = {
    "Kons. RT": "#156082", "PMTB": "#20B6B2", "Kons. Pem.": "#FFC000", "Net Ekspor": "#A02B93", "Lainnya": "#85CFB4",
    "Ind. Pengolahan": "#156082", "Perdagangan": "#20B6B2", "Pertanian": "#FFC000", "Konstruksi": "#A02B93",
    "Lainnya (sektor)": "#808ED2", "Pertambangan": "#F2AA84",
}
C_DIST_PREV, C_DIST_NOW = "#808ED2", "#0070C0"
C_GROW_PREV, C_GROW_NOW = "#85CFB4", "#00B050"


def prev_year_date(ts: pd.Timestamp) -> pd.Timestamp:
    return (pd.Period(ts, freq="Q") - 4).end_time.normalize()


def stacked_share_chart(labels, series, height: int = 215):
    fig = go.Figure()
    for name, values, color in series:
        fig.add_trace(go.Bar(
            x=labels, y=[None if pd.isna(v) else float(v) for v in values], name=name, marker_color=color,
            hovertemplate=name + "<br>%{y:.2f} p.p.<extra></extra>",
        ))
    style_figure(fig, height, legend=True)
    fig.update_layout(
        barmode="relative", margin=dict(l=8, r=8, t=34, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=9)),
    )
    fig.update_yaxes(ticksuffix="%", tickfont=dict(size=9), zeroline=True, zerolinecolor="#B8C2D3")
    fig.update_xaxes(tickfont=dict(size=10))
    return fig


def compare_bar_chart(labels, prev_vals, now_vals, prev_name, now_name, colors, height: int = 210):
    fig = go.Figure()
    for name, vals, color in ((prev_name, prev_vals, colors[0]), (now_name, now_vals, colors[1])):
        fig.add_trace(go.Bar(
            x=labels, y=[None if v is None or pd.isna(v) else float(v) for v in vals], name=name, marker_color=color,
            hovertemplate=name + " · %{x}<br>%{y:.2f}%<extra></extra>",
        ))
    style_figure(fig, height, legend=True)
    fig.update_layout(
        barmode="group", margin=dict(l=8, r=8, t=30, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=9)),
    )
    fig.update_yaxes(ticksuffix="%", tickfont=dict(size=9), zeroline=True, zerolinecolor="#B8C2D3")
    fig.update_xaxes(tickfont=dict(size=9))
    return fig


def component_growth_value(tri: dict, growth_long: Optional[pd.DataFrame], comp: str, ts: pd.Timestamp):
    """Pertumbuhan yoy (%) satu komponen. Prioritas: kolom 'pertumbuhan_<nama>' di Excel triwulanan;
    cadangan (khusus pengeluaran): dihitung dari sheet 'realisasi'."""
    gdf = tri.get("growth")
    if gdf is not None and comp in gdf.columns and ts in gdf.index and pd.notna(gdf.at[ts, comp]):
        return float(gdf.at[ts, comp])
    key = EXP_TO_REALISASI.get(comp)
    if key and growth_long is not None:
        hit = growth_long[(growth_long["komponen"] == key) & (growth_long["tanggal"] == ts)]["yoy"].dropna()
        if not hit.empty:
            return float(hit.iloc[0])
    return None


def render_share_cards(tri: Optional[dict], tri_status: str, growth_long: Optional[pd.DataFrame], cut: pd.Timestamp):
    """Dua kartu Share to Growth (pengeluaran & produksi) - kolom kanan baris pertama."""
    if tri is None:
        with card("share-exp"):
            md('<div class="card-title">Share to Growth menurut Komponen</div>')
            st.info(tri_status)
        return
    stg = tri["stg"]
    idx = stg.index[stg.index <= cut][-3:]
    if len(idx) == 0:
        st.info("Data share to growth belum tersedia untuk periode ini.")
        return
    labels = [quarter_label(t) for t in idx]
    zero = pd.Series(0.0, index=idx)
    col = lambda name: stg.loc[idx, name] if name in stg.columns else zero  # noqa: E731

    # --- Pengeluaran: Kons. RT, PMTB, Kons. Pem., Net Ekspor (= Ekspor - Impor), Lainnya (sisa terhadap PDB)
    core = {
        "Kons. RT": col("Konsumsi RT"), "PMTB": col("PMTB"),
        "Kons. Pem.": col("Konsumsi Pemerintah"), "Net Ekspor": col("Ekspor") - col("Impor"),
    }
    series_exp = [(n, v.tolist(), SHARE_COLORS[n]) for n, v in core.items()]
    if growth_long is not None:
        total = (growth_long[(growth_long["komponen"] == "PDB Aggregate") & (growth_long["tanggal"].isin(idx))]
                 .set_index("tanggal")["yoy"].reindex(idx))
        if total.notna().all():
            series_exp.append(("Lainnya", (total - sum(core.values())).tolist(), SHARE_COLORS["Lainnya"]))
    with card("share-exp"):
        md('<div class="card-title">Share to Growth menurut Komponen Pengeluaran</div>'
           '<div class="card-subtitle">3 Kuartal Terakhir</div>')
        show_chart(stacked_share_chart(labels, series_exp), key="chart_share_exp")

    # --- Produksi: 4 sektor utama, Lainnya (sektor sisanya), Pertambangan
    prod_cols = [c for c in stg.columns if c not in EXP_NAMES]
    main_sectors = [c for c in ["Manufaktur", "Perdagangan", "Pertanian", "Konstruksi"] if c in prod_cols]
    rest = [c for c in prod_cols if c not in main_sectors and c != "Pertambangan"]
    series_prod = [(PROD_SHORT.get(c, c), stg.loc[idx, c].tolist(), SHARE_COLORS[PROD_SHORT.get(c, c)]) for c in main_sectors]
    if rest:
        series_prod.append(("Lainnya", stg.loc[idx, rest].sum(axis=1).tolist(), SHARE_COLORS["Lainnya (sektor)"]))
    if "Pertambangan" in prod_cols:
        series_prod.append(("Pertambangan", stg.loc[idx, "Pertambangan"].tolist(), SHARE_COLORS["Pertambangan"]))
    with card("share-prod"):
        md('<div class="card-title">Share to Growth menurut Komponen Produksi</div>'
           '<div class="card-subtitle">3 Kuartal Terakhir</div>')
        if series_prod:
            show_chart(stacked_share_chart(labels, series_prod), key="chart_share_prod")
        else:
            st.info("Kolom share to growth lapangan usaha belum ada di Excel.")


def render_distribusi_cards(tri: dict, growth_long: Optional[pd.DataFrame], cut: pd.Timestamp):
    """Dua kartu Distribusi & Pertumbuhan (pengeluaran & produksi) - baris penuh."""
    dist = tri["dist"]
    valid = dist.index[dist.index <= cut]
    if len(valid) == 0:
        st.info("Data distribusi belum tersedia untuk periode ini.")
        return
    t = valid[-1]
    tp = prev_year_date(t)
    now_name, prev_name = quarter_label(t), quarter_label(tp)
    has_prev = tp in dist.index
    sub = f"{now_name} vs {prev_name} (yoy)"

    def dist_vals(cols, ts, signed_import=False):
        if ts not in dist.index:
            return [None] * len(cols)
        return [(-1 if (signed_import and c == "Impor") else 1) * float(dist.at[ts, c]) if c in dist.columns else None for c in cols]

    left, right = st.columns(2, gap="medium")

    # --- Pengeluaran
    with left:
        with card("dist-exp"):
            comps = [("Kons. RT", "Konsumsi RT"), ("PMTB", "PMTB"), ("Ekspor", "Ekspor"), ("Kons. Pem.", "Konsumsi Pemerintah"), ("Impor", "Impor")]
            labels, names = [c[0] for c in comps], [c[1] for c in comps]
            md(f'<div class="card-title">Distribusi &amp; Pertumbuhan menurut Komponen Pengeluaran</div>'
               f'<div class="card-subtitle">{esc(sub)}</div><div class="mini-label">Distribusi (%)</div>')
            show_chart(compare_bar_chart(labels, dist_vals(names, tp, True) if has_prev else [None] * len(names),
                                         dist_vals(names, t, True), prev_name, now_name, (C_DIST_PREV, C_DIST_NOW)),
                       key="chart_dist_exp_share")
            md('<div class="mini-label">Pertumbuhan (%, yoy)</div>')
            g_now = [component_growth_value(tri, growth_long, c, t) for c in names]
            g_prev = [component_growth_value(tri, growth_long, c, tp) for c in names]
            show_chart(compare_bar_chart(labels, g_prev, g_now, prev_name, now_name, (C_GROW_PREV, C_GROW_NOW)),
                       key="chart_dist_exp_growth")

    # --- Produksi: 5 sektor dengan distribusi terbesar
    with right:
        with card("dist-prod"):
            prod_cols = [c for c in dist.columns if c not in EXP_NAMES]
            top = dist.loc[t, prod_cols].dropna().sort_values(ascending=False).head(5).index.tolist()
            labels = [PROD_SHORT.get(c, c) for c in top]
            md(f'<div class="card-title">Distribusi &amp; Pertumbuhan menurut Komponen Produksi</div>'
               f'<div class="card-subtitle">{esc(sub)} &middot; 5 sektor distribusi terbesar</div>'
               f'<div class="mini-label">Distribusi (%)</div>')
            show_chart(compare_bar_chart(labels, dist_vals(top, tp) if has_prev else [None] * len(top),
                                         dist_vals(top, t), prev_name, now_name, (C_DIST_PREV, C_DIST_NOW)),
                       key="chart_dist_prod_share")
            md('<div class="mini-label">Pertumbuhan (%, yoy)</div>')
            g_now = [component_growth_value(tri, growth_long, c, t) for c in top]
            g_prev = [component_growth_value(tri, growth_long, c, tp) for c in top]
            if any(v is not None for v in g_now):
                show_chart(compare_bar_chart(labels, g_prev, g_now, prev_name, now_name, (C_GROW_PREV, C_GROW_NOW)),
                           key="chart_dist_prod_growth")
                sources = {tri.get("growth_source", {}).get(c) for c in top} - {None}
                if sources:
                    desc = {"konstan": "nilai harga konstan (pertumbuhan riil)", "nominal": "nilai nominal (termasuk efek harga)"}
                    shown = " dan ".join(desc[x] for x in sorted(sources))
                    md(f'<div class="hint">Pertumbuhan lapangan usaha dihitung dari {shown}, yoy terhadap kuartal yang sama tahun lalu.</div>')
            else:
                md('<div class="hint" style="padding:18px 0">Data pertumbuhan lapangan usaha belum tersedia. '
                   'Tambahkan kolom <b>kons_&lt;nama sektor&gt;</b> (harga konstan), <b>nom_&lt;nama sektor&gt;</b> atau '
                   '<b>pertumbuhan_&lt;nama sektor&gt;</b> (yoy, %) pada sheet PDB agar grafik ini muncul.</div>')


def render_ringkasan(ind_df: Optional[pd.DataFrame], ind_status: str, pdb_history: Optional[dict],
                     tri_data: Optional[dict] = None, tri_status: str = ""):
    if ind_df is None:
        page_title("Ringkasan Ekonomi Makro")
        st.error(ind_status)
        return

    periods = (
        ind_df["Periode"].dt.to_period("M").drop_duplicates().sort_values(ascending=False).tolist()[:24]
    )
    head_l, head_ai, head_r = st.columns([4.3, 1.5, 1.4])
    with head_l:
        page_title("Ringkasan Ekonomi Makro")
    with head_r:
        selected = st.selectbox(
            "Periode data", periods, key="filter_periode_ringkasan",
            format_func=lambda p: f"{BULAN_ID[p.month - 1]} {p.year}", label_visibility="collapsed",
        )
    as_of_end = selected.end_time.normalize()
    cut = min(as_of_end, last_realized_date())
    with head_ai:
        if ai_button("ringkasan"):
            show_ai_assistant(
                "Ringkasan Ekonomi Makro", f"Data sampai {BULAN_ID[selected.month - 1]} {selected.year}",
                build_facts_ringkasan(ind_df, as_of_end, pdb_history, tri_data, cut),
            )

    section_header("Asumsi Dasar Ekonomi Makro")
    for start in range(0, len(ADEM_CARDS), 4):
        cols = st.columns(4, gap="medium")
        for i, meta in enumerate(ADEM_CARDS[start:start + 4]):
            with cols[i]:
                render_adem_card(meta, adem_series(meta["key"], ind_df, as_of_end, pdb_history), start + i)

    section_header("Pertumbuhan Ekonomi")
    growth_long = pdb_history["growth"] if pdb_history and pdb_history.get("growth") is not None else None

    left, right = st.columns(2, gap="medium")
    with left:
        with card("pdb-growth"):
            md('<div class="card-title">Pertumbuhan Ekonomi Indonesia <small>(%, yoy)</small></div>'
               '<div class="card-subtitle">Sumber: BPS · Data Triwulanan (12 kuartal terakhir)</div>')
            if growth_long is None:
                st.info("Data historis PDB belum tersedia.")
            else:
                show_chart(pdb_growth_chart(growth_long, cut, height=520), key="chart_pdb_growth")
    with right:
        render_share_cards(tri_data, tri_status, growth_long, cut)

    if tri_data is not None:
        render_distribusi_cards(tri_data, growth_long, cut)


# =========================
# Halaman: Ringkasan Indikator Ekonomi Terkini
# =========================
LEADING_INDICATORS = [
    "Indeks Keyakinan Konsumen", "Indeks Penjualan Riil", "Mandiri Spending Index",
    "Penjualan Mobil", "Penjualan Motor", "PMI Manufaktur",
    "Penjualan Semen", "Penjualan Listrik", "Penjualan BBM",
]
LEI_TITLES = {
    "PMI Manufaktur": "PMI Manufaktur Indonesia",
    "Penjualan Listrik": "Konsumsi Listrik",
    "Penjualan BBM": "Konsumsi BBM",
}
COMMODITY_INDICATORS = [
    "Crude oil, Brent", "Coal, Australia", "Palm oil", "Emas", "Nickel",
    "Tembaga", "Natural gas, Japan", "Aluminum", "Timah", "Iron ore, cfr spot",
]
INDICATOR_META = {
    "Indeks Keyakinan Konsumen": ("Bank Indonesia", "indeks", "level"),
    "Indeks Penjualan Riil": ("Bank Indonesia", "indeks", "level"),
    "Mandiri Spending Index": ("Bank Mandiri Institute", "indeks", "level"),
    "Penjualan Mobil": ("Gaikindo", "%, yoy", "yoy"),
    "Penjualan Motor": ("AISI", "%, yoy", "yoy"),
    "PMI Manufaktur": ("S&P Global", "indeks", "level"),
    "Penjualan Semen": ("Asosiasi Semen Indonesia", "%, yoy", "yoy"),
    "Penjualan Listrik": ("PLN", "%, yoy", "yoy"),
    "Penjualan BBM": ("Pertamina", "%, yoy", "yoy"),
}
COMMODITY_META = {
    "Crude oil, Brent": ("Minyak Brent", "USD/barel"), "Coal, Australia": ("Batubara", "USD/ton"),
    "Palm oil": ("CPO", "USD/ton"), "Emas": ("Emas", "USD/troy ounce"), "Nickel": ("Nikel", "USD/ton"),
    "Tembaga": ("Tembaga", "USD/ton"), "Natural gas, Japan": ("Natural Gas", "USD/MMBtu"),
    "Aluminum": ("Aluminium", "USD/ton"), "Timah": ("Timah", "USD/ton"),
    "Iron ore, cfr spot": ("Besi (Iron Ore)", "USD/ton"),
}
COMMODITY_GRADIENTS = [
    "linear-gradient(135deg,#1A3A6B,#2B5AA8)", "linear-gradient(135deg,#1C2B4A,#2E4070)",
    "linear-gradient(135deg,#1A3A6B,#163260)", "linear-gradient(135deg,#1A3A6B,#253D6E)",
    "linear-gradient(135deg,#1A3A6B,#1E3560)", "linear-gradient(135deg,#8A4A1E,#B86A2C)",
    "linear-gradient(135deg,#1E3D3A,#2A5450)", "linear-gradient(135deg,#39424E,#4E5C6E)",
    "linear-gradient(135deg,#2F3A5E,#47558A)", "linear-gradient(135deg,#3A3A3E,#55565C)",
]
LEI_COLORS = [C_PRIMARY_LIGHT, C_GREEN, C_PURPLE, C_TEAL, C_ACCENT, C_RED, C_ORANGE, "#E83E8C", C_PRIMARY]


def _latest_valid(series: pd.Series):
    valid = pd.to_numeric(series, errors="coerce").dropna()
    return None if valid.empty else float(valid.iloc[-1])


def _format_indicator_value(value, unit: str, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "—"
    sign = "+" if signed and value > 0 else ""
    decimals = 1 if abs(value) < 1000 else 0
    return sign + _idn(value, decimals) + ("%" if "%" in unit else "")


def _change_pct(current, previous):
    if current is None or previous is None or pd.isna(current) or pd.isna(previous) or previous == 0:
        return None
    return (current / previous - 1.0) * 100.0


def render_leading_card(df: pd.DataFrame, indicator: str, color: str, idx: int):
    source, unit, mode = INDICATOR_META[indicator]
    data = df[["Periode", indicator]].copy().sort_values("Periode")
    data[indicator] = pd.to_numeric(data[indicator], errors="coerce")
    # YoY dihitung dari seluruh histori (basis t-12), baru dipotong 24 bulan terakhir.
    data["display"] = data[indicator] if mode == "level" else data[indicator].pct_change(periods=12, fill_method=None) * 100
    data = data.dropna(subset=["display"]).tail(24)

    with card(f"lei-{idx}"):
        if data.empty:
            md(f'<div class="lei-title">{esc(LEI_TITLES.get(indicator, indicator))}</div>'
               f'<div class="lei-sub">Data belum tersedia</div>')
            return
        current = float(data["display"].iloc[-1])
        md(
            f'<div class="lei-title">{esc(LEI_TITLES.get(indicator, indicator))}</div>'
            f'<div class="lei-sub">{esc(source)} · {esc(periode_label(data["Periode"].iloc[-1]))}</div>'
            f'<div class="lei-value-row"><span class="lei-value">{_format_indicator_value(current, unit, mode == "yoy")}</span>'
            f'<span class="lei-unit">{esc(unit)}</span></div>'
        )
        show_chart(sparkline_figure(data["Periode"], data["display"], color, height=115), key=f"spk_lei_{idx}")


def build_commodity_card_html(df: pd.DataFrame, indicator: str, gradient: str) -> str:
    title, unit = COMMODITY_META[indicator]
    data = df[["Periode", indicator]].copy()
    data[indicator] = pd.to_numeric(data[indicator], errors="coerce")
    data = data.dropna(subset=["Periode", indicator]).sort_values("Periode")
    if data.empty:
        return ""
    latest = data.iloc[-1]
    current = float(latest[indicator])
    dt = pd.Timestamp(latest["Periode"])
    prev = data.iloc[-2][indicator] if len(data) > 1 else None
    prev_year = data.loc[data["Periode"] <= dt - pd.DateOffset(years=1), indicator]
    prev_dec = data.loc[data["Periode"] < pd.Timestamp(dt.year, 1, 1), indicator]
    metrics = [
        ("MoM", _change_pct(current, prev)),
        ("YoY", _change_pct(current, float(prev_year.iloc[-1]) if not prev_year.empty else None)),
        ("YtD", _change_pct(current, float(prev_dec.iloc[-1]) if not prev_dec.empty else None)),
        ("C-to-C", _change_pct(current, float(data.iloc[0][indicator]))),
    ]
    rows = ""
    for label, val in metrics:
        direction = "up" if (val is not None and val >= 0) else "down"
        dot = f'<span class="kom-dot-{direction}"></span> ' if val is not None else ""
        shown = "—" if val is None else ("+" if val > 0 else "−" if val < 0 else "") + _idn(abs(val), 1) + "%"
        rows += (f'<div class="komoditas-row"><span class="komoditas-row-label">{label}</span>'
                 f'<span class="komoditas-row-val kom-{direction}">{dot}{shown}</span></div>')
    value_decimals = 2 if abs(current) < 10 else 1 if abs(current) < 1000 else 0
    return (
        f'<div class="komoditas-card" style="background:{gradient}">'
        f'<div class="komoditas-name">{esc(title)}</div>'
        f'<div class="komoditas-unit">{esc(unit)}</div>'
        f'<div class="komoditas-date">Data {esc(periode_label(dt))}</div>'
        f'<div class="komoditas-value">{_idn(current, value_decimals)}</div>'
        f'<div class="komoditas-rows">{rows}</div></div>'
    )


def render_indicator_summary(ind_df: Optional[pd.DataFrame], ind_status: str):
    head_l, head_ai = st.columns([5.8, 1.5])
    with head_l:
        page_title("Ringkasan Indikator Ekonomi Terkini", "Leading Economic Indicators &amp; Harga Komoditas")
    if ind_df is None:
        st.error(ind_status)
        return
    with head_ai:
        if ai_button("indikator"):
            show_ai_assistant(
                "Ringkasan Indikator Ekonomi Terkini",
                f"Data sampai {periode_label(ind_df['Periode'].max())}",
                build_facts_indikator(ind_df),
            )

    section_header("Leading Economic Indicators", "Data 2 tahun terakhir")
    available = [c for c in LEADING_INDICATORS if c in ind_df.columns]
    for start in range(0, len(available), 4):
        cols = st.columns(4, gap="medium")
        for i, indicator in enumerate(available[start:start + 4]):
            with cols[i]:
                render_leading_card(ind_df, indicator, LEI_COLORS[(start + i) % len(LEI_COLORS)], start + i)

    section_header("Harga Komoditas Utama", "Data dashboard indikator")
    cards_html = "".join(
        build_commodity_card_html(ind_df, ind, COMMODITY_GRADIENTS[i % len(COMMODITY_GRADIENTS)])
        for i, ind in enumerate(COMMODITY_INDICATORS) if ind in ind_df.columns
    )
    md(f'<div class="komoditas-grid">{cards_html}</div>')



# =========================
# Editor simulasi (input shock)
# =========================
def _notice(state_key: str):
    notice = st.session_state.pop(state_key, None)
    if notice:
        level, msg = notice
        getattr(st, level if level in {"success", "warning", "error", "info"} else "info")(msg)


def render_simulasi_fiskal_editor() -> pd.DataFrame:
    md('<div class="sub-title">Jenis <em>Shock</em> (dalam miliar Rupiah)</div>')
    editable_cols = ["out_tw3", "out_tw4"]

    st.session_state.setdefault("simulasi_fiskal_editor_version", 0)
    if "simulasi_fiskal_draft" not in st.session_state:
        st.session_state["simulasi_fiskal_draft"] = get_simulasi_fiskal_df().copy()

    draft_df = st.session_state["simulasi_fiskal_draft"].copy()
    draft_df["indikator"] = SIMULASI_FISKAL_ROWS
    draft_df["out_tw1"] = 0.0  # Q1 dan Q2 sudah realisasi -> tidak ditampilkan, selalu 0
    draft_df["out_tw2"] = 0.0
    for col in editable_cols:
        draft_df[col] = pd.to_numeric(draft_df.get(col, 0.0), errors="coerce").fillna(0.0)

    edited_view = editor_stretch(
        draft_df[["indikator", *editable_cols]],
        key=f"simulasi_fiskal_editor_{st.session_state['simulasi_fiskal_editor_version']}",
        hide_index=True,
        num_rows="fixed",
        disabled=["indikator"],
        column_config={
            "indikator": st.column_config.TextColumn("Simulasi Fiskal", width="large"),
            "out_tw3": st.column_config.NumberColumn("Q3", format="%.2f", step=0.01, width="small"),
            "out_tw4": st.column_config.NumberColumn("Q4", format="%.2f", step=0.01, width="small"),
        },
    )

    edited_df = build_simulasi_fiskal_df()
    edited_df["indikator"] = SIMULASI_FISKAL_ROWS
    for col in editable_cols:
        edited_df[col] = pd.to_numeric(edited_view[col], errors="coerce").fillna(0.0)
    st.session_state["simulasi_fiskal_draft"] = edited_df.copy()

    c1, c2, _ = st.columns([1, 1, 1.4])
    if c1.button("Mulai", type="primary", key="btn_fiskal_mulai"):
        st.session_state["simulasi_fiskal_df"] = edited_df.copy()
        st.session_state["simulasi_fiskal_notice"] = ("success", "Simulasi fiskal berhasil diterapkan.")
        st.rerun()
    if c2.button("Reset", key="btn_fiskal_reset"):
        reset_df = build_simulasi_fiskal_df()
        st.session_state["simulasi_fiskal_df"] = reset_df.copy()
        st.session_state["simulasi_fiskal_draft"] = reset_df.copy()
        st.session_state["simulasi_fiskal_editor_version"] += 1
        st.session_state["simulasi_fiskal_notice"] = ("success", "Simulasi fiskal telah di-reset.")
        st.rerun()
    _notice("simulasi_fiskal_notice")
    return get_simulasi_fiskal_df()


def build_simulasi_makro_pdb_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"indikator": ["ICP (USD/barrel)", "Inflasi (%)"], "target_apbn": [70.0, 2.5], "shock_makro": [None, None]}
    )


def get_simulasi_makro_pdb_df() -> pd.DataFrame:
    if "simulasi_makro_pdb_df" not in st.session_state:
        st.session_state["simulasi_makro_pdb_df"] = build_simulasi_makro_pdb_df()
    df = st.session_state["simulasi_makro_pdb_df"].copy()
    df["indikator"] = ["ICP (USD/barrel)", "Inflasi (%)"]
    df["target_apbn"] = [70.0, 2.5]
    df["shock_makro"] = pd.to_numeric(df.get("shock_makro"), errors="coerce")
    return df[["indikator", "target_apbn", "shock_makro"]]


def render_simulasi_makro_pdb_editor() -> pd.DataFrame:
    md('<div class="sub-title">Simulasi Makro</div>')
    st.session_state.setdefault("simulasi_makro_pdb_editor_version", 0)
    if "simulasi_makro_pdb_draft" not in st.session_state:
        st.session_state["simulasi_makro_pdb_draft"] = get_simulasi_makro_pdb_df().copy()

    draft_df = st.session_state["simulasi_makro_pdb_draft"].copy()
    draft_df["indikator"] = ["ICP (USD/barrel)", "Inflasi (%)"]
    draft_df["target_apbn"] = [70.0, 2.5]
    draft_df["shock_makro"] = pd.to_numeric(draft_df.get("shock_makro"), errors="coerce")

    edited_df = editor_stretch(
        draft_df[["indikator", "target_apbn", "shock_makro"]],
        key=f"simulasi_makro_pdb_editor_{st.session_state['simulasi_makro_pdb_editor_version']}",
        hide_index=True,
        num_rows="fixed",
        disabled=["indikator", "target_apbn"],
        column_config={
            "indikator": st.column_config.TextColumn("Indikator", width="medium"),
            "target_apbn": st.column_config.NumberColumn("Target APBN", format="%.1f", width="small"),
            "shock_makro": st.column_config.NumberColumn("Shock Makro", format="%.1f", step=0.1, width="small"),
        },
    )
    edited_df = edited_df.copy()
    edited_df["indikator"] = ["ICP (USD/barrel)", "Inflasi (%)"]
    edited_df["target_apbn"] = [70.0, 2.5]
    edited_df["shock_makro"] = pd.to_numeric(edited_df["shock_makro"], errors="coerce")
    st.session_state["simulasi_makro_pdb_draft"] = edited_df.copy()

    md('<div class="hint">Dampak shock makro ditampilkan pada Outlook Full Year (kolom paling kanan di grafik).</div>')
    c1, c2, _ = st.columns([1, 1, 1.4])
    if c1.button("Mulai", type="primary", key="apply_simulasi_makro_pdb"):
        st.session_state["simulasi_makro_pdb_df"] = edited_df.copy()
        st.session_state["simulasi_makro_pdb_notice"] = ("success", "Simulasi makro berhasil diterapkan.")
        st.rerun()
    if c2.button("Reset", key="reset_simulasi_makro_pdb"):
        reset_df = build_simulasi_makro_pdb_df()
        st.session_state["simulasi_makro_pdb_df"] = reset_df.copy()
        st.session_state["simulasi_makro_pdb_draft"] = reset_df.copy()
        st.session_state["simulasi_makro_pdb_editor_version"] += 1
        st.session_state["simulasi_makro_pdb_notice"] = ("success", "Simulasi makro telah di-reset.")
        st.rerun()
    _notice("simulasi_makro_pdb_notice")
    return get_simulasi_makro_pdb_df()


def render_simulasi_makro_editor() -> pd.DataFrame:
    md('<div class="sub-title">Simulasi <em>Shock</em> Asumsi Dasar Ekonomi Makro (ADEM)</div>')
    st.session_state.setdefault("simulasi_makro_editor_version", 0)
    if "simulasi_makro_draft" not in st.session_state:
        st.session_state["simulasi_makro_draft"] = get_simulasi_makro_df().copy()

    draft_df = st.session_state["simulasi_makro_draft"].copy()
    draft_df["indikator"] = [row[0] for row in SIMULASI_MAKRO_DEFAULTS]
    draft_df["apbn_2026"] = [row[1] for row in SIMULASI_MAKRO_DEFAULTS]
    draft_df["shock"] = pd.to_numeric(draft_df.get("shock"), errors="coerce")

    view_df = draft_df[["indikator", "apbn_2026", "shock"]].copy()
    view_df["indikator"] = SIMULASI_MAKRO_LABEL_PENDEK
    edited_df = editor_stretch(
        view_df,
        key=f"simulasi_makro_editor_{st.session_state['simulasi_makro_editor_version']}",
        hide_index=True,
        num_rows="fixed",
        disabled=["indikator", "apbn_2026"],
        column_config={
            "indikator": st.column_config.TextColumn("Asumsi Dasar Ekonomi Makro", width="medium"),
            "apbn_2026": st.column_config.NumberColumn(f"APBN {TAHUN}", format="%.1f", width="small"),
            "shock": st.column_config.NumberColumn("Shock", format="%.1f", step=0.1, width="small", help="Diisi manual"),
        },
    )
    edited_df = edited_df.copy()
    edited_df["indikator"] = [row[0] for row in SIMULASI_MAKRO_DEFAULTS]
    edited_df["apbn_2026"] = [row[1] for row in SIMULASI_MAKRO_DEFAULTS]
    edited_df["shock"] = pd.to_numeric(edited_df["shock"], errors="coerce")
    st.session_state["simulasi_makro_draft"] = edited_df.copy()

    applied_df = get_simulasi_makro_df()
    has_pending = not edited_df[["shock"]].reset_index(drop=True).equals(applied_df[["shock"]].reset_index(drop=True))

    c1, c2, _ = st.columns([1, 1, 1.4])
    if c1.button("Mulai", type="primary", key="btn_sadem_mulai"):
        st.session_state["simulasi_makro_df"] = edited_df.copy()
        st.session_state["simulasi_makro_notice"] = ("success", "Input shock makro berhasil diterapkan.")
        st.rerun()
    if c2.button("Reset", key="btn_sadem_reset"):
        reset_df = build_simulasi_makro_df()
        st.session_state["simulasi_makro_df"] = reset_df.copy()
        st.session_state["simulasi_makro_draft"] = reset_df.copy()
        st.session_state["simulasi_makro_editor_version"] += 1
        st.session_state["simulasi_makro_notice"] = ("success", "Kolom shock makro dikosongkan kembali.")
        st.rerun()
    st.caption(
        "Ada perubahan input shock yang belum diterapkan - klik Mulai."
        if has_pending else "Input shock makro sudah sinkron."
    )
    _notice("simulasi_makro_notice")
    return applied_df


# =========================
# Tabel & grafik dampak PDB (halaman Simulasi Fiskal)
# =========================
def _lookup_value(df: pd.DataFrame, indikator: str, col: str):
    if df is None or df.empty or "indikator" not in df.columns or col not in df.columns:
        return None
    mask = df["indikator"].astype(str).str.strip() == indikator
    if not mask.any():
        return None
    series = pd.to_numeric(df.loc[mask, col], errors="coerce")
    return None if series.empty else series.iloc[0]


def _cell_class(base, comp, tol: float = 5e-4) -> str:
    if comp is None or base is None or pd.isna(comp) or pd.isna(base):
        return ""
    diff = float(comp) - float(base)
    if abs(diff) <= tol:
        return "cell-eq"
    return "cell-hi" if diff > 0 else "cell-lo"


def build_impact_table_html(baseline_df, shock_fiskal_df, shock_makro_df, formatter) -> str:
    def prep(df):
        return ensure_schema(df, "pdb") if df is not None and "indikator" in df.columns else df

    baseline_df, shock_fiskal_df = prep(baseline_df), prep(shock_fiskal_df)
    shock_makro_df = shock_fiskal_df.copy() if shock_makro_df is None else prep(shock_makro_df)

    head = (
        '<div class="impact-wrap"><table class="impact-tbl"><thead><tr>'
        '<th rowspan="2" style="text-align:left;vertical-align:middle;min-width:110px">Indikator</th>'
        '<th rowspan="2" class="grp-hdr">Realisasi Q1</th><th rowspan="2" class="grp-hdr">Realisasi Q2</th>'
        '<th colspan="2" class="grp-hdr">Q3</th><th colspan="2" class="grp-hdr">Q4</th>'
        '<th colspan="3" class="grp-hdr">Full Year</th></tr><tr>'
        '<th class="sub-hdr">Baseline</th><th class="sub-hdr">Shock Fiskal</th>'
        '<th class="sub-hdr">Baseline</th><th class="sub-hdr">Shock Fiskal</th>'
        '<th class="sub-hdr">Baseline</th><th class="sub-hdr">Shock Fiskal</th><th class="sub-hdr">Shock Makro</th>'
        '</tr></thead><tbody>'
    )
    body = ""
    for indikator in PDB_MAIN_ROWS:
        row_cls = "ttl-row" if indikator == "PDB Aggregate" else ""
        cells = f"<td>{esc(indikator)}</td>"
        for col in ["out_tw1", "out_tw2"]:
            cells += f"<td>{formatter(_lookup_value(baseline_df, indikator, col))}</td>"
        for col in ["out_tw3", "out_tw4"]:
            base, fiskal = _lookup_value(baseline_df, indikator, col), _lookup_value(shock_fiskal_df, indikator, col)
            cells += f"<td>{formatter(base)}</td><td class=\"{_cell_class(base, fiskal)}\">{formatter(fiskal)}</td>"
        base_fy = _lookup_value(baseline_df, indikator, "full_year")
        fiskal_fy = _lookup_value(shock_fiskal_df, indikator, "full_year")
        makro_fy = _lookup_value(shock_makro_df, indikator, "full_year")
        cells += (
            f"<td>{formatter(base_fy)}</td>"
            f"<td class=\"{_cell_class(base_fy, fiskal_fy)}\">{formatter(fiskal_fy)}</td>"
            f"<td class=\"{_cell_class(base_fy, makro_fy)}\">{formatter(makro_fy)}</td>"
        )
        body += f'<tr class="{row_cls}">{cells}</tr>'
    legend = (
        '</tbody></table></div><div class="legend-row">'
        '<span><i style="background:#E8F7EE;border:1px solid #1A8A4A"></i>Lebih tinggi dari baseline</span>'
        '<span><i style="background:#FDECEA;border:1px solid #C0392B"></i>Lebih rendah dari baseline</span>'
        '<span><i style="background:#EEF1F6;border:1px solid #DDE2EC"></i>Sama dengan baseline</span></div>'
    )
    return head + body + legend


def projection_chart(baseline_yoy, fiskal_yoy, makro_yoy):
    categories = ["Q1", "Q2", "Q3", "Q4", "Full Year"]

    def values(df, only=None):
        out = []
        for col in PERIOD_ORDER:
            if only is not None and col not in only:
                out.append(None)
                continue
            v = _lookup_value(df, "PDB Aggregate", col)
            out.append(None if v is None or pd.isna(v) else float(v))
        return out

    series = [
        ("Baseline", values(baseline_yoy), C_PRIMARY_LIGHT),
        ("Shock Fiskal", values(fiskal_yoy, {"out_tw3", "out_tw4", "full_year"}), C_ACCENT),
        ("Shock Makro", values(makro_yoy, {"full_year"}), C_TEAL),
    ]
    fig = go.Figure()
    for name, vals, color in series:
        fig.add_trace(go.Bar(
            x=categories, y=vals, name=name, marker_color=color,
            text=[("" if v is None else f"{v:.2f}") for v in vals], textposition="outside", cliponaxis=False,
            hovertemplate=name + " %{x}<br>%{y:.2f}%<extra></extra>",
        ))
    style_figure(fig, 400, legend=True)
    fig.update_layout(barmode="group", margin=dict(l=8, r=8, t=28, b=8))
    fig.update_yaxes(ticksuffix="%", rangemode="tozero")
    return fig


# =========================
# Historis PDB
# =========================
HIST_COLORS = [C_PRIMARY_LIGHT, C_ACCENT, C_GREEN, C_PURPLE, C_RED, C_TEAL, "#E83E8C", C_PRIMARY]


def _history_figure(df: pd.DataFrame, value_col: str, selected, title: str, as_pct: bool):
    fig = go.Figure()
    for i, comp in enumerate(selected):
        part = df[df["komponen"] == comp]
        fig.add_trace(go.Scatter(
            x=part["tanggal"], y=part[value_col], mode="lines+markers", name=comp,
            line=dict(color=HIST_COLORS[i % len(HIST_COLORS)], width=2.4), marker=dict(size=5),
            hovertemplate=comp + "<br>%{x|%Y-%m-%d}<br>%{y:,.2f}" + ("%" if as_pct else "") + "<extra></extra>",
        ))
    style_figure(fig, 380, legend=True)
    fig.update_layout(hovermode="x unified", title=dict(text=title, font=dict(size=13)), margin=dict(l=8, r=8, t=44, b=8))
    fig.update_yaxes(zeroline=as_pct, ticksuffix="%" if as_pct else "")
    return fig


def render_history_section(pdb_history: Optional[dict]):
    section_header("Historis PDB")
    with card("historis"):
        selected = st.multiselect(
            "Pilih komponen historis yang ingin ditampilkan", options=PDB_COMPONENTS, default=[],
            placeholder="Pilih satu atau beberapa komponen PDB",
        )
        tab_level, tab_yoy, tab_qtq = st.tabs(["Historis Level", "Year on Year (YoY)", "Quarter to Quarter (QtQ)"])
        if not pdb_history or pdb_history.get("level") is None or pdb_history["level"].empty:
            for tab in (tab_level, tab_yoy, tab_qtq):
                with tab:
                    st.info("Data historis PDB belum tersedia.")
            return
        growth_sel = [c for c in selected if c not in EXCLUDE_GROWTH_ROWS]
        with tab_level:
            show_chart(_history_figure(pdb_history["level"], "nilai", selected, "Nilai PDB (level)", False), "hist_level")
        with tab_yoy:
            show_chart(_history_figure(pdb_history["growth"], "yoy", growth_sel, "Pertumbuhan Year on Year (YoY)", True), "hist_yoy")
        with tab_qtq:
            show_chart(_history_figure(pdb_history["growth"], "qtq", growth_sel, "Pertumbuhan Quarter to Quarter (QtQ)", True), "hist_qtq")


# =========================
# Halaman: Simulasi Fiskal
# =========================
def compute_simulation_state(pdb_nominal_raw: pd.DataFrame, pdb_history, pdb_tables) -> dict:
    simulasi_fiskal_df = get_simulasi_fiskal_df()
    simulasi_makro_pdb_df = get_simulasi_makro_pdb_df()

    baseline_nominal = ensure_full_year_from_quarters(pdb_nominal_raw)
    adjusted_nominal = apply_simulasi_fiskal_to_pdb_nominal(baseline_nominal.copy(), simulasi_fiskal_df)
    macro_nominal = apply_simulasi_makro_to_pdb_nominal(adjusted_nominal.copy(), simulasi_makro_pdb_df)

    baseline_yoy = pdb_tables["yoy"] if pdb_tables else empty_df("pdb")
    baseline_qtq = pdb_tables["qtq"] if pdb_tables else empty_df("pdb")
    adjusted_top = build_adjusted_top_growth_tables(pdb_history, adjusted_nominal)
    adjusted_yoy = adjusted_top.get("yoy", empty_df("pdb"))
    adjusted_qtq = adjusted_top.get("qtq", empty_df("pdb"))
    # Shock makro hanya mengubah Full Year; Q1-Q4 tetap hasil shock fiskal.
    macro_yoy = build_full_year_yoy_from_nominal(pdb_history, macro_nominal, adjusted_yoy)

    return dict(
        simulasi_fiskal_df=simulasi_fiskal_df, simulasi_makro_pdb_df=simulasi_makro_pdb_df,
        baseline_nominal=baseline_nominal, adjusted_nominal=adjusted_nominal, macro_nominal=macro_nominal,
        baseline_yoy=baseline_yoy, adjusted_yoy=adjusted_yoy, macro_yoy=macro_yoy,
        baseline_qtq=baseline_qtq, adjusted_qtq=adjusted_qtq, macro_qtq=adjusted_qtq.copy(),
    )


def render_simulasi_fiskal(state: dict, pdb_history: Optional[dict]):
    page_title("Simulasi Fiskal", "Shock Fiskal terhadap Pertumbuhan Ekonomi")

    left, right = st.columns([44, 56], gap="medium")
    with left:
        with card("shock-fiskal"):
            render_simulasi_fiskal_editor()
        with card("shock-makro"):
            render_simulasi_makro_pdb_editor()
    with right:
        with card("proyeksi-pdb"):
            md('<div class="sub-title">Proyeksi PDB &ndash; Skenario Shock <small style="font-weight:400;color:#8898AA">'
               '(% yoy)</small></div><div class="hint">Baseline vs skenario shock fiskal dan makro</div>')
            show_chart(projection_chart(state["baseline_yoy"], state["adjusted_yoy"], state["macro_yoy"]), "chart_proyeksi_pdb")

    with card("impact"):
        md('<div class="card-title">Dampak ke Komponen &amp; Agregat PDB</div>')
        tab_yoy, tab_nilai, tab_qtq = st.tabs(["Year on Year (YoY)", f"Nilai PDB {TAHUN}", "Quarter to Quarter (QtQ)"])
        with tab_yoy:
            md(build_impact_table_html(state["baseline_yoy"], state["adjusted_yoy"], state["macro_yoy"], fmt_pct))
        with tab_nilai:
            md(build_impact_table_html(state["baseline_nominal"], state["adjusted_nominal"], state["macro_nominal"], fmt_id0))
        with tab_qtq:
            md(build_impact_table_html(state["baseline_qtq"], state["adjusted_qtq"], state["macro_qtq"], fmt_pct))

    render_history_section(pdb_history)


# =========================
# Halaman: Sensitivitas APBN
# =========================
def compute_apbn_impacts(simulasi_makro_df: Optional[pd.DataFrame]) -> dict:
    """Dampak shock ADEM terhadap komponen APBN (miliar rupiah). Koefisien sama dengan versi sebelumnya."""
    d_pp_growth = calculate_pertumbuhan_ekonomi_tax_impact(simulasi_makro_df) or 0.0
    d_pp_infl = calculate_inflasi_tax_impact(simulasi_makro_df) or 0.0
    d_bpp_sun = calculate_sun_10y_bpp_impact(simulasi_makro_df) or 0.0
    kurs = calculate_nilai_tukar_impacts(simulasi_makro_df)
    minyak = calculate_harga_minyak_impacts(simulasi_makro_df)
    lift_minyak = calculate_lifting_minyak_impacts(simulasi_makro_df)
    lift_gas = calculate_lifting_gas_bumi_impacts(simulasi_makro_df)

    return {
        "pp": d_pp_growth + d_pp_infl + kurs["pp"] + minyak["pp"] + lift_minyak["pp"] + lift_gas["pp"],
        "pnbp": kurs["pnbp"] + minyak["pnbp"] + lift_minyak["pnbp"] + lift_gas["pnbp"],
        "hibah": 0.0,
        "bpp": d_bpp_sun + kurs["bpp"] + minyak["bpp"],
        "tkd": 0.0,
    }


def fmt_miliar(value, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "-"
    rounded = round(float(value))
    text = f"{abs(rounded):,.0f}".replace(",", ".")
    if rounded < 0:
        return f"({text})"
    return ("+" if signed and rounded > 0 else "") + text


def fmt_pct_signed(value, decimals: int = 2, suffix: str = "%") -> str:
    if value is None or pd.isna(value):
        return "-"
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f"{sign}{_idn(abs(value), decimals)}{suffix}"


def build_apbn_table_html(dampak: dict) -> str:
    base = APBN_BASE
    a_base = base["pp"] + base["pnbp"] + base["hibah"]
    b_base = base["bpp"] + base["tkd"]
    c_base = a_base - b_base
    a_imp = dampak["pp"] + dampak["pnbp"] + dampak["hibah"]
    b_imp = dampak["bpp"] + dampak["tkd"]
    c_imp = a_imp - b_imp
    pdb_nominal = abs(c_base) / (abs(APBN_DEFISIT_PDB_PCT) / 100.0)

    # (kelas, uraian, baseline, dampak, True bila kenaikan dampak = baik)
    rows = [
        ("grp", "A. Pendapatan Negara dan Hibah", a_base, a_imp, True),
        ("sub", "1. Penerimaan Perpajakan", base["pp"], dampak["pp"], True),
        ("sub", "2. Penerimaan Negara Bukan Pajak", base["pnbp"], dampak["pnbp"], True),
        ("sub", "3. Hibah", base["hibah"], dampak["hibah"], True),
        ("grp", "B. Belanja Negara", b_base, b_imp, False),
        ("sub", "1. Belanja Pemerintah Pusat", base["bpp"], dampak["bpp"], False),
        ("sub", "2. Transfer ke Daerah", base["tkd"], dampak["tkd"], False),
        ("grp", "C. Surplus/Defisit", c_base, c_imp, True),
        ("spec", "Surplus/Defisit (% PDB)", None, None, True),
        ("grp", "D. Pembiayaan Anggaran", -c_base, -c_imp, False),
    ]
    body = ""
    for kind, label, b, imp, up_good in rows:
        if kind == "spec":
            imp_pct = c_imp / pdb_nominal * 100.0
            cls = "" if abs(imp_pct) < 0.005 else "sa-pos" if imp_pct > 0 else "sa-neg"
            body += (
                f'<tr class="spec"><td>{label}</td>'
                f'<td class="nc">{_idn(APBN_DEFISIT_PDB_PCT, 2)}%</td>'
                f'<td class="nc {cls}">{fmt_pct_signed(imp_pct, 2, " p.p.") if cls else "-"}</td>'
                f'<td class="nc">{_idn(APBN_DEFISIT_PDB_PCT + imp_pct, 2)}%</td><td class="nc">-</td></tr>'
            )
            continue
        outlook = b + imp
        pct = imp / abs(b) * 100.0 if b else 0.0
        good = imp > 0 if up_good else imp < 0
        cls = "" if abs(imp) < 0.5 else "sa-pos" if good else "sa-neg"
        pct_cls = "" if abs(pct) < 0.005 else cls
        body += (
            f'<tr class="{kind}"><td>{esc(label)}</td>'
            f'<td class="nc">{fmt_miliar(b)}</td>'
            f'<td class="nc {cls}">{fmt_miliar(imp, True) if cls else "-"}</td>'
            f'<td class="nc">{fmt_miliar(outlook)}</td>'
            f'<td class="nc {pct_cls}">{fmt_pct_signed(pct) if pct_cls else "-"}</td></tr>'
        )

    head = (
        '<div style="overflow-x:auto"><table class="sadem-apbn-tbl"><thead><tr>'
        '<th style="width:38%">Uraian</th>'
        f'<th class="c" style="width:16%">Baseline<br>(APBN {TAHUN})<br><em>Miliar Rupiah</em></th>'
        '<th class="c" style="width:14%">Dampak<br><em>Miliar Rupiah</em></th>'
        '<th class="c" style="width:14%">Outlook<br><em>Miliar Rupiah</em></th>'
        '<th class="c" style="width:18%">% Dampak terhadap<br>Baseline</th></tr></thead><tbody>'
    )
    return head + body + "</tbody></table></div>"


def render_sensitivitas(simulasi_makro_df: pd.DataFrame):
    page_title(
        "Sensitivitas APBN",
        "Simulasi <em>Shock</em> Asumsi Dasar Ekonomi Makro (ADEM) terhadap Pertumbuhan Ekonomi",
    )
    left, right = st.columns([44, 56], gap="medium")
    with left:
        with card("adem-input"):
            applied = render_simulasi_makro_editor()
    # Tabel dampak memakai input yang SUDAH diterapkan (setelah klik Mulai).
    with right:
        with card("adem-dampak"):
            md('<div class="card-title" style="margin-bottom:10px">Dampak terhadap Outlook APBN</div>')
            md(build_apbn_table_html(compute_apbn_impacts(applied)))
    return applied


# =========================
# Asisten AI: narasi pergerakan data + rujukan berita media tepercaya (tanpa API key / login)
# =========================
TRUSTED_NEWS_DOMAINS = [
    # lembaga resmi
    "bps.go.id", "bi.go.id", "kemenkeu.go.id", "ekon.go.id", "esdm.go.id", "ojk.go.id", "skkmigas.go.id",
    # media nasional / internasional
    "antaranews.com", "kontan.co.id", "bisnis.com", "cnbcindonesia.com", "kompas.com", "kompas.id", "katadata.co.id",
    "tempo.co", "cnnindonesia.com", "investor.id", "beritasatu.com", "mediaindonesia.com", "republika.co.id",
    "tirto.id", "detik.com", "liputan6.com", "bloombergtechnoz.com", "reuters.com", "bloomberg.com",
]
try:
    TRUSTED_NEWS_DOMAINS = list(st.secrets.get("trusted_news_domains", TRUSTED_NEWS_DOMAINS))
    FREE_LLM_URL = str(st.secrets.get("free_llm_url", "https://text.pollinations.ai/"))
except Exception:
    FREE_LLM_URL = "https://text.pollinations.ai/"

TARGET_APBN = {"PDB": 5.4, "Inflasi": 2.5, "Nilai Tukar": 16500.0, "Yield SBN 10 Tahun": 6.9,
               "Harga ICP": 70.0, "Lifting Minyak": 610.0, "Lifting Gas": 984.0}
DELTA_TOL = {"PDB": 0.005, "Inflasi": 0.005, "Yield SBN 10 Tahun": 0.005, "Nilai Tukar": 0.5,
             "Harga ICP": 0.05, "Lifting Minyak": 0.05, "Lifting Gas": 0.05}
ADEM_NEWS = {  # key: (kueri, kata kunci wajib pada judul)
    "PDB": ("pertumbuhan ekonomi Indonesia {period} BPS", ["ekonomi", "pdb"]),
    "Inflasi": ("inflasi Indonesia {period} BPS", ["inflasi"]),
    "Nilai Tukar": ("rupiah dolar AS {period}", ["rupiah"]),
    "Yield SBN 10 Tahun": ("yield SBN 10 tahun {period}", ["sbn", "yield", "obligasi", "surat berharga"]),
    "Harga ICP": ("harga minyak mentah Indonesia ICP {period}", ["icp", "minyak"]),
    "Lifting Minyak": ("lifting minyak dan gas bumi {period} SKK Migas", ["lifting"]),
    "Lifting Gas": ("lifting minyak dan gas bumi {period} SKK Migas", ["lifting"]),
}
LEI_NEWS = {
    "Indeks Keyakinan Konsumen": ("Indeks Keyakinan Konsumen Bank Indonesia {period}", ["keyakinan konsumen"]),
    "Indeks Penjualan Riil": ("Indeks Penjualan Riil Bank Indonesia {period}", ["penjualan riil"]),
    "Mandiri Spending Index": ("Mandiri Spending Index {period}", ["mandiri spending"]),
    "Penjualan Mobil": ("penjualan mobil Gaikindo {period}", ["mobil", "gaikindo"]),
    "Penjualan Motor": ("penjualan sepeda motor AISI {period}", ["motor", "aisi"]),
    "PMI Manufaktur": ("PMI Manufaktur Indonesia {period}", ["pmi"]),
    "Penjualan Semen": ("penjualan semen Indonesia {period}", ["semen"]),
    "Penjualan Listrik": ("konsumsi listrik PLN {period}", ["listrik"]),
    "Penjualan BBM": ("konsumsi BBM Pertamina {period}", ["bbm", "bahan bakar"]),
}
COMMODITY_NEWS = {
    "Crude oil, Brent": ("harga minyak Brent {period}", ["brent", "minyak"]),
    "Coal, Australia": ("harga batu bara {period}", ["batu bara", "batubara"]),
    "Palm oil": ("harga CPO {period}", ["cpo", "sawit"]),
    "Emas": ("harga emas dunia {period}", ["emas"]),
    "Nickel": ("harga nikel {period}", ["nikel"]),
    "Tembaga": ("harga tembaga {period}", ["tembaga"]),
    "Natural gas, Japan": ("harga gas alam {period}", ["gas"]),
    "Aluminum": ("harga aluminium {period}", ["aluminium", "aluminum"]),
    "Timah": ("harga timah {period}", ["timah"]),
    "Iron ore, cfr spot": ("harga bijih besi {period}", ["bijih besi"]),
}
ROMAWI = {1: "I", 2: "II", 3: "III", 4: "IV"}


def md_safe(text: str) -> str:
    return str(text).replace("$", "\\$")


def _host(url: str) -> str:
    host = urlparse(str(url)).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _is_trusted(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in TRUSTED_NEWS_DOMAINS)


def parse_news_rss(xml_bytes: bytes, keywords=None, max_items: int = 3) -> list:
    """Urai RSS Google News; simpan hanya berita dari domain tepercaya dan yang judulnya memuat kata kunci."""
    root = ET.fromstring(xml_bytes)
    keywords = [k.lower() for k in (keywords or [])]
    items, seen = [], set()
    for it in root.iter("item"):
        src = it.find("source")
        host = _host(src.get("url", "")) if src is not None else ""
        if not _is_trusted(host):
            continue
        raw_title = (it.findtext("title") or "").strip()
        title = raw_title.rsplit(" - ", 1)[0].strip() if " - " in raw_title else raw_title
        if not title or title in seen or (keywords and not any(k in title.lower() for k in keywords)):
            continue
        date_text = ""
        try:
            d = parsedate_to_datetime(it.findtext("pubDate"))
            date_text = f"{d.day} {BULAN_ID[d.month - 1][:3]} {d.year}"
        except Exception:
            pass
        items.append({"title": title, "source": ((src.text or host) if src is not None else host).strip(),
                      "url": (it.findtext("link") or "").strip(), "date": date_text})
        seen.add(title)
        if len(items) >= max_items:
            break
    return items


def _fetch_news_raw(query: str, keywords, days: int, max_items: int = 2) -> list:
    url = "https://news.google.com/rss/search?q=" + quote_plus(f"{query} when:{days}d") + "&hl=id&gl=ID&ceid=ID:id"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; DashboardDJSEF/1.0)"})
    with urlopen(req, timeout=12) as resp:
        data = resp.read()
    return parse_news_rss(data, keywords, max_items)


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_news_bundle(topics_json: str) -> dict:
    """Ambil berita untuk banyak topik secara paralel. Gagal total -> exception (tidak ikut di-cache)."""
    topics = json.loads(topics_json)

    def work(topic):
        try:
            return topic["label"], _fetch_news_raw(topic["query"], topic["keywords"], topic["days"]), None
        except Exception as exc:  # noqa: BLE001
            return topic["label"], [], exc

    results, errors = {}, 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for label, items, err in pool.map(work, topics):
            results[label] = items
            errors += err is not None
    if topics and errors == len(topics):
        raise RuntimeError("Layanan berita tidak dapat diakses.")
    return results


def _clean_llm_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            text = obj["choices"][0]["message"]["content"]
        except Exception:
            pass
    kept = [p for p in re.split(r"\n{2,}", text) if "pollinations" not in p.lower()]  # buang iklan/pemberitahuan layanan
    return "\n\n".join(kept).strip()


@st.cache_data(show_spinner=False, ttl=3600)
def llm_narrative(messages_json: str) -> str:
    """Panggil AI gratis tanpa login. Gagal -> exception (tidak ikut di-cache)."""
    payload = json.dumps({"messages": json.loads(messages_json), "model": "openai", "private": True}).encode("utf-8")
    req = Request(FREE_LLM_URL, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", "replace")
    text = _clean_llm_text(raw)
    if len(text) < 80:
        raise RuntimeError("Respons AI kosong atau terlalu pendek.")
    return text


def build_llm_messages(page_title: str, facts: list, news: dict) -> list:
    system = (
        "Anda adalah analis ekonomi makro di Direktorat Jenderal Strategi Ekonomi dan Fiskal, Kementerian Keuangan RI. "
        "Tulis narasi analitis singkat (3-4 paragraf, maksimal 280 kata) dalam bahasa Indonesia formal berdasarkan DATA dan BERITA yang diberikan. "
        "Aturan: (1) hanya gunakan angka yang tercantum pada DATA, jangan menambah angka atau fakta lain; "
        "(2) kaitkan pergerakan data dengan konteks dari BERITA dan sebutkan nama media dalam kurung, misalnya (Kontan); "
        "(3) jika berita tidak ada atau tidak relevan, jelaskan pergerakan data saja dan nyatakan konteks berita belum tersedia; "
        "(4) jangan memberi rekomendasi kebijakan; (5) tanpa judul dan tanpa butir/bullet."
    )
    data_text = "\n".join(f"- {f['sentence']}" for f in facts)
    news_lines = []
    for label, items in news.items():
        for item in items:
            news_lines.append(f"[{label}] {item['title']} ({item['source']}, {item['date']})")
    user = f"Halaman: {page_title}\n\nDATA:\n{data_text}\n\nBERITA:\n" + ("\n".join(news_lines) if news_lines else "(tidak ada berita yang ditemukan)")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ---- Fakta & kalimat narasi dari data dashboard ----
def value_phrase(key: str, v: float) -> str:
    if key in {"PDB", "Inflasi", "Yield SBN 10 Tahun"}:
        return f"{_idn(v, 2)}%"
    if key == "Nilai Tukar":
        return f"Rp{_idn(v, 0)} per US$"
    if key == "Harga ICP":
        return f"US${_idn(v, 1)} per barel"
    if key == "Lifting Minyak":
        return f"{_idn(v, 1)} ribu barel per hari"
    return f"{_idn(v, 1)} ribu BOEPD"


def delta_phrase(key: str, d: float) -> str:
    d = abs(d)
    if key in {"PDB", "Inflasi", "Yield SBN 10 Tahun"}:
        return f"{_idn(d, 2)} poin persentase"
    if key == "Nilai Tukar":
        return f"Rp{_idn(d, 0)}"
    if key == "Harga ICP":
        return f"US${_idn(d, 1)}"
    return f"{_idn(d, 1)} ribu"


def target_phrase(key: str, cur: float, target: float) -> str:
    diff = cur - target
    if abs(diff) <= DELTA_TOL.get(key, 0.005) * 2:
        return f"sejalan dengan asumsi APBN ({value_phrase(key, target)})"
    return f"{'di atas' if diff > 0 else 'di bawah'} asumsi APBN ({value_phrase(key, target)}) sebesar {delta_phrase(key, diff)}"


def _magnitude(values: list) -> float:
    s = pd.Series(values, dtype="float64").dropna()
    if len(s) < 3:
        return 0.0
    step = s.diff().dropna()
    return float(abs(step.iloc[-1]) / (step.std() + 1e-9))


def _period_query(period_text: str) -> str:
    m = re.match(r"^Q([1-4])\s+(\d{4})$", period_text)
    return f"kuartal {ROMAWI[int(m.group(1))]} {m.group(2)}" if m else period_text


def build_facts_ringkasan(ind_df: pd.DataFrame, as_of_end: pd.Timestamp, pdb_history: Optional[dict],
                          tri_data: Optional[dict], cut: pd.Timestamp) -> list:
    facts = []
    for meta in ADEM_CARDS:
        key = meta["key"]
        series = adem_series(key, ind_df, as_of_end, pdb_history)
        if series is None:
            continue
        _, y, period_text = series
        vals = pd.to_numeric(pd.Series(list(y)), errors="coerce").dropna().tolist()
        if not vals:
            continue
        cur, prev = vals[-1], (vals[-2] if len(vals) > 1 else None)
        unit_time, pembanding = ("kuartal", "kuartal sebelumnya") if key == "PDB" else ("bulan", "bulan sebelumnya")
        parts = [f"{meta['label']} tercatat {value_phrase(key, cur)} pada {period_text}"]
        if prev is not None:
            d = cur - prev
            if abs(d) <= DELTA_TOL.get(key, 0.005):
                parts.append(f"relatif stabil dibanding {pembanding}")
            else:
                parts.append(f"{'naik' if d > 0 else 'turun'} {delta_phrase(key, d)} dibanding {pembanding}")
        if key in TARGET_APBN:
            parts.append(target_phrase(key, cur, TARGET_APBN[key]))
        if len(vals) >= 6 and cur >= max(vals):
            parts.append(f"dan merupakan level tertinggi dalam {len(vals)} {unit_time} terakhir")
        elif len(vals) >= 6 and cur <= min(vals):
            parts.append(f"dan merupakan level terendah dalam {len(vals)} {unit_time} terakhir")
        query, kw = ADEM_NEWS[key]
        facts.append({"label": meta["label"], "sentence": ", ".join(parts) + ".", "magnitude": _magnitude(vals),
                      "query": query.format(period=_period_query(period_text)), "keywords": kw,
                      "days": 120 if key == "PDB" else 60})
    if tri_data is not None:
        facts += composition_facts(tri_data, cut)
    return facts


def composition_facts(tri: dict, cut: pd.Timestamp) -> list:
    stg = tri["stg"]
    idx = stg.index[stg.index <= cut]
    if len(idx) == 0:
        return []
    t = idx[-1]
    row = stg.loc[t]
    q = quarter_label(t)
    out = []

    def get(name):
        v = row.get(name)
        return None if v is None or pd.isna(v) else float(v)

    if all(get(n) is not None for n in ["Konsumsi RT", "Konsumsi Pemerintah", "PMTB", "Ekspor", "Impor"]):
        contrib = {"konsumsi rumah tangga": get("Konsumsi RT"), "konsumsi pemerintah": get("Konsumsi Pemerintah"),
                   "PMTB": get("PMTB"), "net ekspor": get("Ekspor") - get("Impor")}
        ordered = sorted(contrib.items(), key=lambda kv: kv[1], reverse=True)
        top = [f"{n} ({_idn(v, 2)} p.p.)" for n, v in ordered[:2] if v > 0]
        neg = [f"{n} ({_idn(v, 2)} p.p.)" for n, v in ordered if v < 0]
        if top:
            text = f"Dari sisi pengeluaran, pertumbuhan {q} terutama ditopang {' dan '.join(top)}"
            if neg:
                text += f", sementara {' dan '.join(neg)} menahan pertumbuhan"
            out.append({"label": "Komposisi pengeluaran", "sentence": text + ".", "magnitude": 0.0})
    sectors = {c: float(row[c]) for c in stg.columns if c not in EXP_NAMES and pd.notna(row.get(c))}
    if sectors:
        ordered = sorted(sectors.items(), key=lambda kv: kv[1], reverse=True)
        name = lambda n: {"Manufaktur": "industri pengolahan"}.get(n, n.lower() if len(n) > 4 else n)  # noqa: E731
        top = [f"{name(n)} ({_idn(v, 2)} p.p.)" for n, v in ordered[:3] if v > 0]
        neg = [f"{name(n)} ({_idn(v, 2)} p.p.)" for n, v in ordered if v < 0]
        text = f"Dari sisi lapangan usaha, kontribusi terbesar pada {q} berasal dari {', '.join(top)}"
        if neg:
            text += f", sedangkan {' dan '.join(neg)} menahan pertumbuhan"
        out.append({"label": "Komposisi lapangan usaha", "sentence": text + ".", "magnitude": 0.0})
    return out


def lei_metrics(df: pd.DataFrame, indicator: str) -> Optional[dict]:
    if indicator not in df.columns or indicator not in INDICATOR_META:
        return None
    _, unit, mode = INDICATOR_META[indicator]
    data = df[["Periode", indicator]].copy().sort_values("Periode")
    data[indicator] = pd.to_numeric(data[indicator], errors="coerce")
    data["display"] = data[indicator] if mode == "level" else data[indicator].pct_change(periods=12, fill_method=None) * 100
    data = data.dropna(subset=["display"]).tail(24)
    if data.empty:
        return None
    vals = data["display"].tolist()
    return {"cur": vals[-1], "prev": vals[-2] if len(vals) > 1 else None, "vals": vals, "mode": mode,
            "period": periode_label(data["Periode"].iloc[-1])}


def commodity_metrics(df: pd.DataFrame, indicator: str) -> Optional[dict]:
    if indicator not in df.columns:
        return None
    data = df[["Periode", indicator]].copy()
    data[indicator] = pd.to_numeric(data[indicator], errors="coerce")
    data = data.dropna(subset=["Periode", indicator]).sort_values("Periode")
    if len(data) < 2:
        return None
    cur = float(data.iloc[-1][indicator])
    dt = pd.Timestamp(data.iloc[-1]["Periode"])
    prev_year = data.loc[data["Periode"] <= dt - pd.DateOffset(years=1), indicator]
    prev_dec = data.loc[data["Periode"] < pd.Timestamp(dt.year, 1, 1), indicator]
    return {
        "cur": cur, "period": periode_label(dt),
        "mom": _change_pct(cur, float(data.iloc[-2][indicator])),
        "yoy": _change_pct(cur, float(prev_year.iloc[-1]) if not prev_year.empty else None),
        "ytd": _change_pct(cur, float(prev_dec.iloc[-1]) if not prev_dec.empty else None),
        "pct_series": (data[indicator].pct_change() * 100).dropna().tolist(),
    }


def _arah(x: float) -> str:
    return "naik" if x > 0 else "turun"


def build_facts_indikator(ind_df: pd.DataFrame) -> list:
    facts = []
    for ind in LEADING_INDICATORS:
        m = lei_metrics(ind_df, ind)
        if m is None:
            continue
        title = LEI_TITLES.get(ind, ind)
        cur, prev = m["cur"], m["prev"]
        if m["mode"] == "yoy":
            head = f"{title} {'tumbuh' if cur >= 0 else 'terkontraksi'} {_idn(abs(cur), 1)}% (yoy) pada {m['period']}"
            unit_d = "poin persentase"
        else:
            head = f"{title} berada di level {_idn(cur, 1)} pada {m['period']}"
            unit_d = "poin"
        if prev is not None:
            d = cur - prev
            head += (f", relatif stabil dibanding bulan sebelumnya" if abs(d) < 0.05
                     else f", {_arah(d)} {_idn(abs(d), 1)} {unit_d} dibanding bulan sebelumnya")
        if ind == "PMI Manufaktur":
            head += f" ({'ekspansi' if cur > 50 else 'kontraksi' if cur < 50 else 'netral'} karena {'di atas' if cur > 50 else 'di bawah' if cur < 50 else 'tepat di'} 50)"
        if ind == "Indeks Keyakinan Konsumen":
            head += f" ({'optimistis' if cur > 100 else 'pesimistis'} karena {'di atas' if cur > 100 else 'di bawah'} 100)"
        query, kw = LEI_NEWS[ind]
        facts.append({"label": title, "sentence": head + ".", "magnitude": _magnitude(m["vals"]),
                      "query": query.format(period=m["period"]), "keywords": kw, "days": 60})
    for ind in COMMODITY_INDICATORS:
        m = commodity_metrics(ind_df, ind)
        if m is None or m["mom"] is None:
            continue
        title, unit = COMMODITY_META[ind]
        dec = 2 if abs(m["cur"]) < 10 else 1 if abs(m["cur"]) < 1000 else 0
        text = f"Harga {title} ({unit}) berada di {_idn(m['cur'], dec)} pada {m['period']}, {_arah(m['mom'])} {_idn(abs(m['mom']), 1)}% secara bulanan"
        if m["yoy"] is not None:
            text += f", {_arah(m['yoy'])} {_idn(abs(m['yoy']), 1)}% secara tahunan (yoy)"
        if m["ytd"] is not None:
            text += f", dan {_arah(m['ytd'])} {_idn(abs(m['ytd']), 1)}% sejak awal tahun (YtD)"
        mag = 0.0
        if len(m["pct_series"]) >= 3:
            s_ = pd.Series(m["pct_series"][:-1])
            mag = float(abs(m["pct_series"][-1]) / (s_.std() + 1e-9))
        query, kw = COMMODITY_NEWS[ind]
        facts.append({"label": f"Harga {title}", "sentence": text + ".", "magnitude": mag,
                      "query": query.format(period=m["period"]), "keywords": kw, "days": 60})
    return facts


# ---- Tampilan Asisten AI ----
def pick_news_topics(facts: list, max_topics: int = 8) -> list:
    seen, topics = set(), []
    for f in sorted([x for x in facts if x.get("query")], key=lambda x: x["magnitude"], reverse=True):
        if f["query"] in seen:
            continue
        seen.add(f["query"])
        topics.append({"label": f["label"], "query": f["query"], "keywords": f["keywords"], "days": f["days"]})
        if len(topics) >= max_topics:
            break
    return topics


def _render_ai_body(page_title: str, subtitle: str, facts: list):
    if not facts:
        st.info("Belum ada data yang dapat dinarasikan untuk periode ini.")
        return
    if subtitle:
        st.caption(subtitle)

    st.markdown("#### 📊 Pergerakan data")
    st.markdown("\n".join(f"- {md_safe(f['sentence'])}" for f in facts))

    topics = pick_news_topics(facts)
    news, news_error = {}, None
    with st.spinner("Mencari berita dari media tepercaya..."):
        try:
            news = fetch_news_bundle(json.dumps(topics, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            news_error = str(exc)

    st.markdown("#### 🧠 Analisis AI")
    with st.spinner("Menyusun analisis dengan AI gratis..."):
        try:
            narasi = llm_narrative(json.dumps(build_llm_messages(page_title, facts, news), ensure_ascii=False))
            st.markdown(md_safe(narasi))
            st.caption("Disusun oleh layanan AI gratis tanpa login (Pollinations) dari data dashboard dan judul berita di bawah. "
                       "AI dapat keliru, mohon verifikasi ke sumber sebelum dipakai untuk keputusan.")
        except Exception:  # noqa: BLE001
            st.info("Layanan AI gratis sedang tidak dapat diakses, jadi analisis tertulis belum tersedia. "
                    "Narasi pergerakan data di atas tetap disusun otomatis dari angka dashboard.")

    st.markdown("#### 📰 Rujukan berita media tepercaya")
    if news_error:
        st.info("Berita belum dapat diambil saat ini (layanan pencarian berita tidak dapat diakses). Coba lagi beberapa saat lagi.")
    else:
        shown = False
        for label, items in news.items():
            if not items:
                continue
            shown = True
            st.markdown(f"**{md_safe(label)}**")
            st.markdown("\n".join(
                f"- [{md_safe(i['title'])}]({i['url']}) — {md_safe(i['source'])}" + (f", {i['date']}" if i["date"] else "")
                for i in items
            ))
        if not shown:
            st.info("Tidak ditemukan berita yang relevan dari media tepercaya untuk periode ini.")
    st.caption("Berita dicari dari Google News dan dibatasi pada media nasional/internasional terpilih serta situs resmi pemerintah.")


def show_ai_assistant(page_title: str, subtitle: str, facts: list):
    def body():
        _render_ai_body(page_title, subtitle, facts)

    dialog = getattr(st, "dialog", None)
    title = f"🤖 Asisten AI · {page_title}"
    if dialog is not None:
        try:
            dialog(title, width="large")(body)()
            return
        except TypeError:
            try:
                dialog(title)(body)()
                return
            except TypeError:
                pass
    with card("ai-inline"):
        st.markdown(f"### {title}")
        body()


def ai_button(slot: str) -> bool:
    try:
        holder = st.container(key=f"aibtn-{slot}")
    except TypeError:
        holder = st.container()
    with holder:
        return st.button("🤖 Asisten AI", key=f"btn_ai_{slot}", help="Narasi pergerakan data dan rujukan berita media tepercaya")


# =========================
# Topnav, sidebar, dan alur utama
# =========================
MENU_FISKAL = "📐  Simulasi Fiskal"
MENU_SENSITIVITAS = "◔  Sensitivitas APBN"
MENU_RINGKASAN = "▣  Ringkasan Ekonomi"
MENU_INDIKATOR = "▦  Ringkasan Indikator Ekonomi Terkini"
MENU_ITEMS = [MENU_RINGKASAN, MENU_INDIKATOR, MENU_FISKAL, MENU_SENSITIVITAS]


# Gambar tertanam (base64) agar tidak perlu file terpisah di repo:
# lambang Kementerian Keuangan (tanpa teks, latar transparan) dan bendera Merah Putih.
LOGO_KEMENKEU_B64 = "iVBORw0KGgoAAAANSUhEUgAAAGcAAABgCAMAAAA3mpxzAAABgFBMVEVoVybQnR7g39wcaWqRpaiuiydsmpVVc5AnmV1dXV0cHBwxMTEwaJcIYsJZZFmIbifEu6saGxvJwrJNo3eioqKfyLI/Pz9iYmKDeEPPsWbc3Nw8QToAmjz/0Aytt8O01caVhEIDL2gAPYlKPR53wZkAAAALXK37uREOYrP9/PzOmRe0iBoFSpDZohf+ww/mqRIFBQUTVJQyO0aVlpf+/v7q5+eHh4nc3Nw0WHKsqac4ODgWRHPY2NePeDFQV1NlZ2mphiiadRoZGRkLO26nfRhVVVUnWIW3trXKycoDLlpPZGoJCQl1dncVFRUpSGdpakuLahkATKgFmkwBpUtQXGY1RlB1c0pzZTQXMk4nJydXV1dERUV/f39ISEgUFBQmJiYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACsu+AfAAAAYHRSTlP///7///////83mVr//////9f//x//BEP//xH/////////////AP////3////////t////B/7+D////v/+//////+T//8D///////Y//P///////////////9E/gJEq2pzL+F5AAANE0lEQVR42rVZC0PTSBdNoQ9EEFl119V1d78HM3lMJgw03bRp08bGtpbSB9KCsur//xffvTNJk6ZFwP0cEfqY5OSeOffcO4l29MBRTX4eNrQHzn93dPT18Kv8+0Nxjqq7jWJj99UPjefvo6PPZ23DMNpnj+W7HxVP9e3HuuHWXKP+8W31B8UD5310FrjG0zEbPzXc4OzRQ+TwkHi+ntcMo9YlOunii/OvPySeV18aA6N5yXSd6Dq7bBqDxpdX/2ccUPHjYxBA0YdgcOjELxrG6PzzfRWu3VsAfcNt+7qCASDdb7tG/95y0O6l5keHIID+mCUoEomN+7Ec/v4/xfP1/DQWQHaAHMqGcXo/OWh3q/n5lwYs+iVbRVEhXYI0Gl+e361w7W4BnI/gqn2yDiPlcIpyeHynHLR7CWDI9E0wKAc2vJcctDsEcBYYeQHkuQM5GHfK4dvxPEYBVLrkdhgph4qUQ/W74kEB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"
BENDERA_MERAH_PUTIH_B64 = "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"


def render_topnav():
    md(
        '<nav class="topnav"><div class="logo-area"><div class="logo-box">'
        f'<img src="data:image/png;base64,{LOGO_KEMENKEU_B64}" alt="Kementerian Keuangan"></div>'
        '<div class="logo-text"><span>DJSEF</span><span>Kementerian Keuangan RI</span></div></div>'
        '<div class="topnav-title">'
        f'<img src="data:image/png;base64,{BENDERA_MERAH_PUTIH_B64}" alt="Bendera Merah Putih">'
        '<span>Dashboard Monitoring dan Simulasi Ekonomi Nasional</span></div>'
        '<div class="topnav-spacer"></div></nav>'
    )


def render_navbar() -> str:
    """Menu horizontal permanen di bawah judul dashboard."""
    st.session_state.setdefault("menu_aktif", MENU_ITEMS[0])
    with st.container(key="navbar"):
        cols = st.columns([1.15, 1.3, 1.3, 2.5, 3.2], gap="small")
        for i, item in enumerate(MENU_ITEMS):
            with cols[i]:
                is_active = item == st.session_state["menu_aktif"]
                if st.button(item, key=f"nav_{i}", type="primary" if is_active else "secondary"):
                    st.session_state["menu_aktif"] = item
                    st.rerun()
    return st.session_state["menu_aktif"]


def main():
    render_topnav()
    menu = render_navbar()

    pdb_nominal_raw, pdb_history, pdb_tables, source_status = load_dashboard_data()
    ind_df, ind_status = load_indicator_data()
    tri_data, tri_status = load_triwulan_data()
    if pdb_history is None and source_status != "Data tersedia.":
        st.warning(source_status)

    state = compute_simulation_state(pdb_nominal_raw, pdb_history, pdb_tables)
    simulasi_makro_df = get_simulasi_makro_df()

    if menu == MENU_RINGKASAN:
        render_ringkasan(ind_df, ind_status, pdb_history, tri_data, tri_status)
    elif menu == MENU_INDIKATOR:
        render_indicator_summary(ind_df, ind_status)
    elif menu == MENU_FISKAL:
        render_simulasi_fiskal(state, pdb_history)
    elif menu == MENU_SENSITIVITAS:
        simulasi_makro_df = render_sensitivitas(simulasi_makro_df)

    show_preview = st.toggle("Tampilkan preview data mentah", value=False)
    if show_preview:
        with st.expander("Preview data yang berhasil dimuat", expanded=False):
            previews = [
                ("Simulasi fiskal (input)", state["simulasi_fiskal_df"]),
                ("Baseline PDB nominal", state["baseline_nominal"]),
                ("Shock fiskal PDB nominal", state["adjusted_nominal"]),
                ("Shock makro PDB nominal", state["macro_nominal"]),
                ("Baseline YoY", state["baseline_yoy"]),
                ("Shock fiskal YoY", state["adjusted_yoy"]),
                ("Baseline QtQ", state["baseline_qtq"]),
                ("Shock fiskal QtQ", state["adjusted_qtq"]),
                ("Input shock ADEM (Sensitivitas APBN)", simulasi_makro_df),
            ]
            if pdb_history:
                previews += [("Historis level PDB", pdb_history["level"]), ("Pertumbuhan komponen PDB", pdb_history["growth"])]
            for title, frame in previews:
                st.markdown(f"**{title}**")
                st.dataframe(frame, hide_index=True)


main()
