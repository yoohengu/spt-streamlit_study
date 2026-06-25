from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="POLYTERU 매출 대시보드", page_icon="🧥", layout="wide")

DUMMY_DIR = Path(__file__).parent / "더미데이터"
ORDER_KEY_COLUMNS = {"order_id", "product_id", "total_price"}
PRODUCT_KEY_COLUMNS = {"product_id", "product_name"}
SEOUL_LATITUDE, SEOUL_LONGITUDE = 37.5665, 126.9780

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 3.5rem;
        padding-bottom: 2rem;
    }
    h1 {
        font-weight: 800 !important;
    }
    [data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.65);
        border: 1px solid rgba(49, 51, 63, 0.1);
        border-radius: 14px;
        padding: 1.2rem 1.5rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
    }
    [data-testid="stMetricLabel"] {
        font-size: 1rem;
        font-weight: 600;
        opacity: 0.8;
    }
    [data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 800;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: rgba(255, 255, 255, 0.55);
        border-radius: 14px;
        padding: 0.5rem 0.2rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def identify_kind(df: pd.DataFrame) -> str | None:
    columns = set(df.columns)
    if ORDER_KEY_COLUMNS.issubset(columns):
        return "orders"
    if PRODUCT_KEY_COLUMNS.issubset(columns):
        return "products"
    return None


@st.cache_data
def merge_orders_and_products(orders_file, products_file) -> pd.DataFrame:
    orders = pd.read_excel(orders_file)
    products = pd.read_excel(products_file)
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    return orders.merge(products, on="product_id", how="left")


def won(value: float) -> str:
    return f"{value:,.0f} 원"


@st.cache_data(ttl=600)
def fetch_seoul_weather() -> dict:
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": SEOUL_LATITUDE,
            "longitude": SEOUL_LONGITUDE,
            "current_weather": True,
            "hourly": "temperature_2m",
            "timezone": "Asia/Seoul",
            "forecast_days": 1,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


try:
    weather = fetch_seoul_weather()
    current_temp = weather["current_weather"]["temperature"]
    hourly_df = pd.DataFrame(
        {
            "시간": pd.to_datetime(weather["hourly"]["time"]),
            "기온": weather["hourly"]["temperature_2m"],
        }
    )

    weather_metric_col, weather_chart_col = st.columns([1, 4])
    with weather_metric_col:
        st.metric("☀️ 서울 현재 기온", f"{current_temp:.1f} °C")
    with weather_chart_col:
        fig = px.line(hourly_df, x="시간", y="기온", markers=True)
        fig.update_traces(line_color="#0984E3", line_width=2, marker={"size": 4})
        fig.update_layout(
            height=120,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=5, b=5, l=5, r=5),
            yaxis_title=None,
            xaxis_title=None,
        )
        st.plotly_chart(fig, use_container_width=True)
except requests.RequestException as e:
    st.warning(f"날씨 정보를 불러오지 못했습니다: {e}")

st.divider()

st.title("🧥 POLYTERU 매출 대시보드")
st.caption("주문 데이터와 상품 데이터 엑셀 파일을 업로드하면 자동으로 병합되어 분석 대시보드를 보여줍니다")

st.sidebar.header("📁 데이터 업로드")
uploaded_files = st.sidebar.file_uploader(
    "주문 데이터(polyteru_orders)와 상품 데이터(polyteru_products) 엑셀 파일을 함께 선택하세요",
    type=["xlsx"],
    accept_multiple_files=True,
)
use_demo = st.sidebar.button("🎲 더미데이터로 미리보기", use_container_width=True)

orders_file = products_file = None

if uploaded_files:
    for file in uploaded_files:
        kind = identify_kind(pd.read_excel(file))
        file.seek(0)
        if kind == "orders":
            orders_file = file
        elif kind == "products":
            products_file = file
    if not (orders_file and products_file):
        st.sidebar.error("주문 데이터와 상품 데이터 파일을 각각 하나씩 업로드해주세요.")
elif use_demo:
    orders_file = DUMMY_DIR / "polyteru_orders.xlsx"
    products_file = DUMMY_DIR / "polyteru_products.xlsx"

if not (orders_file and products_file):
    st.info("⬅️ 사이드바에서 주문/상품 엑셀 파일 2개를 업로드하거나 더미데이터 미리보기 버튼을 눌러주세요.")
    st.stop()

df = merge_orders_and_products(orders_file, products_file)

st.sidebar.header("🔎 필터")
min_date, max_date = df["order_date"].min().date(), df["order_date"].max().date()
date_range = st.sidebar.date_input(
    "주문 기간", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
selected_categories = st.sidebar.multiselect(
    "카테고리", options=sorted(df["category"].dropna().unique()), default=sorted(df["category"].dropna().unique())
)
selected_channels = st.sidebar.multiselect(
    "판매 채널", options=sorted(df["channel"].unique()), default=sorted(df["channel"].unique())
)
selected_regions = st.sidebar.multiselect(
    "지역", options=sorted(df["region"].unique()), default=sorted(df["region"].unique())
)
selected_grades = st.sidebar.multiselect(
    "회원 등급", options=sorted(df["member_grade"].unique()), default=sorted(df["member_grade"].unique())
)
include_returns = st.sidebar.checkbox("반품 건 매출 포함", value=False)

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

base_mask = (
    (df["order_date"].dt.date >= start_date)
    & (df["order_date"].dt.date <= end_date)
    & (df["category"].isin(selected_categories))
    & (df["channel"].isin(selected_channels))
    & (df["region"].isin(selected_regions))
    & (df["member_grade"].isin(selected_grades))
)
base_df = df[base_mask]
filtered_df = base_df if include_returns else base_df[base_df["is_returned"] != "Y"]

total_sales = filtered_df["total_price"].sum()
total_quantity = filtered_df["quantity"].sum()
order_count = filtered_df["order_id"].nunique()
avg_order_value = total_sales / order_count if order_count else 0
return_rate = (base_df["is_returned"] == "Y").mean() * 100 if len(base_df) else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("총 매출", won(total_sales))
col2.metric("총 판매 수량", f"{total_quantity:,.0f} 개")
col3.metric("평균 주문 단가", won(avg_order_value))
col4.metric("반품률", f"{return_rate:.1f} %")

st.write("")
tab_overview, tab_product, tab_customer, tab_table = st.tabs(
    ["📊 개요", "👕 상품 분석", "🧑‍🤝‍🧑 고객/채널 분석", "📋 상세 데이터"]
)

with tab_overview:
    col_trend, col_category = st.columns([1.3, 1], gap="large")

    with col_trend:
        with st.container(border=True):
            st.subheader("📈 월별 매출 추이")
            monthly_sales = (
                filtered_df.assign(월=filtered_df["order_date"].dt.to_period("M").astype(str))
                .groupby("월")["total_price"]
                .sum()
                .reset_index()
            )
            fig = px.line(monthly_sales, x="월", y="total_price", markers=True)
            fig.update_traces(line_color="#6C5CE7", line_width=3)
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                yaxis_title="매출 (원)",
                xaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_category:
        with st.container(border=True):
            st.subheader("🗂 카테고리별 매출")
            category_sales = (
                filtered_df.groupby("category")["total_price"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            fig = px.bar(category_sales, x="category", y="total_price", text_auto=",.0f", color="category")
            fig.update_traces(textposition="outside")
            fig.update_layout(
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                yaxis_title="매출 (원)",
                xaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)

with tab_product:
    col_top, col_region = st.columns([1.2, 1], gap="large")

    with col_top:
        with st.container(border=True):
            st.subheader("🏆 매출 TOP 10 상품")
            top_products = (
                filtered_df.groupby("product_name")["total_price"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            fig = px.bar(
                top_products.sort_values("total_price"),
                x="total_price",
                y="product_name",
                orientation="h",
                text_auto=",.0f",
            )
            fig.update_traces(marker_color="#00B894", textposition="outside")
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                xaxis_title="매출 (원)",
                yaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_region:
        with st.container(border=True):
            st.subheader("🌍 지역별 매출")
            region_sales = (
                filtered_df.groupby("region")["total_price"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            fig = px.bar(region_sales, x="region", y="total_price", text_auto=",.0f", color="region")
            fig.update_traces(textposition="outside")
            fig.update_layout(
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                yaxis_title="매출 (원)",
                xaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)

with tab_customer:
    col_channel, col_grade = st.columns(2, gap="large")

    with col_channel:
        with st.container(border=True):
            st.subheader("🛍 채널별 매출 비중")
            channel_sales = filtered_df.groupby("channel")["total_price"].sum().reset_index()
            fig = px.pie(channel_sales, names="channel", values="total_price", hole=0.45)
            fig.update_traces(textinfo="percent+label")
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    with col_grade:
        with st.container(border=True):
            st.subheader("💎 회원 등급별 매출")
            grade_sales = (
                filtered_df.groupby("member_grade")["total_price"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            fig = px.bar(grade_sales, x="member_grade", y="total_price", text_auto=",.0f", color="member_grade")
            fig.update_traces(textposition="outside")
            fig.update_layout(
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                yaxis_title="매출 (원)",
                xaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)

with tab_table:
    st.subheader("📋 병합된 상세 데이터")
    display_columns = [
        "order_id",
        "order_date",
        "product_id",
        "product_name",
        "category",
        "channel",
        "region",
        "quantity",
        "unit_price",
        "total_price",
        "is_returned",
        "member_grade",
    ]
    st.dataframe(
        filtered_df[display_columns].sort_values("order_date", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "⬇️ 병합 데이터 CSV 다운로드",
        data=filtered_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="polyteru_merged_sales.csv",
        mime="text/csv",
    )
