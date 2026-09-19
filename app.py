import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="NSE/BSE Full Day EMA Scanner", layout="wide")

st.title("📊 NSE & BSE Indices - Full Day EMA Touch Scanner")
st.write("आजच्या संपूर्ण ट्रेडिंग दिवसात (Full Day) ज्या कॅण्डल्सने EMA 9, 21, 50 किंवा 200 ला स्पर्श केला आहे त्यांची संपूर्ण यादी.")

# १. साइडबार सेटिंग्ज
st.sidebar.header("सेटिंग्ज")
timeframe_map = {
    "1 Minute": "1m",
    "5 Minutes": "5m",
    "1 Hour": "60m"
}
selected_tf_label = st.sidebar.selectbox("टाइमफ्रेम निवडा:", list(timeframe_map.keys()), index=1)
selected_interval = timeframe_map[selected_tf_label]

# २. निवडक इंडायसेस (NIFTY IT आणि AUTO काढून टाकले आहेत)
watch_list = {
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "NIFTY MIDCAP 50": "^NSEMDCP50",
    "NIFTY NEXT 50": "^NSENVX"
}

# ३. संपूर्ण दिवसाचा डेटा आणि EMA टच तपासणे
def scan_full_day_touches(ticker, interval):
    period = "5d" if interval == "1m" else "1mo"
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    
    if df.empty or len(df) < 200:
        return [], None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # टाइमझोन IST मध्ये रूपांतरित करणे
    if df.index.tz is not None:
        df.index = df.index.tz_convert("Asia/Kolkata")
    else:
        df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")

    # EMA कॅल्क्युलेशन
    df["EMA_9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA_21"] = df["Close"].ewm(span=21, adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()

    # शेवटच्या ट्रेडिंग दिवसाचा डेटा निवडणे
    latest_trading_date = df.index[-1].date()
    full_day_df = df[df.index.date == latest_trading_date]

    detected_records = []

    for idx, row in full_day_df.iterrows():
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
                # कॅण्डलचा प्रत्यक्ष स्पर्श
                if low_p <= val_float <= high_p:
                    touched.append(f"{name} ({round(val_float, 2)})")
        
        if touched:
            detected_records.append({
                "तारीख": idx.strftime("%d-%m-%Y"),
                "वेळ (IST)": idx.strftime("%H:%M"),
                "किंमत (LTP)": round(close_p, 2),
                "कॅण्डल Low": round(low_p, 2),
                "कॅण्डल High": round(high_p, 2),
                "स्पर्श झालेला EMA": ", ".join(touched)
            })
            
    return detected_records, full_day_df

# ४. स्कॅनर चालवणे
if st.sidebar.button("पूर्ण दिवसाचे निकाल स्कॅन करा (Scan Full Day)"):
    st.subheader(f"दिवसभरातील सर्व स्पर्श निकाल ({selected_tf_label})")
    all_results = []

    progress_bar = st.progress(0)
    total_items = len(watch_list)

    for i, (name, symbol) in enumerate(watch_list.items()):
        touches, _ = scan_full_day_touches(symbol, selected_interval)
        for t in touches:
            t["इंडेक्स"] = name
            all_results.append(t)
        progress_bar.progress((i + 1) / total_items)

    if all_results:
        res_df = pd.DataFrame(all_results)
        cols = ["तारीख", "वेळ (IST)", "इंडेक्स", "किंमत (LTP)", "कॅण्डल Low", "कॅण्डल High", "स्पर्श झालेला EMA"]
        res_df = res_df[cols]
        res_df = res_df.sort_values(by="वेळ (IST)", ascending=True)
        st.dataframe(res_df, use_container_width=True)
    else:
        st.warning("दिवसभरात कोणत्याही कॅण्डलने EMA ला स्पर्श केलेला नाही.")

# ५. चार्ट विभाग
st.markdown("---")
st.subheader("आजच्या संपूर्ण दिवसाचा चार्ट")
chart_symbol_name = st.selectbox("इंडेक्स निवडा:", list(watch_list.keys()))

if chart_symbol_name:
    _, day_df = scan_full_day_touches(watch_list[chart_symbol_name], selected_interval)
    if day_df is not None and not day_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=day_df.index,
            open=day_df['Open'], high=day_df['High'],
            low=day_df['Low'], close=day_df['Close'],
            name="इंडेक्स दर"
        ))
        
        fig.add_trace(go.Scatter(x=day_df.index, y=day_df['EMA_9'], line=dict(color='blue', width=1.5), name='EMA 9'))
        fig.add_trace(go.Scatter(x=day_df.index, y=day_df['EMA_21'], line=dict(color='green', width=1.5), name='EMA 21'))
        fig.add_trace(go.Scatter(x=day_df.index, y=day_df['EMA_50'], line=dict(color='orange', width=1.5), name='EMA 50'))
        fig.add_trace(go.Scatter(x=day_df.index, y=day_df['EMA_200'], line=dict(color='red', width=2), name='EMA 200'))

        fig.update_layout(
            height=600, 
            xaxis_rangeslider_visible=False, 
            title=f"{chart_symbol_name} - {day_df.index[-1].strftime('%d-%m-%Y')} (सर्व कॅण्डल्स)"
        )
        st.plotly_chart(fig, use_container_width=True)
