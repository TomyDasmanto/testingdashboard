"""
Dashboard Monitoring dan Simulasi Ekonomi Nasional - DJSEF Kemenkeu
Tampilan mengikuti Dashboard_Simulasi_DJSEF_Kemenkeu_v6.html
Jalankan: streamlit run app_tab_menu.py   (butuh streamlit >= 1.40)
"""
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.request import urlopen
import html

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
.logo-box{width:36px;height:36px;background:#FFFFFF22;border:1.5px solid #FFFFFF44;border-radius:8px;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.logo-text{display:flex;flex-direction:column;}
.logo-text span:first-child{font-size:10px;color:#AFC6E9;font-weight:500;letter-spacing:.5px;text-transform:uppercase;}
.logo-text span:last-child{font-size:12px;color:#fff;font-weight:700;line-height:1.2;}
.topnav-title{flex:1;text-align:center;color:#fff;font-size:15px;font-weight:700;letter-spacing:.3px;}
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
def _find_local_file(candidates) -> Optional[Path]:
    base = Path(__file__).resolve().parent
    for name in candidates:
        path = base / name
        if path.exists():
            return path
    return None


def detect_excel_source() -> Tuple[Optional[Union[str, bytes]], str]:
    local_path = _find_local_file(PDB_FILE_CANDIDATES)
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
    local_path = _find_local_file(INDICATOR_FILE_CANDIDATES)
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


def sparkline_figure(x, y, color: str, height: int = 90):
    y_series = pd.Series(y, dtype="float64").dropna()
    y_range = None
    if not y_series.empty:
        y_min, y_max = float(y_series.min()), float(y_series.max())
        span = (y_max - y_min) or max(abs(y_max) * 0.08, 1.0)
        y_range = [min(0.0, y_min - span * 0.10), y_max + span * 0.22]
    fig = go.Figure(
        go.Scatter(
            x=x, y=y, mode="lines", connectgaps=True,
            line=dict(color=color, width=2.4, shape="spline", smoothing=0.45),
            fill="tozeroy", fillcolor=color + "1A",
            hovertemplate="%{x|%b %Y}<br>%{y:,.2f}<extra></extra>",
        )
    )
    style_figure(fig, height)
    fig.update_layout(margin=dict(l=2, r=2, t=6, b=2))
    fig.update_xaxes(tickformat="%b'%y", nticks=4, fixedrange=True, tickfont=dict(size=9, color=C_TEXT3))
    fig.update_yaxes(showgrid=False, showticklabels=False, range=y_range, fixedrange=True)
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


def pdb_growth_chart(growth: pd.DataFrame, cut: pd.Timestamp):
    g = growth[(growth["komponen"] == "PDB Aggregate") & (growth["tanggal"] <= cut)].dropna(subset=["yoy"]).tail(12)
    fig = go.Figure()
    fig.add_hline(y=5.4, line_dash="dash", line_color=C_ACCENT, line_width=1.4,
                  annotation_text="Target APBN 5,4%", annotation_position="top left",
                  annotation_font=dict(size=10, color=C_ACCENT))
    fig.add_trace(go.Scatter(
        x=[quarter_label(t) for t in g["tanggal"]], y=g["yoy"], mode="lines+markers+text",
        line=dict(color=C_PRIMARY_LIGHT, width=3), marker=dict(size=7, color=C_PRIMARY_LIGHT),
        text=[_idn(v, 2) for v in g["yoy"]], textposition="top center", textfont=dict(size=10, color=C_PRIMARY),
        hovertemplate="%{x}<br>%{y:.2f}%<extra></extra>", name="PDB (yoy)",
    ))
    style_figure(fig, 300)
    fig.update_yaxes(ticksuffix="%", rangemode="tozero")
    return fig


def render_ringkasan(ind_df: Optional[pd.DataFrame], ind_status: str, pdb_history: Optional[dict]):
    if ind_df is None:
        page_title("Ringkasan Ekonomi Makro")
        st.error(ind_status)
        return

    periods = (
        ind_df["Periode"].dt.to_period("M").drop_duplicates().sort_values(ascending=False).tolist()[:24]
    )
    head_l, head_r = st.columns([5, 1.4])
    with head_l:
        page_title("Ringkasan Ekonomi Makro")
    with head_r:
        selected = st.selectbox(
            "Periode data", periods, key="filter_periode_ringkasan",
            format_func=lambda p: f"{BULAN_ID[p.month - 1]} {p.year}", label_visibility="collapsed",
        )
    as_of_end = selected.end_time.normalize()
    cut = min(as_of_end, last_realized_date())

    section_header("Asumsi Dasar Ekonomi Makro")
    for start in range(0, len(ADEM_CARDS), 4):
        cols = st.columns(4, gap="medium")
        for i, meta in enumerate(ADEM_CARDS[start:start + 4]):
            with cols[i]:
                render_adem_card(meta, adem_series(meta["key"], ind_df, as_of_end, pdb_history), start + i)

    section_header("Pertumbuhan Ekonomi")
    if not pdb_history or pdb_history.get("growth") is None:
        st.info("Data historis PDB belum tersedia.")
        return

    growth = pdb_history["growth"]
    with card("pdb-growth"):
        md('<div class="card-title">Pertumbuhan Ekonomi Indonesia <small>(%, yoy)</small></div>'
           '<div class="card-subtitle">Sumber: BPS · Data Triwulanan (12 kuartal terakhir)</div>')
        show_chart(pdb_growth_chart(growth, cut), key="chart_pdb_growth")


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
    page_title("Ringkasan Indikator Ekonomi Terkini", "Leading Economic Indicators &amp; Harga Komoditas")
    if ind_df is None:
        st.error(ind_status)
        return

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
    draft_df["out_tw1"] = 0.0  # Q1 dan Q2 sudah realisasi -> terkunci
    draft_df["out_tw2"] = 0.0
    for col in editable_cols:
        draft_df[col] = pd.to_numeric(draft_df.get(col, 0.0), errors="coerce").fillna(0.0)

    edited_view = editor_stretch(
        draft_df[["indikator", "out_tw1", "out_tw2", *editable_cols]],
        key=f"simulasi_fiskal_editor_{st.session_state['simulasi_fiskal_editor_version']}",
        hide_index=True,
        num_rows="fixed",
        disabled=["indikator", "out_tw1", "out_tw2"],
        column_config={
            "indikator": st.column_config.TextColumn("Simulasi Fiskal", width="medium"),
            "out_tw1": st.column_config.NumberColumn("Q1 🔒", format="%.2f", width="small", help="Sudah realisasi"),
            "out_tw2": st.column_config.NumberColumn("Q2 🔒", format="%.2f", width="small", help="Sudah realisasi"),
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

    edited_df = editor_stretch(
        draft_df[["indikator", "apbn_2026", "shock"]],
        key=f"simulasi_makro_editor_{st.session_state['simulasi_makro_editor_version']}",
        hide_index=True,
        num_rows="fixed",
        disabled=["indikator", "apbn_2026"],
        column_config={
            "indikator": st.column_config.TextColumn("Asumsi Dasar Ekonomi Makro", width="large"),
            "apbn_2026": st.column_config.NumberColumn(f"APBN {TAHUN}", format="%.1f", width="small"),
            "shock": st.column_config.NumberColumn("Shock (diisi manual)", format="%.1f", step=0.1, width="small"),
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
    left, right = st.columns([40, 60], gap="medium")
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
# Topnav, sidebar, dan alur utama
# =========================
MENU_FISKAL = "📐  Simulasi Fiskal"
MENU_SENSITIVITAS = "◔  Sensitivitas APBN"
MENU_RINGKASAN = "▣  Ringkasan Ekonomi"
MENU_INDIKATOR = "▦  Ringkasan Indikator Ekonomi Terkini"
MENU_ITEMS = [MENU_RINGKASAN, MENU_INDIKATOR, MENU_FISKAL, MENU_SENSITIVITAS]


def render_topnav():
    md(
        '<nav class="topnav"><div class="logo-area"><div class="logo-box">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M4 20V13M10 20V8M16 20V11M22 20V4" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg></div><div class="logo-text"><span>DJSEF</span><span>Kementerian Keuangan RI</span></div></div>'
        '<div class="topnav-title">🇮🇩 Dashboard Monitoring dan Simulasi Ekonomi Nasional</div>'
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
    if pdb_history is None and source_status != "Data tersedia.":
        st.warning(source_status)

    state = compute_simulation_state(pdb_nominal_raw, pdb_history, pdb_tables)
    simulasi_makro_df = get_simulasi_makro_df()

    if menu == MENU_RINGKASAN:
        render_ringkasan(ind_df, ind_status, pdb_history)
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
