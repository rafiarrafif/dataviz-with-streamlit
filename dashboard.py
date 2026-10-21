from __future__ import annotations

import html
import re
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Coffee Shop Sales Dashboard",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_PATH = Path(__file__).resolve().parent / "dataset.csv"
REQUIRED_COLUMNS = {
    "transaction_id", "transaction_date", "transaction_time", "transaction_qty",
    "store_id", "store_location", "product_id", "unit_price",
    "product_category", "product_type", "product_detail",
}
ACCENT = "#C68B59"
ACCENT_SOFT = "#E6C9A8"
COFFEE = [
    "#C68B59", "#A1887F", "#E6C9A8", "#A0522D", "#8D6E63",
    "#F0DCC3", "#B5835A", "#D4A373", "#7B5B45", "#CDAA8A",
]
COFFEE_SCALE = ["#4E342E", "#8D6E63", "#C68B59", "#E6C9A8"]
BAR_SCALE = ["#8D6E63", "#C68B59", "#E6C9A8"]

ACCENT_FILTER = "sepia(0.5) hue-rotate(24deg) saturate(0.8) brightness(1.1)"
THEMED_WIDGETS = [
    '[data-testid="stSlider"]', '[data-testid="stRadio"]', '[data-testid="stCheckbox"]',
    '[data-testid="stMultiSelect"]', '[data-testid="stSelectbox"]', '[data-testid="stDateInput"]',
    '[data-testid="stButton"]', '[data-testid="stDownloadButton"]', '[data-baseweb="calendar"]',
]

CUSTOM_CSS = (
    "<style>\n"
    + ",\n".join(THEMED_WIDGETS)
    + " { filter: " + ACCENT_FILTER + "; }\n"
    + '[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * '
    + "{ color: " + ACCENT_SOFT + " !important; fill: " + ACCENT_SOFT + " !important; }\n"
    + ".cs-callout { background: rgba(198,139,89,0.14); border-left: 4px solid " + ACCENT + ";"
    + " border-radius: 0.5rem; padding: 0.85rem 1rem; height: 100%; }\n"
    + ".cs-callout .cs-title { font-size: 0.85rem; opacity: 0.8; margin-bottom: 0.25rem; }\n"
    + ".cs-callout .cs-body { font-size: 1.15rem; font-weight: 600; }\n"
    + "</style>"
)

DAY_ORDER = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
DAY_MAP = dict(enumerate(DAY_ORDER))

METRICS = {
    "Revenue (USD)": ("total_revenue", "sum", "$"),
    "Item Terjual (Qty)": ("transaction_qty", "sum", ""),
    "Jumlah Transaksi": ("transaction_id", "count", ""),
}

FREQ = {"Harian": "D", "Mingguan": "W-MON", "Bulanan": "MS"}
DIMENSIONS = {
    "Kategori Produk": "product_category",
    "Tipe Produk": "product_type",
    "Detail Produk": "product_detail",
}

FILTER_KEYS = ["f_date", "f_store", "f_cat", "f_day", "f_hour"]
_ver = tuple(int(x) for x in re.findall(r"\d+", st.__version__)[:2])
STRETCH = {"width": "stretch"} if _ver >= (1, 50) else {"use_container_width": True}

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def callout(body: str, title: str | None = None, container=st) -> None:
    title_html = f'<div class="cs-title">{html.escape(title)}</div>' if title else ""
    container.markdown(
        f'<div class="cs-callout">{title_html}<div class="cs-body">{body}</div></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner="Memuat & menyiapkan data...")
def load_data(path: str, modified_time: float) -> pd.DataFrame:
    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Kolom berikut tidak ditemukan di CSV: {', '.join(sorted(missing))}")

    df["transaction_date"] = pd.to_datetime(df["transaction_date"], format="%m/%d/%Y")
    df["hour"] = pd.to_datetime(df["transaction_time"], format="%H:%M:%S").dt.hour
    df["total_revenue"] = df["transaction_qty"] * df["unit_price"]
    dow = df["transaction_date"].dt.dayofweek
    df["day_name"] = dow.map(DAY_MAP)
    df["is_weekend"] = dow >= 5
    return df


def filter_df(df: pd.DataFrame, stores, cats, start, end) -> pd.DataFrame:
    mask = (
        df["store_location"].isin(stores)
        & df["product_category"].isin(cats)
        & df["transaction_date"].between(start, end)
    )
    return df[mask]


def aggregate(df: pd.DataFrame, by, metric: str) -> pd.DataFrame:
    col, how, _ = METRICS[metric]
    return df.groupby(by)[col].agg(how).reset_index(name="value")


def money(x: float) -> str:
    return f"${x:,.0f}"


def pct_delta(cur: float, prev: float | None) -> str | None:
    if prev is None or prev == 0:
        return None
    return f"{(cur - prev) / prev * 100:+.1f}%"


def style_fig(fig, height: int = 380):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        legend_title_text="",
        title_font_size=16,
    )
    return fig


def reset_filters():
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


st.title("Coffee Shop Sales Dashboard")
st.markdown(
    """
    Dashboard ini merangkum **performa penjualan tiga toko coffee shop di New York**
    (Astoria, Hell's Kitchen, dan Lower Manhattan) selama **Januari - Juni 2023**.
    Gunakan **filter di sidebar** untuk menelusuri tren pendapatan, produk terlaris,
    serta pola jam & hari tersibuk. Semua KPI dan grafik akan ikut berubah secara otomatis.
    """
)

if not DATA_PATH.exists():
    callout(f"File <code>{html.escape(DATA_PATH.name)}</code> tidak ditemukan. Letakkan di folder "
            f"yang sama dengan skrip ini: <code>{html.escape(str(DATA_PATH.parent))}</code>",
            title="Data tidak ditemukan")
    st.stop()

try:
    df = load_data(str(DATA_PATH), DATA_PATH.stat().st_mtime)
except Exception as exc:
    callout(html.escape(str(exc)), title="Gagal membaca data")
    st.stop()

st.sidebar.header("Filter Data")

min_date, max_date = df["transaction_date"].min().date(), df["transaction_date"].max().date()

date_val = st.sidebar.date_input(
    "Rentang tanggal", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
if not (isinstance(date_val, (tuple, list)) and len(date_val) == 2):
    callout("Pilih tanggal akhir untuk melengkapi rentang.", container=st.sidebar)
    st.stop()
start_date, end_date = pd.Timestamp(date_val[0]), pd.Timestamp(date_val[1])

all_stores = sorted(df["store_location"].unique())
sel_stores = st.sidebar.multiselect("Lokasi toko", all_stores, default=all_stores)

all_cats = sorted(df["product_category"].unique())
sel_cats = st.sidebar.multiselect("Kategori produk", all_cats, default=all_cats)

metric = st.sidebar.radio("Metrik grafik", list(METRICS.keys()))
metric_col, metric_how, _ = METRICS[metric]

df_f = filter_df(df, sel_stores, sel_cats, start_date, end_date)

if df_f.empty:
    callout("Tidak ada data yang cocok dengan kombinasi filter saat ini. "
            "Silakan longgarkan filter di sidebar.", title="Data kosong")
    st.stop()

n_days = (end_date - start_date).days + 1
prev_start, prev_end = start_date - timedelta(days=n_days), start_date - timedelta(days=1)
prev = None
if prev_start.date() >= min_date:
    prev_df = filter_df(df, sel_stores, sel_cats, prev_start, prev_end)
    if not prev_df.empty:
        prev = dict(
            total_revenue=prev_df["total_revenue"].sum(),
            trx=len(prev_df),
            qty=prev_df["transaction_qty"].sum(),
            aov=prev_df["total_revenue"].mean(),
        )

total_rev = df_f["total_revenue"].sum()
total_trx = len(df_f)
total_qty = int(df_f["transaction_qty"].sum())
aov = df_f["total_revenue"].mean()

best_series = df_f.groupby("product_detail")["transaction_qty"].sum().sort_values(ascending=False)
best_name, best_qty = best_series.index[0], int(best_series.iloc[0])

st.subheader("Key Performance Indicators")
delta_help = "Dibandingkan dengan periode sebelumnya yang panjangnya sama."
k1, k2, k3, k4, k5 = st.columns(5)

with k1.container(border=True):
    st.metric("Total Revenue", money(total_rev),
              delta=pct_delta(total_rev, prev["total_revenue"]) if prev else None, delta_color="off", help=delta_help)
with k2.container(border=True):
    st.metric("Total Transaksi", f"{total_trx:,}",
              delta=pct_delta(total_trx, prev["trx"]) if prev else None, delta_color="off", help=delta_help)
with k3.container(border=True):
    st.metric("Item Terjual", f"{total_qty:,}",
              delta=pct_delta(total_qty, prev["qty"]) if prev else None, delta_color="off", help=delta_help)
with k4.container(border=True):
    st.metric("Rata-rata / Transaksi", f"${aov:,.2f}",
              delta=pct_delta(aov, prev["aov"]) if prev else None, delta_color="off", help=delta_help)
with k5.container(border=True):
    st.metric("Produk Terlaris", best_name, help="Berdasarkan jumlah item terjual.")
    st.caption(f"{best_qty:,} item terjual")

if prev is None:
    st.caption("Delta (%) tidak ditampilkan karena periode pembanding berada di luar rentang data.")

st.divider()
st.subheader("Analisis Visual")

col_a, col_b = st.columns([2, 1])

with col_a.container(border=True):
    c1, c2 = st.columns([1, 1])
    granularity = c1.selectbox("Granularitas waktu", list(FREQ.keys()), index=1)
    split_store = c2.checkbox("Pisahkan per toko", value=True)

    group_keys = [pd.Grouper(key="transaction_date", freq=FREQ[granularity], label="left", closed="left")]
    if split_store:
        group_keys.append("store_location")
    trend = df_f.groupby(group_keys)[metric_col].agg(metric_how).reset_index(name="value")

    fig_line = px.line(
        trend, x="transaction_date", y="value",
        color="store_location" if split_store else None,
        markers=granularity != "Harian",
        color_discrete_sequence=COFFEE,
        labels={"transaction_date": "Tanggal", "value": metric, "store_location": "Toko"},
        title=f"Tren {metric} ({granularity})",
    )
    fig_line.update_traces(line_width=2.2)
    st.plotly_chart(style_fig(fig_line), **STRETCH)

with col_b.container(border=True):
    by_store = aggregate(df_f, "store_location", metric)
    fig_pie = px.pie(
        by_store, names="store_location", values="value", hole=0.5,
        color_discrete_sequence=COFFEE,
        title=f"Kontribusi Toko – {metric}",
    )
    fig_pie.update_traces(textinfo="percent+label", textposition="inside")
    fig_pie.update_layout(showlegend=False)
    st.plotly_chart(style_fig(fig_pie, height=446), **STRETCH)

col_c, col_d = st.columns(2)

with col_c.container(border=True):
    c1, c2 = st.columns([2, 1])
    dim_label = c1.selectbox("Peringkat berdasarkan", list(DIMENSIONS.keys()), index=1)
    dim_col = DIMENSIONS[dim_label]
    n_items = df_f[dim_col].nunique()
    if n_items > 3:
        top_n = c2.slider("Top N", 3, min(20, n_items), min(10, n_items))
    else:
        top_n = n_items
        c2.caption(f"{n_items} item")

    ranking = aggregate(df_f, dim_col, metric).nlargest(top_n, "value")
    fig_bar = px.bar(
        ranking, x="value", y=dim_col, orientation="h",
        color="value", color_continuous_scale=BAR_SCALE, text_auto=".3s",
        labels={"value": metric, dim_col: dim_label},
        title=f"Top {len(ranking)} {dim_label} – {metric}",
    )
    fig_bar.update_yaxes(categoryorder="total ascending")
    fig_bar.update_layout(coloraxis_showscale=False)
    st.plotly_chart(style_fig(fig_bar, height=440), **STRETCH)

with col_d.container(border=True):
    pivot = (
        df_f.pivot_table(index="day_name", columns="hour", values=metric_col,
                         aggfunc=metric_how, fill_value=0)
        .reindex(DAY_ORDER)
        .fillna(0)
    )
    fig_heat = px.imshow(
        pivot, aspect="auto", color_continuous_scale=COFFEE_SCALE,
        labels=dict(x="Jam", y="Hari", color=metric),
        title=f"Heatmap Hari × Jam – {metric}",
    )
    fig_heat.update_xaxes(dtick=1)
    st.plotly_chart(style_fig(fig_heat, height=440), **STRETCH)

st.divider()
st.subheader("Insight Otomatis")

top_store = df_f.groupby("store_location")["total_revenue"].sum().idxmax()
busiest_hour = int(df_f.groupby("hour")["transaction_id"].count().idxmax())
daily_rev = df_f.groupby(["transaction_date", "day_name"])["total_revenue"].sum().reset_index()
best_day = daily_rev.groupby("day_name")["total_revenue"].mean().idxmax()
top_cat = df_f.groupby("product_category")["total_revenue"].sum()
top_cat_name, top_cat_share = top_cat.idxmax(), top_cat.max() / top_cat.sum() * 100

i1, i2, i3, i4 = st.columns(4)
callout(html.escape(top_store), title="Toko terbaik", container=i1)
callout(f"{busiest_hour:02d}:00 – {busiest_hour:02d}:59", title="Jam tersibuk", container=i2)
callout(best_day, title="Hari dengan rata-rata revenue tertinggi", container=i3)
callout(f"{html.escape(top_cat_name)} ({top_cat_share:.1f}% revenue)", title="Kategori dominan", container=i4)

with st.expander("Lihat & unduh data terfilter"):
    export_cols = [
        "transaction_id", "transaction_date", "transaction_time", "store_location",
        "product_category", "product_type", "product_detail",
        "transaction_qty", "unit_price", "total_revenue",
    ]
    st.dataframe(df_f[export_cols].head(1000), hide_index=True, **STRETCH)
    st.caption("Menampilkan maksimal 1.000 baris pertama. Tombol di bawah mengunduh seluruh data terfilter.")
    st.download_button(
        "Unduh data terfilter (CSV)",
        data=df_f[export_cols].to_csv(index=False).encode("utf-8"),
        file_name="coffee_shop_filtered.csv",
        mime="text/csv",
    )

st.caption(
    f"Menampilkan **{len(df_f):,}** dari **{len(df):,}** baris transaksi · "
    f"Periode data: {min_date:%d %b %Y} – {max_date:%d %b %Y} · "
    "Dibangun dengan Streamlit & Plotly"
)