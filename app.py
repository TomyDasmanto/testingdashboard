import math
from io import BytesIO
from pathlib import Path
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
# Konstanta dasar
# =========================
REPO_FILE_NAME = "dashboard PDB.xlsx"

try:
    GITHUB_RAW_XLSX_URL = st.secrets.get("github_raw_xlsx_url", "")
except Exception:
    GITHUB_RAW_XLSX_URL = ""

PERIOD_LABELS = {
    "out_tw1": "Outlook Q1",
    "out_tw2": "Outlook Q2",
    "out_tw3": "Outlook Q3",
    "out_tw4": "Outlook Q4",
    "full_year": "Full Year",
}
PERIOD_COLS = list(PERIOD_LABELS.keys())
QUARTER_COLS = PERIOD_COLS[:-1]
TARGET_YEAR = 2026

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

PDB_MAIN_HIDE = {"Konsumsi LNPRT", "Change in Stocks"}
EXCLUDE_GROWTH_ROWS = {"Change in Stocks"}
COLOR_SEQUENCE = ["#3E6DB5", "#E07B39", "#2A9D8F", "#8A5CF6", "#D14D72", "#F4A261", "#4C78A8", "#6C8EAD"]
GRID = "rgba(31,41,55,0.12)"
CHART_CONFIG = {"displayModeBar": True, "displaylogo": False, "responsive": True}

SIM_ROWS = [
    "Bantuan Pangan",
    "Bantuan Langsung Tunai",
    "Kenaikan Gaji",
    "Pembayaran Gaji 14",
    "Diskon Transportasi",
    "Investasi",
]
SIM_RULES = [
    {"name": "Bantuan Pangan", "target": "PKP", "div": {"out_tw1": 1.82, "out_tw2": 1.86, "out_tw3": 1.88, "out_tw4": 1.91}},
    {"name": "Bantuan Langsung Tunai", "target": "Konsumsi RT", "div": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86}},
    {"name": "Kenaikan Gaji", "target": "Konsumsi RT", "div": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86}},
    {"name": "Pembayaran Gaji 14", "target": "Konsumsi RT", "div": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86}},
    {"name": "Diskon Transportasi", "target": "Konsumsi RT", "div": {"out_tw1": 1.82, "out_tw2": 1.84, "out_tw3": 1.85, "out_tw4": 1.86}},
    {"name": "Investasi", "target": "PMTB", "div": {"out_tw1": 1.66, "out_tw2": 1.66, "out_tw3": 1.67, "out_tw4": 1.67}},
]

MAKRO_ADEM_ROWS = [
    ("Pertumbuhan ekonomi (%)", 5.4, None, None),
    ("Inflasi (%)", 2.5, None, None),
    ("Tingkat bunga SUN 10 tahun", 6.9, None, None),
    ("Nilai tukar (Rp100/US$1)", 16500.0, None, None),
    ("Harga minyak (US$/barel)", 70.0, None, None),
    ("Lifting minyak (ribu barel per hari)", 610.0, None, None),
    ("Lifting Gas Bumi (ribu barel setara minyak per hari)", 984.0, None, None),
]

FISKAL_BASELINE_ROWS = [
    ("A Pendapatan Negara dan Hibah", 3153580.45),
    ("1. Penerimaan Perpajakan", 2693714.24),
    ("2. Penerimaan Negara Bukan Pajak", 459199.94),
    ("3. Hibah", 666.27),
    ("B Belanja Negara", 3842728.37),
    ("1. Belanja Pemerintah Pusat", 3149733.39),
    ("2. Transfer ke Daerah", 692994.97),
    ("C Surplus/(Defisit) Anggaran", -689147.92),
    ("D Pembiayaan Anggaran", 689147.92),
]


# =========================
# Helper umum
# =========================
def fmt_number(value, decimals=0):
    if value is None or pd.isna(value):
        return "—"
    text = f"{float(value):,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_percent(value, decimals=2):
    return f"{fmt_number(value, decimals)}%" if not (value is None or pd.isna(value)) else "—"


def normalize_key(text):
    return str(text).strip().lower().replace(" ", "_").replace(".", "").replace("-", "_")


def as_numeric(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def ensure_full_year(df):
    work = df.copy()
    work = as_numeric(work, QUARTER_COLS)
    work["full_year"] = work[QUARTER_COLS].sum(axis=1, min_count=1)
    return work


def format_period_table(df, pct=False):
    if df is None or df.empty:
        return pd.DataFrame(columns=["Indikator", *PERIOD_LABELS.values()])

    out = df[["indikator", *PERIOD_COLS]].copy()
    out = out.rename(columns={"indikator": "Indikator", **PERIOD_LABELS})
    formatter = fmt_percent if pct else fmt_number
    for col in out.columns[1:]:
        out[col] = out[col].apply(formatter)
    return out


def make_ticks(series, pct=False, n=6):
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return [], []

    vmin = float(values.min())
    vmax = float(values.max())
    if pct:
        vmin = min(vmin, 0.0)
        vmax = max(vmax, 0.0)

    if math.isclose(vmin, vmax):
        span = 1 if pct or math.isclose(vmin, 0.0) else abs(vmin) * 0.1
        ticks = [vmin - span, vmin, vmin + span]
    else:
        step = (vmax - vmin) / max(n - 1, 1)
        ticks = [vmin + i * step for i in range(n)]

    labels = [fmt_percent(x) if pct else fmt_number(x) for x in ticks]
    return ticks, labels


def placeholder_chart(message, height=380):
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


# =========================
# Sumber data
# =========================
def load_excel_bytes(url):
    with urlopen(url) as response:
        return response.read()


def detect_excel_source():
    local_path = Path(__file__).resolve().parent / REPO_FILE_NAME
    if local_path.exists():
        return str(local_path), f"Sumber data: file lokal {REPO_FILE_NAME}"
    if GITHUB_RAW_XLSX_URL:
        return load_excel_bytes(GITHUB_RAW_XLSX_URL), "Sumber data: GitHub Raw URL dari st.secrets['github_raw_xlsx_url']"
    return None, f"File {REPO_FILE_NAME} tidak ditemukan. Simpan file di folder yang sama dengan app.py atau isi st.secrets['github_raw_xlsx_url']."


def open_excel(source):
    if isinstance(source, (bytes, bytearray)):
        return pd.ExcelFile(BytesIO(source), engine="openpyxl")
    return pd.ExcelFile(source, engine="openpyxl")


def choose_column(columns, target):
    target_norm = normalize_key(target)
    for col in columns:
        if normalize_key(col) == target_norm:
            return col
    return None


# =========================
# Turunan data PDB
# =========================
def read_realisasi(source):
    xls = open_excel(source)
    realisasi_sheet = next((s for s in xls.sheet_names if s.strip().lower() == "realisasi"), None)
    if realisasi_sheet is None:
        return pd.DataFrame()

    raw = pd.read_excel(xls, sheet_name=realisasi_sheet, engine="openpyxl")
    raw = raw.rename(columns={raw.columns[0]: "tanggal"}).copy()
    raw["tanggal"] = pd.to_datetime(raw["tanggal"], errors="coerce")
    raw = raw.dropna(subset=["tanggal"]).sort_values("tanggal").reset_index(drop=True)

    mapping = {}
    for name in [
        "Konsumsi RT",
        "Konsumsi LNPRT",
        "PKP",
        "PMTB",
        "Ekspor",
        "Impor",
        "Change in Stocks",
        "Statistical Discrepancy",
    ]:
        col = choose_column(list(raw.columns), name)
        if col is not None:
            mapping[name] = col

    level = raw[["tanggal", *mapping.values()]].rename(columns={v: k for k, v in mapping.items()}).copy()

    for col in [
        "Konsumsi RT",
        "Konsumsi LNPRT",
        "PKP",
        "PMTB",
        "Ekspor",
        "Impor",
        "Change in Stocks",
        "Statistical Discrepancy",
    ]:
        if col not in level.columns:
            level[col] = None

    level = as_numeric(level, level.columns[1:])
    level["PDB Aggregate"] = (
        level["Konsumsi RT"].fillna(0)
        + level["Konsumsi LNPRT"].fillna(0)
        + level["PKP"].fillna(0)
        + level["PMTB"].fillna(0)
        + level["Change in Stocks"].fillna(0)
        + level["Ekspor"].fillna(0)
        - level["Impor"].fillna(0)
        + level["Statistical Discrepancy"].fillna(0)
    )

    return level[["tanggal", *PDB_COMPONENTS]].copy()


def build_period_table(level_df, year=TARGET_YEAR):
    rows = []
    for indicator in PDB_COMPONENTS:
        s = level_df[["tanggal", indicator]].copy().sort_values("tanggal")
        s["tahun"] = s["tanggal"].dt.year
        s["quarter"] = s["tanggal"].dt.quarter
        current = s[s["tahun"] == year]

        item = {"indikator": indicator}
        for q in range(1, 5):
            val = current.loc[current["quarter"] == q, indicator]
            item[f"out_tw{q}"] = float(val.iloc[-1]) if not val.empty else None
        rows.append(item)

    return ensure_full_year(pd.DataFrame(rows))


def build_growth_table(level_df, periods, year=TARGET_YEAR):
    rows = []
    for indicator in PDB_COMPONENTS:
        s = level_df[["tanggal", indicator]].copy().sort_values("tanggal")
        s["growth"] = s[indicator].pct_change(periods=periods) * 100
        s["tahun"] = s["tanggal"].dt.year
        s["quarter"] = s["tanggal"].dt.quarter
        current = s[s["tahun"] == year]

        item = {"indikator": indicator}
        for q in range(1, 5):
            val = current.loc[current["quarter"] == q, "growth"]
            item[f"out_tw{q}"] = float(val.iloc[-1]) if not val.empty else None

        annual = s.assign(year_sum=s.groupby("tahun")[indicator].transform("sum"))[["tahun", "year_sum"]]
        annual = annual.drop_duplicates().sort_values("tahun")
        annual["annual_growth"] = annual["year_sum"].pct_change() * 100
        full_year = annual.loc[annual["tahun"] == year, "annual_growth"]
        item["full_year"] = float(full_year.iloc[-1]) if not full_year.empty else None
        rows.append(item)

    return pd.DataFrame(rows)


def build_history_frames(level_df):
    hist_level = level_df.melt(id_vars="tanggal", value_vars=PDB_COMPONENTS, var_name="komponen", value_name="nilai")
    hist_level["nilai_fmt"] = hist_level["nilai"].apply(fmt_number)

    growth_parts = []
    for indicator in PDB_COMPONENTS:
        temp = level_df[["tanggal", indicator]].copy().sort_values("tanggal")
        temp["komponen"] = indicator
        temp["yoy"] = temp[indicator].pct_change(4) * 100
        temp["qtq"] = temp[indicator].pct_change(1) * 100
        growth_parts.append(temp[["tanggal", "komponen", "yoy", "qtq"]])

    hist_growth = pd.concat(growth_parts, ignore_index=True)
    return {"level": hist_level, "growth": hist_growth}


def replace_2026_with_adjusted(level_df, adjusted_nominal):
    wide = level_df.copy()
    date_map = {
        "out_tw1": pd.Timestamp(f"{TARGET_YEAR}-03-31"),
        "out_tw2": pd.Timestamp(f"{TARGET_YEAR}-06-30"),
        "out_tw3": pd.Timestamp(f"{TARGET_YEAR}-09-30"),
        "out_tw4": pd.Timestamp(f"{TARGET_YEAR}-12-31"),
    }

    adjusted = adjusted_nominal.copy()
    adjusted["indikator"] = adjusted["indikator"].astype(str).str.strip()

    for _, row in adjusted.iterrows():
        indicator = row["indikator"]
        if indicator not in PDB_COMPONENTS:
            continue
        for period_col, dt in date_map.items():
            val = pd.to_numeric(row.get(period_col), errors="coerce")
            if pd.isna(val):
                continue
            mask = wide["tanggal"] == dt
            if mask.any():
                wide.loc[mask, indicator] = float(val)

    return wide[["tanggal", *PDB_COMPONENTS]].copy()


# =========================
# Simulasi fiskal
# =========================
def empty_simulation_df():
    return pd.DataFrame({
        "indikator": SIM_ROWS,
        "out_tw1": [0.0] * len(SIM_ROWS),
        "out_tw2": [0.0] * len(SIM_ROWS),
        "out_tw3": [0.0] * len(SIM_ROWS),
        "out_tw4": [0.0] * len(SIM_ROWS),
    })


def get_simulation_df():
    if "simulation_df" not in st.session_state:
        st.session_state["simulation_df"] = empty_simulation_df()
    df = st.session_state["simulation_df"].copy()
    df["indikator"] = SIM_ROWS
    return as_numeric(df, QUARTER_COLS)


def render_simulation_editor():
    st.subheader("Simulasi Fiskal (dalam miliar)")

    if "simulation_draft" not in st.session_state:
        st.session_state["simulation_draft"] = get_simulation_df().copy()

    with st.form("simulation_form", clear_on_submit=False):
        edited = st.data_editor(
            st.session_state["simulation_draft"],
            hide_index=True,
            num_rows="fixed",
            disabled=["indikator"],
            column_config={
                "indikator": st.column_config.TextColumn("Indikator"),
                "out_tw1": st.column_config.NumberColumn("Q1", format="%.2f"),
                "out_tw2": st.column_config.NumberColumn("Q2", format="%.2f"),
                "out_tw3": st.column_config.NumberColumn("Q3", format="%.2f"),
                "out_tw4": st.column_config.NumberColumn("Q4", format="%.2f"),
            },
            use_container_width=True,
        )

        c1, c2 = st.columns(2)
        apply_clicked = c1.form_submit_button("Terapkan")
        reset_clicked = c2.form_submit_button("Reset")

        edited = edited[["indikator", *QUARTER_COLS]].copy()
        edited["indikator"] = SIM_ROWS
        edited = as_numeric(edited, QUARTER_COLS).fillna(0.0)

        if reset_clicked:
            reset_df = empty_simulation_df()
            st.session_state["simulation_df"] = reset_df
            st.session_state["simulation_draft"] = reset_df.copy()
            st.success("Simulasi di-reset.")
            return reset_df

        if apply_clicked:
            st.session_state["simulation_df"] = edited
            st.session_state["simulation_draft"] = edited.copy()
            st.success("Simulasi diterapkan ke tabel utama.")
            return edited

        st.session_state["simulation_draft"] = edited.copy()
        return get_simulation_df()


def apply_simulation_to_nominal(pdb_nominal, sim_df):
    if pdb_nominal is None or pdb_nominal.empty:
        return pdb_nominal

    result = ensure_full_year(pdb_nominal.copy())
    sim = sim_df.copy()
    sim["indikator"] = sim["indikator"].astype(str).str.strip()

    agg_mask = result["indikator"].astype(str).str.strip().eq("PDB Aggregate")

    for rule in SIM_RULES:
        sim_row = sim.loc[sim["indikator"].eq(rule["name"])]
        if sim_row.empty:
            continue

        target_mask = result["indikator"].astype(str).str.strip().eq(rule["target"])
        if not target_mask.any():
            continue

        for col in QUARTER_COLS:
            val = pd.to_numeric(sim_row.iloc[0].get(col), errors="coerce")
            val = 0.0 if pd.isna(val) else float(val)
            div = rule["div"].get(col, 0)
            addition = val / div if div else 0.0

            result.loc[target_mask, col] = pd.to_numeric(result.loc[target_mask, col], errors="coerce").fillna(0) + addition
            result.loc[agg_mask, col] = pd.to_numeric(result.loc[agg_mask, col], errors="coerce").fillna(0) + addition

    return ensure_full_year(result)


# =========================
# Visualisasi
# =========================
def make_level_chart(history_df, selected_components):
    if history_df is None or history_df.empty:
        return placeholder_chart("Data historis belum tersedia.")

    plot_df = history_df[history_df["komponen"].isin(selected_components)].copy()
    if plot_df.empty:
        return placeholder_chart("Komponen yang dipilih belum memiliki data.")

    fig = px.line(
        plot_df,
        x="tanggal",
        y="nilai",
        color="komponen",
        color_discrete_sequence=COLOR_SEQUENCE,
        custom_data=["nilai_fmt"],
    )
    fig.update_traces(
        mode="lines+markers",
        line=dict(width=2.5),
        marker=dict(size=5),
        hovertemplate="<b>%{fullData.name}</b><br>%{x|%Y-%m-%d}: %{customdata[0]}<extra></extra>",
    )
    ticks, labels = make_ticks(plot_df["nilai"], pct=False)
    fig.update_layout(title="Historis Komponen PDB", height=395, hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, tickmode="array", tickvals=ticks, ticktext=labels)
    return fig


def make_growth_chart(history_growth_df, selected_components, metric, title):
    if history_growth_df is None or history_growth_df.empty:
        return placeholder_chart("Data pertumbuhan belum tersedia.")

    plot_df = history_growth_df[history_growth_df["komponen"].isin(selected_components)].copy()
    if plot_df.empty:
        return placeholder_chart("Komponen pertumbuhan yang dipilih belum memiliki data.")

    plot_df["nilai_fmt"] = plot_df[metric].apply(fmt_percent)
    fig = px.line(
        plot_df,
        x="tanggal",
        y=metric,
        color="komponen",
        color_discrete_sequence=COLOR_SEQUENCE,
        custom_data=["nilai_fmt"],
    )
    fig.update_traces(
        mode="lines+markers",
        line=dict(width=2.3),
        marker=dict(size=5),
        hovertemplate="<b>%{fullData.name}</b><br>%{x|%Y-%m-%d}: %{customdata[0]}<extra></extra>",
    )
    ticks, labels = make_ticks(plot_df[metric], pct=True)
    fig.update_layout(title=title, height=395, hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=True, tickmode="array", tickvals=ticks, ticktext=labels)
    return fig


# =========================
# Render tabel
# =========================
def render_period_dataframe(df, pct=False, hide_rows=None):
    work = df.copy()
    if hide_rows:
        work = work[~work["indikator"].isin(hide_rows)]
    st.dataframe(format_period_table(work, pct=pct), use_container_width=True, hide_index=True)


def render_makro_table():
    df = pd.DataFrame(MAKRO_ADEM_ROWS, columns=["Asumsi ADEM", "APBN 2026", "Realisasi", "Sensitivitas"])
    for col in ["APBN 2026", "Realisasi", "Sensitivitas"]:
        df[col] = df[col].apply(lambda x: fmt_number(x, 1) if pd.notna(x) else "—")
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_fiskal_table():
    df = pd.DataFrame(FISKAL_BASELINE_ROWS, columns=["Indikator", "APBN 2026 (baseline)"])
    df["APBN 2026 (baseline)"] = df["APBN 2026 (baseline)"].apply(lambda x: f"({fmt_number(abs(x), 2)})" if x < 0 else fmt_number(x, 2))
    st.dataframe(df, use_container_width=True, hide_index=True)


# =========================
# Main app
# =========================
def main():
    source, source_status = detect_excel_source()
    if source is None:
        st.title("Dashboard Pemantauan PDB")
        st.error(source_status)
        st.stop()

    level_df = read_realisasi(source)
    if level_df.empty:
        st.title("Dashboard Pemantauan PDB")
        st.error("Sheet 'realisasi' tidak ditemukan atau tidak bisa dibaca.")
        st.stop()

    pdb_nominal = build_period_table(level_df)
    pdb_yoy = build_growth_table(level_df, periods=4)
    pdb_qtq = build_growth_table(level_df, periods=1)
    history = build_history_frames(level_df)

    st.sidebar.header("Pengaturan")
    show_preview = st.sidebar.toggle("Tampilkan preview data", value=False)
    st.sidebar.info(source_status)

    st.title("Dashboard Pemantauan PDB")
    st.caption(source_status)

    simulation_df = render_simulation_editor()
    adjusted_nominal = apply_simulation_to_nominal(pdb_nominal, simulation_df)
    adjusted_level = replace_2026_with_adjusted(level_df, adjusted_nominal)
    adjusted_yoy = build_growth_table(adjusted_level, periods=4)
    adjusted_qtq = build_growth_table(adjusted_level, periods=1)

    st.divider()
    st.subheader("Tabel Utama — Blok Accounting")
    st.caption("Tabel utama sudah mencerminkan dampak simulasi fiskal yang diterapkan.")

    top_nominal_tab, top_yoy_tab, top_qtq_tab = st.tabs(["Nominal 2026", "YoY", "QtQ"])
    with top_nominal_tab:
        render_period_dataframe(adjusted_nominal, pct=False, hide_rows=PDB_MAIN_HIDE)
    with top_yoy_tab:
        render_period_dataframe(adjusted_yoy, pct=True, hide_rows=EXCLUDE_GROWTH_ROWS)
    with top_qtq_tab:
        render_period_dataframe(adjusted_qtq, pct=True, hide_rows=EXCLUDE_GROWTH_ROWS)

    tab_makro, tab_pdb, tab_moneter, tab_fiskal = st.tabs(["Blok Makro", "Blok Accounting", "Blok Moneter", "Blok Fiskal"])

    with tab_makro:
        st.subheader("Blok Makro")
        render_makro_table()

    with tab_pdb:
        st.subheader("Blok Accounting")
        baseline_nominal_tab, baseline_yoy_tab, baseline_qtq_tab = st.tabs(["Nominal 2026", "YoY", "QtQ"])
        with baseline_nominal_tab:
            render_period_dataframe(pdb_nominal, pct=False)
        with baseline_yoy_tab:
            render_period_dataframe(pdb_yoy, pct=True, hide_rows=EXCLUDE_GROWTH_ROWS)
        with baseline_qtq_tab:
            render_period_dataframe(pdb_qtq, pct=True, hide_rows=EXCLUDE_GROWTH_ROWS)

        st.markdown("### Grafik Historis")
        selected_components = st.multiselect(
            "Pilih komponen",
            options=PDB_COMPONENTS,
            default=PDB_COMPONENTS,
        ) or PDB_COMPONENTS
        selected_growth = [c for c in selected_components if c not in EXCLUDE_GROWTH_ROWS]

        hist_tab, yoy_tab, qtq_tab = st.tabs(["Historis Level", "YoY", "QtQ"])
        with hist_tab:
            st.plotly_chart(make_level_chart(history["level"], selected_components), use_container_width=True, config=CHART_CONFIG)
        with yoy_tab:
            st.plotly_chart(make_growth_chart(history["growth"], selected_growth, "yoy", "Pertumbuhan Year on Year (YoY)"), use_container_width=True, config=CHART_CONFIG)
        with qtq_tab:
            st.plotly_chart(make_growth_chart(history["growth"], selected_growth, "qtq", "Pertumbuhan Quarter to Quarter (QtQ)"), use_container_width=True, config=CHART_CONFIG)

    with tab_moneter:
        st.subheader("Blok Moneter")
        st.info("Masih placeholder. Blok ini bisa diaktifkan saat workbook sudah memiliki data moneter.")
        st.dataframe(
            pd.DataFrame({"Indikator": ["PUAB", "Kredit", "DPK", "M0", "OMO"]}),
            use_container_width=True,
            hide_index=True,
        )

    with tab_fiskal:
        st.subheader("Blok Fiskal")
        render_fiskal_table()

    if show_preview:
        with st.expander("Preview data", expanded=False):
            st.markdown("#### Level historis")
            st.dataframe(level_df, use_container_width=True, hide_index=True)
            st.markdown("#### PDB nominal baseline")
            st.dataframe(pdb_nominal, use_container_width=True, hide_index=True)
            st.markdown("#### Simulasi fiskal")
            st.dataframe(simulation_df, use_container_width=True, hide_index=True)
            st.markdown("#### PDB nominal setelah simulasi")
            st.dataframe(adjusted_nominal, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
