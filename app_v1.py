from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
import html

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Dashboard Monitoring dan Simulasi Ekonomi Nasional",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

FILE_NAME = "dashboard PDB.xlsx"
try:
    RAW_URL = st.secrets.get("github_raw_xlsx_url", "")
except Exception:
    RAW_URL = ""

QCOLS = ["out_tw1", "out_tw2", "out_tw3", "out_tw4"]
PERIODS = QCOLS + ["full_year"]
LABELS = dict(zip(PERIODS, ["Q1", "Q2", "Q3", "Q4", "Full Year"]))
COMPONENTS = [
    "Konsumsi RT", "Konsumsi LNPRT", "PKP", "PMTB",
    "Change in Stocks", "Ekspor", "Impor", "PDB Aggregate",
]
MAIN_ROWS = ["Konsumsi RT", "PKP", "PMTB", "Ekspor", "Impor", "PDB Aggregate"]
FISCAL_ROWS = [
    "Bantuan Pangan", "Bantuan Langsung Tunai", "Kenaikan Gaji",
    "Pembayaran Gaji 14", "Diskon Transportasi", "Investasi",
]
MACRO_DEFAULTS = [
    ("Pertumbuhan ekonomi (%)", 5.4),
    ("Inflasi (%)", 2.5),
    ("Tingkat bunga SUN 10 tahun", 6.9),
    ("Nilai tukar (Rp100/US$1)", 16500.0),
    ("Harga minyak (US$/barel)", 70.0),
    ("Lifting minyak (ribu barel per hari)", 610.0),
    ("Lifting Gas Bumi (ribu barel setara minyak per hari)", 984.0),
]
DEFAULT_ROWS = {
    "makro": ["Inflasi", "Rupiah", "Yield SBN", "ICP", "Nikel", "Coal", "CPO", "Lifting"],
    "moneter": ["PUAB", "Kredit", "DPK", "M0", "OMO"],
    "fiskal": ["Pendapatan", "Belanja", "Pembiayaan", "Defisit"],
    "pdb": COMPONENTS,
}
COLORS = ["#3E6DB5", "#E07B39", "#2A9D8F", "#8A5CF6", "#D14D72", "#F4A261", "#4C78A8", "#6C8EAD"]

st.markdown(
    """
<style>
:root {
    --navy:#1F4373; --navy-dark:#17375F; --bg:#F4F7FB;
    --border:#D9E2EF; --active:#EAF2FF; --blue:#397CF6;
    --text:#23344D; --title:#14213A; --muted:#66778C;
}
html, body, [class*="css"] {
    font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
}
.stApp {background:var(--bg); color:var(--text);}
header[data-testid="stHeader"] {height:0; background:transparent;}
#MainMenu, footer, div[data-testid="stToolbar"], div[data-testid="stDecoration"] {display:none!important;}
.block-container {max-width:none; padding:6.8rem 2.3rem 3rem; color:var(--text);}

/* Header DJSEF */
.djsef-header {
    position:fixed; z-index:999999; top:0; left:0; right:0; height:84px;
    display:grid; grid-template-columns:320px 1fr 180px; align-items:center;
    color:#FFF; background:linear-gradient(110deg,#1E416F,#214B7E);
    box-shadow:0 3px 12px rgba(15,35,65,.16);
}
.djsef-header, .djsef-header * {color:#FFF!important;}
.djsef-brand {
    height:100%; display:flex; align-items:center; gap:16px; padding-left:22px;
    border-right:1px solid rgba(255,255,255,.08);
}
.djsef-logo {
    width:52px; height:52px; display:flex; align-items:center; justify-content:center;
    border-radius:12px; border:2px solid rgba(255,255,255,.3);
    background:rgba(255,255,255,.1);
}
.djsef-bars {height:27px; display:flex; align-items:flex-end; gap:4px;}
.djsef-bars span {width:4px; border-radius:2px; background:#FFF;}
.djsef-bars span:nth-child(1){height:11px}.djsef-bars span:nth-child(2){height:21px}
.djsef-bars span:nth-child(3){height:16px}.djsef-bars span:nth-child(4){height:27px}
.djsef-brand-name {color:#C7D5E8!important; font-size:16px; font-weight:600;}
.djsef-ministry {font-size:17px; font-weight:700; margin-top:3px;}
.djsef-app-title {text-align:center; font-size:21px; font-weight:700;}
.djsef-profile {display:flex; justify-content:flex-end; align-items:center; gap:22px; padding-right:28px;}
.djsef-bell {position:relative; font-size:22px;}
.djsef-dot {position:absolute; top:0; right:-1px; width:6px; height:6px; border-radius:50%; background:#FF6B7A;}
.djsef-avatar {
    width:48px; height:48px; display:flex; align-items:center; justify-content:center;
    border-radius:50%; font-weight:700; background:linear-gradient(145deg,#568BC6,#2C6099);
    border:2px solid rgba(255,255,255,.28);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    top:84px; height:calc(100vh - 84px); width:320px!important;
    min-width:320px!important; max-width:320px!important;
    background:#FFF; border-right:1px solid #E5EAF1;
}
section[data-testid="stSidebar"] > div {padding-top:1rem;}
section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {padding:0!important;}
.sidebar-title {padding:21px 21px 8px; color:#8A99AC; font-size:14px; font-weight:800; letter-spacing:.08em;}
.sidebar-source {
    margin:18px 20px; padding:12px 13px; border-radius:9px; color:#60748D;
    background:#F5F8FC; border:1px solid #E2E8F0; font-size:12px; line-height:1.45;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label {color:#2F4057;}
section[data-testid="stSidebar"] div[role="radiogroup"] {gap:0;}
section[data-testid="stSidebar"] label[data-baseweb="radio"] {
    width:100%; min-height:55px; margin:0; padding:0 21px; border-radius:0;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {display:none;}
section[data-testid="stSidebar"] label[data-baseweb="radio"] p {
    color:#2F4057!important; font-size:16px; font-weight:500; line-height:1.3;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
    background:var(--active); box-shadow:inset 4px 0 0 var(--blue);
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p {
    color:#123C72!important; font-weight:700;
}

/* Konten dan perbaikan kontras */
.block-container p, .block-container label,
.block-container div[data-testid="stMarkdownContainer"] {color:var(--text);}
.block-container h1, .block-container h2, .block-container h3,
.block-container h4, .block-container h5, .block-container h6 {color:var(--title)!important;}
.page-title {margin:0 0 1.3rem; color:var(--title); font-size:30px; font-weight:750; letter-spacing:-.035em;}
.section-title {
    display:flex; align-items:center; gap:12px; margin:20px 0 15px;
    color:#214679; font-size:19px; font-weight:750;
}
.section-title:after {content:""; height:1px; flex:1; background:#D7E0EC;}
.dashboard-alert {
    display:flex; gap:16px; align-items:center; padding:18px 23px; margin-bottom:30px;
    color:#984919; background:#FFF5E7; border:1px solid #F4A11A;
    border-radius:11px; font-size:16px;
}
.dashboard-alert div {color:#984919!important;}.dashboard-alert strong {color:#8D3E12!important;}
.block-container div[data-testid="stCaptionContainer"] p {color:var(--muted)!important;}
.block-container div[data-testid="stAlert"] p,
.block-container div[data-testid="stAlert"] span {color:var(--text)!important;}

/* Input dan pilihan */
.block-container input, .block-container textarea,
.block-container [data-baseweb="select"] > div,
.block-container [data-baseweb="input"] > div,
.block-container [data-baseweb="base-input"] {
    color:#1F2937!important; background:#FFF!important;
}
.block-container [data-baseweb="select"] span,
.block-container [data-baseweb="tag"] span,
.block-container [data-baseweb="popover"] span,
.block-container [role="option"] {color:#1F2937!important;}
.block-container [data-baseweb="tag"] {background:#EAF2FF!important;}

/* Tab */
.stTabs [data-baseweb="tab-list"] {gap:8px; padding:6px; border-radius:12px; background:#E9EEF6;}
.stTabs [data-baseweb="tab"] {height:44px; padding:0 20px; border-radius:9px; color:#53657D; font-weight:650;}
.stTabs [data-baseweb="tab"] p, .stTabs [data-baseweb="tab"] span {color:#53657D!important;}
.stTabs [aria-selected="true"] {background:var(--navy)!important;}
.stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] span {color:#FFF!important;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {display:none;}

/* Card, tabel, editor, grafik */
div[data-testid="stDataFrame"], div[data-testid="stDataEditor"], div[data-testid="stPlotlyChart"] {
    overflow:hidden; border:1px solid var(--border); border-radius:12px;
    background:#FFF; color:#1F2937!important; box-shadow:0 3px 10px rgba(21,48,82,.06);
}
div[data-testid="stPlotlyChart"] {padding:10px;}
.block-container .stButton button:not([kind="primary"]) {
    color:var(--navy)!important; background:#FFF!important; border:1px solid #B9C6D8!important;
}
.block-container .stButton button:not([kind="primary"]):hover {background:#EEF4FB!important; border-color:var(--navy)!important;}
.block-container .stButton button[kind="primary"],
.block-container .stButton button[kind="primary"] p,
.block-container .stButton button[kind="primary"] span {color:#FFF!important; background:var(--navy)!important;}
.stButton button {min-height:43px; border-radius:9px; font-weight:650;}

/* Tabel perbandingan */
.compare-wrap {overflow-x:auto; border:1px solid var(--border); border-radius:12px; background:#FFF; box-shadow:0 3px 10px rgba(21,48,82,.06);}
.compare-table {border-collapse:collapse; width:100%; min-width:1200px; font-size:.92rem;}
.compare-table th, .compare-table td {border:1px solid #DDE4ED; padding:.6rem .7rem; text-align:center; white-space:nowrap;}
.compare-table th {color:#294766!important; background:#EDF3FA;}
.compare-table td {color:#1F2937; background:#FFF;}
.compare-table th:first-child, .compare-table td:first-child {position:sticky; left:0; z-index:2; text-align:left;}
.compare-table th:first-child {background:#EDF3FA;}.compare-table td:first-child {background:#FFF;}
.compare-table td.up {color:#127A5A!important; background:#E8F7F2; font-weight:700;}
.compare-table td.down {color:#B42318!important; background:#FDEBEC; font-weight:700;}
.compare-table td.missing {color:#6B7280!important; background:#FAFAFA;}
.legend {display:flex; gap:1rem; margin-top:.7rem; color:#66778C; font-size:.85rem;}
.legend span {color:#66778C!important;}.swatch {width:14px; height:14px; border:1px solid #D1D5DB; border-radius:3px; display:inline-block; margin-right:5px;}
.note {color:#66778C!important; font-size:.88rem; margin-top:.55rem;}

/* Tabel fiskal */
.fiscal-table {width:100%; border-collapse:separate; border-spacing:0; border:1px solid var(--border); border-radius:12px; background:#FFF; overflow:hidden;}
.fiscal-table th, .fiscal-table td {padding:.65rem .8rem; border-bottom:1px solid #E2E8F0;}
.fiscal-table th {color:#294766!important; background:#EDF3FA;}.fiscal-table td {color:#1F2937;}

@media(max-width:900px) {
    .djsef-header {grid-template-columns:240px 1fr 100px;}
    .djsef-app-title {font-size:16px;}
    .block-container {padding-left:1rem; padding-right:1rem;}
}
</style>
    """,
    unsafe_allow_html=True,
)


def render_header():
    st.markdown(
        """
<div class="djsef-header">
  <div class="djsef-brand">
    <div class="djsef-logo"><div class="djsef-bars"><span></span><span></span><span></span><span></span></div></div>
    <div><div class="djsef-brand-name">DJSEF</div><div class="djsef-ministry">Kementerian Keuangan RI</div></div>
  </div>
  <div class="djsef-app-title">Dashboard Monitoring dan Simulasi Ekonomi Nasional</div>
  <div class="djsef-profile"><div class="djsef-bell">♧<span class="djsef-dot"></span></div><div class="djsef-avatar">TD</div></div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(status):
    st.sidebar.markdown('<div class="sidebar-title">MENU UTAMA</div>', unsafe_allow_html=True)
    options = [
        "▥  Ringkasan Ekonomi",
        "⌁  Ringkasan Indikator Ekonomi Terkini",
        "▦  Ringkasan Fiskal",
        "♙  Simulasi Fiskal",
        "⌒  Sensitivitas APBN",
        "◎  Simulasi Program Prioritas",
    ]
    selected = st.sidebar.radio("Navigasi", options, label_visibility="collapsed")
    st.sidebar.markdown('<div class="sidebar-title">DOKUMEN</div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div style="padding:14px 21px;color:#2F4057;font-size:16px">▤ &nbsp; Laporan</div>', unsafe_allow_html=True)
    st.sidebar.markdown(f'<div class="sidebar-source"><strong>Sumber Data</strong><br>{html.escape(status)}</div>', unsafe_allow_html=True)
    for symbol in ["▥", "⌁", "▦", "♙", "⌒", "◎"]:
        selected = selected.replace(symbol, "")
    return selected.strip()


def page_title(text):
    st.markdown(f'<div class="page-title">{html.escape(text)}</div>', unsafe_allow_html=True)


def section_title(text):
    st.markdown(f'<div class="section-title">{html.escape(text)}</div>', unsafe_allow_html=True)


def empty_df(block):
    rows = DEFAULT_ROWS[block]
    return pd.DataFrame({"indikator": rows, **{c: [None] * len(rows) for c in PERIODS}})


def normalize(value):
    return str(value).strip().lower().replace(" ", "_").replace(".", "").replace("-", "_")


def fmt_num(value):
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value):
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "%"


def ensure_full_year(df):
    out = df.copy()
    for col in QCOLS:
        if col not in out.columns:
            out[col] = None
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["full_year"] = out[QCOLS].sum(axis=1, min_count=1)
    return out


def detect_excel_source():
    local = Path(__file__).resolve().parent / FILE_NAME
    if local.exists():
        return str(local), f"{FILE_NAME} di folder aplikasi"
    if RAW_URL:
        try:
            with urlopen(RAW_URL) as response:
                return response.read(), "GitHub Raw URL dari st.secrets"
        except Exception as exc:
            return None, f"URL Excel gagal dibaca: {exc}"
    return None, f"{FILE_NAME} belum ditemukan"


def open_excel(source):
    if isinstance(source, bytes):
        return pd.ExcelFile(BytesIO(source), engine="openpyxl")
    return pd.ExcelFile(source, engine="openpyxl")


@st.cache_data(show_spinner=False)
def load_data():
    data = {name: empty_df(name) for name in DEFAULT_ROWS}
    source, status = detect_excel_source()
    if source is None:
        return data, None, None, status
    try:
        xls = open_excel(source)
        sheets = {name.lower().strip(): name for name in xls.sheet_names}
        for block in ["makro", "moneter", "fiskal"]:
            if block in sheets:
                df = pd.read_excel(xls, sheet_name=sheets[block], engine="openpyxl")
                df.columns = [normalize(c) for c in df.columns]
                if "indikator" not in df.columns:
                    df = df.rename(columns={df.columns[0]: "indikator"})
                for col in PERIODS:
                    if col not in df.columns:
                        df[col] = None
                data[block] = df[["indikator", *PERIODS]]

        if "realisasi" not in sheets:
            return data, None, None, status

        raw = pd.read_excel(xls, sheet_name=sheets["realisasi"], engine="openpyxl")
        raw = raw.rename(columns={raw.columns[0]: "tanggal"})
        raw["tanggal"] = pd.to_datetime(raw["tanggal"], errors="coerce")
        raw = raw.dropna(subset=["tanggal"]).sort_values("tanggal").reset_index(drop=True)

        wide = pd.DataFrame({"tanggal": raw["tanggal"]})
        for component in COMPONENTS[:-1]:
            source_col = next((c for c in raw.columns if normalize(c) == normalize(component)), None)
            wide[component] = pd.to_numeric(raw[source_col], errors="coerce") if source_col else None
        discrepancy_col = next((c for c in raw.columns if normalize(c) == normalize("Statistical Discrepancy")), None)
        discrepancy = pd.to_numeric(raw[discrepancy_col], errors="coerce") if discrepancy_col else 0.0
        wide["PDB Aggregate"] = (
            wide["Konsumsi RT"] + wide["Konsumsi LNPRT"] + wide["PKP"] +
            wide["PMTB"] + wide["Change in Stocks"] + wide["Ekspor"] -
            wide["Impor"] + discrepancy
        )

        nominal_rows = []
        for component in COMPONENTS:
            row = {"indikator": component}
            for quarter, col in enumerate(QCOLS, 1):
                selected = wide.loc[
                    (wide["tanggal"].dt.year == 2026) &
                    (wide["tanggal"].dt.quarter == quarter), component
                ]
                row[col] = float(selected.iloc[-1]) if not selected.empty else None
            nominal_rows.append(row)
        data["pdb"] = ensure_full_year(pd.DataFrame(nominal_rows))

        level = wide.melt(id_vars="tanggal", var_name="komponen", value_name="nilai")
        level["nilai_fmt"] = level["nilai"].apply(fmt_num)
        growth_parts, yoy_rows, qtq_rows = [], [], []
        for component in COMPONENTS:
            series = wide[["tanggal", component]].copy()
            series["yoy"] = series[component].pct_change(4, fill_method=None) * 100
            series["qtq"] = series[component].pct_change(1, fill_method=None) * 100
            series["komponen"] = component
            growth_parts.append(series[["tanggal", "komponen", "yoy", "qtq"]])
            yoy_row, qtq_row = {"indikator": component}, {"indikator": component}
            for quarter, col in enumerate(QCOLS, 1):
                selected = series.loc[
                    (series["tanggal"].dt.year == 2026) &
                    (series["tanggal"].dt.quarter == quarter)
                ]
                yoy_row[col] = float(selected["yoy"].iloc[-1]) if not selected.empty else None
                qtq_row[col] = float(selected["qtq"].iloc[-1]) if not selected.empty else None
            annual = series.assign(tahun=series["tanggal"].dt.year).groupby("tahun")[component].sum(min_count=1)
            annual_growth = annual.pct_change(fill_method=None) * 100
            yoy_row["full_year"] = float(annual_growth.loc[2026]) if 2026 in annual_growth.index else None
            qtq_row["full_year"] = None
            yoy_rows.append(yoy_row)
            qtq_rows.append(qtq_row)

        history = {"wide": wide, "level": level, "growth": pd.concat(growth_parts, ignore_index=True)}
        tables = {"yoy": pd.DataFrame(yoy_rows), "qtq": pd.DataFrame(qtq_rows)}
        return data, history, tables, status
    except Exception as exc:
        return data, None, None, f"Gagal membaca Excel: {exc}"


def fiscal_default():
    return pd.DataFrame({"indikator": FISCAL_ROWS, **{col: [0.0] * len(FISCAL_ROWS) for col in QCOLS}})


def macro_default():
    return pd.DataFrame({
        "indikator": [item[0] for item in MACRO_DEFAULTS],
        "apbn_2026": [item[1] for item in MACRO_DEFAULTS],
        "shock": [None] * len(MACRO_DEFAULTS),
    })


def session_df(key, factory):
    if key not in st.session_state:
        st.session_state[key] = factory()
    return st.session_state[key].copy()


def adjust_nominal(base, simulation):
    out = ensure_full_year(base)
    rules = [
        ("Bantuan Pangan", "PKP", [1.82, 1.86, 1.88, 1.91]),
        ("Bantuan Langsung Tunai", "Konsumsi RT", [1.82, 1.84, 1.85, 1.86]),
        ("Kenaikan Gaji", "Konsumsi RT", [1.82, 1.84, 1.85, 1.86]),
        ("Pembayaran Gaji 14", "Konsumsi RT", [1.82, 1.84, 1.85, 1.86]),
        ("Diskon Transportasi", "Konsumsi RT", [1.82, 1.84, 1.85, 1.86]),
        ("Investasi", "PMTB", [1.66, 1.66, 1.67, 1.67]),
    ]
    for simulation_name, target, divisors in rules:
        row = simulation.loc[simulation["indikator"] == simulation_name]
        if row.empty:
            continue
        for col, divisor in zip(QCOLS, divisors):
            raw_value = pd.to_numeric(row.iloc[0][col], errors="coerce")
            addition = 0.0 if pd.isna(raw_value) else float(raw_value) / divisor
            out.loc[out["indikator"] == target, col] += addition
            out.loc[out["indikator"] == "PDB Aggregate", col] += addition
    return ensure_full_year(out)


def adjusted_growth(history, adjusted):
    if not history:
        return {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}
    wide = history["wide"].copy()
    for _, row in adjusted.iterrows():
        if row["indikator"] not in COMPONENTS:
            continue
        for quarter, col in enumerate(QCOLS, 1):
            mask = (wide["tanggal"].dt.year == 2026) & (wide["tanggal"].dt.quarter == quarter)
            wide.loc[mask, row["indikator"]] = row[col]
    yoy_rows, qtq_rows = [], []
    for component in COMPONENTS:
        series = wide[["tanggal", component]].copy()
        series["yoy"] = series[component].pct_change(4, fill_method=None) * 100
        series["qtq"] = series[component].pct_change(1, fill_method=None) * 100
        yoy_row, qtq_row = {"indikator": component}, {"indikator": component}
        for quarter, col in enumerate(QCOLS, 1):
            selected = series.loc[(series["tanggal"].dt.year == 2026) & (series["tanggal"].dt.quarter == quarter)]
            yoy_row[col] = selected["yoy"].iloc[-1] if not selected.empty else None
            qtq_row[col] = selected["qtq"].iloc[-1] if not selected.empty else None
        annual = series.assign(tahun=series["tanggal"].dt.year).groupby("tahun")[component].sum(min_count=1)
        yoy_row["full_year"] = (annual.pct_change(fill_method=None) * 100).get(2026)
        qtq_row["full_year"] = None
        yoy_rows.append(yoy_row)
        qtq_rows.append(qtq_row)
    return {"yoy": pd.DataFrame(yoy_rows), "qtq": pd.DataFrame(qtq_rows)}


def lookup(df, indicator, col):
    selected = pd.to_numeric(df.loc[df["indikator"] == indicator, col], errors="coerce")
    return None if selected.empty else selected.iloc[0]


def comparison_class(base, compared):
    if compared is None or pd.isna(compared):
        return "missing"
    if base is None or pd.isna(base) or abs(float(compared) - float(base)) < 1e-12:
        return "same"
    return "up" if compared > base else "down"


def render_comparison(base, shock, formatter, note=""):
    header_html = (
        '<div class="compare-wrap"><table class="compare-table"><thead><tr>'
        '<th rowspan="2">Indikator</th>' +
        ''.join(f'<th colspan="2">Q{i}</th>' for i in range(1, 5)) +
        '<th colspan="3">Full Year</th></tr><tr>' +
        '<th>Baseline</th><th>Shock Fiskal</th>' * 4 +
        '<th>Baseline</th><th>Shock Fiskal</th><th>Shock Makro</th>'
        '</tr></thead><tbody>'
    )
    rows = []
    for indicator in MAIN_ROWS:
        cells = [f'<td>{html.escape(indicator)}</td>']
        for col in QCOLS:
            base_value = lookup(base, indicator, col)
            shock_value = lookup(shock, indicator, col)
            cells.extend([
                f'<td>{formatter(base_value)}</td>',
                f'<td class="{comparison_class(base_value, shock_value)}">{formatter(shock_value)}</td>',
            ])
        base_value = lookup(base, indicator, "full_year")
        shock_value = lookup(shock, indicator, "full_year")
        cells.extend([
            f'<td>{formatter(base_value)}</td>',
            f'<td class="{comparison_class(base_value, shock_value)}">{formatter(shock_value)}</td>',
            f'<td class="{comparison_class(base_value, shock_value)}">{formatter(shock_value)}</td>',
        ])
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    output = header_html + ''.join(rows) + (
        '</tbody></table></div><div class="legend">'
        '<span><i class="swatch up"></i>Lebih tinggi</span>'
        '<span><i class="swatch down"></i>Lebih rendah</span>'
        '<span><i class="swatch same"></i>Sama</span></div>'
    )
    if note:
        output += f'<div class="note">{html.escape(note)}</div>'
    st.markdown(output, unsafe_allow_html=True)


def render_chart(history, selected, metric=None):
    if not history:
        st.info("Data historis belum tersedia.")
        return
    if metric:
        plot_df = history["growth"]
        plot_df = plot_df.loc[plot_df["komponen"].isin(selected)].copy()
        plot_df["fmt"] = plot_df[metric].apply(fmt_pct)
        fig = px.line(plot_df, x="tanggal", y=metric, color="komponen", custom_data=["fmt"], color_discrete_sequence=COLORS)
    else:
        plot_df = history["level"]
        plot_df = plot_df.loc[plot_df["komponen"].isin(selected)]
        fig = px.line(plot_df, x="tanggal", y="nilai", color="komponen", custom_data=["nilai_fmt"], color_discrete_sequence=COLORS)
    fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m-%d}<br>%{customdata[0]}<extra></extra>")
    fig.update_layout(height=390, hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title_text="", font_color="#23344D")
    fig.update_xaxes(color="#23344D", gridcolor="rgba(31,41,55,.08)")
    fig.update_yaxes(color="#23344D", gridcolor="rgba(31,41,55,.12)")
    st.plotly_chart(fig, use_container_width=True)


def render_fiscal_table(macro):
    def delta(name):
        row = macro.loc[macro["indikator"] == name]
        if row.empty or pd.isna(row.iloc[0]["shock"]):
            return 0.0
        return float(row.iloc[0]["shock"] - row.iloc[0]["apbn_2026"])

    tax_impact = delta("Pertumbuhan ekonomi (%)") / 0.1 * 2080.30
    tax_impact += delta("Lifting Gas Bumi (ribu barel setara minyak per hari)") / 10 * 390.99
    pnbp_impact = delta("Lifting Gas Bumi (ribu barel setara minyak per hari)") / 10 * 870.10
    apbn = {"pp":2693714, "pnbp":459200, "hibah":666, "bpp":3149733, "tkd":692995}
    income = apbn["pp"] + apbn["pnbp"] + apbn["hibah"]
    spending = apbn["bpp"] + apbn["tkd"]
    impact_income = tax_impact + pnbp_impact
    rows = [
        ("A. Pendapatan Negara dan Hibah", income, impact_income, True),
        ("1. Penerimaan Perpajakan", apbn["pp"], tax_impact, False),
        ("2. Penerimaan Negara Bukan Pajak", apbn["pnbp"], pnbp_impact, False),
        ("3. Hibah", apbn["hibah"], 0, False),
        ("B. Belanja Negara", spending, 0, True),
        ("1. Belanja Pemerintah Pusat", apbn["bpp"], 0, False),
        ("2. Transfer ke Daerah", apbn["tkd"], 0, False),
        ("C. Surplus/Defisit", income - spending, impact_income, True),
        ("D. Pembiayaan Anggaran", spending - income, -impact_income, True),
    ]
    body = []
    for name, baseline, impact, bold in rows:
        weight = "font-weight:700" if bold else ""
        body.append(
            f'<tr><td style="{weight}">{html.escape(name)}</td>'
            f'<td style="text-align:right;{weight}">{fmt_num(baseline)}</td>'
            f'<td style="text-align:right;{weight}">{fmt_num(impact)}</td>'
            f'<td style="text-align:right;{weight}">{fmt_num(baseline + impact)}</td></tr>'
        )
    st.markdown(
        '<table class="fiscal-table"><thead><tr><th>Uraian</th>'
        '<th>APBN 2026</th><th>Dampak</th><th>Outlook</th></tr></thead><tbody>' +
        ''.join(body) + '</tbody></table>',
        unsafe_allow_html=True,
    )


# MAIN APP
data, history, tables, source_status = load_data()
render_header()
selected_page = render_sidebar(source_status)
st.markdown(
    '<div class="dashboard-alert">⚠ <div><strong>Perhatian:</strong> '
    'Data PDB 2026 mencakup baseline dan simulasi. Pastikan input shock telah diterapkan sebelum membaca outlook.</div></div>',
    unsafe_allow_html=True,
)

fiscal_simulation = session_df("simulasi_fiskal_df", fiscal_default)
macro_simulation = session_df("simulasi_makro_df", macro_default)
baseline = ensure_full_year(data["pdb"])
adjusted = adjust_nominal(baseline, fiscal_simulation)
baseline_yoy = tables["yoy"] if tables else empty_df("pdb")
baseline_qtq = tables["qtq"] if tables else empty_df("pdb")
adjusted_tables = adjusted_growth(history, adjusted)

if selected_page == "Ringkasan Ekonomi":
    page_title("Ringkasan Ekonomi Makro")
    section_title("Tabel Utama Blok Accounting")
    nominal_tab, yoy_tab, qtq_tab = st.tabs(["Nominal 2026", "Year on Year (YoY)", "Quarter to Quarter (QtQ)"])
    with nominal_tab:
        render_comparison(baseline, adjusted, fmt_num, "Shock Makro pada tabel PDB masih mengikuti Shock Fiskal.")
    with yoy_tab:
        render_comparison(baseline_yoy, adjusted_tables["yoy"], fmt_pct)
    with qtq_tab:
        render_comparison(baseline_qtq, adjusted_tables["qtq"], fmt_pct, "Full Year QtQ dikosongkan karena QtQ adalah perubahan antartriwulan.")
    section_title("Perkembangan Komponen PDB")
    selected_components = st.multiselect("Pilih komponen PDB", COMPONENTS, default=MAIN_ROWS) or MAIN_ROWS
    level_tab, growth_yoy_tab, growth_qtq_tab = st.tabs(["Historis Level", "Pertumbuhan YoY", "Pertumbuhan QtQ"])
    with level_tab:
        render_chart(history, selected_components)
    with growth_yoy_tab:
        render_chart(history, [item for item in selected_components if item != "Change in Stocks"], "yoy")
    with growth_qtq_tab:
        render_chart(history, [item for item in selected_components if item != "Change in Stocks"], "qtq")

elif selected_page == "Ringkasan Indikator Ekonomi Terkini":
    page_title(selected_page)
    macro_tab, monetary_tab = st.tabs(["Indikator Makro", "Indikator Moneter"])
    with macro_tab:
        section_title("Asumsi dan Indikator Makro")
        st.dataframe(data["makro"].rename(columns={"indikator":"Indikator", **LABELS}), hide_index=True, use_container_width=True)
    with monetary_tab:
        section_title("Indikator Moneter")
        st.dataframe(data["moneter"].rename(columns={"indikator":"Indikator", **LABELS}), hide_index=True, use_container_width=True)

elif selected_page == "Ringkasan Fiskal":
    page_title(selected_page)
    section_title("Outlook APBN 2026")
    render_fiscal_table(macro_simulation)

elif selected_page == "Simulasi Fiskal":
    page_title(selected_page)
    st.info("Masukkan stimulus fiskal per triwulan dalam miliar rupiah.")
    section_title("Input Simulasi Fiskal")
    edited = st.data_editor(
        fiscal_simulation, hide_index=True, disabled=["indikator"], use_container_width=True,
        column_config={
            "indikator": st.column_config.TextColumn("Simulasi Fiskal", width="large"),
            **{col: st.column_config.NumberColumn(LABELS[col], format="%.2f") for col in QCOLS},
        },
    )
    col1, col2 = st.columns(2)
    if col1.button("Terapkan Simulasi Fiskal", type="primary", use_container_width=True):
        st.session_state["simulasi_fiskal_df"] = edited
        st.rerun()
    if col2.button("Reset Simulasi Fiskal", use_container_width=True):
        st.session_state["simulasi_fiskal_df"] = fiscal_default()
        st.rerun()
    section_title("Dampak terhadap PDB")
    render_comparison(baseline, adjusted, fmt_num)

elif selected_page == "Sensitivitas APBN":
    page_title(selected_page)
    section_title("Simulasi Asumsi Dasar Ekonomi Makro")
    edited = st.data_editor(
        macro_simulation, hide_index=True, disabled=["indikator", "apbn_2026"], use_container_width=True,
        column_config={
            "indikator": st.column_config.TextColumn("Asumsi Dasar Ekonomi Makro", width="large"),
            "apbn_2026": st.column_config.NumberColumn("APBN 2026", format="%.1f"),
            "shock": st.column_config.NumberColumn("Shock", format="%.1f"),
        },
    )
    col1, col2 = st.columns(2)
    if col1.button("Terapkan Shock Makro", type="primary", use_container_width=True):
        st.session_state["simulasi_makro_df"] = edited
        st.rerun()
    if col2.button("Reset Shock Makro", use_container_width=True):
        st.session_state["simulasi_makro_df"] = macro_default()
        st.rerun()
    section_title("Dampak terhadap Outlook Fiskal")
    render_fiscal_table(macro_simulation)

else:
    page_title(selected_page)
    st.info("Modul simulasi program prioritas sedang disiapkan untuk input program, anggaran, multiplier, dan periode pelaksanaan.")
