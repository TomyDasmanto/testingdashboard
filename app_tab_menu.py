from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.request import urlopen
import html

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
INDICATOR_FILE_NAME = "dashboard indikator.xlsx"
try:
    GITHUB_RAW_XLSX_URL = st.secrets.get("github_raw_xlsx_url", "")
except Exception:
    GITHUB_RAW_XLSX_URL = ""

PRIMARY = "#3E6DB5"
SUCCESS = "#2A9D8F"
ACCENT = "#E07B39"
PURPLE = "#8A5CF6"
NEGATIVE = "#D14D72"
GRID = "rgba(31,41,55,0.12)"
TEXT = "#1F2937"

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

DEFAULT_ROWS = {
    "makro": ["Inflasi", "Rupiah", "Yield SBN", "ICP", "Nikel", "Coal", "CPO", "Lifting"],
    "moneter": ["PUAB", "Kredit", "DPK", "M0", "OMO"],
    "fiskal": ["Pendapatan", "Belanja", "Pembiayaan", "Defisit"],
    "pdb": PDB_COMPONENTS,
}

st.markdown(
    """
    <style>
        .comparison-wrap {
            overflow-x: auto;
            margin-bottom: 0.5rem;
        }
        table.comparison-table {
            border-collapse: collapse;
            width: 100%;
            min-width: 1200px;
            font-size: 0.92rem;
        }
        table.comparison-table th,
        table.comparison-table td {
            border: 1px solid #D1D5DB;
            padding: 0.50rem 0.60rem;
            text-align: center;
            white-space: nowrap;
        }
        table.comparison-table th:first-child,
        table.comparison-table td:first-child {
            text-align: left;
        }
        table.comparison-table thead th {
            background: #F3F4F6;
            font-weight: 700;
        }
        .value-up {
            background: #E8F7F2;
            color: #127A5A;
            font-weight: 700;
        }
        .value-down {
            background: #FDEBEC;
            color: #B42318;
            font-weight: 700;
        }
        .value-same {
            background: #FFFFFF;
            color: #111827;
        }
        .value-missing {
            background: #FAFAFA;
            color: #6B7280;
            font-style: italic;
        }
        .legend-row {
            display: flex;
            gap: 1rem;
            margin-top: 0.5rem;
            flex-wrap: wrap;
            font-size: 0.85rem;
        }
        .legend-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }
        .legend-swatch {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 1px solid #D1D5DB;
        }
        .legend-up { background: #E8F7F2; }
        .legend-down { background: #FDEBEC; }
        .legend-same { background: #FFFFFF; }
        .muted-note {
            color: #6B7280;
            font-size: 0.88rem;
            margin-top: 0.45rem;
        }
        .fiskal-table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 0.5rem;
        }
        .fiskal-table th,
        .fiskal-table td {
            border: 1px solid #D1D5DB;
            padding: 0.55rem 0.70rem;
            white-space: nowrap;
        }
        .fiskal-table thead th {
            background: #F3F4F6;
            font-weight: 700;
        }
        .fiskal-table tbody tr:nth-child(even) {
            background: #FAFAFA;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

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


def fmt_dec1(val):
    if pd.isna(val) or val is None:
        return "—"
    try:
        s = f"{float(val):,.1f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(val)


def fmt_apbn_image(val):
    if val is None or pd.isna(val):
        return ""
    try:
        num = float(val)
        if num < 0:
            return f"({abs(num):,.0f})"
        return f"{num:,.0f}"
    except Exception:
        return str(val)


def fmt_fiskal_dampak(val):
    if val is None or pd.isna(val):
        return ""
    try:
        num = float(val)
        if num < 0:
            return f"({abs(num):,.2f})"
        return f"{num:,.2f}"
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


def detect_excel_source() -> Tuple[Optional[Union[str, bytes]], str]:
    local_path = Path(__file__).resolve().parent / REPO_FILE_NAME
    if local_path.exists():
        return str(local_path), "Data tersedia."
    if GITHUB_RAW_XLSX_URL:
        return (
            load_excel_bytes_from_url(GITHUB_RAW_XLSX_URL),
            "Data tersedia.",
        )
    return (
        None,
        "File Excel belum ditemukan. Simpan dashboard PDB.xlsx di root repo yang sama dengan app.py, "
        "atau isi st.secrets['github_raw_xlsx_url']."
    )


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
        s2026 = work.loc[work["tahun"] == 2026, ["quarter", src]].copy()
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
        s26 = s[s["tahun"] == 2026]

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
        annual26 = annual.loc[annual["tahun"] == 2026, "yoy"]

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


def load_dashboard_data():
    data = {k: empty_df(k) for k in ["makro", "moneter", "fiskal", "pdb"]}
    pdb_history = None
    pdb_tables = None

    source, status = detect_excel_source()
    if source is None:
        return data, pdb_history, pdb_tables, status

    try:
        xls = open_excel_source(source)
        lower_sheet_map = {s.lower().strip(): s for s in xls.sheet_names}

        for block in ["makro", "moneter", "fiskal"]:
            if block in lower_sheet_map:
                data[block] = ensure_schema(
                    pd.read_excel(xls, sheet_name=lower_sheet_map[block], engine="openpyxl"),
                    block
                )

        if "realisasi" in lower_sheet_map:
            data["pdb"], pdb_history, pdb_tables = derive_pdb_from_realisasi(source)
        elif "pdb" in lower_sheet_map:
            data["pdb"] = ensure_schema(
                pd.read_excel(xls, sheet_name=lower_sheet_map["pdb"], engine="openpyxl"),
                "pdb"
            )

        return data, pdb_history, pdb_tables, status
    except Exception as e:
        return data, pdb_history, pdb_tables, f"Gagal membaca sumber Excel otomatis: {e}"


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
            wide.loc[wide["tahun"] == 2025, comp], errors="coerce"
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
        "out_tw1": pd.Timestamp("2026-03-31"),
        "out_tw2": pd.Timestamp("2026-06-30"),
        "out_tw3": pd.Timestamp("2026-09-30"),
        "out_tw4": pd.Timestamp("2026-12-31"),
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
# Render editors
# =========================
def render_simulasi_fiskal_editor() -> pd.DataFrame:
    st.markdown("### Simulasi Fiskal (dalam miliar)")

    editable_cols = ["out_tw3", "out_tw4"]

    if "simulasi_fiskal_editor_version" not in st.session_state:
        st.session_state["simulasi_fiskal_editor_version"] = 0

    if "simulasi_fiskal_draft" not in st.session_state:
        st.session_state["simulasi_fiskal_draft"] = get_simulasi_fiskal_df().copy()

    draft_df = st.session_state["simulasi_fiskal_draft"].copy()
    draft_df["indikator"] = SIMULASI_FISKAL_ROWS

    # Q1 dan Q2 sudah realisasi. Nilainya tetap nol dan tidak ditampilkan di editor.
    draft_df["out_tw1"] = 0.0
    draft_df["out_tw2"] = 0.0
    for col in editable_cols:
        draft_df[col] = pd.to_numeric(
            draft_df.get(col, 0.0), errors="coerce"
        ).fillna(0.0)

    editor_view = draft_df[["indikator", *editable_cols]].copy()
    editor_key = (
        f"simulasi_fiskal_editor_"
        f"{st.session_state['simulasi_fiskal_editor_version']}"
    )

    edited_view = st.data_editor(
        editor_view,
        key=editor_key,
        hide_index=True,
        num_rows="fixed",
        disabled=["indikator"],
        use_container_width=True,
        column_config={
            "indikator": st.column_config.TextColumn(
                "Simulasi Fiskal", width="medium"
            ),
            "out_tw3": st.column_config.NumberColumn(
                "Q3", format="%.2f", step=0.01, width="small"
            ),
            "out_tw4": st.column_config.NumberColumn(
                "Q4", format="%.2f", step=0.01, width="small"
            ),
        },
    )

    # Rebuild full internal structure so downstream calculations remain compatible.
    edited_df = build_simulasi_fiskal_df()
    edited_df["indikator"] = SIMULASI_FISKAL_ROWS
    edited_df["out_tw1"] = 0.0
    edited_df["out_tw2"] = 0.0
    for col in editable_cols:
        edited_df[col] = pd.to_numeric(
            edited_view[col], errors="coerce"
        ).fillna(0.0)

    st.session_state["simulasi_fiskal_draft"] = edited_df.copy()

    applied_df = get_simulasi_fiskal_df()
    has_pending = not edited_df[editable_cols].reset_index(drop=True).equals(
        applied_df[editable_cols].reset_index(drop=True)
    )

    c1, c2 = st.columns(2)
    if c1.button(
        "Terapkan Simulasi Fiskal",
        use_container_width=True,
        type="primary",
    ):
        st.session_state["simulasi_fiskal_df"] = edited_df.copy()
        st.session_state["simulasi_fiskal_draft"] = edited_df.copy()
        st.session_state["simulasi_fiskal_notice"] = (
            "success",
            "Simulasi fiskal berhasil diterapkan ke Tabel Utama.",
        )
        st.rerun()

    if c2.button("Reset Simulasi Fiskal", use_container_width=True):
        reset_df = build_simulasi_fiskal_df()
        st.session_state["simulasi_fiskal_df"] = reset_df.copy()
        st.session_state["simulasi_fiskal_draft"] = reset_df.copy()
        st.session_state["simulasi_fiskal_editor_version"] += 1
        st.session_state["simulasi_fiskal_notice"] = (
            "success",
            "Simulasi fiskal telah di-reset.",
        )
        st.rerun()

    notice = st.session_state.pop("simulasi_fiskal_notice", None)
    if notice:
        level, msg = notice
        getattr(
            st,
            level if level in {"success", "warning", "error", "info"} else "info",
        )(msg)

    return applied_df


def build_simulasi_makro_pdb_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "indikator": ["ICP (USD/barrel)", "Inflasi (%)"],
            "target_apbn": [70.0, 2.5],
            "shock_makro": [None, None],
        }
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
    st.markdown("### Simulasi Makro")

    if "simulasi_makro_pdb_editor_version" not in st.session_state:
        st.session_state["simulasi_makro_pdb_editor_version"] = 0

    if "simulasi_makro_pdb_draft" not in st.session_state:
        st.session_state["simulasi_makro_pdb_draft"] = get_simulasi_makro_pdb_df().copy()

    draft_df = st.session_state["simulasi_makro_pdb_draft"].copy()
    draft_df["indikator"] = ["ICP (USD/barrel)", "Inflasi (%)"]
    draft_df["target_apbn"] = [70.0, 2.5]
    draft_df["shock_makro"] = pd.to_numeric(
        draft_df.get("shock_makro"), errors="coerce"
    )

    editor_key = (
        f"simulasi_makro_pdb_editor_"
        f"{st.session_state['simulasi_makro_pdb_editor_version']}"
    )
    edited_df = st.data_editor(
        draft_df[["indikator", "target_apbn", "shock_makro"]],
        key=editor_key,
        hide_index=True,
        num_rows="fixed",
        disabled=["indikator", "target_apbn"],
        use_container_width=True,
        column_config={
            "indikator": st.column_config.TextColumn("Indikator", width="medium"),
            "target_apbn": st.column_config.NumberColumn(
                "Target APBN", format="%.1f", width="small"
            ),
            "shock_makro": st.column_config.NumberColumn(
                "Shock Makro", format="%.1f", step=0.1, width="small"
            ),
        },
    )

    edited_df["indikator"] = ["ICP (USD/barrel)", "Inflasi (%)"]
    edited_df["target_apbn"] = [70.0, 2.5]
    edited_df["shock_makro"] = pd.to_numeric(
        edited_df["shock_makro"], errors="coerce"
    )
    st.session_state["simulasi_makro_pdb_draft"] = edited_df.copy()

    c1, c2 = st.columns(2)
    if c1.button(
        "Terapkan Simulasi Makro",
        use_container_width=True,
        type="primary",
        key="apply_simulasi_makro_pdb",
    ):
        st.session_state["simulasi_makro_pdb_df"] = edited_df.copy()
        st.session_state["simulasi_makro_pdb_draft"] = edited_df.copy()
        st.session_state["simulasi_makro_pdb_notice"] = (
            "success",
            "Simulasi makro berhasil diterapkan.",
        )
        st.rerun()

    if c2.button(
        "Reset Simulasi Makro",
        use_container_width=True,
        key="reset_simulasi_makro_pdb",
    ):
        reset_df = build_simulasi_makro_pdb_df()
        st.session_state["simulasi_makro_pdb_df"] = reset_df.copy()
        st.session_state["simulasi_makro_pdb_draft"] = reset_df.copy()
        st.session_state["simulasi_makro_pdb_editor_version"] += 1
        st.session_state["simulasi_makro_pdb_notice"] = (
            "success",
            "Simulasi makro telah di-reset.",
        )
        st.rerun()

    notice = st.session_state.pop("simulasi_makro_pdb_notice", None)
    if notice:
        level, msg = notice
        getattr(
            st,
            level if level in {"success", "warning", "error", "info"} else "info",
        )(msg)

    return get_simulasi_makro_pdb_df()


def render_simulasi_makro_editor() -> pd.DataFrame:

    if "simulasi_makro_editor_version" not in st.session_state:
        st.session_state["simulasi_makro_editor_version"] = 0

    if "simulasi_makro_draft" not in st.session_state:
        st.session_state["simulasi_makro_draft"] = get_simulasi_makro_df().copy()

    draft_df = st.session_state["simulasi_makro_draft"].copy()
    draft_df["indikator"] = [row[0] for row in SIMULASI_MAKRO_DEFAULTS]
    draft_df["apbn_2026"] = [row[1] for row in SIMULASI_MAKRO_DEFAULTS]
    draft_df["shock"] = pd.to_numeric(draft_df.get("shock"), errors="coerce")
    draft_df = draft_df[["indikator", "apbn_2026", "shock"]].copy()

    editor_key = f"simulasi_makro_editor_{st.session_state['simulasi_makro_editor_version']}"
    edited_df = st.data_editor(
        draft_df,
        key=editor_key,
        hide_index=True,
        num_rows="fixed",
        disabled=["indikator", "apbn_2026"],
        use_container_width=True,
        column_config={
            "indikator": st.column_config.TextColumn("Asumsi Dasar Ekonomi Makro", width="large"),
            "apbn_2026": st.column_config.NumberColumn("APBN 2026", format="%.1f", step=0.1, width="small"),
            "shock": st.column_config.NumberColumn("Shock", format="%.1f", step=0.1, width="small"),
        },
    )

    edited_df = edited_df[["indikator", "apbn_2026", "shock"]].copy()
    edited_df["indikator"] = [row[0] for row in SIMULASI_MAKRO_DEFAULTS]
    edited_df["apbn_2026"] = [row[1] for row in SIMULASI_MAKRO_DEFAULTS]
    edited_df["shock"] = pd.to_numeric(edited_df["shock"], errors="coerce")

    st.session_state["simulasi_makro_draft"] = edited_df.copy()

    applied_df = get_simulasi_makro_df()
    has_pending = not edited_df[["shock"]].reset_index(drop=True).equals(
        applied_df[["shock"]].reset_index(drop=True)
    )

    c1, c2 = st.columns(2)
    if c1.button("Terapkan Shock Makro", use_container_width=True, type="primary"):
        st.session_state["simulasi_makro_df"] = edited_df.copy()
        st.session_state["simulasi_makro_draft"] = edited_df.copy()
        st.session_state["simulasi_makro_notice"] = ("success", "Input shock makro berhasil disimpan.")
        st.rerun()

    if c2.button("Reset Shock Makro", use_container_width=True):
        reset_df = build_simulasi_makro_df()
        st.session_state["simulasi_makro_df"] = reset_df.copy()
        st.session_state["simulasi_makro_draft"] = reset_df.copy()
        st.session_state["simulasi_makro_editor_version"] += 1
        st.session_state["simulasi_makro_notice"] = (
            "success",
            "Kolom shock makro telah dikosongkan kembali."
        )
        st.rerun()

    st.caption(
        "Ada perubahan input shock makro yang belum diterapkan."
        if has_pending else
        "Input shock makro sudah sinkron."
    )

    notice = st.session_state.pop("simulasi_makro_notice", None)
    if notice:
        level, msg = notice
        getattr(st, level if level in {"success", "warning", "error", "info"} else "info")(msg)

    return applied_df


# =========================
# Display utilities
# =========================
def dataframe_for_display(df: pd.DataFrame, pct: bool = False, hide_rows=None) -> pd.DataFrame:
    view = df.copy()
    if hide_rows:
        view = view[~view["indikator"].isin(hide_rows)].copy()

    view = view[["indikator", *PERIOD_ORDER]].rename(
        columns={"indikator": "Indikator", **PERIOD_MAP}
    )

    for c in view.columns[1:]:
        view[c] = view[c].apply(fmt_pct if pct else fmt_id0)

    return view


def render_table(df: pd.DataFrame, pct: bool = False, hide_rows=None):
    st.dataframe(
        dataframe_for_display(df, pct=pct, hide_rows=hide_rows),
        use_container_width=True,
        hide_index=True,
    )


def _lookup_value(df: pd.DataFrame, indikator: str, col: str):
    if df is None or df.empty or "indikator" not in df.columns or col not in df.columns:
        return None
    mask = df["indikator"].astype(str).str.strip() == indikator
    if not mask.any():
        return None
    series = pd.to_numeric(df.loc[mask, col], errors="coerce")
    if series.empty:
        return None
    return series.iloc[0]


def _compare_class(baseline_val, compare_val, tol: float = 1e-12) -> str:
    if pd.isna(compare_val) or compare_val is None:
        return "value-missing"
    if pd.isna(baseline_val) or baseline_val is None:
        return "value-same"
    try:
        base = float(baseline_val)
        comp = float(compare_val)
    except Exception:
        return "value-same"
    diff = comp - base
    if abs(diff) <= tol:
        return "value-same"
    return "value-up" if diff > 0 else "value-down"


def _format_compare_cell(value, formatter, css_class: str = "value-same") -> str:
    return f'<td class="{css_class}">{formatter(value)}</td>'


def build_main_comparison_table_html(
    baseline_df: pd.DataFrame,
    shock_fiskal_df: pd.DataFrame,
    shock_makro_df: Optional[pd.DataFrame] = None,
    formatter=fmt_id0,
    note_text: Optional[str] = None,
) -> str:
    baseline_df = ensure_schema(baseline_df, "pdb") if "indikator" in baseline_df.columns else baseline_df
    shock_fiskal_df = (
        ensure_schema(shock_fiskal_df, "pdb") if "indikator" in shock_fiskal_df.columns else shock_fiskal_df
    )
    if shock_makro_df is None:
        shock_makro_df = shock_fiskal_df.copy()
    else:
        shock_makro_df = (
            ensure_schema(shock_makro_df, "pdb") if "indikator" in shock_makro_df.columns else shock_makro_df
        )

    header_html = """
    <div class="comparison-wrap">
    <table class="comparison-table">
        <thead>
            <tr>
                <th rowspan="2">Indikator</th>
                <th rowspan="2">Realisasi Q1</th>
                <th rowspan="2">Realisasi Q2</th>
                <th colspan="2">Q3</th>
                <th colspan="2">Q4</th>
                <th colspan="3">Full Year</th>
            </tr>
            <tr>
                <th>Baseline</th><th>Shock Fiskal</th>
                <th>Baseline</th><th>Shock Fiskal</th>
                <th>Baseline</th><th>Shock Fiskal</th><th>Shock Makro</th>
            </tr>
        </thead>
        <tbody>
    """

    body_rows = []
    comparison_periods = ["out_tw3", "out_tw4"]

    for indikator in PDB_MAIN_ROWS:
        cells = [f"<td>{html.escape(indikator)}</td>"]

        # Q1 dan Q2 merupakan realisasi. Masing-masing hanya ditampilkan
        # dalam satu kolom tanpa Baseline dan Shock Fiskal terpisah.
        for col in ["out_tw1", "out_tw2"]:
            realisasi_val = _lookup_value(baseline_df, indikator, col)
            cells.append(_format_compare_cell(realisasi_val, formatter, "value-same"))

        # Q3 dan Q4 tetap membandingkan Baseline dengan Shock Fiskal.
        for col in comparison_periods:
            base_val = _lookup_value(baseline_df, indikator, col)
            fiskal_val = _lookup_value(shock_fiskal_df, indikator, col)
            cells.append(_format_compare_cell(base_val, formatter, "value-same"))
            cells.append(_format_compare_cell(fiskal_val, formatter, _compare_class(base_val, fiskal_val)))

        base_fy = _lookup_value(baseline_df, indikator, "full_year")
        fiskal_fy = _lookup_value(shock_fiskal_df, indikator, "full_year")
        makro_fy = _lookup_value(shock_makro_df, indikator, "full_year")

        cells.append(_format_compare_cell(base_fy, formatter, "value-same"))
        cells.append(_format_compare_cell(fiskal_fy, formatter, _compare_class(base_fy, fiskal_fy)))
        cells.append(_format_compare_cell(makro_fy, formatter, _compare_class(base_fy, makro_fy)))

        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    footer_html = """
        </tbody>
    </table>
    </div>
    <div class="legend-row">
        <span class="legend-badge"><span class="legend-swatch legend-up"></span> Lebih tinggi dari baseline</span>
        <span class="legend-badge"><span class="legend-swatch legend-down"></span> Lebih rendah dari baseline</span>
        <span class="legend-badge"><span class="legend-swatch legend-same"></span> Sama dengan baseline</span>
    </div>
    """

    html_out = header_html + "".join(body_rows) + footer_html
    if note_text:
        html_out += f'<div class="muted-note">{html.escape(note_text)}</div>'
    return html_out


def render_main_comparison_table(
    baseline_df: pd.DataFrame,
    shock_fiskal_df: pd.DataFrame,
    shock_makro_df: Optional[pd.DataFrame] = None,
    formatter=fmt_id0,
    note_text: Optional[str] = None,
):
    html_table = build_main_comparison_table_html(
        baseline_df=baseline_df,
        shock_fiskal_df=shock_fiskal_df,
        shock_makro_df=shock_makro_df,
        formatter=formatter,
        note_text=note_text,
    )
    st.markdown(html_table, unsafe_allow_html=True)


# =========================
# Blok Fiskal
# =========================
def render_fiskal_block_table(simulasi_makro_df: Optional[pd.DataFrame] = None):
    # Dampak dari pertumbuhan ekonomi
    d_pp_pertumbuhan = calculate_pertumbuhan_ekonomi_tax_impact(simulasi_makro_df)
    d_pp_pertumbuhan = 0.0 if d_pp_pertumbuhan is None else d_pp_pertumbuhan

    # Dampak inflasi: setiap kenaikan 0,1 poin persentase menambah
    # Penerimaan Perpajakan sebesar 1.862,99.
    d_pp_inflasi = calculate_inflasi_tax_impact(simulasi_makro_df)
    d_pp_inflasi = 0.0 if d_pp_inflasi is None else d_pp_inflasi

    # Dampak tingkat bunga SUN 10 tahun terhadap Belanja Pemerintah Pusat.
    # Setiap kenaikan 0,1 poin persentase menambah BPP sebesar 1.899,98.
    d_bpp_sun = calculate_sun_10y_bpp_impact(simulasi_makro_df)
    d_bpp_sun = 0.0 if d_bpp_sun is None else d_bpp_sun

    nilai_tukar_impacts = calculate_nilai_tukar_impacts(simulasi_makro_df)
    d_pp_kurs = nilai_tukar_impacts.get("pp", 0.0)
    d_pnbp_kurs = nilai_tukar_impacts.get("pnbp", 0.0)
    d_bpp_kurs = nilai_tukar_impacts.get("bpp", 0.0)

    harga_minyak_impacts = calculate_harga_minyak_impacts(simulasi_makro_df)
    d_pp_minyak = harga_minyak_impacts.get("pp", 0.0)
    d_pnbp_minyak = harga_minyak_impacts.get("pnbp", 0.0)
    d_bpp_minyak = harga_minyak_impacts.get("bpp", 0.0)

    lifting_minyak_impacts = calculate_lifting_minyak_impacts(simulasi_makro_df)
    d_pp_lifting_minyak = lifting_minyak_impacts.get("pp", 0.0)
    d_pnbp_lifting_minyak = lifting_minyak_impacts.get("pnbp", 0.0)

    # Dampak dari lifting gas bumi
    lifting_gas_impacts = calculate_lifting_gas_bumi_impacts(simulasi_makro_df)
    d_pp_gas = lifting_gas_impacts.get("pp", 0.0)
    d_pnbp_gas = lifting_gas_impacts.get("pnbp", 0.0)

    apbn = {
        "pp": 2693714,
        "pnbp": 459200,
        "hibah": 666,
        "bpp": 3149733,
        "tkd": 692995,
    }

    dampak = {
        "pp": d_pp_pertumbuhan + d_pp_inflasi + d_pp_kurs + d_pp_minyak + d_pp_lifting_minyak + d_pp_gas,
        "pnbp": d_pnbp_kurs + d_pnbp_minyak + d_pnbp_lifting_minyak + d_pnbp_gas,
        "hibah": 0.0,
        "bpp": d_bpp_sun + d_bpp_kurs + d_bpp_minyak,
        "tkd": 0.0,
    }

    apbn_A = apbn["pp"] + apbn["pnbp"] + apbn["hibah"]
    apbn_B = apbn["bpp"] + apbn["tkd"]
    apbn_C = apbn_A - apbn_B
    apbn_D = -apbn_C

    dampak_A = dampak["pp"] + dampak["pnbp"] + dampak["hibah"]
    dampak_B = dampak["bpp"] + dampak["tkd"]
    dampak_C = dampak_A - dampak_B
    dampak_D = -dampak_C

    outlook = lambda a, d: a + d

    fiskal_rows = [
        {"uraian": "A. Pendapatan Negara dan Hibah", "apbn": apbn_A, "dampak": dampak_A, "outlook": outlook(apbn_A, dampak_A), "bold": True},
        {"uraian": "1. Penerimaan Perpajakan", "apbn": apbn["pp"], "dampak": dampak["pp"], "outlook": outlook(apbn["pp"], dampak["pp"]), "bold": False},
        {"uraian": "2. Penerimaan Negara Bukan Pajak", "apbn": apbn["pnbp"], "dampak": dampak["pnbp"], "outlook": outlook(apbn["pnbp"], dampak["pnbp"]), "bold": False},
        {"uraian": "3. Hibah", "apbn": apbn["hibah"], "dampak": dampak["hibah"], "outlook": outlook(apbn["hibah"], dampak["hibah"]), "bold": False},
        {"uraian": "B. Belanja Negara", "apbn": apbn_B, "dampak": dampak_B, "outlook": outlook(apbn_B, dampak_B), "bold": True},
        {"uraian": "1. Belanja Pemerintah Pusat", "apbn": apbn["bpp"], "dampak": dampak["bpp"], "outlook": outlook(apbn["bpp"], dampak["bpp"]), "bold": False},
        {"uraian": "2. Transfer ke Daerah", "apbn": apbn["tkd"], "dampak": dampak["tkd"], "outlook": outlook(apbn["tkd"], dampak["tkd"]), "bold": False},
        {"uraian": "C. Surplus/Defisit", "apbn": apbn_C, "dampak": dampak_C, "outlook": outlook(apbn_C, dampak_C), "bold": True},
        {"uraian": "D. Pembiayaan Anggaran", "apbn": apbn_D, "dampak": dampak_D, "outlook": outlook(apbn_D, dampak_D), "bold": True},
    ]

    rows = []
    for r in fiskal_rows:
        fw = "font-weight:700;" if r["bold"] else ""
        rows.append(
            f"<tr>"
            f"<td style='text-align:left;{fw}'>{r['uraian']}</td>"
            f"<td style='text-align:right;{fw}'>{fmt_apbn_image(r['apbn'])}</td>"
            f"<td style='text-align:right;{fw}'>{fmt_fiskal_dampak(r['dampak'])}</td>"
            f"<td style='text-align:right;{fw}'>{fmt_fiskal_dampak(r['outlook'])}</td>"
            f"</tr>"
        )

    html_tbl = (
        '<table class="fiskal-table">'
        "<thead>"
        "<tr>"
        '<th style="text-align:left;">Uraian</th>'
        '<th style="text-align:right;">APBN 2026</th>'
        '<th style="text-align:right;">Dampak</th>'
        '<th style="text-align:right;">Outlook</th>'
        "</tr>"
        "</thead>"
        "<tbody>"
        f"{''.join(rows)}"
        "</tbody>"
        "</table>"
    )

    st.markdown(html_tbl, unsafe_allow_html=True)


# =========================
# Ringkasan Indikator Ekonomi Terkini
# =========================
LEADING_INDICATORS = [
    "Inflasi", "Nilai Tukar", "Yield SBN 10 Tahun", "Harga ICP",
    "Lifting Minyak", "Lifting Gas", "Indeks Keyakinan Konsumen",
    "Indeks Penjualan Riil", "Mandiri Spending Index", "Penjualan Mobil",
    "Penjualan Motor", "PMI Manufaktur", "Penjualan Semen",
    "Penjualan Listrik", "Penjualan BBM",
]
COMMODITY_INDICATORS = [
    "Crude oil, Brent", "Coal, Australia", "Palm oil", "Emas", "Nickel",
    "Tembaga", "Natural gas, Japan", "Aluminum", "Timah", "Iron ore, cfr spot",
]
INDICATOR_META = {
    "Inflasi": ("BPS", "%", "level"), "Nilai Tukar": ("Bank Indonesia", "Rp/US$", "level"),
    "Yield SBN 10 Tahun": ("Kementerian Keuangan", "%", "level"), "Harga ICP": ("Kementerian ESDM", "USD/barel", "level"),
    "Lifting Minyak": ("Kementerian ESDM", "ribu barel/hari", "level"), "Lifting Gas": ("Kementerian ESDM", "ribu BOEPD", "level"),
    "Indeks Keyakinan Konsumen": ("Bank Indonesia", "indeks", "level"), "Indeks Penjualan Riil": ("Bank Indonesia", "indeks", "level"),
    "Mandiri Spending Index": ("Bank Mandiri Institute", "indeks", "level"), "Penjualan Mobil": ("Gaikindo", "%, yoy", "yoy"),
    "Penjualan Motor": ("AISI", "%, yoy", "yoy"), "PMI Manufaktur": ("S&P Global", "indeks", "level"),
    "Penjualan Semen": ("Asosiasi Semen Indonesia", "%, yoy", "yoy"), "Penjualan Listrik": ("PLN", "%, yoy", "yoy"),
    "Penjualan BBM": ("Pertamina", "%, yoy", "yoy"),
}
COMMODITY_META = {
    "Crude oil, Brent": ("Minyak Brent", "USD/barel"), "Coal, Australia": ("Batubara Australia", "USD/ton"),
    "Palm oil": ("CPO", "USD/ton"), "Emas": ("Emas", "USD/troy ounce"), "Nickel": ("Nikel", "USD/ton"),
    "Tembaga": ("Tembaga", "USD/ton"), "Natural gas, Japan": ("Natural Gas Jepang", "USD/MMBtu"),
    "Aluminum": ("Aluminium", "USD/ton"), "Timah": ("Timah", "USD/ton"), "Iron ore, cfr spot": ("Besi (Iron Ore)", "USD/ton"),
}
CARD_COLORS = ["#176B8C", "#00A85A", "#A42B98", "#0878C9", "#D19A00", "#14AAA8", "#6846C7", "#D36B32"]
COMMODITY_COLORS = ["#264F8F", "#2F416D", "#1D3E70", "#2A4779", "#203F70", "#A95C20", "#22534E", "#505158", "#67466E", "#375B67"]

def load_indicator_data() -> Tuple[Optional[pd.DataFrame], str]:
    local_path = Path(__file__).resolve().parent / INDICATOR_FILE_NAME
    if not local_path.exists():
        return None, f"File {INDICATOR_FILE_NAME} belum ditemukan di root repository."
    try:
        df = pd.read_excel(local_path, sheet_name="Data_Wide", engine="openpyxl")
        df.columns = [str(c).strip() for c in df.columns]
        df["Periode"] = pd.to_datetime(df["Periode"], errors="coerce")
        df = df.dropna(subset=["Periode"]).sort_values("Periode").reset_index(drop=True)
        for col in df.columns[1:]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df, "Data indikator tersedia."
    except Exception as exc:
        return None, f"Gagal membaca {INDICATOR_FILE_NAME}: {exc}"

def _latest_valid(series: pd.Series):
    valid = pd.to_numeric(series, errors="coerce").dropna()
    return None if valid.empty else float(valid.iloc[-1])

def _format_indicator_value(value, unit, signed=False):
    if value is None or pd.isna(value): return "—"
    sign = "+" if signed and value > 0 else ""
    decimals = 1 if abs(value) < 1000 else 0
    text = f"{sign}{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text + ("%" if "%" in unit else "")

def _change_pct(current, previous):
    if current is None or previous is None or pd.isna(current) or pd.isna(previous) or previous == 0: return None
    return (current / previous - 1.0) * 100.0

def render_leading_card(df, indicator, color):
    source, unit, mode = INDICATOR_META[indicator]

    # Ambil seluruh data lebih dahulu agar perhitungan YoY memiliki basis t-12.
    # Setelah pertumbuhan dihitung, baru batasi tampilan pada 24 bulan terakhir.
    data = df[["Periode", indicator]].copy().sort_values("Periode")
    data[indicator] = pd.to_numeric(data[indicator], errors="coerce")
    data["display"] = data[indicator]
    if mode == "yoy":
        data["display"] = data[indicator].pct_change(periods=12, fill_method=None) * 100

    data = data.tail(24).copy()
    current = _latest_valid(data["display"])
    if current is None:
        st.warning(f"Data {indicator} belum tersedia.")
        return

    title = indicator
    st.markdown(
        f'<div class="indicator-card-head">'
        f'<div class="indicator-title">{html.escape(title)}</div>'
        f'<div class="indicator-source">{html.escape(source)}</div>'
        f'<div><span class="indicator-value">'
        f'{_format_indicator_value(current, unit, mode == "yoy")}'
        f'</span> <span class="indicator-unit">{html.escape(unit)}</span></div></div>',
        unsafe_allow_html=True,
    )

    # Bentuk kalender bulanan lengkap agar sumbu waktu konsisten.
    # Interpolasi hanya pada celah internal. Nilai setelah observasi terakhir
    # tidak diekstrapolasi, sehingga garis berhenti tepat pada data terbaru.
    plot = data[["Periode", "display"]].copy()
    plot["Periode"] = pd.to_datetime(plot["Periode"], errors="coerce")
    plot = plot.dropna(subset=["Periode"]).drop_duplicates("Periode", keep="last")
    if not plot.empty:
        full_months = pd.date_range(
            plot["Periode"].min().to_period("M").to_timestamp(),
            plot["Periode"].max().to_period("M").to_timestamp(),
            freq="MS",
        )
        plot = plot.set_index("Periode").reindex(full_months)
        plot.index.name = "Periode"
        plot["display"] = plot["display"].interpolate(
            method="linear",
            limit_area="inside",
        )
        plot = plot.reset_index()

    fig = go.Figure(
        go.Scatter(
            x=plot["Periode"],
            y=plot["display"],
            mode="lines",
            connectgaps=True,
            line=dict(color=color, width=3, shape="linear"),
            fill="tozeroy",
            fillcolor=color + "18",
            hovertemplate="%{x|%b %Y}<br>%{y:,.2f}<extra></extra>",
        )
    )
    # Tambahkan ruang vertikal di atas dan bawah seri agar garis tertinggi
    # tidak menyentuh atau tertutup area KPI di atas grafik.
    y_values = pd.to_numeric(plot["display"], errors="coerce").dropna()
    if y_values.empty:
        y_range = None
    else:
        y_min = float(y_values.min())
        y_max = float(y_values.max())
        y_span = y_max - y_min
        if y_span == 0:
            y_span = max(abs(y_max) * 0.10, 1.0)
        y_padding_top = y_span * 0.18
        y_padding_bottom = y_span * 0.10
        # Untuk seri seluruhnya positif, pertahankan area arsiran yang wajar
        # tanpa memaksa garis naik sampai ke batas atas kartu.
        lower_bound = min(0.0, y_min - y_padding_bottom)
        upper_bound = y_max + y_padding_top
        y_range = [lower_bound, upper_bound]

    fig.update_layout(
        height=190,
        margin=dict(l=8, r=8, t=18, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(showgrid=False, tickformat="%b'%y", nticks=5),
        yaxis=dict(
            gridcolor="#E4EAF2",
            zeroline=False,
            range=y_range,
            fixedrange=True,
        ),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def render_commodity_card(df, indicator, color):
    title, unit = COMMODITY_META[indicator]
    data = df[["Periode", indicator]].copy()
    data["Periode"] = pd.to_datetime(data["Periode"], errors="coerce")
    data[indicator] = pd.to_numeric(data[indicator], errors="coerce")
    data = data.dropna(subset=["Periode", indicator]).sort_values("Periode")
    if data.empty:
        return

    # Setiap kartu menggunakan tanggal observasi terakhir indikatornya sendiri.
    latest = data.iloc[-1]
    current = float(latest[indicator])
    dt = pd.Timestamp(latest["Periode"])
    tanggal_data = dt.strftime("%d %B %Y")

    prev = data.iloc[-2][indicator] if len(data) > 1 else None
    prev_year = data.loc[data["Periode"] <= dt - pd.DateOffset(years=1), indicator]
    prev_dec = data.loc[data["Periode"] < pd.Timestamp(dt.year, 1, 1), indicator]
    first = data.iloc[0][indicator]
    metrics = [
        ("MoM", _change_pct(current, prev)),
        ("YoY", _change_pct(current, float(prev_year.iloc[-1]) if not prev_year.empty else None)),
        ("YtD", _change_pct(current, float(prev_dec.iloc[-1]) if not prev_dec.empty else None)),
        ("C-to-C", _change_pct(current, float(first))),
    ]
    rows = "".join(
        f'<div class="commodity-row"><span>{lab}</span>'
        f'<b class="{"pos" if val is not None and val >= 0 else "neg"}">'
        f'{"● " if val is not None else ""}{_format_indicator_value(val, "%", True)}</b></div>'
        for lab, val in metrics
    )
    st.markdown(
        f'<div class="commodity-card" style="background:{color}">'
        f'<div class="commodity-title">{html.escape(title)}</div>'
        f'<div class="commodity-unit">{html.escape(unit)}</div>'
        f'<div class="commodity-date">Data per {html.escape(tanggal_data)}</div>'
        f'<div class="commodity-value">{_format_indicator_value(current, unit)}</div>'
        f'{rows}</div>',
        unsafe_allow_html=True,
    )

def render_indicator_summary():
    df, status = load_indicator_data()
    if df is None:
        st.error(status); return
    st.markdown("""<style>
    .indicator-card-head{background:white;border:1px solid #D9E1EC;border-bottom:0;border-radius:16px 16px 0 0;padding:18px 20px 14px;box-shadow:0 3px 12px rgba(30,55,90,.08)}
    [data-testid="stPlotlyChart"]{background:white;border:1px solid #D9E1EC;border-top:0;border-radius:0 0 16px 16px;box-shadow:0 5px 12px rgba(30,55,90,.08);padding:0 10px 8px;margin-top:0}
    .indicator-title{font-size:1.05rem;font-weight:750;color:#15233D}.indicator-source{color:#8191A7;font-size:.86rem;margin-bottom:10px}.indicator-value{font-size:2rem;font-weight:800;color:#101D35}.indicator-unit{color:#8191A7;font-size:.82rem}
    .section-line{display:flex;align-items:center;gap:14px;margin:8px 0 14px}.section-line h2{font-size:1.3rem;color:#173F7A;margin:0}.section-line span{color:#8191A7}.section-rule{height:1px;background:#D4DDE9;flex:1}
    .commodity-card{min-height:270px;border-radius:16px;padding:22px 24px;color:white;box-shadow:0 6px 14px rgba(20,40,70,.13);margin-bottom:12px}.commodity-title{font-size:1.05rem;font-weight:700;color:#B9CBE5}.commodity-unit{font-size:.85rem;color:#9DB5D6}.commodity-date{font-size:.78rem;color:#D5E1F2;margin-top:5px;letter-spacing:.01em}.commodity-value{font-size:2rem;font-weight:800;margin:9px 0 10px}.commodity-row{display:flex;justify-content:space-between;margin:7px 0;color:#B9CBE5}.commodity-row b{font-size:.95rem}.pos{color:#42EE8B}.neg{color:#FF747A}
    </style>""", unsafe_allow_html=True)
    latest_date=df["Periode"].max()
    st.markdown(f'<div class="section-line"><h2>Leading Economic Indicators</h2><span>Data 2 tahun terakhir · pembaruan {latest_date:%B %Y}</span><div class="section-rule"></div></div>', unsafe_allow_html=True)
    for start in range(0,len(LEADING_INDICATORS),4):
        cols=st.columns(4,gap="large")
        for i,indicator in enumerate(LEADING_INDICATORS[start:start+4]):
            with cols[i]: render_leading_card(df,indicator,CARD_COLORS[(start+i)%len(CARD_COLORS)])
    st.markdown('<div class="section-line" style="margin-top:28px"><h2>Harga Komoditas Utama</h2><span>Data dashboard indikator</span><div class="section-rule"></div></div>', unsafe_allow_html=True)
    for start in range(0,len(COMMODITY_INDICATORS),4):
        cols=st.columns(4,gap="large")
        for i,indicator in enumerate(COMMODITY_INDICATORS[start:start+4]):
            with cols[i]: render_commodity_card(df,indicator,COMMODITY_COLORS[(start+i)%len(COMMODITY_COLORS)])

# =========================
# Charts
# =========================
def make_history_chart(pdb_history: Optional[dict], selected_components):
    if not pdb_history or pdb_history.get("level") is None or pdb_history["level"].empty:
        st.info("Data historis PDB belum tersedia.")
        return

    plot_df = pdb_history["level"].copy()
    plot_df = plot_df[plot_df["komponen"].isin(selected_components)]

    fig = px.line(
        plot_df,
        x="tanggal",
        y="nilai",
        color="komponen",
        custom_data=["nilai_fmt"],
        color_discrete_sequence=[PRIMARY, ACCENT, SUCCESS, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"],
    )
    fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m-%d}<br>%{customdata[0]}")
    fig.update_layout(
        height=380,
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
    )
    fig.update_yaxes(gridcolor=GRID)
    st.plotly_chart(fig, use_container_width=True)


def make_growth_chart(pdb_history: Optional[dict], selected_components, growth_col: str, title: str):
    if not pdb_history or pdb_history.get("growth") is None or pdb_history["growth"].empty:
        st.info("Data pertumbuhan PDB belum tersedia.")
        return

    plot_df = pdb_history["growth"].copy()
    plot_df = plot_df[plot_df["komponen"].isin(selected_components)]
    plot_df["fmt"] = plot_df[growth_col].apply(fmt_pct)

    fig = px.line(
        plot_df,
        x="tanggal",
        y=growth_col,
        color="komponen",
        custom_data=["fmt"],
        color_discrete_sequence=[SUCCESS, ACCENT, PRIMARY, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"],
    )
    fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m-%d}<br>%{customdata[0]}")
    fig.update_layout(
        title=title,
        height=380,
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
    )
    fig.update_yaxes(gridcolor=GRID, zeroline=True)
    st.plotly_chart(fig, use_container_width=True)


# =========================
# Main App
# =========================
workbook, pdb_history, pdb_tables, source_status = load_dashboard_data()

st.sidebar.markdown('<div class="menu-title">MENU UTAMA</div>', unsafe_allow_html=True)
st.sidebar.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E7EDF6;
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 1.25rem;
        padding-left: 0.55rem;
        padding-right: 0.55rem;
    }
    .menu-title {
        color: #8191A7;
        font-size: 0.90rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        margin: 0.10rem 0.85rem 0.35rem 0.85rem;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 0.20rem;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        min-height: 3.45rem;
        padding: 0.70rem 0.80rem;
        border-left: 4px solid transparent;
        border-radius: 0;
        background: #FFFFFF;
        color: #334155;
        font-size: 1.02rem;
        line-height: 1.15;
        transition: background-color 0.15s ease, border-color 0.15s ease;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: #F5F8FC;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: #EAF1FC;
        border-left-color: #173F7A;
        color: #12386F;
        font-weight: 700;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

menu_utama = st.sidebar.radio(
    "Menu Utama",
    options=["📐  Simulasi Fiskal", "◔  Sensitivitas APBN", "▦  Ringkasan Indikator Ekonomi Terkini"],
    index=0,
    label_visibility="collapsed",
    key="menu_utama_dashboard",
)

st.sidebar.markdown("---")
show_preview = st.sidebar.toggle("Tampilkan preview data mentah", value=False)

simulasi_fiskal_df = get_simulasi_fiskal_df()
simulasi_makro_df = get_simulasi_makro_df()

baseline_pdb_nominal = ensure_full_year_from_quarters(workbook["pdb"])
adjusted_pdb_nominal = apply_simulasi_fiskal_to_pdb_nominal(
    baseline_pdb_nominal.copy(), simulasi_fiskal_df
)

# Ambil input makro yang sudah diterapkan dari session state, lalu terapkan
# shock ICP dan inflasi di atas hasil shock fiskal, khusus Full Year.
simulasi_makro_pdb_df = get_simulasi_makro_pdb_df()
macro_adjusted_pdb_nominal = apply_simulasi_makro_to_pdb_nominal(
    adjusted_pdb_nominal.copy(), simulasi_makro_pdb_df
)

baseline_top_yoy = pdb_tables["yoy"] if pdb_tables else empty_df("pdb")
baseline_top_qtq = pdb_tables["qtq"] if pdb_tables else empty_df("pdb")
adjusted_top_tables = build_adjusted_top_growth_tables(
    pdb_history, adjusted_pdb_nominal
)
adjusted_top_yoy = adjusted_top_tables.get("yoy", empty_df("pdb"))
adjusted_top_qtq = adjusted_top_tables.get("qtq", empty_df("pdb"))

# Shock Makro tidak mengubah Q1-Q4. Hanya Full Year YoY yang dihitung ulang
# dari nominal Full Year setelah Shock Makro, dengan acuan Shock Fiskal.
macro_adjusted_top_yoy = build_full_year_yoy_from_nominal(
    pdb_history=pdb_history,
    nominal_df=macro_adjusted_pdb_nominal,
    quarter_growth_reference=adjusted_top_yoy,
)
macro_adjusted_top_qtq = adjusted_top_qtq.copy()

st.title("Dashboard Pemantauan PDB")
st.markdown("---")

if menu_utama == "📐  Simulasi Fiskal":
    st.markdown("## Simulasi Fiskal")

    top_yoy_tab, top_nominal_tab, top_qtq_tab = st.tabs(
        ["Year on Year (YoY)", "Nilai PDB 2026", "Quarter to Quarter (QtQ)"]
    )

    with top_yoy_tab:
        render_main_comparison_table(
            baseline_df=baseline_top_yoy,
            shock_fiskal_df=adjusted_top_yoy,
            shock_makro_df=macro_adjusted_top_yoy,
            formatter=fmt_pct,
            note_text=None,
        )

    with top_nominal_tab:
        render_main_comparison_table(
            baseline_df=baseline_pdb_nominal,
            shock_fiskal_df=adjusted_pdb_nominal,
            shock_makro_df=macro_adjusted_pdb_nominal,
            formatter=fmt_id0,
            note_text=None,
        )

    with top_qtq_tab:
        render_main_comparison_table(
            baseline_df=baseline_top_qtq,
            shock_fiskal_df=adjusted_top_qtq,
            shock_makro_df=macro_adjusted_top_qtq,
            formatter=fmt_pct,
            note_text=None,
        )

    st.markdown("---")
    simulasi_fiskal_col, simulasi_makro_col = st.columns([1.35, 1.0], gap="large")
    with simulasi_fiskal_col:
        simulasi_fiskal_df = render_simulasi_fiskal_editor()
    with simulasi_makro_col:
        simulasi_makro_pdb_df = render_simulasi_makro_pdb_editor()

    st.markdown("## Historis PDB")

    selected_components = st.multiselect(
        "Pilih komponen historis yang ingin ditampilkan",
        options=PDB_COMPONENTS,
        default=[],
        placeholder="Pilih satu atau beberapa komponen PDB",
    )
    hist_tab, yoyc_tab, qtqc_tab = st.tabs(
        ["Historis Level", "Year on Year (YoY)", "Quarter to Quarter (QtQ)"]
    )
    with hist_tab:
        make_history_chart(pdb_history, selected_components)
    with yoyc_tab:
        make_growth_chart(
            pdb_history,
            [c for c in selected_components if c not in EXCLUDE_GROWTH_ROWS],
            "yoy",
            "Pertumbuhan Year on Year (YoY)",
        )
    with qtqc_tab:
        make_growth_chart(
            pdb_history,
            [c for c in selected_components if c not in EXCLUDE_GROWTH_ROWS],
            "qtq",
            "Pertumbuhan Quarter to Quarter (QtQ)",
        )

elif menu_utama == "◔  Sensitivitas APBN":
    st.markdown("## Sensitivitas APBN")
    simulasi_makro_df = render_simulasi_makro_editor()
    st.markdown("---")
    st.markdown("### Dampak terhadap APBN 2026")
    render_fiskal_block_table(simulasi_makro_df)
elif menu_utama == "▦  Ringkasan Indikator Ekonomi Terkini":
    st.markdown("## Ringkasan Indikator Ekonomi Terkini")
    render_indicator_summary()

if show_preview:
    with st.expander("Preview data yang berhasil dimuat", expanded=False):
        st.markdown("### Preview simulasi fiskal editable")
        st.dataframe(simulasi_fiskal_df, use_container_width=True, hide_index=True)
        st.markdown("### Preview baseline PDB nominal")
        st.dataframe(baseline_pdb_nominal, use_container_width=True, hide_index=True)
        st.markdown("### Preview shock fiskal PDB nominal")
        st.dataframe(adjusted_pdb_nominal, use_container_width=True, hide_index=True)
        st.markdown("### Preview shock makro PDB nominal")
        st.dataframe(macro_adjusted_pdb_nominal, use_container_width=True, hide_index=True)
        st.markdown("### Preview baseline YoY")
        st.dataframe(baseline_top_yoy, use_container_width=True, hide_index=True)
        st.markdown("### Preview shock fiskal YoY")
        st.dataframe(adjusted_top_yoy, use_container_width=True, hide_index=True)
        st.markdown("### Preview baseline QtQ")
        st.dataframe(baseline_top_qtq, use_container_width=True, hide_index=True)
        st.markdown("### Preview shock fiskal QtQ")
        st.dataframe(adjusted_top_qtq, use_container_width=True, hide_index=True)
        st.markdown("### Preview input shock makro")
        st.dataframe(simulasi_makro_df, use_container_width=True, hide_index=True)
        if pdb_history:
            st.markdown("### Preview historis komponen PDB")
            st.dataframe(pdb_history["level"], use_container_width=True, hide_index=True)
            st.markdown("### Preview pertumbuhan komponen PDB")
            st.dataframe(pdb_history["growth"], use_container_width=True, hide_index=True)
