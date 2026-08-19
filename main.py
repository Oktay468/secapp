import os
import random
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from modules.data_fetcher import (
    fetch_sec_financials,
    fetch_stock_data,
    get_all_market_tickers,
)
from modules.whale_detector import detect_whale_activity

load_dotenv()

st.set_page_config(
    page_title="Balina Avcisi & SEC EDGAR Finansal Radar",
    page_icon="🐋",
    layout="wide",
)

# --- OTURUM HAFIZASI (SESSION STATE) ---
if "scan_results" not in st.session_state:
    st.session_state["scan_results"] = None
if "last_selected_tickers" not in st.session_state:
    st.session_state["last_selected_tickers"] = []

st.title("🐋 Balina Avcisi & SEC EDGAR Finansal Radar")
st.caption("Teknik Akumulasyon Analizi ve SEC EDGAR Bilanco Sorgulama Platformu")

# Ana Sekme Yapisi
tab_radar, tab_sec = st.tabs(["🐋 Balina Avcisi Radar", "📊 SEC EDGAR Finansal Sorgulama"])

# ==========================================
# SEKMELER 1: BALINA RADAR
# ==========================================
with tab_radar:
    st.sidebar.header("⚙️ Radar Ayarlari")

    alpaca_key = os.getenv("ALPACA_API_KEY")
    if alpaca_key:
        st.sidebar.success("🟢 Alpaca API Bagli (Canli Veri)")
    else:
        st.sidebar.warning("🟡 Alpaca Key Bulunamadi (Gecikmeli Veri)")

    market_type = st.sidebar.radio(
        "Islem Yapilacak Piyasa:",
        options=["BIST", "ABD Borsasi (US)"],
        index=1,
    )
    market_code = "BIST" if market_type == "BIST" else "US"
    currency = "TL" if market_code == "BIST" else "$"

    if market_code == "US":
        st.sidebar.info("🎯 **ABD Filtresi Aktif:** Sadece **7$ ve altindaki** hisseler taranir.")

    with st.sidebar.status("Hisse Listesi Yukleniyor...", expanded=False):
        all_tickers = get_all_market_tickers(market_type=market_code)

    st.sidebar.info(f"Yuklenen Hisse Adedi: **{len(all_tickers)}**")

    scan_limit = st.sidebar.slider(
        "Taranacak Hisse Adedi:",
        min_value=10,
        max_value=min(len(all_tickers), 1000) if all_tickers else 100,
        value=50,
        step=10,
    )

    vol_multiplier = st.sidebar.slider(
        "Hacim Patlamasi Hassasiyeti (Kat):",
        min_value=1.5,
        max_value=10.0,
        value=2.5,
        step=0.5,
    )

    if st.button("🔍 Canli Taramayi Baslat", type="primary"):
        selected_tickers = random.sample(all_tickers, min(len(all_tickers), scan_limit))

        progress_bar = st.progress(0)
        results = []

        for idx, symbol in enumerate(selected_tickers):
            df = fetch_stock_data(symbol, market_type=market_code)
            if not df.empty:
                res = detect_whale_activity(df, volume_multiplier=vol_multiplier)
                close_price = res.get("close_price", 0)

                if market_code == "US" and close_price > 7.0:
                    progress_bar.progress((idx + 1) / len(selected_tickers))
                    continue

                res["ticker"] = symbol.upper()
                results.append(res)

            progress_bar.progress((idx + 1) / len(selected_tickers))

        progress_bar.empty()

        # Sonuçları ve seçilen sembolleri hafızaya kaydet
        st.session_state["scan_results"] = results
        st.session_state["last_selected_tickers"] = selected_tickers

    # --- SEKMELER ARASI GEÇİŞTE KORUNAN SONUÇ EKRANI ---
    if st.session_state["scan_results"] is not None:
        results = st.session_state["scan_results"]
        selected_tickers = st.session_state.get("last_selected_tickers", [])

        st.divider()
        st.subheader(f"📊 {market_type} Taramasi ({len(selected_tickers)} Rastgele Hisse Analiz Ediliyor)")

        with st.expander("👁️ Taranan Hisse Sembollerini Gor"):
            st.write(", ".join(selected_tickers))

        if results:
            data_table = []
            for r in results:
                if r.get("close_price", 0) > 0:
                    status = "🚨 BALINA VAR!" if r["detected"] else "⚪ Normal"
                    data_table.append(
                        {
                            "Hisse": r["ticker"],
                            "Durum": status,
                            "Guven Skoru": f"{r['score']} / 100",
                            f"Son Fiyat ({currency})": f"{r['close_price']} {currency}",
                            "Hacim Kati": f"{r['vol_ratio']}x",
                            "RSI": r["rsi"],
                            "Mum Degisimi": f"%{r['price_change_pct']}",
                            "Onay Detaylari": r["reasons"],
                        }
                    )

            res_df = pd.DataFrame(data_table)
            if not res_df.empty:
                res_df = res_df.sort_values(by="Guven Skoru", ascending=False)
                st.dataframe(res_df, use_container_width=True)

                whales_found = [r for r in results if r.get("detected")]
                if whales_found:
                    st.success(f"🔥 Toplam {len(whales_found)} hissede balina girisi / akumulasyon tespit edildi!")
                    cols = st.columns(min(len(whales_found), 3))
                    for i, w in enumerate(whales_found[:6]):
                        with cols[i % 3]:
                            st.metric(
                                label=f"🚨 {w['ticker']} (Skor: {w['score']})",
                                value=f"{w['close_price']} {currency}",
                                delta=f"Hacim: {w['vol_ratio']}x",
                            )
                else:
                    st.info("ℹ️ Taranan 7$ alti hisseler arasinda balina tespiti yapilan bulunamadi.")
        else:
            st.warning("⚠️ Secilen rastgele hisseler icinde 7$ altinda kalan veya verisi cekilebilen hisse bulunamadi. Lutfen tekrar 'Canli Taramayi Baslat' butonuna basarak yeni bir paket taratin.")

# ==========================================
# SEKMELER 2: SEC EDGAR FINANSAL SORGU
# ==========================================
with tab_sec:
    st.subheader("🏛️ SEC EDGAR Finansal Tablo Sorgulama")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        sec_ticker = st.text_input("Ticker Girin (Orn: AAPL, MSFT, RTX, TSLA):", value="EBRCZ").strip().upper()
    with col2:
        st.write("")
        st.write("")
        search_btn = st.button("Finansallari Getir", type="primary")

    if search_btn and sec_ticker:
        with st.spinner(f"{sec_ticker} icin SEC EDGAR verileri cekiliyor..."):
            res = fetch_sec_financials(sec_ticker)

        if "error" in res:
            st.error(res["error"])
        else:
            st.success(f"**{res['company']} ({res['ticker']})** verileri yuklendi.")

            def fmt_curr(val):
                if val == 'N/A' or val is None or pd.isna(val):
                    return 'N/A'
                try:
                    return f"${float(val):,.0f}"
                except:
                    return str(val)

            def fmt_eps(val):
                if val == 'N/A' or val is None or pd.isna(val):
                    return 'N/A'
                try:
                    return f"${float(val):.2f}"
                except:
                    return str(val)

            def fmt_num(val):
                if val == 'N/A' or val is None or pd.isna(val):
                    return 'N/A'
                try:
                    return f"{float(val):,.0f}"
                except:
                    return str(val)

            df_yearly = pd.DataFrame(res.get("data", []))
            df_quarterly = pd.DataFrame(res.get("quarterly_data", []))

            # 1. Bilanco Tablosu
            st.markdown("#### 1. Bilanco (Balance Sheet)")
            if not df_yearly.empty and 'Varliklar' in df_yearly.columns:
                df_bs = df_yearly[['Yil', 'Varliklar', 'Yukumlulukler', 'Ozkaynaklar']].copy()
                for col in ['Varliklar', 'Yukumlulukler', 'Ozkaynaklar']:
                    df_bs[col] = df_bs[col].apply(fmt_curr)
                st.table(df_bs)
            else:
                st.info("Bu sirket icin yillik bilanco verisi bulunamadi.")

            # 2. Yillik Gelir Tablosu
            st.markdown("#### 2. Yillik Gelir Tablosu (Income Statement - 10-K)")
            if not df_yearly.empty and 'Hasilat' in df_yearly.columns:
                df_is = df_yearly[['Yil', 'Hasilat', 'Brut Kar', 'Net Kar', 'EPS']].copy()
                for col in ['Hasilat', 'Brut Kar', 'Net Kar']:
                    df_is[col] = df_is[col].apply(fmt_curr)
                df_is['EPS'] = df_is['EPS'].apply(fmt_eps)
                st.table(df_is)
            else:
                st.info("Bu sirket icin yillik gelir tablosu verisi bulunamadi.")

            # 3. Ceyreklik Performans
            st.markdown("#### 3. Ceyreklik Performans (Son 10-Q Raporlari)")
            if not df_quarterly.empty and 'Hasilat' in df_quarterly.columns:
                df_qs = df_quarterly.copy()
                for col in ['Hasilat', 'Brut Kar', 'Net Kar']:
                    if col in df_qs.columns:
                        df_qs[col] = df_qs[col].apply(fmt_curr)
                if 'EPS' in df_qs.columns:
                    df_qs['EPS'] = df_qs['EPS'].apply(fmt_eps)
                st.table(df_qs)
            else:
                st.info("Bu sirket icin ceyreklik veri bulunamadi.")

            # 4. Nakit Akisi
            st.markdown("#### 4. Nakit Akisi ve Hisse Yapisi (FCF & Buybacks)")
            if not df_yearly.empty and 'FCF (Nakit Akisi)' in df_yearly.columns:
                df_cf = df_yearly[['Yil', 'FCF (Nakit Akisi)', 'Hisse Geri Alimi', 'Tedavuldeki Hisse']].copy()
                df_cf['FCF (Nakit Akisi)'] = df_cf['FCF (Nakit Akisi)'].apply(fmt_curr)
                df_cf['Hisse Geri Alimi'] = df_cf['Hisse Geri Alimi'].apply(fmt_curr)
                df_cf['Tedavuldeki Hisse'] = df_cf['Tedavuldeki Hisse'].apply(fmt_num)
                st.table(df_cf)
            else:
                st.info("Bu sirket icin nakit akisi verisi bulunamadi.")
