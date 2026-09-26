import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="NSE/BSE Live EMA Scanner & Telegram Alert", layout="wide")

st.title("📊 NSE & BSE Indices - Live EMA Scanner & Telegram Alert")

# ----------------- १. टेलिग्राम कॉन्फिगरेशन -----------------
st.sidebar.header("🔔 Telegram अलर्ट सेटिंग्ज")
enable_telegram = st.sidebar.checkbox("Telegram अलर्ट सुरू करा", value=False)
bot_token = st.sidebar.text_input("Bot Token:", type="password", placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
chat_id = st.sidebar.text_input("Chat ID:", placeholder="123456789 किंवा -100123456789")

def send_telegram_alert(message: str):
    """टेलिग्रामवर मेसेज पाठवणारे फंक्शन"""
    if not (bot_token and chat_id):
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Error: {e}")

# आधी पाठवलेले अलर्ट लक्षात ठेवण्यासाठी session_state
if "sent_alerts" not in st.session_state:
    st.session_state.sent_alerts = set()

# ----------------- २. ऑटो-रिफ्रेश (Auto-refresh) -----------------
st.sidebar.markdown("---")
st.sidebar.header("⚙️ टाइमफ्रेम आणि लाईव्ह सेटिंग्ज")
refresh_interval = st.sidebar.slider("ऑटो-रिफ्रेश सेकंद (Auto-Refresh Sec):", min_value=15, max_value=120, value=30, step=5)
# हे फंक्शन दर X सेकंदांनी ॲपला बॅकग्राउंडमध्ये रिफ्रेश करेल
st_autorefresh(interval=refresh_interval * 1000, key="data_refresher")

timeframe_map = {
    "1 Minute": "1m",
    "5 Minutes": "5m",
    "1 Hour": "60m"
}
selected_tf_label = st.sidebar.selectbox("टाइमफ्रेम निवडा:", list(timeframe_map.keys()), index=1)
selected_interval = timeframe_map[selected_tf_label]

watch_list = {
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "NIFTY MIDCAP 50": "^NSEMDCP50",
    "NIFTY NEXT 50": "^NSENVX"
}

# ----------------- ३. डेटा फेचिंग आणि EMA कॅल्क्युलेशन -----------------
def fetch_and_calculate(ticker: str, interval: str):
    period = "7d" if interval == "1m" else ("1mo" if interval == "5m" else "6mo")
    
    # लाईव्ह डेटासाठी कॅशिंग न वापरता थेट कॉल (yfinance 1-2 मिनिट डिले असतो)
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    
    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(ticker, axis=1, level=1)
        except Exception:
            df.columns = df.columns.get_level_values(0)

    if len(df) < 200:
        return None

    if df.index.tz is not None:
        df.index = df.index.tz_convert("Asia/Kolkata")
    else:
        df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")

    df["EMA_9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA_21"] = df["Close"].ewm(span=21, adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()

    return df

def scan_full_day_touches(name: str, ticker: str, interval: str):
    df = fetch_and_calculate(ticker, interval)
    if df is None or df.empty:
        return [], None

    latest_trading_date = df.index[-1].date()
    full_day_df = df[df.index.date == latest_trading_date].copy()

    detected_records = []

    for idx, row in full_day_df.iterrows():
        low_p = float(row["Low"])
        high_p = float(row["High"])
        close_p = float(row["Close"])
        candle_time = idx.strftime("%H:%M")
        
        emas = {
            "EMA 9": row["EMA_9"],
            "EMA 21": row["EMA_21"],
            "EMA 50": row["EMA_50"],
            "EMA 200": row["EMA_200"]
        }
        
        touched = []
        for ema_name, val in emas.items():
            if pd.notna(val):
                val_float = float(val)
                if low_p <= val_float <= high_p:
                    touched.append(f"{ema_name} ({round(val_float, 2)})")
        
        if touched:
            touch_str = ", ".join(touched)
            record = {
                "तारीख": idx.strftime("%d-%m-%Y"),
                "वेळ (IST)": candle_time,
                "इंडेक्स": name,
                "किंमत (LTP)": round(close_p, 2),
                "कॅण्डल Low": round(low_p, 2),
                "कॅण्डल High": round(high_p, 2),
                "स्पर्श झालेला EMA": touch_str
            }
            detected_records.append(record)

            # टेलिग्राम अलर्ट पाठवणे (फक्त नवीन कॅण्डलसाठी, डुप्लिकेट टाळण्यासाठी ID वापरला आहे)
            alert_id = f"{name}_{idx.strftime('%Y%m%d_%H%M')}_{touch_str}"
            if enable_telegram and alert_id not in st.session_state.sent_alerts:
                # फक्त शेवटच्या २ कॅण्डल्ससाठीच लाईव्ह मेसेज पाठवा (मागील जुन्या डेटाचे स्पॅम होऊ नये म्हणून)
                if idx >= full_day_df.index[-2]:
                    msg = (
                        f"🚨 *EMA Touch Alert!* 🚨\n\n"
                        f"📊 *इंडेक्स:* `{name}`\n"
                        f"⏰ *वेळ:* `{candle_time} IST`\n"
                        f"🎯 *स्पर्श:* `{touch_str}`\n"
                        f"💰 *LTP:* `{round(close_p, 2)}`\n"
                        f"🕯️ *High/Low:* `{round(high_p, 2)} / {round(low_p, 2)}`\n"
                        f"⏱️ *Timeframe:* `{selected_tf_label}`"
                    )
                    send_telegram_alert(msg)
                st.session_state.sent_alerts.add(alert_id)
            
    return detected_records, full_day_df

# ----------------- ४. स्कॅनर डिस्प्ले -----------------
st.subheader(f"⚡ लाईव्ह स्कॅनर निकाल ({selected_tf_label}) - ऑटो रिफ्रेश सुरू आहे")

all_results = []
for name, symbol in watch_list.items():
    touches, _ = scan_full_day_touches(name, symbol, selected_interval)
    all_results.extend(touches)

if all_results:
    res_df = pd.DataFrame(all_results)
    cols = ["तारीख", "वेळ (IST)", "इंडेक्स", "किंमत (LTP)", "कॅण्डल Low", "कॅण्डल High", "स्पर्श झालेला EMA"]
    res_df = res_df[cols]
    res_df = res_df.sort_values(by="वेळ (IST)", ascending=False) # नवीन कॅण्डल वर दिसेल
    st.dataframe(res_df, use_container_width=True)
else:
    st.info("सध्या कोणत्याही कॅण्डलने EMA ला स्पर्श केलेला नाही.")

# ----------------- ५. चार्ट विभाग -----------------
st.markdown("---")
st.subheader("लाईव्ह चार्ट")
chart_symbol_name = st.selectbox("इंडेक्स निवडा:", list(watch_list.keys()))

if chart_symbol_name:
    _, day_df = scan_full_day_touches(chart_symbol_name, watch_list[chart_symbol_name], selected_interval)
    if day_df is not None and not day_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=day_df.index,
            open=day_df['Open'], high=day_df['High'],
            low=day_df['Low'], close=day_df['Close'],
            name="कॅण्डलस्टिक"
        ))
        
        fig.add_trace(go.Scatter(x=day_df.index, y=day_df['EMA_9'], line=dict(color='blue', width=1.5), name='EMA 9'))
        fig.add_trace(go.Scatter(x=day_df.index, y=day_df['EMA_21'], line=dict(color='green', width=1.5), name='EMA 21'))
        fig.add_trace(go.Scatter(x=day_df.index, y=day_df['EMA_50'], line=dict(color='orange', width=1.5), name='EMA 50'))
        fig.add_trace(go.Scatter(x=day_df.index, y=day_df['EMA_200'], line=dict(color='red', width=2), name='EMA 200'))

        fig.update_layout(
            height=550, 
            xaxis_rangeslider_visible=False, 
            title=f"{chart_symbol_name} - {day_df.index[-1].strftime('%d-%m-%Y')} (Live View)"
        )
        st.plotly_chart(fig, use_container_width=True)
