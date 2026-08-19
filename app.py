from flask import Flask, render_template, jsonify
import requests

app = Flask(__name__)

HEADERS = {'User-Agent': 'LocalFinancialApp obirlik68@gmail.com'}
TICKERS_URL = 'https://www.sec.gov/files/company_tickers.json'

# 1. SAYFA: SEC Bilanço Sorgulama
@app.route('/')
def index():
    return render_template('index.html')

# 2. SAYFA: Balina Avcısı Radar Ekranı
@app.route('/radar')
def radar():
    return render_template('radar.html')

@app.route('/api/financials/<ticker>')
def get_financials(ticker):
    ticker = ticker.upper()
    
    # 1. Ticker -> CIK Dönüşümü
    try:
        tickers_res = requests.get(TICKERS_URL, headers=HEADERS)
        tickers_data = tickers_res.json()
    except Exception:
        return jsonify({'error': 'SEC Şirket listesi alınamadı'}), 500

    cik = None
    title = ""
    for item in tickers_data.values():
        if item['ticker'] == ticker:
            cik = str(item['cik_str']).zfill(10)
            title = item['title']
            break

    if not cik:
        return jsonify({'error': f"'{ticker}' ticker kodu bulunamadı!"}), 404

    # 2. XBRL Verisini Çekme
    facts_url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
    facts_res = requests.get(facts_url, headers=HEADERS)
    
    if facts_res.status_code != 200:
        return jsonify({'error': 'Finansal veriler alınamadı'}), 500

    data = facts_res.json()
    us_gaap = data.get('facts', {}).get('us-gaap', {})

    # Yardımcı Fonksiyon (Yıllık 10-K Verilerini Süzme)
    def extract_yearly_data(concept_names, unit_key='USD'):
        results = {}
        if isinstance(concept_names, str):
            concept_names = [concept_names]

        for concept in concept_names:
            concept_data = us_gaap.get(concept, {}).get('units', {}).get(unit_key, [])
            for item in concept_data:
                if item.get('form') == '10-K' and 'fy' in item and 'val' in item:
                    fy = item['fy']
                    if fy not in results:
                        results[fy] = item['val']
        return results

    # Yardımcı Fonksiyon (Çeyreklik 10-Q Verilerini Süzme)
    def extract_quarterly_data(concept_names, unit_key='USD'):
        results = {}
        if isinstance(concept_names, str):
            concept_names = [concept_names]

        for concept in concept_names:
            concept_data = us_gaap.get(concept, {}).get('units', {}).get(unit_key, [])
            for item in concept_data:
                if item.get('form') == '10-Q' and 'fy' in item and 'fp' in item and 'val' in item:
                    period_key = f"{item['fy']}-{item['fp']}"
                    if period_key not in results:
                        results[period_key] = item['val']
        return results

    # Bilanço Kalemleri
    assets = extract_yearly_data(['Assets'])
    liabilities = extract_yearly_data(['Liabilities'])
    equity = extract_yearly_data(['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'])

    # Gelir Tablosu Kalemleri
    revenue = extract_yearly_data([
        'Revenues', 
        'SalesRevenueNet', 
        'RevenueFromContractWithCustomerExcludingAssessedTax', 
        'InterestAndDividendIncome',
        'InterestIncomeExpenseAfterProvisionForLoanLosses',
        'NoninterestIncome'
    ])
    gross_profit = extract_yearly_data([
        'GrossProfit', 
        'GrossProfitLoss',
        'InterestIncomeExpenseNet'
    ])
    net_income = extract_yearly_data(['NetIncomeLoss', 'ProfitLoss'])
    eps = extract_yearly_data(['EarningsPerShareDiluted', 'EarningsPerShareBasic'], unit_key='USD/shares')

    # EKLEME: Yıllık Nakit Akışı ve Hisse Verileri
    op_cash_flow = extract_yearly_data(['NetCashProvidedByUsedInOperatingActivities'])
    capex = extract_yearly_data(['PaymentsToAcquirePropertyPlantAndEquipment'])
    buybacks = extract_yearly_data(['PaymentsForRepurchaseOfCommonStock'])
    shares = extract_yearly_data(['EntityCommonStockSharesOutstanding', 'CommonStockSharesOutstanding'], unit_key='shares')

    # Çeyreklik Veri Kalemleri
    q_revenue = extract_quarterly_data([
        'Revenues', 
        'SalesRevenueNet', 
        'RevenueFromContractWithCustomerExcludingAssessedTax', 
        'InterestAndDividendIncome',
        'InterestIncomeExpenseAfterProvisionForLoanLosses',
        'NoninterestIncome'
    ])
    q_net_income = extract_quarterly_data(['NetIncomeLoss', 'ProfitLoss'])
    q_gross_profit = extract_quarterly_data(['GrossProfit', 'GrossProfitLoss', 'InterestIncomeExpenseNet'])
    q_eps = extract_quarterly_data(['EarningsPerShareDiluted', 'EarningsPerShareBasic'], unit_key='USD/shares')

    # Yılları Birleştirme (Son 5 Yıl)
    all_years = sorted(list(set(assets.keys()) | set(revenue.keys()) | set(net_income.keys())), reverse=True)[:5]
    
    rows = []
    for year in all_years:
        a_val = assets.get(year, None)
        e_val = equity.get(year, None)
        
        if a_val is not None and e_val is not None:
            l_val = a_val - e_val
        else:
            l_val = liabilities.get(year, 'N/A')

        # Serbest Nakit Akışı (FCF = İşletme Nakit Akışı - CapEx)
        cf_val = op_cash_flow.get(year, None)
        cx_val = capex.get(year, None)
        if cf_val is not None and cx_val is not None:
            fcf_val = cf_val - cx_val
        elif cf_val is not None:
            fcf_val = cf_val
        else:
            fcf_val = 'N/A'

        rows.append({
            'year': year,
            'assets': a_val if a_val is not None else 'N/A',
            'liabilities': l_val,
            'equity': e_val if e_val is not None else 'N/A',
            'revenue': revenue.get(year, 'N/A'),
            'gross_profit': gross_profit.get(year, 'N/A'),
            'net_income': net_income.get(year, 'N/A'),
            'eps': eps.get(year, 'N/A'),
            'fcf': fcf_val,
            'buybacks': buybacks.get(year, 'N/A'),
            'shares': shares.get(year, 'N/A')
        })

    # Son Çeyrekleri Sıralama (Son 6 Çeyrek)
    all_quarters = sorted(list(set(q_revenue.keys()) | set(q_net_income.keys())), reverse=True)[:6]
    quarterly_rows = []
    for q_key in all_quarters:
        quarterly_rows.append({
            'quarter': q_key,
            'revenue': q_revenue.get(q_key, 'N/A'),
            'gross_profit': q_gross_profit.get(q_key, 'N/A'),
            'net_income': q_net_income.get(q_key, 'N/A'),
            'eps': q_eps.get(q_key, 'N/A')
        })

    return jsonify({
        'company': title,
        'ticker': ticker,
        'cik': cik,
        'data': rows,
        'quarterly_data': quarterly_rows
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)