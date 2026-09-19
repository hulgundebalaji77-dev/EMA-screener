import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="NSE/BSE Indices EMA Screener", layout="wide")

st.title("📊 NSE & BSE Indices - EMA Touch Scanner")
st.write("इंडायसेसचे 9, 21, 50, आणि 200 EMA टच स्कॅनर (मागील कॅण्डल्सच्या नोंदींसह).")

# १. साइडबार सेटिंग्ज
st.sidebar.header("सेटिंग्ज")
timeframe_map = {
    "1 Minute": "1m",
    "5 Minutes": "5m",
    "1 Hour": "60m"
}
selected_tf_label = st.sidebar.selectbox("टाइमफ्रेम निवडा:", list(timeframe_map.keys()), index=1)
selected_interval = timeframe_map[selected_tf_label]

# मागील किती कॅण्डल्स तपासायच्या यासाठी स्लाइडर
lookback_bars = st.sidebar.slider("मागील किती कॅण्डल्स तपासायच्या:", min_value=1, max_value=20, value=5)

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

# २. डेटा फेचिंग आणि EMA टच तपासणे
def check_ema_touch(ticker, interval, lookback):
    period = "5d" if interval == "1m" else "1mo"
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    
    if df.empty or len(df) < 200:
        return [], None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # टाइमझोन भारतीय प्रमाणवेळेत (IST) करणे
    if df.index.tz is not None:
        df.index = df.index.tz_convert("Asia/Kolkata")
    else:
        df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")

    # EMA कॅल्क्युलेशन
    df["EMA_9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA_21"] = df["Close"].ewm(span=21, adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()

    detected_records = []
    
    # शेवटच्या N कॅण्डल्स तपासणे
    target_slice = df.tail(lookback)
    
    for idx, row in target_slice.iterrows():
        low_p = float(row["Low"])
        high_p = float(row["High"])
        close_p = float(row["Close"])
        
        emas = {
            "EMA 9": row["EMA_9"],
            "EMA 21": row["EMA_21"],
            "EMA 50": row["EMA_50"],
            "EMA 200": row["EMA_200"]
        }
        
        touched = []
        for name, val in emas.items():
            if pd.notna(val):
                val_float = float(val)
                # अचूक टच: कॅण्डलचा Low <= EMA <= High
                if low_p <= val_float <= high_p:
                    touched.append(f"{name} ({round(val_float, 2)})")
        
        if touched:
            detected_records.append({
                "तारीख": idx.strftime("%d-%m-%Y"),
                "वेळ (IST)": idx.strftime("%H:%M:%S"),
                "चालू किंमत": round(close_p, 2),
                "कॅण्डल Low": round(low_p, 2),
                "कॅण्डल High": round(high_p, 2),
                "टच झालेला EMA": ", ".join(touched)
            })
            
    return detected_records, df

# ३. स्कॅन करणे
if st.sidebar.button("इंडायसेस स्कॅन करा (Scan Indices)"):
    st.subheader(f"स्कॅन निकाल ({selected_tf_label}) - शेवटच्या {lookback_bars} कॅण्डल्समधील स्पर्श")
    all_results = []

    progress_bar = st.progress(0)
    total_items = len(watch_list)

    for i, (name, symbol) in enumerate(watch_list.items()):
        touches, df = check_ema_touch(symbol, selected_interval, lookback_bars)
        for t in touches:
            t["इंडेक्स"] = name
            all_results.append(t)
        progress_bar.progress((i + 1) / total_items)

    if all_results:
        res_df = pd.DataFrame(all_results)
        # कॉलम्सचा क्रम
        cols = ["तारीख", "वेळ (IST)", "इंडेक्स", "चालू किंमत", "कॅण्डल Low", "कॅण्डल High", "टच झालेला EMA"]
        res_df = res_df[cols]
        st.dataframe(res_df, use_container_width=True)
    else:
        st.warning("निवडलेल्या मागील कॅण्डल्समध्ये कोणत्याही इंडेक्सने EMA ला स्पर्श केलेला नाही.")

# ४. चार्ट विभाग
st.markdown("---")
st.subheader("इंडेक्स कॅण्डलस्टिक आणि EMA चार्ट")
chart_symbol_name = st.selectbox("चार्ट पाहण्यासाठी इंडेक्स निवडा:", list(watch_list.keys()))

if chart_symbol_name:
    _, chart_df = check_ema_touch(watch_list[chart_symbol_name], selected_interval, lookback_bars)
    if chart_df is not None and not chart_df.empty:
        plot_df = chart_df.tail(100)
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=plot_df.index,
            open=plot_df['Open'], high=plot_df['High'],
            low=plot_df['Low'], close=plot_df['Close'],
            name="इंडेक्स दर"
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
