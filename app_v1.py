from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
import html
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Dashboard Monitoring dan Simulasi Ekonomi Nasional", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

FILE_NAME = "dashboard PDB.xlsx"
try:
    RAW_URL = st.secrets.get("github_raw_xlsx_url", "")
except Exception:
    RAW_URL = ""

QCOLS = ["out_tw1", "out_tw2", "out_tw3", "out_tw4"]
PERIODS = QCOLS + ["full_year"]
LABELS = dict(zip(PERIODS, ["Q1", "Q2", "Q3", "Q4", "Full Year"]))
COMPONENTS = ["Konsumsi RT", "Konsumsi LNPRT", "PKP", "PMTB", "Change in Stocks", "Ekspor", "Impor", "PDB Aggregate"]
MAIN_ROWS = ["Konsumsi RT", "PKP", "PMTB", "Ekspor", "Impor", "PDB Aggregate"]
FISCAL_ROWS = ["Bantuan Pangan", "Bantuan Langsung Tunai", "Kenaikan Gaji", "Pembayaran Gaji 14", "Diskon Transportasi", "Investasi"]
MACRO_DEFAULTS = [
    ("Pertumbuhan ekonomi (%)", 5.4), ("Inflasi (%)", 2.5),
    ("Tingkat bunga SUN 10 tahun", 6.9), ("Nilai tukar (Rp100/US$1)", 16500.0),
    ("Harga minyak (US$/barel)", 70.0), ("Lifting minyak (ribu barel per hari)", 610.0),
    ("Lifting Gas Bumi (ribu barel setara minyak per hari)", 984.0),
]
DEFAULT_ROWS = {
    "makro": ["Inflasi", "Rupiah", "Yield SBN", "ICP", "Nikel", "Coal", "CPO", "Lifting"],
    "moneter": ["PUAB", "Kredit", "DPK", "M0", "OMO"],
    "fiskal": ["Pendapatan", "Belanja", "Pembiayaan", "Defisit"],
    "pdb": COMPONENTS,
}
COLORS = ["#3E6DB5", "#E07B39", "#2A9D8F", "#8A5CF6", "#D14D72", "#F4A261", "#4C78A8", "#6C8EAD"]

st.markdown("""
<style>
:root{--navy:#1f4373;--bg:#f4f7fb;--border:#d9e2ef;--active:#eaf2ff;--blue:#397cf6}
html,body,[class*=css]{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}.stApp{background:var(--bg)}
header[data-testid=stHeader]{height:0;background:transparent}#MainMenu,footer,div[data-testid=stToolbar],div[data-testid=stDecoration]{display:none!important}
.block-container{max-width:none;padding:6.8rem 2.3rem 3rem}
.djsef-header{position:fixed;z-index:999999;top:0;left:0;right:0;height:84px;display:grid;grid-template-columns:320px 1fr 180px;align-items:center;color:#fff;background:linear-gradient(110deg,#1e416f,#214b7e);box-shadow:0 3px 12px rgba(15,35,65,.16)}
.brand{height:100%;display:flex;align-items:center;gap:16px;padding-left:22px;border-right:1px solid rgba(255,255,255,.08)}.logo{width:52px;height:52px;display:flex;align-items:center;justify-content:center;border-radius:12px;border:2px solid rgba(255,255,255,.3);background:rgba(255,255,255,.1)}
.bars{height:27px;display:flex;align-items:flex-end;gap:4px}.bars span{width:4px;border-radius:2px;background:#fff}.bars span:nth-child(1){height:11px}.bars span:nth-child(2){height:21px}.bars span:nth-child(3){height:16px}.bars span:nth-child(4){height:27px}
.brand-name{color:#c7d5e8;font-size:16px;font-weight:600}.ministry{font-size:17px;font-weight:700;margin-top:3px}.app-title{text-align:center;font-size:21px;font-weight:700}.profile{display:flex;justify-content:flex-end;align-items:center;gap:22px;padding-right:28px}.bell{position:relative;font-size:22px}.dot{position:absolute;top:0;right:-1px;width:6px;height:6px;border-radius:50%;background:#ff6b7a}.avatar{width:48px;height:48px;display:flex;align-items:center;justify-content:center;border-radius:50%;font-weight:700;background:linear-gradient(145deg,#568bc6,#2c6099);border:2px solid rgba(255,255,255,.28)}
section[data-testid=stSidebar]{top:84px;height:calc(100vh - 84px);width:320px!important;min-width:320px!important;max-width:320px!important;background:#fff;border-right:1px solid #e5eaf1}section[data-testid=stSidebar]>div{padding-top:1rem}section[data-testid=stSidebar] div[data-testid=stSidebarUserContent]{padding:0!important}
.side-title{padding:21px 21px 8px;color:#8a99ac;font-size:14px;font-weight:800;letter-spacing:.08em}.source{margin:18px 20px;padding:12px 13px;border-radius:9px;color:#60748d;background:#f5f8fc;border:1px solid #e2e8f0;font-size:12px;line-height:1.45}
section[data-testid=stSidebar] div[role=radiogroup]{gap:0}section[data-testid=stSidebar] label[data-baseweb=radio]{width:100%;min-height:55px;margin:0;padding:0 21px;border-radius:0}section[data-testid=stSidebar] label[data-baseweb=radio]>div:first-child{display:none}section[data-testid=stSidebar] label[data-baseweb=radio] p{color:#2f4057;font-size:16px;font-weight:500;line-height:1.3}section[data-testid=stSidebar] label[data-baseweb=radio]:has(input:checked){background:var(--active);box-shadow:inset 4px 0 0 var(--blue)}section[data-testid=stSidebar] label[data-baseweb=radio]:has(input:checked) p{color:#123c72;font-weight:700}
.page-title{margin:0 0 1.3rem;color:#14213a;font-size:30px;font-weight:750;letter-spacing:-.035em}.section-title{display:flex;align-items:center;gap:12px;margin:20px 0 15px;color:#214679;font-size:19px;font-weight:750}.section-title:after{content:"";height:1px;flex:1;background:#d7e0ec}.alert{display:flex;gap:16px;align-items:center;padding:18px 23px;margin-bottom:30px;color:#984919;background:#fff5e7;border:1px solid #f4a11a;border-radius:11px;font-size:16px}.alert strong{color:#8d3e12}
.stTabs [data-baseweb=tab-list]{gap:8px;padding:6px;border-radius:12px;background:#e9eef6}.stTabs [data-baseweb=tab]{height:44px;padding:0 20px;border-radius:9px;color:#53657d;font-weight:650}.stTabs [aria-selected=true]{color:#fff!important;background:var(--navy)!important}.stTabs [data-baseweb=tab-highlight],.stTabs [data-baseweb=tab-border]{display:none}
div[data-testid=stDataFrame],div[data-testid=stDataEditor],div[data-testid=stPlotlyChart]{overflow:hidden;border:1px solid var(--border);border-radius:12px;background:#fff;box-shadow:0 3px 10px rgba(21,48,82,.06)}div[data-testid=stPlotlyChart]{padding:10px}.stButton button{min-height:43px;border-radius:9px;font-weight:650}.stButton button[kind=primary]{border-color:var(--navy);background:var(--navy)}
.compare-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:12px;background:#fff;box-shadow:0 3px 10px rgba(21,48,82,.06)}.compare{border-collapse:collapse;width:100%;min-width:1200px;font-size:.92rem}.compare th,.compare td{border:1px solid #dde4ed;padding:.6rem .7rem;text-align:center;white-space:nowrap}.compare th{color:#294766;background:#edf3fa}.compare th:first-child,.compare td:first-child{position:sticky;left:0;z-index:2;text-align:left;background:#fff}.compare th:first-child{background:#edf3fa}.up{color:#127a5a;background:#e8f7f2;font-weight:700}.down{color:#b42318;background:#fdebec;font-weight:700}.same{background:#fff}.missing{color:#6b7280;background:#fafafa}.note{color:#6b7280;font-size:.88rem;margin-top:.55rem}.legend{display:flex;gap:1rem;margin-top:.7rem;color:#66778c;font-size:.85rem}.sw{width:14px;height:14px;border:1px solid #d1d5db;border-radius:3px;display:inline-block;margin-right:5px}.fiscal{width:100%;border-collapse:separate;border-spacing:0;border:1px solid var(--border);border-radius:12px;background:#fff;overflow:hidden}.fiscal th,.fiscal td{padding:.65rem .8rem;border-bottom:1px solid #e2e8f0}.fiscal th{color:#294766;background:#edf3fa}
@media(max-width:900px){.djsef-header{grid-template-columns:240px 1fr 100px}.app-title{font-size:16px}.block-container{padding-left:1rem;padding-right:1rem}}
</style>
""", unsafe_allow_html=True)


def header():
    st.markdown("""<div class="djsef-header"><div class="brand"><div class="logo"><div class="bars"><span></span><span></span><span></span><span></span></div></div><div><div class="brand-name">DJSEF</div><div class="ministry">Kementerian Keuangan RI</div></div></div><div class="app-title">Dashboard Monitoring dan Simulasi Ekonomi Nasional</div><div class="profile"><div class="bell">♧<span class="dot"></span></div><div class="avatar">TD</div></div></div>""", unsafe_allow_html=True)


def sidebar(status):
    st.sidebar.markdown('<div class="side-title">MENU UTAMA</div>', unsafe_allow_html=True)
    options = ["▥  Ringkasan Ekonomi", "⌁  Ringkasan Indikator Ekonomi Terkini", "▦  Ringkasan Fiskal", "♙  Simulasi Fiskal", "⌒  Sensitivitas APBN", "◎  Simulasi Program Prioritas"]
    selected = st.sidebar.radio("Navigasi", options, label_visibility="collapsed")
    st.sidebar.markdown('<div class="side-title">DOKUMEN</div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div style="padding:14px 21px;color:#2f4057;font-size:16px">▤ &nbsp; Laporan</div>', unsafe_allow_html=True)
    st.sidebar.markdown(f'<div class="source"><strong>Sumber Data</strong><br>{html.escape(status)}</div>', unsafe_allow_html=True)
    for symbol in ["▥", "⌁", "▦", "♙", "⌒", "◎"]: selected = selected.replace(symbol, "")
    return selected.strip()


def page_title(text): st.markdown(f'<div class="page-title">{html.escape(text)}</div>', unsafe_allow_html=True)
def section(text): st.markdown(f'<div class="section-title">{html.escape(text)}</div>', unsafe_allow_html=True)
def empty_df(block):
    rows = DEFAULT_ROWS[block]
    return pd.DataFrame({"indikator": rows, **{c: [None] * len(rows) for c in PERIODS}})
def norm(x): return str(x).strip().lower().replace(" ", "_").replace(".", "").replace("-", "_")
def fmt_num(x):
    if x is None or pd.isna(x): return "—"
    return f"{float(x):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
def fmt_pct(x):
    if x is None or pd.isna(x): return "—"
    return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "%"
def ensure_full_year(df):
    df = df.copy()
    for c in QCOLS: df[c] = pd.to_numeric(df.get(c), errors="coerce")
    df["full_year"] = df[QCOLS].sum(axis=1, min_count=1)
    return df


def excel_source():
    p = Path(__file__).resolve().parent / FILE_NAME
    if p.exists(): return str(p), f"{FILE_NAME} di folder aplikasi"
    if RAW_URL:
        try:
            with urlopen(RAW_URL) as r: return r.read(), "GitHub Raw URL dari st.secrets"
        except Exception as e: return None, f"URL Excel gagal dibaca: {e}"
    return None, f"{FILE_NAME} belum ditemukan"


def excel_file(src): return pd.ExcelFile(BytesIO(src), engine="openpyxl") if isinstance(src, bytes) else pd.ExcelFile(src, engine="openpyxl")


@st.cache_data(show_spinner=False)
def load_data():
    data = {k: empty_df(k) for k in DEFAULT_ROWS}
    src, status = excel_source()
    if src is None: return data, None, None, status
    try:
        xls = excel_file(src); smap = {s.lower().strip(): s for s in xls.sheet_names}
        for block in ["makro", "moneter", "fiskal"]:
            if block in smap:
                d = pd.read_excel(xls, sheet_name=smap[block], engine="openpyxl")
                d.columns = [norm(c) for c in d.columns]
                if "indikator" not in d: d = d.rename(columns={d.columns[0]: "indikator"})
                for c in PERIODS:
                    if c not in d: d[c] = None
                data[block] = d[["indikator", *PERIODS]]
        if "realisasi" not in smap: return data, None, None, status
        raw = pd.read_excel(xls, sheet_name=smap["realisasi"], engine="openpyxl")
        raw = raw.rename(columns={raw.columns[0]: "tanggal"}); raw["tanggal"] = pd.to_datetime(raw["tanggal"], errors="coerce"); raw = raw.dropna(subset=["tanggal"]).sort_values("tanggal")
        wide = pd.DataFrame({"tanggal": raw["tanggal"]})
        for c in COMPONENTS[:-1]:
            src_col = next((x for x in raw.columns if norm(x) == norm(c)), None)
            if c != "PDB Aggregate": wide[c] = pd.to_numeric(raw[src_col], errors="coerce") if src_col else None
        disc_col = next((x for x in raw.columns if norm(x) == norm("Statistical Discrepancy")), None)
        disc = pd.to_numeric(raw[disc_col], errors="coerce") if disc_col else 0
        wide["PDB Aggregate"] = wide["Konsumsi RT"] + wide["Konsumsi LNPRT"] + wide["PKP"] + wide["PMTB"] + wide["Change in Stocks"] + wide["Ekspor"] - wide["Impor"] + disc
        nominal_rows = []
        for comp in COMPONENTS:
            row = {"indikator": comp}
            for q, col in enumerate(QCOLS, 1):
                s = wide.loc[(wide.tanggal.dt.year == 2026) & (wide.tanggal.dt.quarter == q), comp]
                row[col] = float(s.iloc[-1]) if not s.empty else None
            nominal_rows.append(row)
        data["pdb"] = ensure_full_year(pd.DataFrame(nominal_rows))
        levels = wide.melt(id_vars="tanggal", var_name="komponen", value_name="nilai"); levels["nilai_fmt"] = levels["nilai"].apply(fmt_num)
        grows = []
        yoy_rows, qtq_rows = [], []
        for comp in COMPONENTS:
            s = wide[["tanggal", comp]].copy(); s["yoy"] = s[comp].pct_change(4, fill_method=None) * 100; s["qtq"] = s[comp].pct_change(fill_method=None) * 100; s["komponen"] = comp; grows.append(s[["tanggal", "komponen", "yoy", "qtq"]])
            yr, qr = {"indikator": comp}, {"indikator": comp}
            for q, col in enumerate(QCOLS, 1):
                z = s[(s.tanggal.dt.year == 2026) & (s.tanggal.dt.quarter == q)]
                yr[col] = float(z.yoy.iloc[-1]) if not z.empty else None; qr[col] = float(z.qtq.iloc[-1]) if not z.empty else None
            annual = s.assign(tahun=s.tanggal.dt.year).groupby("tahun")[comp].sum(min_count=1).pct_change(fill_method=None) * 100
            yr["full_year"] = float(annual.loc[2026]) if 2026 in annual.index else None; qr["full_year"] = None
            yoy_rows.append(yr); qtq_rows.append(qr)
        hist = {"wide": wide, "level": levels, "growth": pd.concat(grows, ignore_index=True)}
        tables = {"yoy": pd.DataFrame(yoy_rows), "qtq": pd.DataFrame(qtq_rows)}
        return data, hist, tables, status
    except Exception as e: return data, None, None, f"Gagal membaca Excel: {e}"


def fiscal_default(): return pd.DataFrame({"indikator": FISCAL_ROWS, **{c: [0.0] * len(FISCAL_ROWS) for c in QCOLS}})
def macro_default(): return pd.DataFrame({"indikator": [x[0] for x in MACRO_DEFAULTS], "apbn_2026": [x[1] for x in MACRO_DEFAULTS], "shock": [None] * len(MACRO_DEFAULTS)})
def state_df(key, factory):
    if key not in st.session_state: st.session_state[key] = factory()
    return st.session_state[key].copy()


def adjust_nominal(base, sim):
    out = ensure_full_year(base); rules = [("Bantuan Pangan", "PKP", [1.82,1.86,1.88,1.91]), ("Bantuan Langsung Tunai", "Konsumsi RT", [1.82,1.84,1.85,1.86]), ("Kenaikan Gaji", "Konsumsi RT", [1.82,1.84,1.85,1.86]), ("Pembayaran Gaji 14", "Konsumsi RT", [1.82,1.84,1.85,1.86]), ("Diskon Transportasi", "Konsumsi RT", [1.82,1.84,1.85,1.86]), ("Investasi", "PMTB", [1.66,1.66,1.67,1.67])]
    for sname, target, divs in rules:
        sr = sim[sim.indikator == sname]
        if sr.empty: continue
        for col, div in zip(QCOLS, divs):
            add = float(pd.to_numeric(sr.iloc[0][col], errors="coerce") or 0) / div
            out.loc[out.indikator == target, col] += add; out.loc[out.indikator == "PDB Aggregate", col] += add
    return ensure_full_year(out)


def adjusted_growth(hist, adjusted):
    if not hist: return {"yoy": empty_df("pdb"), "qtq": empty_df("pdb")}
    wide = hist["wide"].copy()
    for _, r in adjusted.iterrows():
        if r.indikator not in COMPONENTS: continue
        for q, col in enumerate(QCOLS, 1): wide.loc[(wide.tanggal.dt.year == 2026) & (wide.tanggal.dt.quarter == q), r.indikator] = r[col]
    yr, qr = [], []
    for comp in COMPONENTS:
        s = wide[["tanggal", comp]].copy(); s["yoy"] = s[comp].pct_change(4, fill_method=None) * 100; s["qtq"] = s[comp].pct_change(fill_method=None) * 100
        a, b = {"indikator": comp}, {"indikator": comp}
        for q, col in enumerate(QCOLS, 1):
            z = s[(s.tanggal.dt.year == 2026) & (s.tanggal.dt.quarter == q)]; a[col] = z.yoy.iloc[-1]; b[col] = z.qtq.iloc[-1]
        annual = s.assign(tahun=s.tanggal.dt.year).groupby("tahun")[comp].sum().pct_change(fill_method=None) * 100; a["full_year"] = annual.loc[2026]; b["full_year"] = None; yr.append(a); qr.append(b)
    return {"yoy": pd.DataFrame(yr), "qtq": pd.DataFrame(qr)}


def val(df, ind, col):
    s = pd.to_numeric(df.loc[df.indikator == ind, col], errors="coerce"); return None if s.empty else s.iloc[0]
def cls(a, b):
    if b is None or pd.isna(b): return "missing"
    if a is None or pd.isna(a) or abs(float(b)-float(a)) < 1e-12: return "same"
    return "up" if b > a else "down"
def comparison(base, shock, formatter, note=""):
    h = '<div class="compare-wrap"><table class="compare"><thead><tr><th rowspan="2">Indikator</th>' + ''.join(f'<th colspan="2">Q{i}</th>' for i in range(1,5)) + '<th colspan="3">Full Year</th></tr><tr>' + '<th>Baseline</th><th>Shock Fiskal</th>' * 4 + '<th>Baseline</th><th>Shock Fiskal</th><th>Shock Makro</th></tr></thead><tbody>'
    rows = []
    for ind in MAIN_ROWS:
        cells = [f'<td>{ind}</td>']
        for c in QCOLS:
            a,b = val(base,ind,c),val(shock,ind,c); cells += [f'<td>{formatter(a)}</td>', f'<td class="{cls(a,b)}">{formatter(b)}</td>']
        a,b = val(base,ind,"full_year"),val(shock,ind,"full_year"); cells += [f'<td>{formatter(a)}</td>', f'<td class="{cls(a,b)}">{formatter(b)}</td>', f'<td class="{cls(a,b)}">{formatter(b)}</td>']; rows.append('<tr>'+''.join(cells)+'</tr>')
    out = h + ''.join(rows) + '</tbody></table></div><div class="legend"><span><i class="sw up"></i>Lebih tinggi</span><span><i class="sw down"></i>Lebih rendah</span><span><i class="sw same"></i>Sama</span></div>'
    if note: out += f'<div class="note">{html.escape(note)}</div>'
    st.markdown(out, unsafe_allow_html=True)


def chart(hist, selected, metric=None):
    if not hist: st.info("Data historis belum tersedia."); return
    if metric:
        d = hist["growth"]; d = d[d.komponen.isin(selected)].copy(); d["fmt"] = d[metric].apply(fmt_pct); fig = px.line(d, x="tanggal", y=metric, color="komponen", custom_data=["fmt"], color_discrete_sequence=COLORS)
    else:
        d = hist["level"]; d = d[d.komponen.isin(selected)]; fig = px.line(d, x="tanggal", y="nilai", color="komponen", custom_data=["nilai_fmt"], color_discrete_sequence=COLORS)
    fig.update_traces(mode="lines+markers", hovertemplate="%{x|%Y-%m-%d}<br>%{customdata[0]}<extra></extra>"); fig.update_layout(height=390, hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title_text=""); st.plotly_chart(fig, use_container_width=True)


def fiscal_table(macro):
    def delta(name):
        r = macro[macro.indikator == name]
        if r.empty or pd.isna(r.iloc[0].shock): return 0
        return float(r.iloc[0].shock - r.iloc[0].apbn_2026)
    pp_impact = delta("Pertumbuhan ekonomi (%)") / .1 * 2080.30 + delta("Lifting Gas Bumi (ribu barel setara minyak per hari)") / 10 * 390.99
    pnbp_impact = delta("Lifting Gas Bumi (ribu barel setara minyak per hari)") / 10 * 870.10
    apbn = {"pp":2693714,"pnbp":459200,"hibah":666,"bpp":3149733,"tkd":692995}; A=apbn["pp"]+apbn["pnbp"]+apbn["hibah"]; B=apbn["bpp"]+apbn["tkd"]
    rows=[("A. Pendapatan Negara dan Hibah",A,pp_impact+pnbp_impact,1),("1. Penerimaan Perpajakan",apbn["pp"],pp_impact,0),("2. Penerimaan Negara Bukan Pajak",apbn["pnbp"],pnbp_impact,0),("3. Hibah",apbn["hibah"],0,0),("B. Belanja Negara",B,0,1),("1. Belanja Pemerintah Pusat",apbn["bpp"],0,0),("2. Transfer ke Daerah",apbn["tkd"],0,0),("C. Surplus/Defisit",A-B,pp_impact+pnbp_impact,1),("D. Pembiayaan Anggaran",B-A,-pp_impact-pnbp_impact,1)]
    trs=[]
    for name,a,d,b in rows:
        fw='font-weight:700' if b else ''; trs.append(f'<tr><td style="{fw}">{name}</td><td style="text-align:right;{fw}">{fmt_num(a)}</td><td style="text-align:right;{fw}">{fmt_num(d)}</td><td style="text-align:right;{fw}">{fmt_num(a+d)}</td></tr>')
    st.markdown('<table class="fiscal"><thead><tr><th>Uraian</th><th>APBN 2026</th><th>Dampak</th><th>Outlook</th></tr></thead><tbody>'+''.join(trs)+'</tbody></table>', unsafe_allow_html=True)


data, hist, tables, status = load_data(); header(); page = sidebar(status)
st.markdown('<div class="alert">⚠ <div><strong>Perhatian:</strong> Data PDB 2026 mencakup baseline dan simulasi. Pastikan input shock telah diterapkan sebelum membaca outlook.</div></div>', unsafe_allow_html=True)
sim_fiscal = state_df("simulasi_fiskal_df", fiscal_default); sim_macro = state_df("simulasi_makro_df", macro_default)
base = ensure_full_year(data["pdb"]); adjusted = adjust_nominal(base, sim_fiscal); base_yoy = tables["yoy"] if tables else empty_df("pdb"); base_qtq = tables["qtq"] if tables else empty_df("pdb"); ag = adjusted_growth(hist, adjusted)

if page == "Ringkasan Ekonomi":
    page_title("Ringkasan Ekonomi Makro"); section("Tabel Utama Blok Accounting"); a,b,c=st.tabs(["Nominal 2026","Year on Year (YoY)","Quarter to Quarter (QtQ)"])
    with a: comparison(base, adjusted, fmt_num, "Shock Makro pada tabel PDB masih mengikuti Shock Fiskal.")
    with b: comparison(base_yoy, ag["yoy"], fmt_pct)
    with c: comparison(base_qtq, ag["qtq"], fmt_pct, "Full Year QtQ dikosongkan karena QtQ adalah perubahan antartriwulan.")
    section("Perkembangan Komponen PDB"); selected=st.multiselect("Pilih komponen PDB", COMPONENTS, default=MAIN_ROWS) or MAIN_ROWS; x,y,z=st.tabs(["Historis Level","Pertumbuhan YoY","Pertumbuhan QtQ"])
    with x: chart(hist,selected)
    with y: chart(hist,[i for i in selected if i != "Change in Stocks"],"yoy")
    with z: chart(hist,[i for i in selected if i != "Change in Stocks"],"qtq")
elif page == "Ringkasan Indikator Ekonomi Terkini":
    page_title(page); a,b=st.tabs(["Indikator Makro","Indikator Moneter"])
    with a: section("Asumsi dan Indikator Makro"); st.dataframe(data["makro"].rename(columns={"indikator":"Indikator",**LABELS}),hide_index=True,use_container_width=True)
    with b: section("Indikator Moneter"); st.dataframe(data["moneter"].rename(columns={"indikator":"Indikator",**LABELS}),hide_index=True,use_container_width=True)
elif page == "Ringkasan Fiskal":
    page_title(page); section("Outlook APBN 2026"); fiscal_table(sim_macro)
elif page == "Simulasi Fiskal":
    page_title(page); st.info("Masukkan stimulus fiskal per triwulan dalam miliar rupiah."); section("Input Simulasi Fiskal")
    edited=st.data_editor(sim_fiscal,hide_index=True,disabled=["indikator"],use_container_width=True,column_config={"indikator":st.column_config.TextColumn("Simulasi Fiskal",width="large"),**{c:st.column_config.NumberColumn(LABELS[c],format="%.2f") for c in QCOLS}}); c1,c2=st.columns(2)
    if c1.button("Terapkan Simulasi Fiskal",type="primary",use_container_width=True): st.session_state.simulasi_fiskal_df=edited; st.rerun()
    if c2.button("Reset Simulasi Fiskal",use_container_width=True): st.session_state.simulasi_fiskal_df=fiscal_default(); st.rerun()
    section("Dampak terhadap PDB"); comparison(base,adjusted,fmt_num)
elif page == "Sensitivitas APBN":
    page_title(page); section("Simulasi Asumsi Dasar Ekonomi Makro")
    edited=st.data_editor(sim_macro,hide_index=True,disabled=["indikator","apbn_2026"],use_container_width=True,column_config={"indikator":st.column_config.TextColumn("Asumsi Dasar Ekonomi Makro",width="large"),"apbn_2026":st.column_config.NumberColumn("APBN 2026",format="%.1f"),"shock":st.column_config.NumberColumn("Shock",format="%.1f")}); c1,c2=st.columns(2)
    if c1.button("Terapkan Shock Makro",type="primary",use_container_width=True): st.session_state.simulasi_makro_df=edited; st.rerun()
    if c2.button("Reset Shock Makro",use_container_width=True): st.session_state.simulasi_makro_df=macro_default(); st.rerun()
    section("Dampak terhadap Outlook Fiskal"); fiscal_table(sim_macro)
else:
    page_title(page); st.info("Modul simulasi program prioritas sedang disiapkan untuk input program, anggaran, multiplier, dan periode pelaksanaan.")
