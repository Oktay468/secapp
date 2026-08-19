import streamlit as st
import random
import time
import pandas as pd
from modules.data_fetcher import get_all_market_tickers, fetch_stock_data, fetch_sec_financials
from modules.analysis import detect_whale_activity

st.set_page_config(page_title="Balina Avcisi & SEC EDGAR", layout="wide", page_icon="🐋")

# --- OTURUM HAFIZASI (SESSION STATE) TANIMLARI ---
if "scan_results" not in st.session_state:
    st.session_state["scan_results"] = None
if "last_scan_info" not in st.session_state:
    st.session_state["last_scan_info"] = ""

st.title("🐋 Balina Avcisi Radar & SEC EDGAR Sorgulama")

tab1, tab2 = st.tabs(["🐋 Balina Avcisi Radar", "📊 SEC EDGAR Finansal Sorgulama"])

# ==========================================
# TAB 1: BALİNA AVCISI RADAR
# ==========================================
with tab1:
    st.sidebar.header("⚙️ Tarama Parametreleri")
    
    market_type = st.sidebar.selectbox("Piyasa Secin", ["ABD Borsasi (US)", "Borsa Istanbul (BIST)"])
    market_code = "US" if "US" in market_type else "BIST"

    scan_limit = st.sidebar.slider("Taranacak Hisse Adedi (Rastgele)", min_value=10, max_value=300, value=50, step=10)
    vol_multiplier = st.sidebar.slider("Hacim Patlamasi Katsayisi (x)", min_value=1.5, max_value=10.0, value=3.0, step=0.5)

    all_tickers = get_all_market_tickers(market_type=market_code)

    st.subheader(f"📊 {market_type} Taramasi")

    if st.button("🔍 Canli Taramayi Baslat", type="primary"):
        selected_tickers = random.sample(all_tickers, min(len(all_tickers), scan_limit))

        st.info(f"{len(selected_tickers)} adet rastgele hisse analiz ediliyor, lutfen bekleyin...")
        progress_bar = st.progress(0)
        results = []

        for idx, symbol in enumerate(selected_tickers):
            df = fetch_stock_data(symbol, market_type=market_code)
            if not df.empty:
                res = detect_whale_activity(df, volume_multiplier=vol_multiplier)
                close_price = res.get("close_price", 0)

                # Sadece geçerli fiyatlı VE (ABD ise) $7 altı hisseleri al
                if close_price > 0 and (market_code != "US" or close_price <= 7.0):
                    res["ticker"] = symbol.upper()
                    results.append(res)

            progress_bar.progress((idx + 1) / len(selected_tickers))

        progress_bar.empty()

        # Sonuçları ve tarama bilgisini oturum hafızasına kaydet
        st.session_state["scan_results"] = results
        st.session_state["last_scan_info"] = f"Son taramada {len(selected_tickers)} hisse incelendi ve kriterlere uyan {len(results)} hisse bulundu."

    # --- SEKMELER ARASI GEÇİŞTE DE KORUNAN SONUÇ EKRANI ---
    if st.session_state["scan_results"] is not None:
        results = st.session_state["scan_results"]
        if st.session_state["last_scan_info"]:
            st.caption(st.session_state["last_scan_info"])

        if results:
            df_res = pd.DataFrame(results)
            
            # Sütun düzenleme ve Türkçe isimler
            cols_order = ["ticker", "close_price", "volume_spike", "avg_volume", "last_volume", "signal"]
            existing_cols = [c for c in cols_order if c in df_res.columns]
            df_display = df_res[existing_cols].copy()

            df_display.rename(columns={
                "ticker": "Hisse",
                "close_price": "Son Fiyat ($)",
                "volume_spike": "Hacim Katlanmasi",
                "avg_volume": "Ort. Hacim (20G)",
                "last_volume": "Son Hacim",
                "signal": "Sinyal / Durum"
            }, inplace=True)

            st.success(f"🔥 Filtreye Uyan {len(results)} Hisse Yakalandi!")
            st.dataframe(df_display, use_container_width=True)
        else:
            st.warning("⚠️ Secilen hisseler icinde 7$ altinda kalan veya kriterlere uyan hisse bulunamadi. 'Canli Taramayi Baslat' butonuna basarak yeni bir paket taratabilirsiniz.")

# ==========================================
# TAB 2: SEC EDGAR FİNANSAL SORULAMA
# ==========================================
with tab2:
    st.subheader("🔍 ABD Şirketleri SEC EDGAR Bilanço Sorgulama")
    st.write("Tarama listesinden kopyaladığınız $7 altı hisse sembolünü buraya yazarak bilanço ve nakit akış verilerini inceleyebilirsiniz.")

    input_ticker = st.text_input("Hisse Sembolü Girin (Örn: EBRCZ, SNDL, PLUG):", value="EBRCZ").strip().upper()

    if st.button("📊 Bilanço Verilerini Getir"):
        if input_ticker:
            with st.spinner(f"{input_ticker} için SEC EDGAR verileri çekiliyor..."):
                sec_data = fetch_sec_financials(input_ticker)

            if "error" in sec_data:
                st.error(sec_data["error"])
            else:
                st.success(f"🏢 **{sec_data['company']}** ({sec_data['ticker']}) Finansal Verileri")

                # Yıllık Bilanço Tablosu
                if sec_data.get("data"):
                    st.markdown("### 📅 Yillik Bilanço ve Gelir Tablosu (Son 5 Yil)")
                    df_annual = pd.DataFrame(sec_data["data"])
                    st.dataframe(df_annual, use_container_width=True)

                # Çeyreklik Bilanço Tablosu
                if sec_data.get("quarterly_data"):
                    st.markdown("### ⏱️ Ceyreklik Performans (Son Ceyrekler)")
                    df_quarterly = pd.DataFrame(sec_data["quarterly_data"])
                    st.dataframe(df_quarterly, use_container_width=True)
        else:
            st.warning("Lütfen geçerli bir hisse kodu girin.")
