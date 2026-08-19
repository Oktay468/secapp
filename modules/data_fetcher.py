import os
import requests
import pandas as pd
import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

def get_all_market_tickers(market_type="US"):
    if market_type == "BIST":
        try:
            bist_tickers = ["THYAO.IS", "GARAN.IS", "ASELS.IS", "EREGL.IS", "AKBNK.IS", "KCHOL.IS", "SASAN.IS", "SISE.IS", "TUPRS.IS", "BIMAS.IS"]
            return bist_tickers
        except Exception:
            return ["THYAO.IS", "GARAN.IS", "ASELS.IS"]
    else:
        try:
            # SEC EDGAR zorunlu kurumsal User-Agent header
            headers = {'User-Agent': 'WhaleRadarAdmin contact@whaleradar.com'}
            res = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                tickers = [v['ticker'] for v in data.values()]
                return sorted(tickers)
            else:
                # SEC yanıt vermezse devreye girecek düşük fiyatlı yedek hisseler
                return ["EBRCZ", "SNDL", "MULN", "CEI", "ZOM", "IDEX", "SHIP", "TOPS", "NAKD", "BBIG", "XELA", "CIDM", "PLUG", "FCEL"]
        except Exception:
            return ["EBRCZ", "SNDL", "MULN", "CEI", "ZOM", "SHIP", "PLUG"]

def fetch_stock_data(symbol, market_type="US"):
    try:
        alpaca_key = os.getenv("ALPACA_API_KEY")
        alpaca_secret = os.getenv("ALPACA_SECRET_KEY")

        if market_type == "US" and alpaca_key and alpaca_secret:
            client = StockHistoricalDataClient(alpaca_key, alpaca_secret)
            request_params = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=120)
            )
            bars = client.get_stock_bars(request_params)
            df = bars.df
            if not df.empty:
                if isinstance(df.index, pd.MultiIndex):
                    df = df.xs(symbol)
                df = df.rename(columns={
                    'close': 'Close',
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low',
                    'volume': 'Volume'
                })
                return df

        ticker = yf.Ticker(symbol)
        df = ticker.history(period="6mo")
        return df
    except Exception:
        return pd.DataFrame()

def fetch_sec_financials(ticker):
    headers = {'User-Agent': 'WhaleRadarAdmin contact@whaleradar.com'}
    try:
        c_res = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
        if c_res.status_code != 200:
            return {"error": "SEC Şirket dizini çekilemedi."}

        company_data = c_res.json()
        cik = None
        comp_title = ticker
        for item in company_data.values():
            if item['ticker'].upper() == ticker.upper():
                cik = str(item['cik_str']).zfill(10)
                comp_title = item['title']
                break

        if not cik:
            return {"error": f"'{ticker}' için CIK kodu bulunamadı."}

        facts_res = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", headers=headers)
        if facts_res.status_code != 200:
            return {"error": "SEC XBRL finansal verileri çekilemedi."}

        facts = facts_res.json().get('facts', {})
        us_gaap = facts.get('us-gaap', {})

        def get_concept_units(concept_name):
            if concept_name in us_gaap:
                units = us_gaap[concept_name].get('units', {})
                for u in ['USD', 'shares', 'USD/shares']:
                    if u in units:
                        return units[u]
            return []

        def parse_annual_and_quarterly(concept_name):
            units = get_concept_units(concept_name)
            annual, quarterly = {}, {}
            for item in units:
                form = item.get('form', '')
                fy = item.get('fy')
                val = item.get('val')
                fp = item.get('fp')

                if form == '10-K' and fy and val is not None:
                    annual[str(fy)] = val
                elif form == '10-Q' and fy and fp and val is not None:
                    q_key = f"{fy}-{fp}"
                    quarterly[q_key] = val
            return annual, quarterly

        assets, _ = parse_annual_and_quarterly('Assets')
        liab, _ = parse_annual_and_quarterly('Liabilities')
        equity, _ = parse_annual_and_quarterly('StockholdersEquity')
        revenue, q_revenue = parse_annual_and_quarterly('Revenues')
        if not revenue:
            revenue, q_revenue = parse_annual_and_quarterly('RevenueFromContractWithCustomerExcludingAssessedTax')

        gross_profit, q_gross_profit = parse_annual_and_quarterly('GrossProfit')
        net_income, q_net_income = parse_annual_and_quarterly('NetIncomeLoss')
        eps, q_eps = parse_annual_and_quarterly('EarningsPerShareDiluted')
        fcf, _ = parse_annual_and_quarterly('FreeCashFlow')
        buybacks, _ = parse_annual_and_quarterly('PaymentsForRepurchaseOfCommonStock')
        shares, _ = parse_annual_and_quarterly('WeightedAverageNumberOfDilutedSharesOutstanding')

        all_years = sorted(list(set(assets.keys()) | set(revenue.keys()) | set(net_income.keys())), reverse=True)[:5]

        rows = []
        for year in all_years:
            a_val = assets.get(year)
            l_val = liab.get(year)
            e_val = equity.get(year)

            if a_val is not None and e_val is not None and l_val is None:
                l_val = a_val - e_val
            elif a_val is not None and l_val is not None and e_val is None:
                e_val = a_val - l_val

            rows.append({
                'Yil': year,
                'Varliklar': a_val if a_val is not None else 'N/A',
                'Yukumlulukler': l_val if l_val is not None else 'N/A',
                'Ozkaynaklar': e_val if e_val is not None else 'N/A',
                'Hasilat': revenue.get(year, 'N/A'),
                'Brut Kar': gross_profit.get(year, 'N/A'),
                'Net Kar': net_income.get(year, 'N/A'),
                'EPS': eps.get(year, 'N/A'),
                'FCF (Nakit Akisi)': fcf.get(year, 'N/A'),
                'Hisse Geri Alimi': buybacks.get(year, 'N/A'),
                'Tedavuldeki Hisse': shares.get(year, 'N/A')
            })

        all_quarters = sorted(list(set(q_revenue.keys()) | set(q_net_income.keys())), reverse=True)[:6]
        quarterly_rows = []
        for q_key in all_quarters:
            quarterly_rows.append({
                'Donem': q_key,
                'Hasilat': q_revenue.get(q_key, 'N/A'),
                'Brut Kar': q_gross_profit.get(q_key, 'N/A'),
                'Net Kar': q_net_income.get(q_key, 'N/A'),
                'EPS': q_eps.get(q_key, 'N/A')
            })

        return {
            "company": comp_title,
            "ticker": ticker,
            "data": rows,
            "quarterly_data": quarterly_rows
        }

    except Exception as e:
        return {"error": f"SEC verileri işlenirken hata oluştu: {str(e)}"}
