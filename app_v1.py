from pathlib import Path

APP = Path("app.py")
if not APP.exists():
    raise FileNotFoundError("Letakkan perbaiki_kontras.py di folder yang sama dengan app.py")

text = APP.read_text(encoding="utf-8")

css = r'''
/* ===== KONTRAS NYAMAN: TANPA HITAM MURNI ===== */
:root {
    --ink-strong: #19375F;
    --ink-main: #284766;
    --ink-soft: #58708E;
    --line-soft: #D5E0EC;
    --head-bg: #DCE8F5;
    --row-alt: #F4F8FC;
    --card-bg: #FFFFFF;
}

/* Teks umum. Hindari #000 dan #111. */
.block-container,
.block-container p,
.block-container label,
.block-container span {
    color: var(--ink-main);
}

/* Tabel HTML PDB */
.compare-table {
    font-size: 0.96rem;
}
.compare-table th {
    color: var(--ink-strong) !important;
    background: var(--head-bg) !important;
    font-weight: 750;
    border-color: #C6D4E3 !important;
}
.compare-table td {
    color: var(--ink-main) !important;
    background: var(--card-bg);
    font-weight: 600;
    border-color: var(--line-soft) !important;
}
.compare-table tbody tr:nth-child(even) td {
    background: var(--row-alt);
}
.compare-table tbody tr:hover td {
    background: #EAF2FB !important;
}
.compare-table td.up {
    color: #137157 !important;
    background: #DDF3EA !important;
    font-weight: 750;
}
.compare-table td.down {
    color: #A33D4E !important;
    background: #F8E5E8 !important;
    font-weight: 750;
}
.compare-table td.same {
    color: var(--ink-main) !important;
}
.compare-table td.missing {
    color: #71859E !important;
    background: #F3F6F9 !important;
}

/* Tabel fiskal */
.fiscal-table th {
    color: var(--ink-strong) !important;
    background: var(--head-bg) !important;
    font-weight: 750;
}
.fiscal-table td {
    color: var(--ink-main) !important;
    font-weight: 600;
}
.fiscal-table tbody tr:nth-child(even) td {
    background: var(--row-alt);
}

/* Dataframe dan editor Streamlit */
div[data-testid="stDataFrame"],
div[data-testid="stDataEditor"] {
    color: var(--ink-main) !important;
    background: #FFFFFF !important;
    border: 1px solid #C8D6E5 !important;
}
div[data-testid="stDataFrame"] *,
div[data-testid="stDataEditor"] * {
    color: var(--ink-main);
}

/* Tab. Putih hanya pada tab aktif berlatar biru. */
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] span {
    color: #334E70 !important;
    font-weight: 650;
}
.stTabs [aria-selected="true"],
.stTabs [aria-selected="true"] p,
.stTabs [aria-selected="true"] span {
    color: #FFFFFF !important;
}

/* Legenda dan catatan */
.legend, .legend span, .note {
    color: var(--ink-soft) !important;
}

/* Pertahankan teks putih hanya pada elemen biru. */
.djsef-header, .djsef-header *,
.block-container .stButton button[kind="primary"],
.block-container .stButton button[kind="primary"] * {
    color: #FFFFFF !important;
}
'''

if "/* ===== KONTRAS NYAMAN: TANPA HITAM MURNI ===== */" not in text:
    pos = text.find("</style>")
    if pos < 0:
        raise RuntimeError("Tag </style> tidak ditemukan pada app.py")
    text = text[:pos] + css + "\n" + text[pos:]

# Perkuat warna teks Plotly tanpa memakai hitam murni.
text = text.replace(
    'font_color="#23344D"',
    'font_color="#284766", title_font_color="#19375F"',
)
text = text.replace(
    'fig.update_xaxes(color="#23344D", gridcolor="rgba(31,41,55,.08)")',
    'fig.update_xaxes(color="#4E6989", title_font_color="#315A89", tickfont=dict(color="#4E6989", size=12), gridcolor="#E0E7F0", linecolor="#B8C8DA", zerolinecolor="#C8D5E3")',
)
text = text.replace(
    'fig.update_yaxes(color="#23344D", gridcolor="rgba(31,41,55,.12)")',
    'fig.update_yaxes(color="#4E6989", title_font_color="#315A89", tickfont=dict(color="#4E6989", size=12), gridcolor="#D6E0EC", linecolor="#B8C8DA", zerolinecolor="#C8D5E3")',
)

# Jika baris font Plotly belum ada, tambahkan sesudah update_layout yang memuat legend_title_text.
if 'legend=dict(font=dict(color="#315A89"' not in text:
    old = 'legend_title_text="", font_color="#284766", title_font_color="#19375F")'
    new = 'legend_title_text="", font_color="#284766", title_font_color="#19375F", legend=dict(font=dict(color="#315A89", size=12), bgcolor="rgba(255,255,255,0.85)"))'
    text = text.replace(old, new)

APP.write_text(text, encoding="utf-8")
print("[OK] Kontras tabel dan grafik diperbaiki pada app.py")
