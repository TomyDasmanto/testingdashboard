
from __future__ import annotations

import html
import math
import textwrap
from io import BytesIO
from pathlib import Path
from typing import Any, Optional, Union
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Dashboard Pemantauan PDB",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================
# Konfigurasi inti
# =========================
REPO_FILE_NAME = "dashboard PDB.xlsx"
try:
    GITHUB_RAW_XLSX_URL = st.secrets.get("github_raw_xlsx_url", "")
except Exception:
    GITHUB_RAW_XLSX_URL = ""

PRIMARY = "#3E6DB5"
ACCENT = "#E07B39"
SUCCESS = "#2A9D8F"
PURPLE = "#8A5CF6"
NEGATIVE = "#D14D72"
POS_LIGHT = "#DCEFEA"
NEG_LIGHT = "#F8E1E8"
NEUTRAL_LIGHT = "#F3F4F6"
CELL_A = "#D7DBEA"
CELL_B = "#E8EBF4"
CELL_ORANGE = "#EFD9CF"
BG = "#F6F7FB"
TEXT = "#1F2937"
GRID = "rgba(31,41,55,0.12)"
CHART_CONFIG = {"displayModeBar": True, "displaylogo": False, "responsive": True}

PERIOD_MAP = {
    "out_tw1": "Outlook Q1",
    "out_tw2": "Outlook Q2",
    "out_tw3": "Outlook Q3",
    "out_tw4": "Outlook Q4",
    "full_year": "Full Year",
}
PERIOD_ORDER = list(PERIOD_MAP.keys())

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
PDB_MAIN_HIDE = ["Konsumsi LNPRT", "Change in Stocks"]
EXCLUDE_GROWTH_ROWS = ["Change in Stocks"]

EXPECTED_SHEETS = {
    "simulasi": ["indikator", *PERIOD_ORDER],
    "makro": ["indikator", *PERIOD_ORDER],
    "pdb": ["indikator", *PERIOD_ORDER],
    "moneter": ["indikator", *PERIOD_ORDER],
    "fiskal": ["indikator", *PERIOD_ORDER],
}

DEFAULT_ROWS = {
    "simulasi": ["Consumption", "Investment", "Govt. Spending", "Export", "Import", "Unemployment"],
    "makro": ["Inflasi", "Rupiah", "Yield SBN", "ICP", "Nikel", "Coal", "CPO", "Lifting"],
    "pdb": PDB_COMPONENTS,
    "moneter": ["PUAB", "Kredit", "DPK", "M0", "OMO"],
    "fiskal": ["Pendapatan", "Belanja", "Pembiayaan", "Defisit"],
}

BLOCK_TITLES = {
    "makro": "Blok Makro",
    "pdb": "Blok Accounting / PDB",
    "moneter": "Blok Moneter",
    "fiskal": "Blok Fiskal",
}

BLOCK_NOTES = {
    "makro": "Indikator makroekonomi. Jika sheet makro tidak tersedia, tabel default akan ditampilkan.",
    "pdb": "Outlook baseline PDB 2026 diturunkan otomatis dari sheet realisasi, lalu dapat disesuaikan lewat simulasi fiskal.",
    "moneter": "Variabel moneter. Jika sheet moneter tidak tersedia, tabel default akan ditampilkan.",
    "fiskal": "I-Account APBN. Jika sheet fiskal tidak tersedia, tabel default akan ditampilkan.",
}

SIMULASI_FISKAL_ROWS = [
    "Bantuan Pangan",
    "Bantuan Langsung Tunai",
    "Kenaikan Gaji",
    "Pembayaran Gaji 14",
    "Diskon Transportasi",
    "Investasi",
]
SIMULASI_FISKAL_COLS = ["out_tw1", "out_tw2", "out_tw3", "out_tw4"]
FISCAL_TO_PDB_MAP = {
    "Bantuan Pangan": "Konsumsi RT",
    "Bantuan Langsung Tunai": "Konsumsi RT",
    "Diskon Transportasi": "Konsumsi RT",
    "Kenaikan Gaji": "PKP",
    "Pembayaran Gaji 14": "PKP",
    "Investasi": "PMTB",
}

st.markdown(
    f"""
    <style>
        .main {{ background-color: {BG}; }}
        .block-title {{ font-size: 1.05rem; font-weight: 700; color: {TEXT}; margin: 0.15rem 0 0.4rem 0; }}
        .sub-title {{ font-size: 0.95rem; font-weight: 700; color: {TEXT}; margin: 0.35rem 0 0.35rem 0; }}
        .section-card {{ border: 1px solid rgba(62,109,181,0.14); border-radius: 14px; padding: 0.8rem 0.9rem; background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.03); margin-bottom: 0.9rem; overflow: visible; }}
        .section-note {{ color: #6B7280; font-size: 0.88rem; margin-bottom: 0.35rem; }}
        .status-box {{ border: 1px dashed rgba(62,109,181,0.30); border-radius: 12px; padding: 0.55rem 0.75rem; background: rgba(62,109,181,0.03); color: #374151; margin-bottom: 0.75rem; font-size: 0.86rem; }}
        .small-muted {{ color: #6B7280; font-size: 0.84rem; }}
        div[data-testid="stDataEditor"] * {{ font-size: 0.95rem !important; }}
        .sticky-table-wrap {{ width: 100%; max-width: 100%; overflow-x: auto; margin: 0.25rem 0 0.70rem 0; border-radius: 12px; --first-col-min: 250px; --first-col-max: 360px; --num-col-min: 92px; }}
        .sticky-table {{ border-collapse: separate; border-spacing: 0; width: max-content; min-width: 100%; font-size: 0.95rem; table-layout: fixed; }}
        .sticky-table thead th {{ position: sticky; top: 0; z-index: 4; color: white; font-weight: 700; white-space: nowrap; box-shadow: inset 0 -1px 0 rgba(255,255,255,0.18); }}
        .sticky-table th, .sticky-table td {{ padding: 8px 10px; border-right: 1px solid rgba(255,255,255,0.42); border-bottom: 1px solid rgba(255,255,255,0.42); vertical-align: middle; }}
        .sticky-table th:first-child, .sticky-table td:first-child {{ position: sticky; left: 0; min-width: var(--first-col-min); max-width: var(--first-col-max); width: var(--first-col-min); white-space: normal; word-break: break-word; }}
        .sticky-table thead th:first-child {{ z-index: 6; }}
        .sticky-table tbody td:first-child {{ z-index: 3; }}
        .sticky-table .num {{ text-align: center; white-space: nowrap; min-width: var(--num-col-min); }}
        .sticky-table .txt {{ text-align: left; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# Helper umum
# =========================
def normalize_key(text: Any) -> str:
    return str(text).strip().lower().replace(" ", "_").replace(".", "").replace("-", "_")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={c: normalize_key(c) for c in df.columns}).copy()


def empty_df(block: str) -> pd.DataFrame:
    rows = DEFAULT_ROWS[block]
    payload = {"indikator": rows}
    for col in PERIOD_ORDER:
        payload[col] = [None] * len(rows)
    return pd.DataFrame(payload)


def ensure_indicator_rows(df: pd.DataFrame, block: str) -> pd.DataFrame:
    expected_rows = DEFAULT_ROWS.get(block, [])
    if not expected_rows or "indikator" not in df.columns:
        return df
    work = df.copy()
    work["indikator"] = work["indikator"].fillna("").astype(str).str.strip()
    numeric_cols = [c for c in work.columns if c != "indikator"]
    rows = []
    for ind in expected_rows:
        found = work.loc[work["indikator"] == ind]
        if not found.empty:
            rows.append(found.iloc[0].to_dict())
        else:
            row = {"indikator": ind}
            for col in numeric_cols:
                row[col] = None
            rows.append(row)
    return pd.DataFrame(rows)


def coerce_schema(df: pd.DataFrame, block: str) -> pd.DataFrame:
    work = normalize_columns(df)
    if "indikator" not in work.columns and len(work.columns) > 0:
        work = work.rename(columns={work.columns[0]: "indikator"})
    expected = EXPECTED_SHEETS[block]
    for col in expected:
        if col not in work.columns:
            work[col] = None
    work = work[expected].copy()
    for col in PERIOD_ORDER:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    return ensure_indicator_rows(work, block)


def filter_growth_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_df("pdb")
    return df.loc[~df["indikator"].isin(EXCLUDE_GROWTH_ROWS)].copy()


def filter_growth_components(components: list[str]) -> list[str]:
    return [c for c in components if c not in EXCLUDE_GROWTH_ROWS]


def filter_main_pdb_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_df("pdb")
    return df.loc[~df["indikator"].isin(PDB_MAIN_HIDE)].copy()


def ensure_full_year_from_quarters(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_df("pdb")
    work = df.copy()
    for col in ["out_tw1", "out_tw2", "out_tw3", "out_tw4"]:
        if col not in work.columns:
            work[col] = None
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work["full_year"] = work[["out_tw1", "out_tw2", "out_tw3", "out_tw4"]].sum(axis=1, min_count=1)
    return work


def _format_id_number(val: float, decimals: int = 0) -> str:
    s = f"{float(val):,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_id0(val: Any) -> str:
    if pd.isna(val) or val is None:
        return "—"
    try:
        return _format_id_number(val, decimals=0)
    except Exception:
        return str(val)


def fmt_pct_id2(val: Any) -> str:
    if pd.isna(val) or val is None:
        return "—"
    try:
        return _format_id_number(val, decimals=2) + "%"
    except Exception:
        return str(val)


def make_tick_values(series: pd.Series, n: int = 6) -> tuple[list[float], list[str]]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return [], []
    vmin = float(s.min())
    vmax = float(s.max())
    if math.isclose(vmin, vmax):
        vals = [0] if math.isclose(vmin, 0.0) else [vmin - abs(vmin) * 0.1, vmin, vmin + abs(vmin) * 0.1]
    else:
        step = (vmax - vmin) / max(n - 1, 1)
        vals = [vmin + i * step for i in range(n)]
    return vals, [fmt_id0(v) for v in vals]


def make_tick_values_pct(series: pd.Series, n: int = 6) -> tuple[list[float], list[str]]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return [], []
    vmin = float(s.min())
    vmax = float(s.max())
    base_min = min(vmin, 0.0)
    base_max = max(vmax, 0.0)
    if math.isclose(base_min, base_max):
        vals = [base_min - 1, base_min, base_min + 1]
    else:
        step = (base_max - base_min) / max(n - 1, 1)
        vals = [base_min + i * step for i in range(n)]
    return vals, [fmt_pct_id2(v) for v in vals]


def wrap_table_label(text: object, width: int = 18) -> str:
    if text is None or pd.isna(text):
        return "—"
    s = str(text).strip()
    if not s or s == "nan":
        return "—"
    if len(s) <= width:
        return s
    return "<br>".join(textwrap.wrap(s, width=width, break_long_words=False, break_on_hyphens=False))


def get_table_block_spec(block_key: str = "", growth_mode: bool = False) -> dict[str, int]:
    if growth_mode:
        return {"first_min": 300, "first_max": 400, "num_min": 96, "wrap": 20}
    specs = {
        "pdb": {"first_min": 300, "first_max": 400, "num_min": 96, "wrap": 20},
        "moneter": {"first_min": 250, "first_max": 340, "num_min": 92, "wrap": 18},
        "fiskal": {"first_min": 240, "first_max": 330, "num_min": 92, "wrap": 18},
        "makro": {"first_min": 240, "first_max": 330, "num_min": 92, "wrap": 18},
        "simulasi": {"first_min": 260, "first_max": 340, "num_min": 92, "wrap": 18},
    }
    return specs.get(block_key, {"first_min": 250, "first_max": 340, "num_min": 92, "wrap": 18})


def html_escape_keep_breaks(text: object) -> str:
    if text is None:
        return "—"
    try:
        s = "—" if pd.isna(text) else str(text)
    except Exception:
        s = str(text)
    return html.escape(s).replace("&lt;br&gt;", "<br>")


def format_display_sticky(df: pd.DataFrame, value_formatter=fmt_id0, wrap_width: int = 18) -> pd.DataFrame:
    view = df.copy()
    ordered_cols = ["indikator", *PERIOD_ORDER]
    for col in ordered_cols:
        if col not in view.columns:
            view[col] = None
    view = view[ordered_cols].rename(columns={"indikator": "Indikator", **PERIOD_MAP})
    view["Indikator"] = view["Indikator"].apply(lambda x: wrap_table_label(x, width=wrap_width))
    for col in view.columns[1:]:
        view[col] = view[col].apply(value_formatter)
    return view.fillna("—")


def build_sticky_html_table(
    df: pd.DataFrame,
    header_fill: str,
    row_fill_1: str,
    row_fill_2: str,
    value_formatter=fmt_id0,
    raw_value_df: Optional[pd.DataFrame] = None,
    growth_mode: bool = False,
    block_key: str = "",
) -> str:
    spec = get_table_block_spec(block_key=block_key, growth_mode=growth_mode)
    view = format_display_sticky(df, value_formatter=value_formatter, wrap_width=spec["wrap"])
    rows_html: list[str] = []
    raw_ordered = None
    if growth_mode and raw_value_df is not None:
        raw_ordered = raw_value_df[["indikator", *PERIOD_ORDER]].copy()

    def growth_color(value: Any) -> str:
        if pd.isna(value) or value is None:
            return NEUTRAL_LIGHT
        try:
            v = float(value)
        except Exception:
            return NEUTRAL_LIGHT
        if v > 0:
            return POS_LIGHT
        if v < 0:
            return NEG_LIGHT
        return NEUTRAL_LIGHT

    for idx in range(len(view)):
        row_bg = row_fill_1 if idx % 2 == 0 else row_fill_2
        row_cells = []
        for col_idx, col in enumerate(view.columns):
            classes = "txt" if col_idx == 0 else "num"
            cell_value = html_escape_keep_breaks(view.iloc[idx, col_idx])
            style = f"background:{row_bg}; color:{TEXT};"
            if growth_mode and raw_ordered is not None and col_idx > 0:
                raw_col = PERIOD_ORDER[col_idx - 1]
                style = f"background:{growth_color(raw_ordered.iloc[idx][raw_col])}; color:{TEXT};"
            if col_idx == 0:
                style += f" z-index:3;"
            row_cells.append(f'<td class="{classes}" style="{style}">{cell_value}</td>')
        rows_html.append("<tr>" + "".join(row_cells) + "</tr>")

    head_cells = []
    for idx, col in enumerate(view.columns):
        classes = "txt" if idx == 0 else "num"
        head_cells.append(
            f'<th class="{classes}" style="background:{header_fill};">{html_escape_keep_breaks(col)}</th>'
        )
    return (
        f'<div class="sticky-table-wrap" style="--first-col-min:{spec["first_min"]}px; --first-col-max:{spec["first_max"]}px; --num-col-min:{spec["num_min"]}px;">'
        f'<table class="sticky-table"><thead><tr>{"".join(head_cells)}</tr></thead><tbody>{"".join(rows_html)}</tbody></table></div>'
    )


def block_card(title: str, note: Optional[str] = None) -> None:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="block-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="section-note">{html.escape(note)}</div>', unsafe_allow_html=True)


def close_block_card() -> None:
    st.markdown('</div>', unsafe_allow_html=True)


def sub_title(text: str) -> None:
    st.markdown(f'<div class="sub-title">{html.escape(text)}</div>', unsafe_allow_html=True)


def placeholder_chart(msg: str, height: int = 380) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=14, color="#6B7280"))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


# =========================
# Lazy loading & cache data
# =========================
def detect_excel_source() -> tuple[Optional[Union[str, bytes]], str, str]:
    local_path = Path(__file__).resolve().parent / REPO_FILE_NAME
    if local_path.exists():
        mtime = int(local_path.stat().st_mtime)
        source_key = f"local::{local_path}::{mtime}"
        return str(local_path), f"Sumber data otomatis: file lokal {REPO_FILE_NAME}", source_key
    if GITHUB_RAW_XLSX_URL:
        source_bytes = fetch_excel_bytes(GITHUB_RAW_XLSX_URL)
        source_key = f"remote::{GITHUB_RAW_XLSX_URL}::{len(source_bytes)}"
        return source_bytes, "Sumber data otomatis: GitHub Raw URL dari st.secrets['github_raw_xlsx_url']", source_key
    return None, (
        "File Excel belum ditemukan. Simpan dashboard PDB.xlsx di folder yang sama dengan app.py, atau isi st.secrets['github_raw_xlsx_url'] dengan raw URL GitHub file tersebut."
    ), "missing"


@st.cache_data(show_spinner=False)
def fetch_excel_bytes(url: str) -> bytes:
    with urlopen(url) as response:
        return response.read()


@st.cache_data(show_spinner=False)
def read_workbook_payload(source_payload: Union[str, bytes], source_key: str) -> dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(BytesIO(source_payload), engine="openpyxl") if isinstance(source_payload, (bytes, bytearray)) else pd.ExcelFile(source_payload, engine="openpyxl")
    out: dict[str, pd.DataFrame] = {}
    for sheet in xls.sheet_names:
        out[sheet.lower().strip()] = pd.read_excel(xls, sheet_name=sheet, engine="openpyxl")
    return out


@st.cache_data(show_spinner=False)
def derive_pdb_from_realisasi(source_payload: Union[str, bytes], source_key: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    xls = pd.ExcelFile(BytesIO(source_payload), engine="openpyxl") if isinstance(source_payload, (bytes, bytearray)) else pd.ExcelFile(source_payload, engine="openpyxl")
    sheet_map = {s.lower().strip(): s for s in xls.sheet_names}
    if "realisasi" not in sheet_map:
        return empty_df("pdb"), {"wide": pd.DataFrame(), "level": pd.DataFrame(), "growth": pd.DataFrame()}, {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}

    raw = pd.read_excel(xls, sheet_name=sheet_map["realisasi"], engine="openpyxl")
    raw = raw.rename(columns={raw.columns[0]: "tanggal"}).copy()
    raw["tanggal"] = pd.to_datetime(raw["tanggal"], errors="coerce")
    raw = raw.dropna(subset=["tanggal"]).sort_values("tanggal").reset_index(drop=True)

    norm_map = {normalize_key(c): c for c in raw.columns}
    component_map = {
        "Konsumsi RT": norm_map.get("konsumsi_rt"),
        "Konsumsi LNPRT": norm_map.get("konsumsi_lnprt"),
        "PKP": norm_map.get("pkp"),
        "PMTB": norm_map.get("pmtb"),
        "Change in Stocks": norm_map.get("change_in_stocks"),
        "Ekspor": norm_map.get("ekspor"),
        "Impor": norm_map.get("impor"),
        "Statistical Discrepancy": norm_map.get("statistical_discrepancy"),
        "PDB Aggregate Existing": norm_map.get("pdb_aggregate"),
    }

    wide = pd.DataFrame({"tanggal": raw["tanggal"]})
    for indikator in ["Konsumsi RT", "Konsumsi LNPRT", "PKP", "PMTB", "Change in Stocks", "Ekspor", "Impor"]:
        src = component_map.get(indikator)
        wide[indikator] = pd.to_numeric(raw[src], errors="coerce") if src in raw.columns else None

    if component_map.get("PDB Aggregate Existing") in raw.columns:
        wide["PDB Aggregate"] = pd.to_numeric(raw[component_map["PDB Aggregate Existing"]], errors="coerce")
    else:
        stat_disc = pd.to_numeric(raw[component_map["Statistical Discrepancy"]], errors="coerce") if component_map.get("Statistical Discrepancy") in raw.columns else 0.0
        wide["PDB Aggregate"] = (
            wide["Konsumsi RT"].fillna(0)
            + wide["Konsumsi LNPRT"].fillna(0)
            + wide["PKP"].fillna(0)
            + wide["PMTB"].fillna(0)
            + wide["Change in Stocks"].fillna(0)
            + wide["Ekspor"].fillna(0)
            - wide["Impor"].fillna(0)
            + stat_disc.fillna(0)
        )

    level_long = wide.melt(id_vars="tanggal", value_vars=PDB_COMPONENTS, var_name="komponen", value_name="nilai")
    level_long["nilai_fmt"] = level_long["nilai"].apply(fmt_id0)

    growth_frames = []
    for comp in PDB_COMPONENTS:
        tmp = wide[["tanggal", comp]].rename(columns={comp: "nilai"}).copy()
        tmp["komponen"] = comp
        tmp["yoy"] = tmp["nilai"].pct_change(periods=4) * 100
        tmp["qtq"] = tmp["nilai"].pct_change(periods=1) * 100
        growth_frames.append(tmp)
    growth_long = pd.concat(growth_frames, ignore_index=True)

    wide_2026 = wide.loc[wide["tanggal"].dt.year == 2026].copy()
    nominal_rows = []
    yoy_rows = []
    qtq_rows = []
    for comp in PDB_COMPONENTS:
        row_nominal = {"indikator": comp}
        row_yoy = {"indikator": comp}
        row_qtq = {"indikator": comp}
        comp_series = wide[["tanggal", comp]].copy().sort_values("tanggal")
        comp_series["tahun"] = comp_series["tanggal"].dt.year
        comp_series["quarter"] = comp_series["tanggal"].dt.quarter
        comp_series["yoy"] = comp_series[comp].pct_change(periods=4) * 100
        comp_series["qtq"] = comp_series[comp].pct_change(periods=1) * 100
        row_2026 = comp_series.loc[comp_series["tahun"] == 2026].copy()
        for q in [1, 2, 3, 4]:
            sel = row_2026.loc[row_2026["quarter"] == q]
            row_nominal[f"out_tw{q}"] = float(sel[comp].iloc[-1]) if not sel.empty else None
            row_yoy[f"out_tw{q}"] = float(sel["yoy"].iloc[-1]) if not sel.empty else None
            row_qtq[f"out_tw{q}"] = float(sel["qtq"].iloc[-1]) if not sel.empty else None
        row_nominal["full_year"] = pd.to_numeric(row_2026[comp], errors="coerce").sum(min_count=1)

        annual = comp_series.groupby("tahun", as_index=False)[comp].sum(min_count=1)
        annual["growth"] = annual[comp].pct_change() * 100
        annual_2026 = annual.loc[annual["tahun"] == 2026, "growth"]
        row_yoy["full_year"] = float(annual_2026.iloc[-1]) if not annual_2026.empty else None
        row_qtq["full_year"] = None
        nominal_rows.append(row_nominal)
        yoy_rows.append(row_yoy)
        qtq_rows.append(row_qtq)

    nominal_2026 = pd.DataFrame(nominal_rows)
    yoy_2026 = pd.DataFrame(yoy_rows)
    qtq_2026 = pd.DataFrame(qtq_rows)

    return nominal_2026, {"wide": wide, "level": level_long, "growth": growth_long}, {"yoy": yoy_2026, "qtq": qtq_2026}


@st.cache_data(show_spinner=False)
def load_dashboard_data(source_payload: Union[str, bytes], source_key: str) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    data = {k: empty_df(k) for k in EXPECTED_SHEETS.keys()}
    workbook_payload = read_workbook_payload(source_payload, source_key)
    for block in ["simulasi", "makro", "moneter", "fiskal"]:
        if block in workbook_payload:
            data[block] = coerce_schema(workbook_payload[block], block)

    # Prioritas tetap ke sheet realisasi bila tersedia, karena dari sini historis + growth dapat dibangun.
    if "realisasi" in workbook_payload:
        data["pdb"], pdb_history, pdb_tables = derive_pdb_from_realisasi(source_payload, source_key)
    elif "pdb" in workbook_payload:
        data["pdb"] = coerce_schema(workbook_payload["pdb"], "pdb")
        pdb_history = {"wide": pd.DataFrame(), "level": pd.DataFrame(), "growth": pd.DataFrame()}
        pdb_tables = {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}
    else:
        pdb_history = {"wide": pd.DataFrame(), "level": pd.DataFrame(), "growth": pd.DataFrame()}
        pdb_tables = {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}
    return data, pdb_history, pdb_tables


# =========================
# Tabel & chart PDB
# =========================
def render_table_block(block_df: pd.DataFrame, accent: bool = False, block_key: str = "") -> None:
    html_table = build_sticky_html_table(
        block_df,
        header_fill=PRIMARY,
        row_fill_1=CELL_A if not accent else CELL_ORANGE,
        row_fill_2=CELL_B if not accent else "#F4E5DE",
        value_formatter=fmt_id0,
        raw_value_df=None,
        growth_mode=False,
        block_key=block_key,
    )
    st.markdown(html_table, unsafe_allow_html=True)


def render_growth_table(df: pd.DataFrame, title: str, header_fill: str) -> None:
    sub_title(title)
    table_df = filter_growth_rows(df)
    html_table = build_sticky_html_table(
        table_df,
        header_fill=header_fill,
        row_fill_1=NEUTRAL_LIGHT,
        row_fill_2="#FFFFFF",
        value_formatter=fmt_pct_id2,
        raw_value_df=table_df,
        growth_mode=True,
        block_key="pdb",
    )
    st.markdown(html_table, unsafe_allow_html=True)


def make_pdb_history_chart(pdb_history: dict[str, pd.DataFrame], selected_components: list[str]) -> go.Figure:
    if not pdb_history or pdb_history.get("level") is None or pdb_history["level"].empty:
        return placeholder_chart("Data historis PDB belum tersedia pada sumber Excel otomatis.")
    plot_df = pdb_history["level"].loc[pdb_history["level"]["komponen"].isin(selected_components)].copy()
    if plot_df.empty:
        return placeholder_chart("Komponen historis yang dipilih belum memiliki data.")
    fig = px.line(
        plot_df,
        x="tanggal",
        y="nilai",
        color="komponen",
        color_discrete_sequence=[PRIMARY, ACCENT, SUCCESS, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"],
        custom_data=["nilai_fmt"],
    )
    fig.update_traces(mode="lines+markers", line=dict(width=2.6), marker=dict(size=5.5), hovertemplate="%{x|%Y-%m-%d}: %{customdata[0]}")
    tickvals, ticktext = make_tick_values(plot_df["nilai"])
    fig.update_layout(
        title="Historis Komponen PDB",
        height=395,
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        legend_title_text="Komponen",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, tickmode="array", tickvals=tickvals, ticktext=ticktext)
    return fig


def make_growth_chart(pdb_history: dict[str, pd.DataFrame], selected_components: list[str], growth_col: str, title: str, colors: Optional[list[str]] = None) -> go.Figure:
    if not pdb_history or pdb_history.get("growth") is None or pdb_history["growth"].empty:
        return placeholder_chart("Data pertumbuhan PDB belum tersedia pada sumber Excel otomatis.")
    plot_df = pdb_history["growth"].loc[pdb_history["growth"]["komponen"].isin(selected_components)].copy()
    if plot_df.empty:
        return placeholder_chart("Komponen pertumbuhan yang dipilih belum memiliki data.")
    plot_df["nilai_fmt"] = plot_df[growth_col].apply(fmt_pct_id2)
    fig = px.line(
        plot_df,
        x="tanggal",
        y=growth_col,
        color="komponen",
        color_discrete_sequence=colors or [PRIMARY, ACCENT, SUCCESS, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"],
        custom_data=["nilai_fmt"],
    )
    fig.update_traces(mode="lines+markers", line=dict(width=2.4), marker=dict(size=5.0), hovertemplate="%{x|%Y-%m-%d}: %{customdata[0]}")
    tickvals, ticktext = make_tick_values_pct(plot_df[growth_col])
    fig.update_layout(
        title=title,
        height=395,
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        legend_title_text="Komponen",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=True, tickmode="array", tickvals=tickvals, ticktext=ticktext)
    return fig


# =========================
# Simulasi fiskal (dibuat ringan)
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
    df = df[["indikator", *SIMULASI_FISKAL_COLS]].copy()
    df["indikator"] = SIMULASI_FISKAL_ROWS
    for col in SIMULASI_FISKAL_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    st.session_state["simulasi_fiskal_df"] = df
    return df


def render_simulasi_fiskal_editor() -> pd.DataFrame:
    base_df = get_simulasi_fiskal_df()
    block_card("Simulasi Fiskal", "Editor dibungkus dalam form agar dashboard tidak rerun penuh di setiap ketikan. Perhitungan baru dijalankan setelah klik tombol Terapkan Simulasi.")
    with st.form("simulasi_fiskal_form", clear_on_submit=False):
        edited = st.data_editor(
            base_df,
            key="simulasi_fiskal_editor",
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=["indikator"],
            column_config={
                "indikator": st.column_config.TextColumn("Instrumen", width="medium"),
                "out_tw1": st.column_config.NumberColumn("Outlook Q1", format="%.2f"),
                "out_tw2": st.column_config.NumberColumn("Outlook Q2", format="%.2f"),
                "out_tw3": st.column_config.NumberColumn("Outlook Q3", format="%.2f"),
                "out_tw4": st.column_config.NumberColumn("Outlook Q4", format="%.2f"),
            },
        )
        submitted = st.form_submit_button("Terapkan Simulasi", type="primary", use_container_width=False)
    if submitted:
        edited = edited[["indikator", *SIMULASI_FISKAL_COLS]].copy()
        edited["indikator"] = SIMULASI_FISKAL_ROWS
        for col in SIMULASI_FISKAL_COLS:
            edited[col] = pd.to_numeric(edited[col], errors="coerce").fillna(0.0)
        st.session_state["simulasi_fiskal_df"] = edited
        st.success("Simulasi fiskal diperbarui.")
    st.markdown('<div class="small-muted">Satuan input simulasi diasumsikan sama dengan satuan nominal pada tabel PDB.</div>', unsafe_allow_html=True)
    close_block_card()
    return get_simulasi_fiskal_df()


def apply_simulasi_fiskal_to_pdb_nominal(pdb_df: pd.DataFrame, simulasi_df: pd.DataFrame) -> pd.DataFrame:
    if pdb_df is None or pdb_df.empty:
        return empty_df("pdb")
    out = ensure_full_year_from_quarters(pdb_df).copy()
    for col in SIMULASI_FISKAL_COLS:
        if col not in out.columns:
            out[col] = 0.0
    for _, row in simulasi_df.iterrows():
        target = FISCAL_TO_PDB_MAP.get(str(row["indikator"]))
        if not target:
            continue
        mask = out["indikator"] == target
        if not mask.any():
            continue
        for col in SIMULASI_FISKAL_COLS:
            out.loc[mask, col] = pd.to_numeric(out.loc[mask, col], errors="coerce").fillna(0).values + float(row[col])
    out["full_year"] = out[SIMULASI_FISKAL_COLS].sum(axis=1, min_count=1)

    component_values = {name: out.loc[out["indikator"] == name, SIMULASI_FISKAL_COLS].sum() for name in PDB_COMPONENTS if name != "PDB Aggregate"}
    mask_agg = out["indikator"] == "PDB Aggregate"
    if mask_agg.any():
        agg_quarters = (
            component_values.get("Konsumsi RT", pd.Series(dtype=float)).fillna(0)
            + component_values.get("Konsumsi LNPRT", pd.Series(dtype=float)).fillna(0)
            + component_values.get("PKP", pd.Series(dtype=float)).fillna(0)
            + component_values.get("PMTB", pd.Series(dtype=float)).fillna(0)
            + component_values.get("Change in Stocks", pd.Series(dtype=float)).fillna(0)
            + component_values.get("Ekspor", pd.Series(dtype=float)).fillna(0)
            - component_values.get("Impor", pd.Series(dtype=float)).fillna(0)
        )
        for col in SIMULASI_FISKAL_COLS:
            out.loc[mask_agg, col] = float(agg_quarters[col]) if col in agg_quarters.index else None
        out.loc[mask_agg, "full_year"] = pd.to_numeric(out.loc[mask_agg, SIMULASI_FISKAL_COLS].iloc[0], errors="coerce").sum(min_count=1)
    return out


def adjusted_wide_history_from_nominal(base_wide: pd.DataFrame, adjusted_nominal: pd.DataFrame) -> pd.DataFrame:
    if base_wide is None or base_wide.empty:
        return pd.DataFrame()
    wide = base_wide.copy()
    wide["tahun"] = wide["tanggal"].dt.year
    wide["quarter"] = wide["tanggal"].dt.quarter
    for comp in PDB_COMPONENTS:
        row = adjusted_nominal.loc[adjusted_nominal["indikator"] == comp]
        if row.empty:
            continue
        for q in [1, 2, 3, 4]:
            value = row.iloc[0].get(f"out_tw{q}")
            mask = (wide["tahun"] == 2026) & (wide["quarter"] == q)
            if mask.any():
                wide.loc[mask, comp] = value
    return wide.drop(columns=["tahun", "quarter"])


def build_growth_table_from_adjusted_wide(adjusted_wide: pd.DataFrame, growth_name: str) -> pd.DataFrame:
    periods = 4 if growth_name == "yoy" else 1
    rows = []
    for comp in PDB_COMPONENTS:
        s = adjusted_wide[["tanggal", comp]].copy().sort_values("tanggal")
        s["tahun"] = s["tanggal"].dt.year
        s["quarter"] = s["tanggal"].dt.quarter
        s[growth_name] = s[comp].pct_change(periods=periods) * 100
        s_2026 = s.loc[s["tahun"] == 2026].copy()
        row = {"indikator": comp}
        for q in [1, 2, 3, 4]:
            sel = s_2026.loc[s_2026["quarter"] == q, growth_name]
            row[f"out_tw{q}"] = float(sel.iloc[-1]) if not sel.empty else None
        if growth_name == "yoy":
            annual = s.groupby("tahun", as_index=False)[comp].sum(min_count=1)
            annual[growth_name] = annual[comp].pct_change() * 100
            annual_2026 = annual.loc[annual["tahun"] == 2026, growth_name]
            row["full_year"] = float(annual_2026.iloc[-1]) if not annual_2026.empty else None
        else:
            row["full_year"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def build_adjusted_top_growth_tables(pdb_history: dict[str, pd.DataFrame], adjusted_nominal: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if not pdb_history or pdb_history.get("wide") is None or pdb_history["wide"].empty:
        return {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}
    if adjusted_nominal is None or adjusted_nominal.empty:
        return {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}
    adjusted_wide = adjusted_wide_history_from_nominal(pdb_history["wide"], adjusted_nominal)
    if adjusted_wide.empty:
        return {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}
    return {
        "yoy": build_growth_table_from_adjusted_wide(adjusted_wide, "yoy"),
        "qtq": build_growth_table_from_adjusted_wide(adjusted_wide, "qtq"),
    }


# =========================
# Main UI dengan lazy loading
# =========================
source_payload, source_status, source_key = detect_excel_source()
if source_payload is None:
    st.title("Dashboard Pemantauan PDB")
    st.markdown(f'<div class="status-box">{html.escape(source_status)}</div>', unsafe_allow_html=True)
    st.stop()

workbook, pdb_history, pdb_tables = load_dashboard_data(source_payload, source_key)
base_pdb_nominal = ensure_full_year_from_quarters(workbook["pdb"])

st.sidebar.markdown("## Pengaturan Dashboard")
show_preview = st.sidebar.toggle("Tampilkan preview data mentah", value=False)
st.sidebar.markdown("### Sumber Data")
st.sidebar.info(source_status)
active_block = st.sidebar.radio(
    "Pilih blok yang ingin dibuka",
    options=["Ringkasan Utama", "Blok Makro", "Blok Accounting", "Blok Moneter", "Blok Fiskal"],
    index=0,
)

st.title("Dashboard Pemantauan PDB")
st.markdown("---")
st.markdown(f'<div class="status-box">{html.escape(source_status)}</div>', unsafe_allow_html=True)

simulasi_fiskal_df = render_simulasi_fiskal_editor()
adjusted_pdb_nominal = apply_simulasi_fiskal_to_pdb_nominal(base_pdb_nominal, simulasi_fiskal_df)

# ---- Ringkasan utama (lazy via radio, bukan st.tabs) ----
if active_block == "Ringkasan Utama":
    block_card("Tabel Utama — Blok Accounting", BLOCK_NOTES["pdb"])
    top_view = st.radio(
        "Pilih tampilan tabel utama",
        options=["Tabel Nominal 2026", "Tabel Year on Year (YoY)", "Tabel Quarter to Quarter (QtQ)"],
        horizontal=True,
        label_visibility="collapsed",
        key="top_view_selector",
    )
    if top_view == "Tabel Nominal 2026":
        render_table_block(filter_main_pdb_rows(adjusted_pdb_nominal), block_key="pdb")
    else:
        adjusted_top_tables = build_adjusted_top_growth_tables(pdb_history, adjusted_pdb_nominal)
        if top_view == "Tabel Year on Year (YoY)":
            render_growth_table(adjusted_top_tables.get("yoy", empty_df("pdb")), "Tabel Year on Year (YoY)", header_fill=PRIMARY)
        else:
            render_growth_table(adjusted_top_tables.get("qtq", empty_df("pdb")), "Tabel Quarter to Quarter (QtQ)", header_fill=PRIMARY)
    close_block_card()

elif active_block == "Blok Makro":
    block_card(BLOCK_TITLES["makro"], BLOCK_NOTES["makro"])
    render_table_block(workbook["makro"], block_key="makro")
    close_block_card()

elif active_block == "Blok Accounting":
    block_card(BLOCK_TITLES["pdb"], BLOCK_NOTES["pdb"])
    pdb_table_view = st.radio(
        "Pilih tampilan accounting",
        options=["Tabel Nominal 2026", "Tabel Year on Year (YoY)", "Tabel Quarter to Quarter (QtQ)"],
        horizontal=True,
        label_visibility="collapsed",
        key="pdb_table_view",
    )
    if pdb_table_view == "Tabel Nominal 2026":
        render_table_block(workbook["pdb"], block_key="pdb")
    elif pdb_table_view == "Tabel Year on Year (YoY)":
        render_growth_table(pdb_tables.get("yoy", empty_df("pdb")), "Tabel Year on Year (YoY)", header_fill=PRIMARY)
    else:
        render_growth_table(pdb_tables.get("qtq", empty_df("pdb")), "Tabel Quarter to Quarter (QtQ)", header_fill=PRIMARY)

    st.markdown("<hr>", unsafe_allow_html=True)
    selected_components = st.multiselect(
        "Pilih komponen historis yang ingin ditampilkan",
        options=PDB_COMPONENTS,
        default=PDB_COMPONENTS,
        key="hist_components_pdb",
    )
    selected_components = selected_components or PDB_COMPONENTS
    selected_growth_components = filter_growth_components(selected_components)
    chart_view = st.radio(
        "Pilih tampilan chart",
        options=["Historis Level", "Year on Year (YoY)", "Quarter to Quarter (QtQ)"],
        horizontal=True,
        label_visibility="collapsed",
        key="pdb_chart_view",
    )
    if chart_view == "Historis Level":
        fig = make_pdb_history_chart(pdb_history, selected_components)
    elif chart_view == "Year on Year (YoY)":
        fig = make_growth_chart(
            pdb_history,
            selected_growth_components,
            "yoy",
            "Pertumbuhan Year on Year (YoY)",
            colors=[SUCCESS, ACCENT, PRIMARY, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"],
        )
    else:
        fig = make_growth_chart(
            pdb_history,
            selected_growth_components,
            "qtq",
            "Pertumbuhan Quarter to Quarter (QtQ)",
            colors=[PURPLE, SUCCESS, PRIMARY, ACCENT, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"],
        )
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    close_block_card()

elif active_block == "Blok Moneter":
    block_card(BLOCK_TITLES["moneter"], BLOCK_NOTES["moneter"])
    render_table_block(workbook["moneter"], block_key="moneter")
    close_block_card()

elif active_block == "Blok Fiskal":
    block_card(BLOCK_TITLES["fiskal"], BLOCK_NOTES["fiskal"])
    render_table_block(workbook["fiskal"], block_key="fiskal")
    close_block_card()

with st.expander("Lihat struktur sumber Excel"):
    info = pd.DataFrame(
        {
            "Sumber": [REPO_FILE_NAME, "st.secrets['github_raw_xlsx_url'] (opsional)"],
            "Keterangan": [
                "File diletakkan di repo yang sama dengan app.py sehingga otomatis terbaca saat deploy Streamlit dari GitHub.",
                "Dipakai hanya bila file Excel tidak diletakkan langsung di repo lokal.",
            ],
        }
    )
    st.dataframe(info, use_container_width=True, hide_index=True)

if show_preview:
    with st.expander("Preview data yang berhasil dimuat", expanded=False):
        preview_names = ["Simulasi", "Makro", "PDB Nominal", "PDB YoY", "PDB QtQ", "Moneter", "Fiskal", "Simulasi Fiskal Aktif"]
        preview_frames = [
            workbook["simulasi"],
            workbook["makro"],
            ensure_full_year_from_quarters(workbook["pdb"]),
            filter_growth_rows(pdb_tables.get("yoy", empty_df("pdb"))),
            filter_growth_rows(pdb_tables.get("qtq", empty_df("pdb"))),
            workbook["moneter"],
            workbook["fiskal"],
            simulasi_fiskal_df,
        ]
        preview_choice = st.selectbox("Pilih preview", preview_names, index=0)
        preview_map = dict(zip(preview_names, preview_frames))
        st.dataframe(preview_map[preview_choice], use_container_width=True, hide_index=True)
        if preview_choice == "PDB Nominal" and pdb_history is not None and pdb_history.get("wide") is not None and not pdb_history["wide"].empty:
            st.markdown("### Preview wide historis PDB")
            st.dataframe(pdb_history["wide"], use_container_width=True, hide_index=True)
