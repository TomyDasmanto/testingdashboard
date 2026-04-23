
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Union
from urllib.request import urlopen
import html

import pandas as pd
import plotly.express as px
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
SUCCESS = "#2A9D8F"
ACCENT = "#E07B39"
PURPLE = "#8A5CF6"
NEGATIVE = "#D14D72"
GRID = "rgba(31,41,55,0.12)"

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
    "Konsumsi RT", "Konsumsi LNPRT", "PKP", "PMTB",
    "Change in Stocks", "Ekspor", "Impor", "PDB Aggregate",
]
PDB_MAIN_ROWS = ["Konsumsi RT", "PKP", "PMTB", "Ekspor", "Impor", "PDB Aggregate"]
EXCLUDE_GROWTH_ROWS = ["Change in Stocks"]
DEFAULT_ROWS = {
    "makro": ["Inflasi", "Rupiah", "Yield SBN", "ICP", "Nikel", "Coal", "CPO", "Lifting"],
    "moneter": ["PUAB", "Kredit", "DPK", "M0", "OMO"],
    "fiskal": ["Pendapatan", "Belanja", "Pembiayaan", "Defisit"],
    "pdb": PDB_COMPONENTS,
}

FISKAL_COMPONENTS_BASE = {
    "1. Penerimaan Perpajakan": 2693714.0,
    "2. Penerimaan Negara Bukan Pajak": 459200.0,
    "3. Hibah": 666.0,
    "1. Belanja Pemerintah Pusat": 3149733.0,
    "2. Transfer ke Daerah": 692995.0,
}
PERTUMBUHAN_ROW = "Pertumbuhan ekonomi (%)"
PERTUMBUHAN_APBN = 5.4
DAMPAK_PER_0_1_PERTUMBUHAN = 2080.30
BUNGA_SUN_ROW = "Tingkat bunga SUN 10 tahun"
BUNGA_SUN_APBN = 6.9
DAMPAK_PER_0_1_BUNGA_SUN = 1899.98

st.markdown(
    """
    <style>
    .fiskal-table {width:100%; border-collapse:collapse; margin-top:.35rem;}
    .fiskal-table th, .fiskal-table td {border:1px solid rgba(31,41,55,0.10); padding:8px 10px; font-size:.92rem;}
    .fiskal-table th {background:#F3F4F6; text-align:left;}
    .fiskal-table td.num, .fiskal-table th.num {text-align:right; white-space:nowrap;}
    .fiskal-table tr.group td {font-weight:700; background:#FAFAFA;}
    </style>
    """,
    unsafe_allow_html=True,
)


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
        s = f"{float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s + "%"
    except Exception:
        return str(val)


def fmt_fiskal(val):
    if val is None or pd.isna(val):
        return ""
    try:
        num = float(val)
        abs_txt = f"{abs(num):,.2f}" if abs(num - round(num)) > 1e-9 else f"{abs(num):,.0f}"
        return f"({abs_txt})" if num < 0 else abs_txt
    except Exception:
        return str(val)


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
            rows.append(found.iloc[0].to_dict() if not found.empty else {"indikator": ind, **{c: None for c in PERIOD_ORDER}})
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


def load_excel_bytes_from_url(url: str) -> bytes:
    with urlopen(url) as resp:
        return resp.read()


def open_excel_source(source: Union[str, bytes, bytearray]):
    return pd.ExcelFile(BytesIO(source), engine="openpyxl") if isinstance(source, (bytes, bytearray)) else pd.ExcelFile(source, engine="openpyxl")


def detect_excel_source() -> Tuple[Optional[Union[str, bytes]], str]:
    local_path = Path(__file__).resolve().parent / REPO_FILE_NAME
    if local_path.exists():
        return str(local_path), f"Sumber data otomatis: {local_path.name} di folder repo"
    if GITHUB_RAW_XLSX_URL:
        return load_excel_bytes_from_url(GITHUB_RAW_XLSX_URL), "Sumber data otomatis: GitHub Raw URL dari st.secrets['github_raw_xlsx_url']"
    return None, "File Excel belum ditemukan. Simpan dashboard PDB.xlsx di root repo yang sama dengan app.py, atau isi st.secrets['github_raw_xlsx_url']."


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
        quarter_values = {f"out_tw{q}": (float(s2026.loc[s2026['quarter'] == q, src].iloc[-1]) if not s2026.loc[s2026['quarter'] == q, src].empty else None) for q in [1,2,3,4]}
        fy = s2026[src].sum() if not s2026.empty else None
        rows.append({"indikator": indikator, **quarter_values, "full_year": fy})
    out = pd.DataFrame(rows)
    if not out.empty:
        idx = out.set_index("indikator")
        agg_vals = {}
        for c in PERIOD_ORDER:
            def gv(name):
                try:
                    return pd.to_numeric(idx.loc[name, c], errors="coerce")
                except Exception:
                    return 0.0
            agg_vals[c] = (
                (0 if pd.isna(gv("Konsumsi RT")) else float(gv("Konsumsi RT")))
                + (0 if pd.isna(gv("Konsumsi LNPRT")) else float(gv("Konsumsi LNPRT")))
                + (0 if pd.isna(gv("PKP")) else float(gv("PKP")))
                + (0 if pd.isna(gv("PMTB")) else float(gv("PMTB")))
                + (0 if pd.isna(gv("Change in Stocks")) else float(gv("Change in Stocks")))
                + (0 if pd.isna(gv("Ekspor")) else float(gv("Ekspor")))
                - (0 if pd.isna(gv("Impor")) else float(gv("Impor")))
                + (0 if pd.isna(gv("Statistical Discrepancy")) else float(gv("Statistical Discrepancy")))
            )
        out = pd.concat([out[out["indikator"] != "Statistical Discrepancy"], pd.DataFrame([{"indikator": "PDB Aggregate", **agg_vals}])], ignore_index=True)
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
    wide = pd.DataFrame({
        "tanggal": work["tanggal"],
        "Konsumsi RT": pd.to_numeric(work[col_rt], errors="coerce") if col_rt else None,
        "Konsumsi LNPRT": pd.to_numeric(work[col_lnprt], errors="coerce") if col_lnprt else None,
        "PKP": pd.to_numeric(work[col_pkp], errors="coerce") if col_pkp else None,
        "PMTB": pd.to_numeric(work[col_pmtb], errors="coerce") if col_pmtb else None,
        "Change in Stocks": pd.to_numeric(work[col_stocks], errors="coerce") if col_stocks else None,
        "Ekspor": pd.to_numeric(work[col_exp], errors="coerce") if col_exp else None,
        "Impor": pd.to_numeric(work[col_imp], errors="coerce") if col_imp else None,
    })
    discrepancy = pd.to_numeric(work[col_disc], errors="coerce") if col_disc else 0.0
    wide["PDB Aggregate"] = wide["Konsumsi RT"].fillna(0) + wide["Konsumsi LNPRT"].fillna(0) + wide["PKP"].fillna(0) + wide["PMTB"].fillna(0) + wide["Change in Stocks"].fillna(0) + wide["Ekspor"].fillna(0) - wide["Impor"].fillna(0) + pd.to_numeric(discrepancy, errors="coerce").fillna(0)
    return wide


def _build_growth_tables_from_wide(wide: pd.DataFrame):
    long_rows, growth_rows, yoy_rows, qtq_rows = [], [], [], []
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
        yoy_row, qtq_row = {"indikator": comp}, {"indikator": comp}
        for q in [1,2,3,4]:
            sel = s26[s26["quarter"] == q]
            yoy_row[date_map[q]] = float(sel["yoy"].iloc[-1]) if not sel.empty and pd.notna(sel["yoy"].iloc[-1]) else None
            qtq_row[date_map[q]] = float(sel["qtq"].iloc[-1]) if not sel.empty and pd.notna(sel["qtq"].iloc[-1]) else None
        annual = s.groupby("tahun", as_index=False)["nilai"].sum()
        annual["yoy"] = annual["nilai"].pct_change(1) * 100
        annual26 = annual.loc[annual["tahun"] == 2026, "yoy"]
        yoy_row["full_year"] = float(annual26.iloc[-1]) if not annual26.empty and pd.notna(annual26.iloc[-1]) else None
        qtq_row["full_year"] = float(s["qtq"].dropna().iloc[-1]) if not s["qtq"].dropna().empty else None
        yoy_rows.append(yoy_row)
        qtq_rows.append(qtq_row)
    return pd.concat(long_rows, ignore_index=True), pd.concat(growth_rows, ignore_index=True), ensure_schema(pd.DataFrame(yoy_rows), "pdb"), ensure_schema(pd.DataFrame(qtq_rows), "pdb")


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
                data[block] = ensure_schema(pd.read_excel(xls, sheet_name=lower_sheet_map[block], engine="openpyxl"), block)
        if "realisasi" in lower_sheet_map:
            data["pdb"], pdb_history, pdb_tables = derive_pdb_from_realisasi(source)
        elif "pdb" in lower_sheet_map:
            data["pdb"] = ensure_schema(pd.read_excel(xls, sheet_name=lower_sheet_map["pdb"], engine="openpyxl"), "pdb")
        return data, pdb_history, pdb_tables, status
    except Exception as e:
        return data, pdb_history, pdb_tables, f"Gagal membaca sumber Excel otomatis: {e}"


def build_simulasi_fiskal_df() -> pd.DataFrame:
    return pd.DataFrame({"indikator": SIMULASI_FISKAL_ROWS, **{c: [0.0]*len(SIMULASI_FISKAL_ROWS) for c in SIMULASI_FISKAL_COLS}})


def get_simulasi_fiskal_df() -> pd.DataFrame:
    if "simulasi_fiskal_df" not in st.session_state:
        st.session_state["simulasi_fiskal_df"] = build_simulasi_fiskal_df()
    df = st.session_state["simulasi_fiskal_df"].copy()
    df["indikator"] = SIMULASI_FISKAL_ROWS
    for c in SIMULASI_FISKAL_COLS:
        df[c] = pd.to_numeric(df.get(c, 0.0), errors="coerce").fillna(0.0)
    return df[["indikator", *SIMULASI_FISKAL_COLS]]


def build_simulasi_makro_df() -> pd.DataFrame:
    return pd.DataFrame({"indikator": [r[0] for r in SIMULASI_MAKRO_DEFAULTS], "apbn_2026": [r[1] for r in SIMULASI_MAKRO_DEFAULTS], "shock": [None]*len(SIMULASI_MAKRO_DEFAULTS)})


def get_simulasi_makro_df() -> pd.DataFrame:
    if "simulasi_makro_df" not in st.session_state:
        st.session_state["simulasi_makro_df"] = build_simulasi_makro_df()
    df = st.session_state["simulasi_makro_df"].copy()
    df["indikator"] = [r[0] for r in SIMULASI_MAKRO_DEFAULTS]
    df["apbn_2026"] = [r[1] for r in SIMULASI_MAKRO_DEFAULTS]
    df["shock"] = pd.to_numeric(df.get("shock"), errors="coerce")
    return df[["indikator", "apbn_2026", "shock"]]


def apply_simulasi_fiskal_to_pdb_nominal(pdb_df: pd.DataFrame, simulasi_df: pd.DataFrame) -> pd.DataFrame:
    if pdb_df is None or pdb_df.empty:
        return pdb_df
    work = ensure_full_year_from_quarters(pdb_df.copy())
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
            input_val = pd.to_numeric(sim_row.iloc[0].get(col, 0.0), errors="coerce")
            addition = (0.0 if pd.isna(input_val) else float(input_val)) / div if div else 0.0
            work.loc[target_mask, col] = pd.to_numeric(work.loc[target_mask, col], errors="coerce").fillna(0.0) + addition
            if agg_mask.any():
                work.loc[agg_mask, col] = pd.to_numeric(work.loc[agg_mask, col], errors="coerce").fillna(0.0) + addition
    return ensure_full_year_from_quarters(work)


def build_adjusted_top_growth_tables(pdb_history: Optional[dict], adjusted_nominal: pd.DataFrame):
    if not pdb_history or pdb_history.get("wide") is None or adjusted_nominal is None or adjusted_nominal.empty:
        return {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}
    wide = pdb_history["wide"].copy()
    date_map = {"out_tw1": pd.Timestamp("2026-03-31"), "out_tw2": pd.Timestamp("2026-06-30"), "out_tw3": pd.Timestamp("2026-09-30"), "out_tw4": pd.Timestamp("2026-12-31")}
    adj = adjusted_nominal.copy()
    adj["indikator"] = adj["indikator"].astype(str).str.strip()
    for _, row in adj.iterrows():
        if row["indikator"] not in PDB_COMPONENTS:
            continue
        for col, dt in date_map.items():
            val = pd.to_numeric(row.get(col), errors="coerce")
            if pd.notna(val):
                wide.loc[wide["tanggal"] == dt, row["indikator"]] = float(val)
    _, _, yoy_df, qtq_df = _build_growth_tables_from_wide(wide)
    return {"yoy": yoy_df, "qtq": qtq_df}


def render_simulasi_fiskal_editor() -> pd.DataFrame:
    st.markdown("### Simulasi Fiskal (dalam miliar)")
    if "simulasi_fiskal_draft" not in st.session_state:
        st.session_state["simulasi_fiskal_draft"] = get_simulasi_fiskal_df().copy()
    draft_df = st.session_state["simulasi_fiskal_draft"].copy()[["indikator", *SIMULASI_FISKAL_COLS]]
    edited_df = st.data_editor(draft_df, key="sim_fiskal_editor", hide_index=True, num_rows="fixed", disabled=["indikator"], use_container_width=False, width=760)
    edited_df["indikator"] = SIMULASI_FISKAL_ROWS
    for c in SIMULASI_FISKAL_COLS:
        edited_df[c] = pd.to_numeric(edited_df[c], errors="coerce").fillna(0.0)
    st.session_state["simulasi_fiskal_draft"] = edited_df.copy()
    c1, c2 = st.columns(2)
    if c1.button("Terapkan Simulasi Fiskal", use_container_width=True, type="primary"):
        st.session_state["simulasi_fiskal_df"] = edited_df.copy(); st.rerun()
    if c2.button("Reset Simulasi Fiskal", use_container_width=True):
        st.session_state["simulasi_fiskal_df"] = build_simulasi_fiskal_df(); st.session_state["simulasi_fiskal_draft"] = build_simulasi_fiskal_df(); st.rerun()
    return get_simulasi_fiskal_df()


def render_simulasi_makro_editor() -> pd.DataFrame:
    st.markdown("### Simulasi Asumsi Dasar Ekonomi Makro")
    st.caption(
        "Aturan 1: perubahan 0,1 pada 'Pertumbuhan ekonomi (%)' memberi Dampak 2.080,30 pada '1. Penerimaan Perpajakan'. "
        "Aturan 2: perubahan 0,1 pada 'Tingkat bunga SUN 10 tahun' memberi Dampak 1.899,98 pada '1. Belanja Pemerintah Pusat'."
    )
    if "simulasi_makro_draft" not in st.session_state:
        st.session_state["simulasi_makro_draft"] = get_simulasi_makro_df().copy()
    draft_df = st.session_state["simulasi_makro_draft"].copy()[["indikator", "apbn_2026", "shock"]]
    edited_df = st.data_editor(draft_df, key="sim_makro_editor", hide_index=True, num_rows="fixed", disabled=["indikator", "apbn_2026"], use_container_width=True)
    edited_df["indikator"] = [r[0] for r in SIMULASI_MAKRO_DEFAULTS]
    edited_df["apbn_2026"] = [r[1] for r in SIMULASI_MAKRO_DEFAULTS]
    edited_df["shock"] = pd.to_numeric(edited_df["shock"], errors="coerce")
    st.session_state["simulasi_makro_draft"] = edited_df.copy()
    c1, c2 = st.columns(2)
    if c1.button("Terapkan Shock Makro", use_container_width=True, type="primary"):
        st.session_state["simulasi_makro_df"] = edited_df.copy(); st.rerun()
    if c2.button("Reset Shock Makro", use_container_width=True):
        st.session_state["simulasi_makro_df"] = build_simulasi_makro_df(); st.session_state["simulasi_makro_draft"] = build_simulasi_makro_df(); st.rerun()
    return get_simulasi_makro_df()


def dataframe_for_display(df: pd.DataFrame, pct: bool = False, hide_rows=None) -> pd.DataFrame:
    view = df.copy()
    if hide_rows:
        view = view[~view["indikator"].isin(hide_rows)].copy()
    view = view[["indikator", *PERIOD_ORDER]].rename(columns={"indikator": "Indikator", **PERIOD_MAP})
    for c in view.columns[1:]:
        view[c] = view[c].apply(fmt_pct if pct else fmt_id0)
    return view


def render_table(df: pd.DataFrame, pct: bool = False, hide_rows=None):
    st.dataframe(dataframe_for_display(df, pct=pct, hide_rows=hide_rows), use_container_width=True, hide_index=True)


def _get_delta_from_macro(simulasi_makro_df: Optional[pd.DataFrame], indikator: str, apbn_default: float) -> float:
    if simulasi_makro_df is None or simulasi_makro_df.empty:
        return 0.0
    work = simulasi_makro_df.copy(); work["indikator"] = work["indikator"].astype(str).str.strip()
    row = work.loc[work["indikator"] == indikator]
    if row.empty:
        return 0.0
    base = pd.to_numeric(row.iloc[0].get("apbn_2026", apbn_default), errors="coerce")
    shock = pd.to_numeric(row.iloc[0].get("shock"), errors="coerce")
    if pd.isna(base) or pd.isna(shock):
        return 0.0
    return float(shock) - float(base)


def compute_dampak_growth_from_macro(simulasi_makro_df: Optional[pd.DataFrame]) -> float:
    return round((_get_delta_from_macro(simulasi_makro_df, PERTUMBUHAN_ROW, PERTUMBUHAN_APBN) / 0.1) * DAMPAK_PER_0_1_PERTUMBUHAN, 2)


def compute_dampak_bunga_sun_from_macro(simulasi_makro_df: Optional[pd.DataFrame]) -> float:
    return round((_get_delta_from_macro(simulasi_makro_df, BUNGA_SUN_ROW, BUNGA_SUN_APBN) / 0.1) * DAMPAK_PER_0_1_BUNGA_SUN, 2)


def build_fiskal_rows(simulasi_makro_df: Optional[pd.DataFrame]):
    dampak_growth = compute_dampak_growth_from_macro(simulasi_makro_df)
    dampak_bunga = compute_dampak_bunga_sun_from_macro(simulasi_makro_df)
    komponen = {k: {"apbn": v, "dampak": 0.0, "outlook": v} for k, v in FISKAL_COMPONENTS_BASE.items()}
    komponen["1. Penerimaan Perpajakan"]["dampak"] = dampak_growth
    komponen["1. Penerimaan Perpajakan"]["outlook"] += dampak_growth
    komponen["1. Belanja Pemerintah Pusat"]["dampak"] = dampak_bunga
    komponen["1. Belanja Pemerintah Pusat"]["outlook"] += dampak_bunga

    def add_vals(*vals):
        vals = [float(v) for v in vals if v is not None and not pd.isna(v)]
        return sum(vals) if vals else None

    pendapatan = {
        "apbn": add_vals(komponen["1. Penerimaan Perpajakan"]["apbn"], komponen["2. Penerimaan Negara Bukan Pajak"]["apbn"], komponen["3. Hibah"]["apbn"]),
        "dampak": add_vals(komponen["1. Penerimaan Perpajakan"]["dampak"], komponen["2. Penerimaan Negara Bukan Pajak"]["dampak"], komponen["3. Hibah"]["dampak"]),
        "outlook": add_vals(komponen["1. Penerimaan Perpajakan"]["outlook"], komponen["2. Penerimaan Negara Bukan Pajak"]["outlook"], komponen["3. Hibah"]["outlook"]),
    }
    belanja = {
        "apbn": add_vals(komponen["1. Belanja Pemerintah Pusat"]["apbn"], komponen["2. Transfer ke Daerah"]["apbn"]),
        "dampak": add_vals(komponen["1. Belanja Pemerintah Pusat"]["dampak"], komponen["2. Transfer ke Daerah"]["dampak"]),
        "outlook": add_vals(komponen["1. Belanja Pemerintah Pusat"]["outlook"], komponen["2. Transfer ke Daerah"]["outlook"]),
    }
    surplus = {"apbn": pendapatan["apbn"] - belanja["apbn"], "dampak": pendapatan["dampak"] - belanja["dampak"], "outlook": pendapatan["outlook"] - belanja["outlook"]}
    pembiayaan = {"apbn": -surplus["apbn"], "dampak": -surplus["dampak"], "outlook": -surplus["outlook"]}
    return [
        {"uraian": "A. Pendapatan Negara dan Hibah", **pendapatan, "bold": True},
        {"uraian": "1. Penerimaan Perpajakan", **komponen["1. Penerimaan Perpajakan"], "bold": False},
        {"uraian": "2. Penerimaan Negara Bukan Pajak", **komponen["2. Penerimaan Negara Bukan Pajak"], "bold": False},
        {"uraian": "3. Hibah", **komponen["3. Hibah"], "bold": False},
        {"uraian": "B. Belanja Negara", **belanja, "bold": True},
        {"uraian": "1. Belanja Pemerintah Pusat", **komponen["1. Belanja Pemerintah Pusat"], "bold": False},
        {"uraian": "2. Transfer ke Daerah", **komponen["2. Transfer ke Daerah"], "bold": False},
        {"uraian": "C. Surplus/Defisit", **surplus, "bold": True},
        {"uraian": "D. Pembiayaan Anggaran", **pembiayaan, "bold": True},
    ]


def render_fiskal_block_table(simulasi_makro_df: Optional[pd.DataFrame]):
    fiskal_rows = build_fiskal_rows(simulasi_makro_df)
    body_rows = []
    for row in fiskal_rows:
        cls = "group" if row.get("bold") else ""
        fw = "font-weight:700;" if row.get("bold") else ""
        body_rows.append(
            f"<tr class='{cls}'>"
            f"<td style='{fw}'>{html.escape(str(row['uraian']))}</td>"
            f"<td class='num' style='{fw}'>{fmt_fiskal(row['apbn'])}</td>"
            f"<td class='num' style='{fw}'>{fmt_fiskal(row['dampak'])}</td>"
            f"<td class='num' style='{fw}'>{fmt_fiskal(row['outlook'])}</td>"
            f"</tr>"
        )
    st.markdown(
        "<table class='fiskal-table'><thead><tr><th>Uraian</th><th class='num'>APBN 2026</th><th class='num'>Dampak</th><th class='num'>Outlook</th></tr></thead><tbody>" + ''.join(body_rows) + "</tbody></table>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Aturan 1: setiap perubahan 0,1 pada '{PERTUMBUHAN_ROW}' memberi Dampak {fmt_fiskal(DAMPAK_PER_0_1_PERTUMBUHAN)} pada '1. Penerimaan Perpajakan'. "
        f"Aturan 2: setiap perubahan 0,1 pada '{BUNGA_SUN_ROW}' memberi Dampak {fmt_fiskal(DAMPAK_PER_0_1_BUNGA_SUN)} pada '1. Belanja Pemerintah Pusat'."
    )


def make_history_chart(pdb_history: Optional[dict], selected_components):
    if not pdb_history or pdb_history.get("level") is None or pdb_history["level"].empty:
        st.info("Data historis PDB belum tersedia.")
        return
    plot_df = pdb_history["level"].copy(); plot_df = plot_df[plot_df["komponen"].isin(selected_components)]
    fig = px.line(plot_df, x="tanggal", y="nilai", color="komponen", custom_data=["nilai_fmt"], color_discrete_sequence=[PRIMARY, ACCENT, SUCCESS, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"])
    fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m-%d}<br>%{customdata[0]}")
    fig.update_layout(height=380, hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title_text="")
    fig.update_yaxes(gridcolor=GRID)
    st.plotly_chart(fig, use_container_width=True)


def make_growth_chart(pdb_history: Optional[dict], selected_components, growth_col: str, title: str):
    if not pdb_history or pdb_history.get("growth") is None or pdb_history["growth"].empty:
        st.info("Data pertumbuhan PDB belum tersedia.")
        return
    plot_df = pdb_history["growth"].copy(); plot_df = plot_df[plot_df["komponen"].isin(selected_components)]
    plot_df["fmt"] = plot_df[growth_col].apply(fmt_pct)
    fig = px.line(plot_df, x="tanggal", y=growth_col, color="komponen", custom_data=["fmt"], color_discrete_sequence=[SUCCESS, ACCENT, PRIMARY, PURPLE, NEGATIVE, "#F4A261", "#4C78A8", "#6C8EAD"])
    fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m-%d}<br>%{customdata[0]}")
    fig.update_layout(title=title, height=380, hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title_text="")
    fig.update_yaxes(gridcolor=GRID, zeroline=True)
    st.plotly_chart(fig, use_container_width=True)


workbook, pdb_history, pdb_tables, source_status = load_dashboard_data()
st.sidebar.markdown("## Pengaturan Dashboard")
show_preview = st.sidebar.toggle("Tampilkan preview data mentah", value=False)
st.sidebar.markdown("### Sumber Data")
st.sidebar.info(source_status)

st.title("Dashboard Pemantauan PDB")
st.markdown("---")
st.info(source_status)

simulasi_fiskal_df = get_simulasi_fiskal_df()
simulasi_makro_df = get_simulasi_makro_df()

baseline_pdb_nominal = ensure_full_year_from_quarters(workbook["pdb"])
adjusted_pdb_nominal = apply_simulasi_fiskal_to_pdb_nominal(baseline_pdb_nominal.copy(), simulasi_fiskal_df)
baseline_top_yoy = pdb_tables["yoy"] if pdb_tables else empty_df("pdb")
baseline_top_qtq = pdb_tables["qtq"] if pdb_tables else empty_df("pdb")
adjusted_top_tables = build_adjusted_top_growth_tables(pdb_history, adjusted_pdb_nominal)
adjusted_top_yoy = adjusted_top_tables.get("yoy", empty_df("pdb"))
adjusted_top_qtq = adjusted_top_tables.get("qtq", empty_df("pdb"))

st.markdown("## Tabel Utama — Blok Accounting")
top_nominal_tab, top_yoy_tab, top_qtq_tab = st.tabs(["Tabel Nominal 2026", "Tabel Year on Year (YoY)", "Tabel Quarter to Quarter (QtQ)"])
with top_nominal_tab:
    st.dataframe(dataframe_for_display(adjusted_pdb_nominal), use_container_width=True, hide_index=True)
with top_yoy_tab:
    st.dataframe(dataframe_for_display(adjusted_top_yoy, pct=True, hide_rows=EXCLUDE_GROWTH_ROWS), use_container_width=True, hide_index=True)
with top_qtq_tab:
    st.dataframe(dataframe_for_display(adjusted_top_qtq, pct=True, hide_rows=EXCLUDE_GROWTH_ROWS), use_container_width=True, hide_index=True)

simulasi_fiskal_df = render_simulasi_fiskal_editor()
makro_tab, pdb_tab, moneter_tab, fiskal_tab = st.tabs(["Blok Makro", "Blok Accounting", "Blok Moneter", "Blok Fiskal"])
with makro_tab:
    st.markdown("## Blok Makro")
    render_table(workbook["makro"])
with pdb_tab:
    st.markdown("## Accounting / PDB")
    nominal_tab, yoy_tab, qtq_tab = st.tabs(["Tabel Nominal 2026", "Tabel Year on Year (YoY)", "Tabel Quarter to Quarter (QtQ)"])
    with nominal_tab:
        render_table(workbook["pdb"])
    with yoy_tab:
        render_table(baseline_top_yoy, pct=True, hide_rows=EXCLUDE_GROWTH_ROWS)
    with qtq_tab:
        render_table(baseline_top_qtq, pct=True, hide_rows=EXCLUDE_GROWTH_ROWS)
    selected_components = st.multiselect("Pilih komponen historis yang ingin ditampilkan", options=PDB_COMPONENTS, default=PDB_COMPONENTS)
    selected_components = selected_components or PDB_COMPONENTS
    hist_tab, yoyc_tab, qtqc_tab = st.tabs(["Historis Level", "Year on Year (YoY)", "Quarter to Quarter (QtQ)"])
    with hist_tab:
        make_history_chart(pdb_history, selected_components)
    with yoyc_tab:
        make_growth_chart(pdb_history, [c for c in selected_components if c not in EXCLUDE_GROWTH_ROWS], "yoy", "Pertumbuhan Year on Year (YoY)")
    with qtqc_tab:
        make_growth_chart(pdb_history, [c for c in selected_components if c not in EXCLUDE_GROWTH_ROWS], "qtq", "Pertumbuhan Quarter to Quarter (QtQ)")
with moneter_tab:
    st.markdown("## Blok Moneter")
    render_table(workbook["moneter"])
with fiskal_tab:
    st.markdown("## Blok Fiskal")
    render_fiskal_block_table(simulasi_makro_df)
    st.markdown("---")
    simulasi_makro_df = render_simulasi_makro_editor()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Dampak Pertumbuhan", fmt_fiskal(compute_dampak_growth_from_macro(simulasi_makro_df)))
    c2.metric("Dampak SUN 10 Tahun", fmt_fiskal(compute_dampak_bunga_sun_from_macro(simulasi_makro_df)))
    grow = simulasi_makro_df.loc[simulasi_makro_df["indikator"] == PERTUMBUHAN_ROW, "shock"]
    sun = simulasi_makro_df.loc[simulasi_makro_df["indikator"] == BUNGA_SUN_ROW, "shock"]
    c3.metric("Shock Pertumbuhan", "—" if grow.empty or pd.isna(grow.iloc[0]) else f"{float(grow.iloc[0]):.1f}")
    c4.metric("Shock SUN 10 Tahun", "—" if sun.empty or pd.isna(sun.iloc[0]) else f"{float(sun.iloc[0]):.1f}")

if show_preview:
    with st.expander("Preview data yang berhasil dimuat", expanded=False):
        fiskal_preview = pd.DataFrame(build_fiskal_rows(simulasi_makro_df))[ ["uraian", "apbn", "dampak", "outlook"] ].rename(columns={"uraian":"Uraian","apbn":"APBN 2026","dampak":"Dampak","outlook":"Outlook"})
        st.dataframe(fiskal_preview, use_container_width=True, hide_index=True)
