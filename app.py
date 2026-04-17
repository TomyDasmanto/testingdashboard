
import math
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Union
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
EXCLUDE_GROWTH_ROWS = ["Change in Stocks"]
PDB_MAIN_HIDE = ["Konsumsi LNPRT", "Change in Stocks"]

SIMULASI_FISKAL_ROWS = [
    "Bantuan Pangan",
    "Bantuan Langsung Tunai",
    "Kenaikan Gaji",
    "Pembayaran Gaji 14",
    "Diskon Transportasi",
    "Investasi",
]
SIMULASI_FISKAL_COLS = ["out_tw1", "out_tw2", "out_tw3", "out_tw4"]

FISKAL_BASELINE_ROWS = [
    ("A  Pendapatan Negara dan Hibah", 3153580.45),
    ("1. Penerimaan Perpajakan", 2693714.24),
    ("2. Penerimaan Negara Bukan Pajak", 459199.94),
    ("3. Hibah", 666.27),
    ("B  Belanja Negara", 3842728.37),
    ("1. Belanja Pemerintah Pusat", 3149733.39),
    ("2. Transfer ke Daerah", 692994.97),
    ("C  Surplus/(Defisit) Anggaran", -689147.92),
    ("D  Pembiayaan Anggaran", 689147.92),
]
FISKAL_OUTLOOK_DEFAULT = {label: None for label, _ in FISKAL_BASELINE_ROWS}

MAKRO_ADEM_ROWS = [
    ("Pertumbuhan ekonomi (%)", 5.4, None, None),
    ("Inflasi (%)", 2.5, None, None),
    ("Tingkat bunga SUN 10 tahun", 6.9, None, None),
    ("Nilai tukar (Rp100/US$1)", 16500.0, None, None),
    ("Harga minyak (US$/barel)", 70.0, None, None),
    ("Lifting minyak (ribu barel per hari)", 610.0, None, None),
    ("Lifting Gas Bumi (ribu barel setara minyak per hari)", 984.0, None, None),
]

st.markdown(
    f"""
    <style>
        .main {{ background-color: {BG}; }}
        .block-title {{ font-size: 1.05rem; font-weight: 700; color: {TEXT}; margin: 0.15rem 0 0.35rem 0; }}
        .sub-title {{ font-size: 0.95rem; font-weight: 700; color: {TEXT}; margin: 0.15rem 0 0.35rem 0; }}
        .section-note {{ color: #6B7280; font-size: 0.88rem; margin-bottom: 0.45rem; }}
        .status-box {{ border: 1px dashed rgba(62,109,181,0.30); border-radius: 12px; padding: 0.55rem 0.75rem; background: rgba(62,109,181,0.03); color: #374151; margin-bottom: 0.75rem; font-size: 0.86rem; }}
        .fiscal-editor-header {{ display:block; margin-top:0.35rem; margin-bottom:0.25rem; }}
        .fiscal-editor-title {{ color: {PRIMARY}; font-size: 1.02rem; font-weight: 700; display:inline; }}
        .fiscal-editor-unit {{ color: #111827; font-size: 0.92rem; display:inline; margin-left: 0.35rem; }}
        .macro-adem-wrap, .simple-fiskal-wrap {{ font-family: inherit; }}
        .macro-adem-wrap table, .simple-fiskal-wrap table {{ width: 100%; border-collapse: collapse; table-layout: fixed; font-family: inherit; font-size: 0.95rem; line-height: 1.35; background: white; color: {TEXT}; }}
        .macro-adem-wrap th, .macro-adem-wrap td, .simple-fiskal-wrap th, .simple-fiskal-wrap td {{ border: 1px solid #D1D5DB; padding: 0.48rem 0.70rem; font-family: inherit; font-size: 0.95rem; }}
        .macro-adem-wrap th, .simple-fiskal-wrap th {{ color: {TEXT}; font-weight: 600; text-align: center; background: #FFFFFF; }}
        .macro-adem-wrap td, .simple-fiskal-wrap td {{ font-weight: 400; background: #FFFFFF; }}
        .macro-adem-wrap th:first-child, .simple-fiskal-wrap th:first-child {{ text-align: left; }}
        .macro-adem-wrap td:first-child, .simple-fiskal-wrap td:first-child {{ text-align: left; white-space: normal; word-break: break-word; }}
        .macro-adem-wrap td:nth-child(2), .macro-adem-wrap td:nth-child(3), .macro-adem-wrap td:nth-child(4), .simple-fiskal-wrap td:nth-child(2), .simple-fiskal-wrap td:nth-child(3) {{ text-align: right; font-weight: 400; }}
        .macro-adem-wrap th:nth-child(2) {{ background: #8FAFD1; }}
        .macro-adem-wrap td:nth-child(2) {{ background: #A9C2DE; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def normalize_key(text: object) -> str:
    return str(text).strip().lower().replace(" ", "_").replace(".", "").replace("-", "_")


def _format_id_number(val: float, decimals: int = 0) -> str:
    s = f"{float(val):,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_id0(val):
    if pd.isna(val) or val is None:
        return "—"
    try:
        return _format_id_number(val, 0)
    except Exception:
        return str(val)


def fmt_id1(val):
    if pd.isna(val) or val is None:
        return "—"
    try:
        return _format_id_number(val, 1)
    except Exception:
        return str(val)


def fmt_id2(val):
    if pd.isna(val) or val is None:
        return "—"
    try:
        return _format_id_number(val, 2)
    except Exception:
        return str(val)


def fmt_pct_id2(val):
    if pd.isna(val) or val is None:
        return "—"
    try:
        return _format_id_number(val, 2) + "%"
    except Exception:
        return str(val)


def make_tick_values(series: pd.Series, n: int = 6):
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


def make_tick_values_pct(series: pd.Series, n: int = 6):
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


def ensure_full_year_from_quarters(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for col in ["out_tw1", "out_tw2", "out_tw3", "out_tw4"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work["full_year"] = work[["out_tw1", "out_tw2", "out_tw3", "out_tw4"]].sum(axis=1, min_count=1)
    return work


def format_period_table(df: pd.DataFrame, pct: bool = False) -> pd.DataFrame:
    work = df[["indikator", *PERIOD_ORDER]].copy().rename(columns={"indikator": "Indikator", **PERIOD_MAP})
    formatter = fmt_pct_id2 if pct else fmt_id0
    for col in work.columns[1:]:
        work[col] = work[col].apply(formatter)
    return work.fillna("—")


def filter_growth_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["indikator", *PERIOD_ORDER])
    return df[~df["indikator"].isin(EXCLUDE_GROWTH_ROWS)].copy()


def filter_growth_components(components: list[str]) -> list[str]:
    return [c for c in components if c not in EXCLUDE_GROWTH_ROWS]


def filter_main_pdb_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["indikator"].isin(PDB_MAIN_HIDE)].copy()


def simple_block_df(indicators: list[str]) -> pd.DataFrame:
    df = pd.DataFrame({"indikator": indicators})
    for col in PERIOD_ORDER:
        df[col] = None
    return df


def get_fiskal_outlook_map() -> dict:
    if "fiskal_outlook_map" not in st.session_state:
        st.session_state["fiskal_outlook_map"] = FISKAL_OUTLOOK_DEFAULT.copy()
    outlook_map = st.session_state["fiskal_outlook_map"].copy()
    for label, _ in FISKAL_BASELINE_ROWS:
        outlook_map.setdefault(label, None)
    return outlook_map


def load_excel_bytes_from_url(url: str) -> bytes:
    with urlopen(url) as response:
        return response.read()


def open_excel_source(source: Union[str, bytes, bytearray]):
    if isinstance(source, (bytes, bytearray)):
        return pd.ExcelFile(BytesIO(source), engine="openpyxl")
    return pd.ExcelFile(source, engine="openpyxl")


def detect_excel_source() -> Tuple[Optional[Union[str, bytes]], str]:
    local_path = Path(__file__).resolve().parent / REPO_FILE_NAME
    if local_path.exists():
        return str(local_path), f"Sumber data otomatis: file lokal {REPO_FILE_NAME}"
    if GITHUB_RAW_XLSX_URL:
        return load_excel_bytes_from_url(GITHUB_RAW_XLSX_URL), "Sumber data otomatis: GitHub Raw URL dari st.secrets['github_raw_xlsx_url']"
    return None, "File Excel belum ditemukan. Simpan dashboard PDB.xlsx di folder yang sama dengan app.py atau isi st.secrets['github_raw_xlsx_url']."


def _choose_realisasi_column(columns: list[str], target: str) -> Optional[str]:
    target_norm = normalize_key(target)
    for col in columns:
        if normalize_key(col) == target_norm:
            return col
    return None


def _build_period_table_from_series_map(df: pd.DataFrame, row_map: dict[str, str]) -> pd.DataFrame:
    out = []
    for indikator, source_col in row_map.items():
        row_df = df[["tanggal", source_col]].copy().sort_values("tanggal")
        row_df["tahun"] = row_df["tanggal"].dt.year
        row_df["quarter"] = row_df["tanggal"].dt.quarter
        row_2026 = row_df[row_df["tahun"] == 2026].copy()
        quarter_values = {}
        for q in [1, 2, 3, 4]:
            sel = row_2026.loc[row_2026["quarter"] == q, source_col]
            quarter_values[f"out_tw{q}"] = float(sel.iloc[-1]) if not sel.empty else None
        fy = sum(v for v in quarter_values.values() if v is not None) if any(v is not None for v in quarter_values.values()) else None
        out.append({"indikator": indikator, **quarter_values, "full_year": fy})
    return pd.DataFrame(out)


def _build_growth_table(level_df: pd.DataFrame, periods: int, growth_name: str) -> pd.DataFrame:
    out_rows = []
    for indikator in PDB_COMPONENTS:
        s = level_df[["tanggal", indikator]].copy().sort_values("tanggal")
        s[growth_name] = s[indikator].pct_change(periods=periods) * 100
        s["tahun"] = s["tanggal"].dt.year
        s["quarter"] = s["tanggal"].dt.quarter
        s_2026 = s[s["tahun"] == 2026].copy()
        quarter_values = {}
        for q in [1, 2, 3, 4]:
            sel = s_2026.loc[s_2026["quarter"] == q, growth_name]
            quarter_values[f"out_tw{q}"] = float(sel.iloc[-1]) if not sel.empty else None
        annual = s.assign(yearly_sum=s.groupby("tahun")[indikator].transform("sum"))[["tahun", "yearly_sum"]].drop_duplicates().sort_values("tahun")
        annual[growth_name] = annual["yearly_sum"].pct_change(periods=1) * 100
        annual_2026 = annual.loc[annual["tahun"] == 2026, growth_name]
        full_year = float(annual_2026.iloc[-1]) if not annual_2026.empty else None
        out_rows.append({"indikator": indikator, **quarter_values, "full_year": full_year})
    return pd.DataFrame(out_rows)


def derive_pdb_from_realisasi(source: Union[str, bytes]):
    xls = open_excel_source(source)
    if "realisasi" not in {s.lower().strip() for s in xls.sheet_names}:
        return pd.DataFrame(), None, None

    realisasi_name = next(s for s in xls.sheet_names if s.lower().strip() == "realisasi")
    raw = pd.read_excel(xls, sheet_name=realisasi_name, engine="openpyxl")
    raw = raw.rename(columns={raw.columns[0]: "tanggal"}).copy()
    raw["tanggal"] = pd.to_datetime(raw["tanggal"], errors="coerce")
    raw = raw.dropna(subset=["tanggal"]).sort_values("tanggal").reset_index(drop=True)

    alias_map = {
        "Konsumsi RT": ["Konsumsi_RT"],
        "Konsumsi LNPRT": ["Konsumsi_LNPRT"],
        "PKP": ["PKP"],
        "PMTB": ["PMTB"],
        "Change in Stocks": ["Change_in_Stocks"],
        "Ekspor": ["Ekspor"],
        "Impor": ["Impor"],
        "Statistical Discrepancy": ["Statistical_Discrepancy"],
    }

    mapping = {}
    for indikator, aliases in alias_map.items():
        source_col = _choose_realisasi_column(list(raw.columns), indikator)
        if source_col is None:
            for alias in aliases:
                source_col = _choose_realisasi_column(list(raw.columns), alias)
                if source_col is not None:
                    break
        if source_col is not None:
            mapping[indikator] = source_col

    level_df = raw[["tanggal", *mapping.values()]].copy().rename(columns={v: k for k, v in mapping.items()})
    for indikator in alias_map.keys():
        if indikator not in level_df.columns:
            level_df[indikator] = None
        level_df[indikator] = pd.to_numeric(level_df[indikator], errors="coerce")

    level_df["PDB Aggregate"] = (
        level_df["Konsumsi RT"].fillna(0)
        + level_df["Konsumsi LNPRT"].fillna(0)
        + level_df["PKP"].fillna(0)
        + level_df["PMTB"].fillna(0)
        + level_df["Change in Stocks"].fillna(0)
        + level_df["Ekspor"].fillna(0)
        - level_df["Impor"].fillna(0)
        + level_df["Statistical Discrepancy"].fillna(0)
    )
    level_df = level_df[["tanggal", *PDB_COMPONENTS]].copy()

    nominal = ensure_full_year_from_quarters(_build_period_table_from_series_map(level_df, {k: k for k in PDB_COMPONENTS}))
    yoy = _build_growth_table(level_df, periods=4, growth_name="yoy")
    qtq = _build_growth_table(level_df, periods=1, growth_name="qtq")

    hist_level = level_df.melt(id_vars="tanggal", value_vars=PDB_COMPONENTS, var_name="komponen", value_name="nilai")
    hist_level["nilai_fmt"] = hist_level["nilai"].apply(fmt_id0)
    growth_parts = []
    for indikator in PDB_COMPONENTS:
        temp = level_df[["tanggal", indikator]].copy().sort_values("tanggal")
        temp["komponen"] = indikator
        temp["yoy"] = temp[indikator].pct_change(4) * 100
        temp["qtq"] = temp[indikator].pct_change(1) * 100
        growth_parts.append(temp[["tanggal", "komponen", "yoy", "qtq"]])
    hist_growth = pd.concat(growth_parts, ignore_index=True)
    return nominal, {"level": hist_level, "growth": hist_growth}, {"yoy": yoy, "qtq": qtq}


def build_simulasi_fiskal_df() -> pd.DataFrame:
    return pd.DataFrame({
        "indikator": SIMULASI_FISKAL_ROWS,
        "out_tw1": [0.0] * len(SIMULASI_FISKAL_ROWS),
        "out_tw2": [0.0] * len(SIMULASI_FISKAL_ROWS),
        "out_tw3": [0.0] * len(SIMULASI_FISKAL_ROWS),
        "out_tw4": [0.0] * len(SIMULASI_FISKAL_ROWS),
    })


def get_simulasi_fiskal_df() -> pd.DataFrame:
    if "simulasi_fiskal_df" not in st.session_state:
        st.session_state["simulasi_fiskal_df"] = build_simulasi_fiskal_df()
    df = st.session_state["simulasi_fiskal_df"].copy()
    df["indikator"] = SIMULASI_FISKAL_ROWS
    for col in SIMULASI_FISKAL_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df[["indikator", *SIMULASI_FISKAL_COLS]].copy()


def apply_simulasi_fiskal_to_pdb_nominal(pdb_df: pd.DataFrame, simulasi_df: pd.DataFrame) -> pd.DataFrame:
    if pdb_df is None or pdb_df.empty:
        return pdb_df
    work = ensure_full_year_from_quarters(pdb_df.copy())
    if simulasi_df is None or simulasi_df.empty:
        return work

    sim = simulasi_df.copy()
    sim["indikator"] = sim["indikator"].astype(str).str.strip()
    rules = [
        {"sim_indicator": "Bantuan Pangan", "target_indicator": "PKP", "divisors": {"out_tw1": 1.82, "out_tw2": 1.86, "out_tw3": 1.88, "out_tw4": 1.91}},
        {"sim_indicator": "Bantuan Langsung Tunai", "target_indicator": "Konsumsi RT", "divisors": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86}},
        {"sim_indicator": "Kenaikan Gaji", "target_indicator": "Konsumsi RT", "divisors": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86}},
        {"sim_indicator": "Pembayaran Gaji 14", "target_indicator": "Konsumsi RT", "divisors": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86}},
        {"sim_indicator": "Diskon Transportasi", "target_indicator": "Konsumsi RT", "divisors": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86}},
        {"sim_indicator": "Investasi", "target_indicator": "PMTB", "divisors": {"out_tw1": 1.66, "out_tw2": 1.66, "out_tw3": 1.67, "out_tw4": 1.67}},
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
            input_val = pd.to_numeric(sim_row.iloc[0].get(col, 0), errors="coerce")
            input_val = 0.0 if pd.isna(input_val) else float(input_val)
            addition = input_val / div if div else 0.0
            base_target = pd.to_numeric(work.loc[target_mask, col], errors="coerce").fillna(0.0)
            work.loc[target_mask, col] = base_target + addition
            if agg_mask.any():
                base_agg = pd.to_numeric(work.loc[agg_mask, col], errors="coerce").fillna(0.0)
                work.loc[agg_mask, col] = base_agg + addition
    return ensure_full_year_from_quarters(work)


def build_adjusted_top_growth_tables(pdb_history: Optional[dict], adjusted_nominal: pd.DataFrame):
    if not pdb_history or pdb_history.get("level") is None or pdb_history["level"].empty:
        empty = pd.DataFrame(columns=["indikator", *PERIOD_ORDER])
        return {"yoy": empty, "qtq": empty}
    if adjusted_nominal is None or adjusted_nominal.empty:
        empty = pd.DataFrame(columns=["indikator", *PERIOD_ORDER])
        return {"yoy": empty, "qtq": empty}

    wide = pdb_history["level"].pivot_table(index="tanggal", columns="komponen", values="nilai", aggfunc="last").reset_index()
    date_map = {
        "out_tw1": pd.Timestamp("2026-03-31"),
        "out_tw2": pd.Timestamp("2026-06-30"),
        "out_tw3": pd.Timestamp("2026-09-30"),
        "out_tw4": pd.Timestamp("2026-12-31"),
    }
    for comp in PDB_COMPONENTS:
        if comp not in wide.columns:
            wide[comp] = None
        wide[comp] = pd.to_numeric(wide[comp], errors="coerce")

    adj = adjusted_nominal.copy()
    adj["indikator"] = adj["indikator"].astype(str).str.strip()
    for _, row in adj.iterrows():
        indikator = row["indikator"]
        if indikator not in PDB_COMPONENTS:
            continue
        for col, dt in date_map.items():
            val = pd.to_numeric(row.get(col), errors="coerce")
            if pd.isna(val):
                continue
            wide.loc[wide["tanggal"] == dt, indikator] = float(val)

    wide = wide[["tanggal", *PDB_COMPONENTS]].copy()
    return {"yoy": _build_growth_table(wide, periods=4, growth_name="yoy"), "qtq": _build_growth_table(wide, periods=1, growth_name="qtq")}


def render_simulasi_fiskal_editor() -> pd.DataFrame:
    st.markdown('<div class="fiscal-editor-header"><span class="fiscal-editor-title">SIMULASI FISKAL</span><span class="fiscal-editor-unit">(dalam Miliar)</span></div>', unsafe_allow_html=True)
    if "simulasi_fiskal_draft" not in st.session_state:
        st.session_state["simulasi_fiskal_draft"] = get_simulasi_fiskal_df().copy()

    with st.form("simulasi_fiskal_form", clear_on_submit=False):
        draft_df = st.session_state["simulasi_fiskal_draft"].copy()
        edited_df = st.data_editor(
            draft_df,
            key="simulasi_fiskal_editor",
            hide_index=True,
            use_container_width=False,
            width=760,
            num_rows="fixed",
            disabled=["indikator"],
            column_config={
                "indikator": st.column_config.TextColumn("SIMULASI FISKAL", width="medium"),
                "out_tw1": st.column_config.NumberColumn("Q1", format="%.2f", step=0.01, width="small"),
                "out_tw2": st.column_config.NumberColumn("Q2", format="%.2f", step=0.01, width="small"),
                "out_tw3": st.column_config.NumberColumn("Q3", format="%.2f", step=0.01, width="small"),
                "out_tw4": st.column_config.NumberColumn("Q4", format="%.2f", step=0.01, width="small"),
            },
        )
        c1, c2 = st.columns([1, 1])
        apply_clicked = c1.form_submit_button("Terapkan Simulasi", use_container_width=True)
        reset_clicked = c2.form_submit_button("Reset Simulasi", use_container_width=True)

    edited_df = edited_df[["indikator", *SIMULASI_FISKAL_COLS]].copy()
    edited_df["indikator"] = SIMULASI_FISKAL_ROWS
    for col in SIMULASI_FISKAL_COLS:
        edited_df[col] = pd.to_numeric(edited_df[col], errors="coerce").fillna(0.0)

    if reset_clicked:
        reset_df = build_simulasi_fiskal_df()
        st.session_state["simulasi_fiskal_df"] = reset_df
        st.session_state["simulasi_fiskal_draft"] = reset_df.copy()
        st.success("Simulasi fiskal telah di-reset.")
        return reset_df
    if apply_clicked:
        st.session_state["simulasi_fiskal_df"] = edited_df
        st.session_state["simulasi_fiskal_draft"] = edited_df.copy()
        st.success("Simulasi fiskal berhasil diterapkan ke Tabel Utama.")
        return edited_df

    st.session_state["simulasi_fiskal_draft"] = edited_df.copy()
    return get_simulasi_fiskal_df()


def placeholder_chart(msg: str, height: int = 380):
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=14, color="#6B7280"))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def make_pdb_history_chart(pdb_history: Optional[dict], selected_components: list[str]):
    if not pdb_history or pdb_history.get("level") is None or pdb_history["level"].empty:
        return placeholder_chart("Data historis PDB belum tersedia pada sumber Excel otomatis.")
    plot_df = pdb_history["level"]
    plot_df = plot_df[plot_df["komponen"].isin(selected_components)].copy()
    if plot_df.empty:
        return placeholder_chart("Komponen historis yang dipilih belum memiliki data.")
    fig = px.line(plot_df, x="tanggal", y="nilai", color="komponen", color_discrete_sequence=[PRIMARY, ACCENT, SUCCESS, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"], custom_data=["nilai_fmt"])
    fig.update_traces(mode="lines+markers", line=dict(width=2.6), marker=dict(size=5.5), hovertemplate="<b>%{fullData.name}</b><br>%{x|%Y-%m-%d}: %{customdata[0]}<extra></extra>")
    tickvals, ticktext = make_tick_values(plot_df["nilai"])
    fig.update_layout(title="Historis Komponen PDB", height=395, margin=dict(l=10, r=10, t=50, b=10), hovermode="x unified", legend_title_text="Komponen", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, tickmode="array", tickvals=tickvals, ticktext=ticktext)
    return fig


def make_growth_chart(pdb_history: Optional[dict], selected_components: list[str], growth_col: str, title: str, colors=None):
    if not pdb_history or pdb_history.get("growth") is None or pdb_history["growth"].empty:
        return placeholder_chart("Data pertumbuhan PDB belum tersedia pada sumber Excel otomatis.")
    plot_df = pdb_history["growth"]
    plot_df = plot_df[plot_df["komponen"].isin(selected_components)].copy()
    if plot_df.empty:
        return placeholder_chart("Komponen pertumbuhan yang dipilih belum memiliki data.")
    plot_df["nilai_fmt"] = plot_df[growth_col].apply(fmt_pct_id2)
    fig = px.line(plot_df, x="tanggal", y=growth_col, color="komponen", color_discrete_sequence=colors or [PRIMARY, ACCENT, SUCCESS, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"], custom_data=["nilai_fmt"])
    fig.update_traces(mode="lines+markers", line=dict(width=2.4), marker=dict(size=5.0), hovertemplate="<b>%{fullData.name}</b><br>%{x|%Y-%m-%d}: %{customdata[0]}<extra></extra>")
    tickvals, ticktext = make_tick_values_pct(plot_df[growth_col])
    fig.update_layout(title=title, height=395, margin=dict(l=10, r=10, t=50, b=10), hovermode="x unified", legend_title_text="Komponen", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=True, tickmode="array", tickvals=tickvals, ticktext=ticktext)
    return fig


def block_card(title: str, note: Optional[str] = None):
    st.markdown(f'<div class="block-title">{title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="section-note">{note}</div>', unsafe_allow_html=True)


def sub_title(text: str):
    st.markdown(f'<div class="sub-title">{text}</div>', unsafe_allow_html=True)


def render_table_block(df: pd.DataFrame):
    st.dataframe(format_period_table(df, pct=False), use_container_width=True, hide_index=True)


def render_growth_table(df: pd.DataFrame, title: str):
    sub_title(title)
    st.dataframe(format_period_table(filter_growth_rows(df), pct=True), use_container_width=True, hide_index=True)


def render_makro_adem_table():
    def _fmt(v):
        return fmt_id1(v)

    rows_html = "".join(
        f"<tr><td>{label}</td><td>{_fmt(apbn)}</td><td>{_fmt(real)}</td><td>{_fmt(sens)}</td></tr>"
        for label, apbn, real, sens in MAKRO_ADEM_ROWS
    )
    html = (
        '<div class="macro-adem-wrap">'
        '<table>'
        '<thead><tr>'
        '<th style="width:61%;">Asumsi ADEM</th>'
        '<th style="width:15%;">APBN 2026</th>'
        '<th style="width:12%;">Realisasi</th>'
        '<th style="width:12%;">Sensitivitas</th>'
        '</tr></thead>'
        '<tbody>' + rows_html + '</tbody>'
        '</table>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_fiskal_baseline_table():
    def _fmt_fiskal(v):
        if v is None or pd.isna(v):
            return "—"
        s = _format_id_number(abs(float(v)), 2)
        return f"({s})" if float(v) < 0 else s

    outlook_map = get_fiskal_outlook_map()
    rows_html = "".join(
        f"<tr><td>{label}</td><td>{_fmt_fiskal(value)}</td><td>{_fmt_fiskal(outlook_map.get(label))}</td></tr>"
        for label, value in FISKAL_BASELINE_ROWS
    )
    html = (
        '<div class="simple-fiskal-wrap">'
        '<table>'
        '<thead><tr>'
        '<th style="text-align:left; width:54%;"></th>'
        '<th style="width:23%;">APBN 2026 (baseline)</th>'
        '<th style="width:23%;">Outlook</th>'
        '</tr></thead>'
        '<tbody>' + rows_html + '</tbody>'
        '</table>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def main():
    source, source_status = detect_excel_source()
    if source is None:
        st.title("Dashboard Pemantauan PDB")
        st.error(source_status)
        st.stop()

    pdb_nominal, pdb_history, pdb_tables = derive_pdb_from_realisasi(source)
    workbook = {"pdb": pdb_nominal, "moneter": simple_block_df(["PUAB", "Kredit", "DPK", "M0", "OMO"])}

    st.sidebar.markdown("## Pengaturan Dashboard")
    show_preview = st.sidebar.toggle("Tampilkan preview data mentah", value=False)
    st.sidebar.markdown("### Sumber Data")
    st.sidebar.info(source_status)

    st.title("Dashboard Pemantauan PDB")
    st.markdown("---")
    st.markdown(f"<div class='status-box'>{source_status}</div>", unsafe_allow_html=True)

    top_table_slot = st.empty()
    simulasi_fiskal_df = render_simulasi_fiskal_editor()
    adjusted_pdb_nominal = apply_simulasi_fiskal_to_pdb_nominal(workbook["pdb"], simulasi_fiskal_df)
    adjusted_top_tables = build_adjusted_top_growth_tables(pdb_history, adjusted_pdb_nominal)

    with top_table_slot.container():
        block_card("Tabel Utama — Blok Accounting", "Tabel utama ini sudah mencerminkan dampak simulasi fiskal yang diterapkan.")
        top_nominal_tab, top_yoy_tab, top_qtq_tab = st.tabs(["Tabel Nominal 2026", "Tabel Year on Year (YoY)", "Tabel Quarter to Quarter (QtQ)"])
        with top_nominal_tab:
            render_table_block(filter_main_pdb_rows(adjusted_pdb_nominal))
        with top_yoy_tab:
            render_growth_table(adjusted_top_tables.get("yoy", pd.DataFrame(columns=["indikator", *PERIOD_ORDER])), "Tabel Year on Year (YoY)")
        with top_qtq_tab:
            render_growth_table(adjusted_top_tables.get("qtq", pd.DataFrame(columns=["indikator", *PERIOD_ORDER])), "Tabel Quarter to Quarter (QtQ)")

    tab_makro, tab_pdb, tab_moneter, tab_fiskal = st.tabs(["Blok Makro", "Blok Accounting", "Blok Moneter", "Blok Fiskal"])

    with tab_makro:
        block_card("Blok Makro", "Asumsi ADEM.")
        render_makro_adem_table()

    with tab_pdb:
        block_card("Blok Accounting", "Baseline/original dari turunan sheet realisasi.")
        nominal_tab, yoy_tab, qtq_tab = st.tabs(["Tabel Nominal 2026", "Tabel Year on Year (YoY)", "Tabel Quarter to Quarter (QtQ)"])
        with nominal_tab:
            render_table_block(workbook["pdb"])
        with yoy_tab:
            render_growth_table(pdb_tables.get("yoy", pd.DataFrame(columns=["indikator", *PERIOD_ORDER])), "Tabel Year on Year (YoY)")
        with qtq_tab:
            render_growth_table(pdb_tables.get("qtq", pd.DataFrame(columns=["indikator", *PERIOD_ORDER])), "Tabel Quarter to Quarter (QtQ)")

        st.markdown("<div class='section-note'>Grafik historis tetap memakai histori level dari sheet realisasi.</div>", unsafe_allow_html=True)
        selected_components = st.multiselect("Pilih komponen historis yang ingin ditampilkan", options=PDB_COMPONENTS, default=PDB_COMPONENTS, key="hist_components_pdb")
        selected_components = selected_components or PDB_COMPONENTS
        selected_growth_components = filter_growth_components(selected_components)
        ch1, ch2, ch3 = st.tabs(["Historis Level", "Year on Year (YoY)", "Quarter to Quarter (QtQ)"])
        with ch1:
            st.plotly_chart(make_pdb_history_chart(pdb_history, selected_components), use_container_width=True, config=CHART_CONFIG)
        with ch2:
            st.plotly_chart(make_growth_chart(pdb_history, selected_growth_components, "yoy", "Pertumbuhan Year on Year (YoY)", colors=[SUCCESS, ACCENT, PRIMARY, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"]), use_container_width=True, config=CHART_CONFIG)
        with ch3:
            st.plotly_chart(make_growth_chart(pdb_history, selected_growth_components, "qtq", "Pertumbuhan Quarter to Quarter (QtQ)", colors=[PURPLE, SUCCESS, PRIMARY, ACCENT, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"]), use_container_width=True, config=CHART_CONFIG)

    with tab_moneter:
        block_card("Blok Moneter", "Placeholder moneter. Dapat diisi jika nanti workbook memiliki sheet moneter.")
        render_table_block(workbook["moneter"])

    with tab_fiskal:
        block_card("Blok Fiskal", "I-Account APBN.")
        render_fiskal_baseline_table()

    if show_preview:
        with st.expander("Preview data yang berhasil dimuat", expanded=False):
            st.markdown("### PDB Nominal Baseline")
            st.dataframe(workbook["pdb"], use_container_width=True, hide_index=True)
            st.markdown("### Simulasi Fiskal Applied")
            st.dataframe(simulasi_fiskal_df, use_container_width=True, hide_index=True)
            st.markdown("### Makro ADEM")
            st.dataframe(pd.DataFrame(MAKRO_ADEM_ROWS, columns=["Asumsi ADEM", "APBN 2026", "Realisasi", "Sensitivitas"]), use_container_width=True, hide_index=True)
            if pdb_history is not None:
                st.markdown("### Historis Level")
                st.dataframe(pdb_history["level"], use_container_width=True, hide_index=True)
                st.markdown("### Historis Growth")
                st.dataframe(pdb_history["growth"], use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
