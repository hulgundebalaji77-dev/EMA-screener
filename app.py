import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="NSE/BSE Indices EMA Screener", layout="wide")

st.title("📊 NSE & BSE Indices - EMA Touch Scanner")
st.write("इंडायसेसचे 9, 21, 50, आणि 200 EMA टच स्कॅनर (सिग्नल तारीख आणि वेळेसह).")

# १. साइडबार - टाइमफ्रेम निवडा
st.sidebar.header("सेटिंग्ज")
timeframe_map = {
    "1 Minute": "1m",
    "5 Minutes": "5m",
    "1 Hour": "60m"
}
selected_tf_label = st.sidebar.selectbox("टाइमफ्रेम निवडा:", list(timeframe_map.keys()), index=1)
selected_interval = timeframe_map[selected_tf_label]

# २. इंडेक्सची यादी
watch_list = {
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "NIFTY MIDCAP 50": "^NSEMDCP50",
    "NIFTY NEXT 50": "^NSENVX",
    "NIFTY IT": "^CNXIT",
    "NIFTY AUTO": "^CNXAUTO"
}

# ३. डेटा फेचिंग आणि EMA कॅल्क्युलेशन
def check_ema_touch(ticker, interval):
    period = "5d" if interval == "1m" else "1mo"
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    
    if df.empty or len(df) < 200:
        return None, None
    
    # मल्टि-इंडेक्स कॉलम्स सपाट करणे
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # टाइमझोन भारतीय प्रमाणवेळेत (IST) रूपांतरित करणे
    if df.index.tz is not None:
        df.index = df.index.tz_convert("Asia/Kolkata")
    else:
        df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")

    # EMA कॅल्क्युलेशन
    df["EMA_9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA_21"] = df["Close"].ewm(span=21, adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()
    
    latest = df.iloc[-1]
    low_price = float(latest["Low"])
    high_price = float(latest["High"])
    
    touched_emas = []
    for ema_val, name in [(latest["EMA_9"], "EMA 9"), 
                          (latest["EMA_21"], "EMA 21"), 
                          (latest["EMA_50"], "EMA 50"), 
                          (latest["EMA_200"], "EMA 200")]:
        if pd.notna(ema_val):
            if low_price <= float(ema_val) <= high_price:
                touched_emas.append(name)
                
    return touched_emas, df

# ४. स्कॅनर रन करणे
if st.sidebar.button("इंडायसेस स्कॅन करा (Scan Indices)"):
    st.subheader(f"स्कॅन निकाल ({selected_tf_label})")
    results = []

    progress_bar = st.progress(0)
    total_items = len(watch_list)

    for i, (name, symbol) in enumerate(watch_list.items()):
        touched, df = check_ema_touch(symbol, selected_interval)
        if touched:
            latest_bar = df.iloc[-1]
            signal_timestamp = df.index[-1]
            
            results.append({
                "तारीख (Date)": signal_timestamp.strftime("%d-%m-%Y"),
                "वेळ (Time IST)": signal_timestamp.strftime("%H:%M:%S"),
                "इंडेक्स (Index)": name,
                "किंमत (LTP)": round(float(latest_bar["Close"]), 2),
                "कॅण्डल Low": round(float(latest_bar["Low"]), 2),
                "कॅण्डल High": round(float(latest_bar["High"]), 2),
                "टच झालेला EMA": ", ".join(touched)
            })
        progress_bar.progress((i + 1) / total_items)

    if results:
        res_df = pd.DataFrame(results)
        st.dataframe(res_df, use_container_width=True)
    else:
        st.info("सध्या कोणत्याही इंडेक्सच्या चालू कॅण्डलने निवडलेल्या EMA ला स्पर्श केलेला नाही.")

# ५. इंडेक्स चार्ट विभाग
st.markdown("---")
st.subheader("इंडेक्स कॅण्डलस्टिक आणि EMA चार्ट")
chart_symbol_name = st.selectbox("चार्ट पाहण्यासाठी इंडेक्स निवडा:", list(watch_list.keys()))

if chart_symbol_name:
    _, chart_df = check_ema_touch(watch_list[chart_symbol_name], selected_interval)
    if chart_df is not None and not chart_df.empty:
        plot_df = chart_df.tail(100)
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=plot_df.index,
            open=plot_df['Open'], high=plot_df['High'],
            low=plot_df['Low'], close=plot_df['Close'],
            name="इंडेक्स किंमत"
        ))
        
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_9'], line=dict(color='blue', width=1.5), name='EMA 9'))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_21'], line=dict(color='green', width=1.5), name='EMA 21'))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_50'], line=dict(color='orange', width=1.5), name='EMA 50'))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_200'], line=dict(color='red', width=2), name='EMA 200'))

        fig.update_layout(
            height=600, 
            xaxis_rangeslider_visible=False, 
            title=f"{chart_symbol_name} ({selected_tf_label})"
        )
        st.plotly_chart(fig, use_container_width=True)
