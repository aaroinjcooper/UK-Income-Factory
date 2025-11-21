import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from io import StringIO
import time

st.set_page_config(page_title="UK Income Factory", layout="wide")
st.title("🇬🇧 UK Income Factory – Live Dashboard")

# ==============================
# 1. Load portfolio
# ==============================
text_input = st.sidebar.text_area("Paste your CSV here (easy option)", height=250)
uploaded_file = st.sidebar.file_uploader("Or upload portfolio.csv", type=["csv"])

if text_input.strip():
    try:
        df = pd.read_csv(StringIO(text_input))
    except:
        st.error("CSV paste failed – check format")
        st.stop()
elif uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
    except:
        st.error("File upload failed – check it's a valid CSV")
        st.stop()
else:
    st.info("↑ Paste your CSV or upload the file to continue")
    st.stop()

# Clean
if "Total" in df["Slice"].values:
    df = df[df["Slice"] != "Total"]
df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
df["Owned quantity"] = pd.to_numeric(df["Owned quantity"], errors="coerce")
df["Ticker"] = df["Slice"] + ".L"      # for Yahoo
df["Symbol"] = df["Slice"]             # for other APIs

total_cost = df["Value"].sum()

# ==============================
# 2. Get live price (no yfinance!)
# ==============================
@st.cache_data(ttl=1800, show_spinner=False)
def get_price(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        data = requests.get(url, headers=headers, timeout=10).json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        return round(price, 4)
    except:
        return 0.0

# ==============================
# 3. Get yield & target
# ==============================
@st.cache_data(ttl=86400, show_spinner=False)
def get_yield_and_target(symbol):
    try:
        url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey=demo"
        data = requests.get(url, timeout=10).json()[0]
        return {
            "yield": round((data.get("dividendYield") or 0) * 100, 2),
            "target": data.get("targetPrice")
        }
    except:
        return {"yield": 0.0, "target": None}

# ==============================
# 4. Fetch all data
# ==============================
progress = st.progress(0)
prices = []
extra = []

for i, row in df.iterrows():
    p = get_price(row["Ticker"])
    info = get_yield_and_target(row["Symbol"])
    prices.append(p)
    extra.append(info)
    progress.progress((i + 1) / len(df))
    time.sleep(0.05)

df["Price"] = prices
df["Market_Value"] = df["Price"] * df["Owned quantity"]
df["Unrealised"] = df["Market_Value"] - df["Value"]
df["Weight"] = df["Market_Value"] / df["Market_Value"].sum()

extra_df = pd.DataFrame(extra)
df["Yield_%"] = extra_df["yield"]
df["Target"] = extra_df["target"]

total_now = df["Market_Value"].sum()
expected_income = (df["Market_Value"] * df["Yield_%"] / 100).sum()

# ==============================
# 5. Display
# ==============================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Portfolio Value", f"£{total_now:,.0f}", f"£{total_now-total_cost:+,.0f}")
c2.metric("Weighted Yield", f"{df['Market_Value'].dot(df['Yield_%'])/total_now/100:.2%}")
c3.metric("Expected Income (12m)", f"£{expected_income:,.0f}")
c4.metric("Holdings", len(df))

st.subheader("Live Holdings")
disp = df[["Name","Owned quantity","Price","Market_Value","Weight","Yield_%","Unrealised"]].copy()
disp.columns = ["Company","Shares","Price £","Value £","Weight","Yield","P/L £"]
disp = disp.round({"Price £":2, "Value £":0, "P/L £":0})
disp["Weight"] = (disp["Weight"]*100).round(2).astype(str) + "%"
disp["Yield"] = disp["Yield"].round(2).astype(str) + "%"
disp = disp.sort_values("Value £", ascending=False)

st.dataframe(disp, use_container_width=True, hide_index=True)

st.success(f"Refreshed: {datetime.now().strftime('%d %b %Y – %H:%M')}")
if st.button("Refresh now"):
    st.rerun()