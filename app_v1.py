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
COLORS = ["#356CB5", "#D77A32", "#248A78", "#7857D8", "#B94A68", "#C89436", "#497EA8", "#6686A2"]

st.markdown(
    """
<style>
:root {
    --navy:#1F4373; --navy2:#17375F; --surface:#FFFFFF; --page:#F3F7FB;
    --ink:#284766; --ink-strong:#19375F; --ink-soft:#58708E;
    --border:#C9D7E6; --header:#DCE8F5; --stripe:#F4F8FC;
    --active:#E8F1FC; --green:#137157; --green-bg:#DDF3EA;
    --red:#A33D4E; --red-bg:#F8E5E8;
}
html, body, [class*="css"] {font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;}
.stApp {background:var(--page); color:var(--ink);}
header[data-testid="stHeader"] {height:0;background:transparent;}
#MainMenu, footer, div[data-testid="stToolbar"], div[data-testid="stDecoration"] {display:none!important;}
.block-container {max-width:none;padding:6.8rem 2.2rem 3rem;color:var(--ink);}

/* HEADER */
.djsef-header {position:fixed;z-index:999999;top:0;left:0;right:0;height:84px;display:grid;grid-template-columns:320px 1fr 180px;align-items:center;background:linear-gradient(110deg,#1E416F,#214B7E);box-shadow:0 3px 12px rgba(31,67,115,.18);}
.djsef-header,.djsef-header * {color:#FFF!important;}
.brand {height:100%;display:flex;align-items:center;gap:16px;padding-left:22px;border-right:1px solid rgba(255,255,255,.1);}
.logo {width:52px;height:52px;display:flex;align-items:center;justify-content:center;border-radius:12px;border:2px solid rgba(255,255,255,.32);background:rgba(255,255,255,.1);}
.bars {height:27px;display:flex;align-items:flex-end;gap:4px}.bars span{width:4px;border-radius:2px;background:#FFF}.bars span:nth-child(1){height:11px}.bars span:nth-child(2){height:21px}.bars span:nth-child(3){height:16px}.bars span:nth-child(4){height:27px}
.brand-name {color:#CBDAEC!important;font-size:16px;font-weight:650}.ministry{font-size:17px;font-weight:750;margin-top:3px}.app-title{text-align:center;font-size:21px;font-weight:750}.profile{display:flex;justify-content:flex-end;align-items:center;gap:22px;padding-right:28px}.bell{position:relative;font-size:22px}.dot{position:absolute;top:0;right:-1px;width:6px;height:6px;border-radius:50%;background:#FF7B89}.avatar{width:48px;height:48px;display:flex;align-items:center;justify-content:center;border-radius:50%;font-weight:750;background:linear-gradient(145deg,#568BC6,#2C6099);border:2px solid rgba(255,255,255,.3)}

/* SIDEBAR */
section[data-testid="stSidebar"] {top:84px;height:calc(100vh - 84px);width:320px!important;min-width:320px!important;max-width:320px!important;background:#FFF;border-right:1px solid #DCE5EF;}
section[data-testid="stSidebar"]>div{padding-top:1rem}section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"]{padding:0!important}
.side-title{padding:21px 21px 8px;color:#8192A8;font-size:14px;font-weight:800;letter-spacing:.08em}.source{margin:18px 20px;padding:12px 13px;border-radius:9px;color:#58708E;background:#F3F7FB;border:1px solid #D8E2ED;font-size:12px;line-height:1.45}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] span,section[data-testid="stSidebar"] label{color:#334E70}
section[data-testid="stSidebar"] div[role="radiogroup"]{gap:0}section[data-testid="stSidebar"] label[data-baseweb="radio"]{width:100%;min-height:55px;margin:0;padding:0 21px;border-radius:0}section[data-testid="stSidebar"] label[data-baseweb="radio"]>div:first-child{display:none}section[data-testid="stSidebar"] label[data-baseweb="radio"] p{color:#334E70!important;font-size:16px;font-weight:550;line-height:1.3}section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked){background:var(--active);box-shadow:inset 4px 0 0 #467DC5}section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p{color:#193F71!important;font-weight:750}

/* CONTENT */
.block-container p,.block-container label,.block-container span{color:var(--ink)}
.block-container h1,.block-container h2,.block-container h3{color:var(--ink-strong)!important}
.page-title{margin:0 0 1.3rem;color:var(--ink-strong);font-size:30px;font-weight:780;letter-spacing:-.03em}.section-title{display:flex;align-items:center;gap:12px;margin:20px 0 15px;color:#234D80;font-size:19px;font-weight:760}.section-title:after{content:"";height:1px;flex:1;background:#CBD8E6}
.alert{display:flex;gap:16px;align-items:center;padding:18px 23px;margin-bottom:30px;color:#915126;background:#FFF4E5;border:1px solid #E8A54D;border-radius:11px;font-size:16px}.alert div{color:#915126!important}.alert strong{color:#7D431F!important}
.block-container div[data-testid="stAlert"] p,.block-container div[data-testid="stAlert"] span{color:var(--ink)!important}

/* INPUT */
.block-container input,.block-container textarea,.block-container [data-baseweb="select"]>div,.block-container [data-baseweb="input"]>div{color:var(--ink)!important;background:#FFF!important}.block-container [data-baseweb="select"] span,.block-container [data-baseweb="tag"] span,.block-container [role="option"]{color:var(--ink)!important}.block-container [data-baseweb="tag"]{background:#E3EDF8!important}

/* TABS */
.stTabs [data-baseweb="tab-list"]{gap:8px;padding:6px;border-radius:12px;background:#E7EDF5}.stTabs [data-baseweb="tab"]{height:44px;padding:0 20px;border-radius:9px;font-weight:680}.stTabs [data-baseweb="tab"] p,.stTabs [data-baseweb="tab"] span{color:#334E70!important}.stTabs [aria-selected="true"]{background:var(--navy)!important}.stTabs [aria-selected="true"] p,.stTabs [aria-selected="true"] span{color:#FFF!important}.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none}

/* CARDS */
div[data-testid="stDataFrame"],div[data-testid="stDataEditor"],div[data-testid="stPlotlyChart"]{overflow:hidden;border:1px solid var(--border);border-radius:12px;background:#FFF;color:var(--ink)!important;box-shadow:0 3px 10px rgba(31,67,115,.06)}div[data-testid="stPlotlyChart"]{padding:10px}
div[data-testid="stDataFrame"] *,div[data-testid="stDataEditor"] *{color:var(--ink)}
.stButton button{min-height:43px;border-radius:9px;font-weight:680}.block-container .stButton button:not([kind="primary"]){color:var(--navy)!important;background:#FFF!important;border:1px solid #AFC1D5!important}.block-container .stButton button:not([kind="primary"]):hover{background:#EAF2FA!important;border-color:var(--navy)!important}.block-container .stButton button[kind="primary"],.block-container .stButton button[kind="primary"] *{color:#FFF!important;background:var(--navy)!important}

/* COMPARISON TABLE */
.compare-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:12px;background:#FFF;box-shadow:0 3px 10px rgba(31,67,115,.06)}.compare-table{border-collapse:collapse;width:100%;min-width:1200px;font-size:.97rem}.compare-table th,.compare-table td{border:1px solid #C9D7E6;padding:.66rem .72rem;text-align:center;white-space:nowrap}.compare-table th{color:var(--ink-strong)!important;background:var(--header)!important;font-weight:780}.compare-table td{color:var(--ink)!important;background:#FFF;font-weight:640}.compare-table tbody tr:nth-child(even) td{background:var(--stripe)}.compare-table tbody tr:hover td{background:#E8F1FA!important}.compare-table th:first-child,.compare-table td:first-child{position:sticky;left:0;z-index:2;text-align:left}.compare-table th:first-child{background:var(--header)!important}.compare-table td:first-child{color:var(--ink-strong)!important;font-weight:720}.compare-table td.up{color:var(--green)!important;background:var(--green-bg)!important;font-weight:780}.compare-table td.down{color:var(--red)!important;background:var(--red-bg)!important;font-weight:780}.compare-table td.missing{color:#71859E!important;background:#F0F4F8!important}.legend{display:flex;gap:1rem;margin-top:.7rem;color:var(--ink-soft);font-size:.86rem}.legend span,.note{color:var(--ink-soft)!important}.swatch{width:14px;height:14px;border:1px solid #BAC9D9;border-radius:3px;display:inline-block;margin-right:5px}.note{font-size:.89rem;margin-top:.55rem}

/* FISCAL */
.fiscal-table{width:100%;border-collapse:separate;border-spacing:0;border:1px solid var(--border);border-radius:12px;background:#FFF;overflow:hidden}.fiscal-table th,.fiscal-table td{padding:.68rem .82rem;border-bottom:1px solid #D8E2ED}.fiscal-table th{color:var(--ink-strong)!important;background:var(--header)!important;font-weight:780}.fiscal-table td{color:var(--ink)!important;font-weight:620}.fiscal-table tbody tr:nth-child(even) td{background:var(--stripe)}
@media(max-width:900px){.djsef-header{grid-template-columns:240px 1fr 100px}.app-title{font-size:16px}.block-container{padding-left:1rem;padding-right:1rem}}
</style>
    """,
    unsafe_allow_html=True,
)


def header():
    st.markdown("""
<div class="djsef-header"><div class="brand"><div class="logo"><div class="bars"><span></span><span></span><span></span><span></span></div></div><div><div class="brand-name">DJSEF</div><div class="ministry">Kementerian Keuangan RI</div></div></div><div class="app-title">Dashboard Monitoring dan Simulasi Ekonomi Nasional</div><div class="profile"><div class="bell">♧<span class="dot"></span></div><div class="avatar">TD</div></div></div>
    """, unsafe_allow_html=True)


def sidebar(status):
    st.sidebar.markdown('<div class="side-title">MENU UTAMA</div>', unsafe_allow_html=True)
    options = [
        "▥  Ringkasan Ekonomi", "⌁  Ringkasan Indikator Ekonomi Terkini",
        "▦  Ringkasan Fiskal", "♙  Simulasi Fiskal",
        "⌒  Sensitivitas APBN", "◎  Simulasi Program Prioritas",
    ]
    selected = st.sidebar.radio("Navigasi", options, label_visibility="collapsed")
    st.sidebar.markdown('<div class="side-title">DOKUMEN</div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div style="padding:14px 21px;color:#334E70;font-size:16px">▤ &nbsp; Laporan</div>', unsafe_allow_html=True)
    st.sidebar.markdown(f'<div class="source"><strong>Sumber Data</strong><br>{html.escape(status)}</div>', unsafe_allow_html=True)
    for symbol in ["▥", "⌁", "▦", "♙", "⌒", "◎"]:
        selected = selected.replace(symbol, "")
    return selected.strip()


def title(text):
    st.markdown(f'<div class="page-title">{html.escape(text)}</div>', unsafe_allow_html=True)


def section(text):
    st.markdown(f'<div class="section-title">{html.escape(text)}</div>', unsafe_allow_html=True)


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


def empty_df(block):
    rows = DEFAULT_ROWS[block]
    return pd.DataFrame({"indikator": rows, **{col: [None] * len(rows) for col in PERIODS}})


def ensure_full_year(df):
    out = df.copy()
    for col in QCOLS:
        if col not in out.columns:
            out[col] = None
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["full_year"] = out[QCOLS].sum(axis=1, min_count=1)
    return out


def source():
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


def open_excel(src):
    return pd.ExcelFile(BytesIO(src), engine="openpyxl") if isinstance(src, bytes) else pd.ExcelFile(src, engine="openpyxl")


@st.cache_data(show_spinner=False)
def load_data():
    data = {name: empty_df(name) for name in DEFAULT_ROWS}
    src, status = source()
    if src is None:
        return data, None, None, status
    try:
        xls = open_excel(src)
        sheets = {name.lower().strip(): name for name in xls.sheet_names}
        for block in ["makro", "moneter", "fiskal"]:
            if block in sheets:
                frame = pd.read_excel(xls, sheet_name=sheets[block], engine="openpyxl")
                frame.columns = [normalize(col) for col in frame.columns]
                if "indikator" not in frame.columns:
                    frame = frame.rename(columns={frame.columns[0]: "indikator"})
                for col in PERIODS:
                    if col not in frame.columns:
                        frame[col] = None
                data[block] = frame[["indikator", *PERIODS]]

        if "realisasi" not in sheets:
            return data, None, None, status

        raw = pd.read_excel(xls, sheet_name=sheets["realisasi"], engine="openpyxl")
        raw = raw.rename(columns={raw.columns[0]: "tanggal"})
        raw["tanggal"] = pd.to_datetime(raw["tanggal"], errors="coerce")
        raw = raw.dropna(subset=["tanggal"]).sort_values("tanggal").reset_index(drop=True)

        wide = pd.DataFrame({"tanggal": raw["tanggal"]})
        for component in COMPONENTS[:-1]:
            col = next((item for item in raw.columns if normalize(item) == normalize(component)), None)
            wide[component] = pd.to_numeric(raw[col], errors="coerce") if col else None
        discrepancy_col = next((item for item in raw.columns if normalize(item) == normalize("Statistical Discrepancy")), None)
        discrepancy = pd.to_numeric(raw[discrepancy_col], errors="coerce") if discrepancy_col else 0.0
        wide["PDB Aggregate"] = (
            wide["Konsumsi RT"] + wide["Konsumsi LNPRT"] + wide["PKP"] +
            wide["PMTB"] + wide["Change in Stocks"] + wide["Ekspor"] -
            wide["Impor"] + discrepancy
        )

        nominal = []
        for component in COMPONENTS:
            row = {"indikator": component}
            for quarter, col in enumerate(QCOLS, 1):
                values = wide.loc[(wide["tanggal"].dt.year == 2026) & (wide["tanggal"].dt.quarter == quarter), component]
                row[col] = float(values.iloc[-1]) if not values.empty else None
            nominal.append(row)
        data["pdb"] = ensure_full_year(pd.DataFrame(nominal))

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
                selected = series.loc[(series["tanggal"].dt.year == 2026) & (series["tanggal"].dt.quarter == quarter)]
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
        "indikator": [row[0] for row in MACRO_DEFAULTS],
        "apbn_2026": [row[1] for row in MACRO_DEFAULTS],
        "shock": [None] * len(MACRO_DEFAULTS),
    })


def state_frame(key, factory):
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
    for sim_name, target, divisors in rules:
        row = simulation.loc[simulation["indikator"] == sim_name]
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


def lookup(frame, indicator, col):
    selected = pd.to_numeric(frame.loc[frame["indikator"] == indicator, col], errors="coerce")
    return None if selected.empty else selected.iloc[0]


def value_class(base, compared):
    if compared is None or pd.isna(compared):
        return "missing"
    if base is None or pd.isna(base) or abs(float(compared) - float(base)) < 1e-12:
        return "same"
    return "up" if compared > base else "down"


def comparison(base, shock, formatter, note=""):
    table_head = (
        '<div class="compare-wrap"><table class="compare-table"><thead><tr>'
        '<th rowspan="2">Indikator</th>' + ''.join(f'<th colspan="2">Q{i}</th>' for i in range(1, 5)) +
        '<th colspan="3">Full Year</th></tr><tr>' + '<th>Baseline</th><th>Shock Fiskal</th>' * 4 +
        '<th>Baseline</th><th>Shock Fiskal</th><th>Shock Makro</th></tr></thead><tbody>'
    )
    rows = []
    for indicator in MAIN_ROWS:
        cells = [f'<td>{html.escape(indicator)}</td>']
        for col in QCOLS:
            base_value, shock_value = lookup(base, indicator, col), lookup(shock, indicator, col)
            cells.extend([f'<td>{formatter(base_value)}</td>', f'<td class="{value_class(base_value, shock_value)}">{formatter(shock_value)}</td>'])
        base_value, shock_value = lookup(base, indicator, "full_year"), lookup(shock, indicator, "full_year")
        cells.extend([f'<td>{formatter(base_value)}</td>', f'<td class="{value_class(base_value, shock_value)}">{formatter(shock_value)}</td>', f'<td class="{value_class(base_value, shock_value)}">{formatter(shock_value)}</td>'])
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    output = table_head + ''.join(rows) + '</tbody></table></div><div class="legend"><span><i class="swatch" style="background:#DDF3EA"></i>Lebih tinggi</span><span><i class="swatch" style="background:#F8E5E8"></i>Lebih rendah</span><span><i class="swatch" style="background:#FFFFFF"></i>Sama</span></div>'
    if note:
        output += f'<div class="note">{html.escape(note)}</div>'
    st.markdown(output, unsafe_allow_html=True)


def chart(history, selected, metric=None):
    if not history:
        st.info("Data historis belum tersedia.")
        return
    if metric:
        plot_df = history["growth"].loc[history["growth"]["komponen"].isin(selected)].copy()
        plot_df["fmt"] = plot_df[metric].apply(fmt_pct)
        fig = px.line(plot_df, x="tanggal", y=metric, color="komponen", custom_data=["fmt"], color_discrete_sequence=COLORS)
    else:
        plot_df = history["level"].loc[history["level"]["komponen"].isin(selected)].copy()
        fig = px.line(plot_df, x="tanggal", y="nilai", color="komponen", custom_data=["nilai_fmt"], color_discrete_sequence=COLORS)
    fig.update_traces(mode="lines+markers", line=dict(width=2.6), marker=dict(size=6), hovertemplate="%{x|%Y-%m-%d}<br>%{customdata[0]}<extra></extra>")
    fig.update_layout(
        height=410, hovermode="x unified", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        font=dict(color="#284766", size=12), title_font=dict(color="#19375F"),
        legend_title_text="", legend=dict(font=dict(color="#315A89", size=12), bgcolor="rgba(255,255,255,.88)"),
        margin=dict(l=65, r=35, t=40, b=60),
    )
    fig.update_xaxes(color="#4E6989", title_font_color="#315A89", tickfont=dict(color="#4E6989", size=12), gridcolor="#E0E7F0", linecolor="#B8C8DA", zerolinecolor="#C8D5E3")
    fig.update_yaxes(color="#4E6989", title_font_color="#315A89", tickfont=dict(color="#4E6989", size=12), gridcolor="#D6E0EC", linecolor="#B8C8DA", zerolinecolor="#C8D5E3")
    st.plotly_chart(fig, use_container_width=True)


def fiscal_table(macro):
    def delta(name):
        row = macro.loc[macro["indikator"] == name]
        if row.empty or pd.isna(row.iloc[0]["shock"]):
            return 0.0
        return float(row.iloc[0]["shock"] - row.iloc[0]["apbn_2026"])
    tax = delta("Pertumbuhan ekonomi (%)") / 0.1 * 2080.30 + delta("Lifting Gas Bumi (ribu barel setara minyak per hari)") / 10 * 390.99
    pnbp = delta("Lifting Gas Bumi (ribu barel setara minyak per hari)") / 10 * 870.10
    apbn = {"pp":2693714,"pnbp":459200,"hibah":666,"bpp":3149733,"tkd":692995}
    income, spending = apbn["pp"] + apbn["pnbp"] + apbn["hibah"], apbn["bpp"] + apbn["tkd"]
    impact = tax + pnbp
    rows = [
        ("A. Pendapatan Negara dan Hibah",income,impact,True),("1. Penerimaan Perpajakan",apbn["pp"],tax,False),
        ("2. Penerimaan Negara Bukan Pajak",apbn["pnbp"],pnbp,False),("3. Hibah",apbn["hibah"],0,False),
        ("B. Belanja Negara",spending,0,True),("1. Belanja Pemerintah Pusat",apbn["bpp"],0,False),
        ("2. Transfer ke Daerah",apbn["tkd"],0,False),("C. Surplus/Defisit",income-spending,impact,True),
        ("D. Pembiayaan Anggaran",spending-income,-impact,True),
    ]
    body=[]
    for name, baseline, effect, bold in rows:
        weight="font-weight:760" if bold else ""
        body.append(f'<tr><td style="{weight}">{html.escape(name)}</td><td style="text-align:right;{weight}">{fmt_num(baseline)}</td><td style="text-align:right;{weight}">{fmt_num(effect)}</td><td style="text-align:right;{weight}">{fmt_num(baseline+effect)}</td></tr>')
    st.markdown('<table class="fiscal-table"><thead><tr><th>Uraian</th><th>APBN 2026</th><th>Dampak</th><th>Outlook</th></tr></thead><tbody>'+''.join(body)+'</tbody></table>', unsafe_allow_html=True)


# MAIN
data, history, tables, status = load_data()
header()
page = sidebar(status)
st.markdown('<div class="alert">⚠ <div><strong>Perhatian:</strong> Data PDB 2026 mencakup baseline dan simulasi. Pastikan input shock telah diterapkan sebelum membaca outlook.</div></div>', unsafe_allow_html=True)

fiscal_sim = state_frame("simulasi_fiskal_df", fiscal_default)
macro_sim = state_frame("simulasi_makro_df", macro_default)
baseline = ensure_full_year(data["pdb"])
adjusted = adjust_nominal(baseline, fiscal_sim)
baseline_yoy = tables["yoy"] if tables else empty_df("pdb")
baseline_qtq = tables["qtq"] if tables else empty_df("pdb")
adjusted_tables = adjusted_growth(history, adjusted)

if page == "Ringkasan Ekonomi":
    title("Ringkasan Ekonomi Makro")
    section("Tabel Utama Blok Accounting")
    nominal_tab, yoy_tab, qtq_tab = st.tabs(["Nominal 2026", "Year on Year (YoY)", "Quarter to Quarter (QtQ)"])
    with nominal_tab:
        comparison(baseline, adjusted, fmt_num, "Shock Makro pada tabel PDB masih mengikuti Shock Fiskal.")
    with yoy_tab:
        comparison(baseline_yoy, adjusted_tables["yoy"], fmt_pct)
    with qtq_tab:
        comparison(baseline_qtq, adjusted_tables["qtq"], fmt_pct, "Full Year QtQ dikosongkan karena QtQ adalah perubahan antartriwulan.")
    section("Perkembangan Komponen PDB")
    selected = st.multiselect("Pilih komponen PDB", COMPONENTS, default=MAIN_ROWS) or MAIN_ROWS
    level_tab, hist_yoy_tab, hist_qtq_tab = st.tabs(["Historis Level", "Pertumbuhan YoY", "Pertumbuhan QtQ"])
    with level_tab:
        chart(history, selected)
    with hist_yoy_tab:
        chart(history, [item for item in selected if item != "Change in Stocks"], "yoy")
    with hist_qtq_tab:
        chart(history, [item for item in selected if item != "Change in Stocks"], "qtq")

elif page == "Ringkasan Indikator Ekonomi Terkini":
    title(page)
    macro_tab, monetary_tab = st.tabs(["Indikator Makro", "Indikator Moneter"])
    with macro_tab:
        section("Asumsi dan Indikator Makro")
        st.dataframe(data["makro"].rename(columns={"indikator":"Indikator", **LABELS}), hide_index=True, use_container_width=True)
    with monetary_tab:
        section("Indikator Moneter")
        st.dataframe(data["moneter"].rename(columns={"indikator":"Indikator", **LABELS}), hide_index=True, use_container_width=True)

elif page == "Ringkasan Fiskal":
    title(page)
    section("Outlook APBN 2026")
    fiscal_table(macro_sim)

elif page == "Simulasi Fiskal":
    title(page)
    st.info("Masukkan stimulus fiskal per triwulan dalam miliar rupiah.")
    section("Input Simulasi Fiskal")
    edited = st.data_editor(
        fiscal_sim, hide_index=True, disabled=["indikator"], use_container_width=True,
        column_config={"indikator":st.column_config.TextColumn("Simulasi Fiskal",width="large"), **{col:st.column_config.NumberColumn(LABELS[col],format="%.2f") for col in QCOLS}},
    )
    left, right = st.columns(2)
    if left.button("Terapkan Simulasi Fiskal", type="primary", use_container_width=True):
        st.session_state["simulasi_fiskal_df"] = edited
        st.rerun()
    if right.button("Reset Simulasi Fiskal", use_container_width=True):
        st.session_state["simulasi_fiskal_df"] = fiscal_default()
        st.rerun()
    section("Dampak terhadap PDB")
    comparison(baseline, adjusted, fmt_num)

elif page == "Sensitivitas APBN":
    title(page)
    section("Simulasi Asumsi Dasar Ekonomi Makro")
    edited = st.data_editor(
        macro_sim, hide_index=True, disabled=["indikator", "apbn_2026"], use_container_width=True,
        column_config={"indikator":st.column_config.TextColumn("Asumsi Dasar Ekonomi Makro",width="large"), "apbn_2026":st.column_config.NumberColumn("APBN 2026",format="%.1f"), "shock":st.column_config.NumberColumn("Shock",format="%.1f")},
    )
    left, right = st.columns(2)
    if left.button("Terapkan Shock Makro", type="primary", use_container_width=True):
        st.session_state["simulasi_makro_df"] = edited
        st.rerun()
    if right.button("Reset Shock Makro", use_container_width=True):
        st.session_state["simulasi_makro_df"] = macro_default()
        st.rerun()
    section("Dampak terhadap Outlook Fiskal")
    fiscal_table(macro_sim)

else:
    title(page)
    st.info("Modul simulasi program prioritas sedang disiapkan untuk input program, anggaran, multiplier, dan periode pelaksanaan.")
