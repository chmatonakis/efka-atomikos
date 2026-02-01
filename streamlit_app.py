import streamlit as st
import pandas as pd
import json
from pdf_parser import parse_efka_pdf, APODOXES_DESCRIPTIONS

# Set page configuration
st.set_page_config(page_title="e-EFKA Parser", page_icon="📊", layout="wide")

# --- Formatting Helpers ---
def format_number_gr(value, decimals=2):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num == 0:
        return ""
    formatted = f"{num:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

def format_currency_gr(value):
    formatted = format_number_gr(value, 2)
    return f"€{formatted}" if formatted != "" else ""

def format_percent_gr(value):
    formatted = format_number_gr(value, 2)
    return f"{formatted}%" if formatted != "" else ""

def apply_left_align(styler):
    return styler.set_properties(**{'text-align': 'left'}).set_table_styles(
        [{'selector': 'th', 'props': [('text-align', 'left')]}]
    )

def format_df_for_display(
    df,
    currency_cols=None,
    int_cols=None,
    percent_cols=None,
    float_cols_decimals=None,
):
    df_display = df.copy()
    currency_cols = set(currency_cols or [])
    int_cols = set(int_cols or [])
    percent_cols = set(percent_cols or [])
    float_cols_decimals = float_cols_decimals or {}

    for col in df_display.columns:
        if col in currency_cols:
            df_display[col] = df_display[col].apply(format_currency_gr)
        elif col in percent_cols:
            df_display[col] = df_display[col].apply(format_percent_gr)
        elif col in int_cols:
            df_display[col] = df_display[col].apply(lambda v: format_number_gr(v, 0))
        elif col in float_cols_decimals:
            decimals = float_cols_decimals[col]
            df_display[col] = df_display[col].apply(lambda v: format_number_gr(v, decimals))
        else:
            df_display[col] = df_display[col].where(pd.notna(df_display[col]), "")
            df_display[col] = df_display[col].astype(str)

    return df_display

def round_float_columns(df, decimals=2):
    df_out = df.copy()
    float_cols = df_out.select_dtypes(include=["float"]).columns
    if len(float_cols) > 0:
        df_out[float_cols] = df_out[float_cols].round(decimals)
    return df_out

def round_numeric_columns(df, columns, decimals=2):
    df_out = df.copy()
    for col in columns:
        if col in df_out.columns:
            numeric_values = pd.to_numeric(df_out[col], errors="coerce")
            df_out[col] = numeric_values.round(decimals).where(numeric_values.notna(), df_out[col])
    return df_out

# --- Data Dictionaries ---
insurable_ceiling_old = {
    '2002': 1884.75, '2003': 1960.25, '2004': 2058.25, '2005': 2140.50, '2006': 2226.00,
    '2007': 2315.00, '2008': 2384.50, '2009': 2432.25, '2010': 2432.25, '2011': 2432.25,
    '2012': 2432.25, '2013': 5546.80, '2014': 5546.80, '2015': 5546.80, '2016': 5861.00,
    '2017': 5861.00, '2018': 5861.00, '2019': 6500.00, '2020': 6500.00, '2021': 6500.00,
    '2022': 6500.00, '2023': 7126.94, '2024': 7126.94, '2025': 7572.62, '2026': 7572.62
}

insurable_ceiling_new = {
    '2002': 4693.52, '2003': 4693.52, '2004': 4693.52, '2005': 4881.26, '2006': 5076.51,
    '2007': 5279.57, '2008': 5437.96, '2009': 5543.55, '2010': 5543.55, '2011': 5543.55,
    '2012': 5546.80, '2013': 5546.80, '2014': 5546.80, '2015': 5546.80, '2016': 5861.00,
    '2017': 5861.00, '2018': 5861.00, '2019': 6500.00, '2020': 6500.00, '2021': 6500.00,
    '2022': 6500.00, '2023': 7126.94, '2024': 7126.94, '2025': 7572.62, '2026': 7572.62
}

DTK_TABLE = {
    2020: {
        2002: 1.31786, 2003: 1.27329, 2004: 1.23741, 2005: 1.19556, 2006: 1.15849,
        2007: 1.12584, 2008: 1.08046, 2009: 1.06754, 2010: 1.01949, 2011: 1,
        2012: 1, 2013: 1, 2014: 1, 2015: 1.01169, 2016: 1.02011, 2017: 1.0088,
        2018: 1.00253, 2019: 1, 2020: 1, 2021: 1, 2022: 1, 2023: 1, 2024: 1, 2025: 1
    },
    2021: {
        2002: 1.30204, 2003: 1.25801, 2004: 1.22256, 2005: 1.18121, 2006: 1.14459,
        2007: 1.11233, 2008: 1.0675, 2009: 1.05473, 2010: 1.00726, 2011: 1,
        2012: 1, 2013: 1, 2014: 1, 2015: 1, 2016: 1.00787, 2017: 1, 2018: 1,
        2019: 1, 2020: 1, 2021: 1, 2022: 1, 2023: 1, 2024: 1, 2025: 1
    },
    2022: {
        2002: 1.31758, 2003: 1.27302, 2004: 1.23714, 2005: 1.19531, 2006: 1.15824,
        2007: 1.1256, 2008: 1.08023, 2009: 1.06742, 2010: 1.01951, 2011: 1,
        2012: 1, 2013: 1, 2014: 1, 2015: 1.0113, 2016: 1.01945, 2017: 1.00836,
        2018: 1.00235, 2019: 1, 2020: 1.01200, 2021: 1, 2022: 1, 2023: 1, 2024: 1, 2025: 1
    },
    2023: {
        2002: 1.44406, 2003: 1.39523, 2004: 1.35591, 2005: 1.31006, 2006: 1.26944,
        2007: 1.23366, 2008: 1.18393, 2009: 1.16990, 2010: 1.11738, 2011: 1.08168,
        2012: 1.06570, 2013: 1.07538, 2014: 1.08954, 2015: 1.10838, 2016: 1.11732,
        2017: 1.10516, 2018: 1.09857, 2019: 1.09529, 2020: 1.10915, 2021: 1.09600,
        2022: 1.00000, 2023: 1.00000, 2024: 1, 2025: 1
    },
    2024: {
        2002: 1.49444, 2003: 1.44391, 2004: 1.40321, 2005: 1.35576, 2006: 1.31372,
        2007: 1.27670, 2008: 1.22524, 2009: 1.21059, 2010: 1.15610, 2011: 1.11885,
        2012: 1.10229, 2013: 1.11254, 2014: 1.12734, 2015: 1.14725, 2016: 1.15680,
        2017: 1.14398, 2018: 1.13686, 2019: 1.13400, 2020: 1.14833, 2021: 1.13444,
        2022: 1.03465, 2023: 1.00000, 2024: 1.00000, 2025: 1.00000
    },
    2025: {
        2002: 1.53541, 2003: 1.48349, 2004: 1.44168, 2005: 1.39293, 2006: 1.34974,
        2007: 1.31170, 2008: 1.25883, 2009: 1.24378, 2010: 1.18780, 2011: 1.14952,
        2012: 1.13251, 2013: 1.14304, 2014: 1.15824, 2015: 1.17870, 2016: 1.18852,
        2017: 1.17534, 2018: 1.16803, 2019: 1.16508, 2020: 1.17981, 2021: 1.16554,
        2022: 1.06301, 2023: 1.02741, 2024: 1.00000, 2025: 1.00000
    },
    2026: {
        2002: 1.57226, 2003: 1.51910, 2004: 1.47628, 2005: 1.42636, 2006: 1.38213,
        2007: 1.34318, 2008: 1.28904, 2009: 1.27363, 2010: 1.21631, 2011: 1.17711,
        2012: 1.15969, 2013: 1.17047, 2014: 1.18604, 2015: 1.20699, 2016: 1.21705,
        2017: 1.20355, 2018: 1.19606, 2019: 1.19304, 2020: 1.20813, 2021: 1.19351,
        2022: 1.08852, 2023: 1.05207, 2024: 1.02400, 2025: 1.02400, 2026: 1.00000
    }
}


# --- Helper Functions ---
def load_data(uploaded_file):
    """Loads and parses the PDF file, returns two dataframes."""
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        df_monthly, df_annual = parse_efka_pdf(file_bytes)
        return df_monthly, df_annual
    return None, None

# --- UI Layout ---
st.markdown(
    """
    <style>
    .top-bar {
        background: linear-gradient(90deg, #6b73ff 0%, #7e57c2 100%);
        color: #ffffff;
        padding: 16px 24px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
    }
    .top-bar .title {
        font-size: 22px;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .top-bar .subtitle {
        font-size: 12px;
        opacity: 0.9;
    }
    .top-bar .menu {
        display: flex;
        gap: 16px;
        font-size: 14px;
        font-weight: 600;
    }
    .top-bar .menu span {
        background: rgba(255,255,255,0.15);
        padding: 6px 10px;
        border-radius: 16px;
    }
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 32px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 18px;
        font-weight: 700;
        padding: 12px 24px;
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 18px;
        font-weight: 700;
    }
    /* Red buttons */
    .stButton > button {
        background-color: #dc3545 !important;
        color: white !important;
        border: none !important;
    }
    .stButton > button:hover {
        background-color: #c82333 !important;
        color: white !important;
    }
    .stButton > button:active {
        background-color: #bd2130 !important;
    }
    .stDownloadButton > button {
        background-color: #dc3545 !important;
        color: white !important;
        border: none !important;
    }
    .stDownloadButton > button:hover {
        background-color: #c82333 !important;
        color: white !important;
    }
    .stFormSubmitButton > button {
        background-color: #dc3545 !important;
        color: white !important;
        border: none !important;
    }
    .stFormSubmitButton > button:hover {
        background-color: #c82333 !important;
        color: white !important;
    }
    </style>
    <div class="top-bar">
        <div>
            <div class="title">📊 Ατομικός Λογαριασμός e-EFKA</div>
            <div class="subtitle">Ανάλυση και Επεξεργασία Ασφαλιστικών Δεδομένων</div>
        </div>
        <div class="menu">
            <span>🏠 Αρχική</span>
            <span>📄 Οδηγίες</span>
            <span>ℹ️ Σχετικά</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "analysis_requested" not in st.session_state:
    st.session_state["analysis_requested"] = False

if not st.session_state["analysis_requested"]:
    st.markdown(
        """
        <div style="text-align:center; margin-top: 12px;">
            <h2>Ανεβάστε το PDF αρχείο σας</h2>
            <p>Επιλέξτε το αρχείο e-EFKA που θέλετε να αναλύσετε</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        uploaded_file = st.file_uploader("Επιλέξτε PDF αρχείο", type="pdf")
        analyze_clicked = st.button("🔍 Αναλύστε το Αρχείο", use_container_width=True)
        st.markdown(
            """
            <div style="text-align:center; font-size: 0.9em; color: #6b7280;">
                Προτείνεται χρήση Chrome ή Edge για καλύτερη συμβατότητα.
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    analyze_clicked = False
    uploaded_file = st.session_state.get("uploaded_file")

if analyze_clicked:
    if uploaded_file is None:
        st.warning("Παρακαλώ επιλέξτε πρώτα ένα PDF αρχείο.")
        st.session_state["analysis_requested"] = False
    else:
        st.session_state["analysis_requested"] = True
        st.session_state["uploaded_file"] = uploaded_file
        st.rerun()  # Ξαναφόρτωσε τη σελίδα για να κρύψει τη φόρμα


# --- Main Logic ---
effective_file = uploaded_file or st.session_state.get("uploaded_file")
if effective_file is not None and st.session_state["analysis_requested"]:
    with st.spinner('Γίνεται ανάλυση του PDF...'):
        df_monthly, df_annual = load_data(effective_file)
        st.success('Η ανάλυση του PDF ολοκληρώθηκε!')

    if df_monthly is not None and not df_monthly.empty:
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "Πλήρης Ανάλυση",
            "Συντάξιμες Αποδοχές",
            "Συνοπτικά Δεδομένα",
            "Στοιχεία χωρίς επεξεργασία"
        ])

        yearly_totals = None

        # --- Tab 1: Full Analysis ---
        with tab1:
            st.header("Πλήρης Ανάλυση Αποδοχών / Εισφορών / Πλαφόν")
            
            df_analysis = df_monthly.copy()
            period_str = df_analysis['ΠΕΡΙΟΔΟΣ'].astype(str).str.strip()
            # Κανονικοποίηση μήνα σε 2 ψηφία για σταθερό parsing (π.χ. 1/2003 -> 01/2003)
            period_str = period_str.str.replace(r'^(\d{1})/', r'0\1/', regex=True)
            df_analysis['ΠΕΡΙΟΔΟΣ'] = period_str
            period_dt = pd.to_datetime(period_str, format='%m/%Y', errors='coerce')
            df_analysis['ΕΤΟΣ'] = period_dt.dt.year.astype('Int64').astype(str)

            # Φίλτρα προβολής (κενό = όλα)
            available_years = sorted([y for y in df_analysis['ΕΤΟΣ'].dropna().unique()])
            year_options = ['(Όλα)'] + available_years

            type_codes = sorted([str(t) for t in df_analysis['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].dropna().unique()])
            type_label_map = {
                code: f"{code} - {APODOXES_DESCRIPTIONS.get(code, 'Άγνωστη Περιγραφή')}"
                for code in type_codes
            }
            type_options = [type_label_map[code] for code in type_codes]
            type_label_to_code = {label: code for code, label in type_label_map.items()}

            package_codes = sorted([str(p) for p in df_analysis['ΚΩΔ. ΠΑΚΕΤΟ ΚΑΛΥΨΗΣ'].dropna().unique()])
            package_desc_map = {}
            if df_annual is not None and not df_annual.empty:
                package_desc_map = (
                    df_annual.dropna(subset=['ΠΑΚ. ΚΑΛ.'])
                    .groupby('ΠΑΚ. ΚΑΛ.')['ΠΕΡΙΓΡΑΦΗ']
                    .first()
                    .to_dict()
                )
            package_label_map = {
                code: f"{code} - {package_desc_map.get(code, '').strip()}" if package_desc_map.get(code) else code
                for code in package_codes
            }
            package_options = [package_label_map[code] for code in package_codes]
            package_label_to_code = {label: code for code, label in package_label_map.items()}

            # Initialize session state for ceiling_type
            if "ceiling_type" not in st.session_state:
                st.session_state["ceiling_type"] = 'Παλιός'

            with st.form("filters_form"):
                col_f1, col_f2, col_f3, col_f4, col_f5, col_btn = st.columns([1, 1, 1, 2, 2, 1.5])
                with col_f1:
                    ceiling_type = st.selectbox(
                        "Πλαφόν",
                        ('Παλιός', 'Νέος'),
                        index=0 if st.session_state["ceiling_type"] == 'Παλιός' else 1,
                        key="ceiling_type_select"
                    )
                    st.session_state["ceiling_type"] = ceiling_type
                with col_f2:
                    year_from = st.selectbox("Έτος από", options=year_options, index=0)
                with col_f3:
                    year_to = st.selectbox("Έτος έως", options=year_options, index=0)
                with col_f4:
                    selected_type_labels = st.multiselect("Τύπος Αποδοχών", options=type_options, default=[])
                with col_f5:
                    selected_package_labels = st.multiselect("Πακέτο Κάλυψης", options=package_options, default=[])
                with col_btn:
                    st.write("")  # Empty space for alignment
                    st.write("")  # Empty space for alignment
                    apply_filters = st.form_submit_button("Εφαρμογή φίλτρων", use_container_width=True)

            # Εφαρμογή φίλτρων
            filtered = df_analysis.copy()
            if apply_filters:
                if year_from != '(Όλα)' or year_to != '(Όλα)':
                    min_year = available_years[0] if available_years else None
                    max_year = available_years[-1] if available_years else None
                    from_year = year_from if year_from != '(Όλα)' else min_year
                    to_year = year_to if year_to != '(Όλα)' else max_year
                    if from_year and to_year and from_year > to_year:
                        from_year, to_year = to_year, from_year
                    if from_year and to_year:
                        filtered = filtered[(filtered['ΕΤΟΣ'] >= from_year) & (filtered['ΕΤΟΣ'] <= to_year)]

                if selected_type_labels:
                    selected_types = [type_label_to_code[label] for label in selected_type_labels]
                    filtered = filtered[filtered['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str).isin(selected_types)]

                if selected_package_labels:
                    selected_packages = [package_label_to_code[label] for label in selected_package_labels]
                    filtered = filtered[filtered['ΚΩΔ. ΠΑΚΕΤΟ ΚΑΛΥΨΗΣ'].astype(str).isin(selected_packages)]

            df_analysis = filtered.copy()

            # Υπολογισμός ΒΑΣΙΚΟ ΠΛΑΦΟΝ με βάση το επιλεγμένο ceiling_type
            ceiling_type = st.session_state.get("ceiling_type", "Παλιός")
            ceiling_dict = insurable_ceiling_old if ceiling_type == 'Παλιός' else insurable_ceiling_new
            df_analysis['ΒΑΣΙΚΟ ΠΛΑΦΟΝ'] = df_analysis['ΕΤΟΣ'].map(ceiling_dict).fillna(0)

            # Αποδοχές μήνα: άθροισμα αποδοχών ίδιου μήνα, εξαιρώντας Δώρα/Επίδομα Αδείας
            excluded_mask = df_analysis['ΠΕΡΙΓΡΑΦΗ_ΑΠΟΔΟΧΩΝ'].astype(str).str.contains(
                r'δώρο|επίδομα\s+αδείας', case=False, regex=True
            ) | df_analysis['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str).isin(['03', '04', '05'])
            df_analysis['IS_SPECIAL'] = excluded_mask
            monthly_earnings = (
                df_analysis.loc[~excluded_mask]
                .groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΑΠΟΔΟΧΕΣ']
                .sum()
            )
            df_analysis['ΑΠΟΔΟΧΕΣ ΜΗΝΑ'] = df_analysis['ΠΕΡΙΟΔΟΣ'].map(monthly_earnings)

            # Υπολογισμός πλαφόν ανά μήνα με βάση τις ημέρες εργασίας από τον κωδικό 01
            days_map = (
                df_analysis.loc[df_analysis['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str) == '01']
                .groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΗΜΕΡ. ΑΠΑΣΧ.']
                .max()
            )
            base_plafon_map = (
                df_analysis.groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΒΑΣΙΚΟ ΠΛΑΦΟΝ']
                .max()
            )
            plafon_month_map = (base_plafon_map / 25 * days_map).clip(upper=base_plafon_map)
            plafon_month_map = plafon_month_map.fillna(base_plafon_map)

            # Εισφορίσιμο πλαφόν ανά γραμμή
            df_analysis['ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'] = df_analysis['ΠΕΡΙΟΔΟΣ'].map(plafon_month_map)
            df_analysis.loc[df_analysis['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str) == '03', 'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'] = df_analysis['ΒΑΣΙΚΟ ΠΛΑΦΟΝ']
            df_analysis.loc[df_analysis['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str).isin(['04', '05']), 'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'] = df_analysis['ΒΑΣΙΚΟ ΠΛΑΦΟΝ'] / 2

            # Εισφορίσιμες αποδοχές ανά μήνα (όχι ανά γραμμή), εκτός από ειδικές αποδοχές
            monthly_plafon = (
                df_analysis.groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ']
                .max()
            )
            monthly_insurable = (df_analysis['ΠΕΡΙΟΔΟΣ'].map(monthly_earnings)
                                 .combine(df_analysis['ΠΕΡΙΟΔΟΣ'].map(monthly_plafon), min))
            df_analysis['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = monthly_insurable

            perikopi_map = (df_analysis['ΠΕΡΙΟΔΟΣ'].map(monthly_earnings) -
                            df_analysis['ΠΕΡΙΟΔΟΣ'].map(monthly_plafon))
            df_analysis['ΠΕΡΙΚΟΠΗ'] = perikopi_map.where(perikopi_map > 0, None)

            # Για ειδικές αποδοχές (Δώρα/Επίδομα), ο έλεγχος γίνεται ανά γραμμή
            df_analysis.loc[df_analysis['IS_SPECIAL'], 'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = df_analysis.loc[
                df_analysis['IS_SPECIAL'], ['ΑΠΟΔΟΧΕΣ', 'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ']
            ].min(axis=1)
            df_analysis.loc[df_analysis['IS_SPECIAL'], 'ΠΕΡΙΚΟΠΗ'] = (
                df_analysis.loc[df_analysis['IS_SPECIAL'], 'ΑΠΟΔΟΧΕΣ'] -
                df_analysis.loc[df_analysis['IS_SPECIAL'], 'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ']
            ).where(lambda s: s > 0, None)

            # Αποφυγή διαίρεσης με το μηδέν
            df_analysis['ΠΟΣΟΣΤΟ'] = df_analysis.apply(
                lambda row: (row['ΕΙΣΦΟΡΕΣ'] / row['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ']) * 100 if row['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] > 0 else 0,
                axis=1
            )

            display_df = df_analysis.copy()
            # Κρατάμε σταθερά keys για την ομαδοποίηση πριν "κενώσουμε" τα πεδία
            display_df['ΕΤΟΣ_KEY'] = display_df['ΕΤΟΣ']
            display_df['ΠΕΡΙΟΔΟΣ_KEY'] = display_df['ΠΕΡΙΟΔΟΣ']

            # Ταξινόμηση για ομαδοποίηση ανά έτος και περίοδο
            # Ειδικές αποδοχές (Δώρα/Επίδομα) στο τέλος του έτους
            # Εντός μήνα, ταξινόμηση με βάση ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ (01 πρώτα)
            display_df['ΤΥΠΟΣ_SORT'] = display_df['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str)
            display_df = display_df.sort_values([
                'ΕΤΟΣ_KEY', 'IS_SPECIAL', 'ΠΕΡΙΟΔΟΣ_KEY', 'ΤΥΠΟΣ_SORT'
            ])

            # Εμφάνιση έτους μόνο στην πρώτη γραμμή κάθε έτους
            display_df['ΕΤΟΣ'] = display_df['ΕΤΟΣ'].where(~display_df.duplicated(['ΕΤΟΣ_KEY']), '')
            # Εμφάνιση περιόδου μόνο στην πρώτη γραμμή κάθε περιόδου
            display_df['ΠΕΡΙΟΔΟΣ'] = display_df['ΠΕΡΙΟΔΟΣ'].where(~display_df.duplicated(['ΕΤΟΣ_KEY', 'ΠΕΡΙΟΔΟΣ_KEY']), '')

            # Εμφάνιση "ΑΠΟΔΟΧΕΣ ΜΗΝΑ", "ΠΛΑΦΟΝ", "ΠΕΡΙΚΟΠΗ" μόνο στην πρώτη γραμμή κάθε περιόδου
            show_month_total = ~display_df.duplicated(['ΕΤΟΣ_KEY', 'ΠΕΡΙΟΔΟΣ_KEY'])
            display_df['ΑΠΟΔΟΧΕΣ ΜΗΝΑ'] = display_df['ΑΠΟΔΟΧΕΣ ΜΗΝΑ'].where(show_month_total, '')
            display_df['ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'] = display_df['ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'].where(
                show_month_total | display_df['IS_SPECIAL'], ''
            )
            display_df['ΠΕΡΙΚΟΠΗ'] = display_df['ΠΕΡΙΚΟΠΗ'].where(
                show_month_total | display_df['IS_SPECIAL'], ''
            )
            display_df['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = display_df['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'].where(
                show_month_total | display_df['IS_SPECIAL'], ''
            )

            visible_columns = [
                'ΕΤΟΣ', 'ΠΕΡΙΟΔΟΣ', 'ΚΩΔ. ΠΑΚΕΤΟ ΚΑΛΥΨΗΣ', 'ΗΜΕΡ. ΑΠΑΣΧ.', 'ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ',
                'ΠΕΡΙΓΡΑΦΗ_ΑΠΟΔΟΧΩΝ', 'ΑΠΟΔΟΧΕΣ', 'ΕΙΣΦΟΡΕΣ', 'ΠΟΣΟΣΤΟ', 'ΑΠΟΔΟΧΕΣ ΜΗΝΑ',
                'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ', 'ΠΕΡΙΚΟΠΗ', 'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'
            ]
            display_df_visible = display_df[visible_columns]

            # Προσθήκη γραμμών σύνοψης ανά έτος και κενής γραμμής μετά
            rows = []
            summary_flags = []
            yearly_totals_rows = []
            years = [y for y in display_df['ΕΤΟΣ_KEY'].dropna().unique()]
            years = sorted(years)
            for year in years:
                year_mask = display_df['ΕΤΟΣ_KEY'] == year
                year_rows = display_df_visible[year_mask]
                for _, row in year_rows.iterrows():
                    rows.append(row.to_dict())
                    summary_flags.append(False)

                totals = df_analysis[df_analysis['ΕΤΟΣ'] == str(year)]
                summary_row = {col: '' for col in visible_columns}
                summary_row['ΕΤΟΣ'] = f"ΣΥΝΟΛΟ {year}"
                total_days = totals['ΗΜΕΡ. ΑΠΑΣΧ.'].sum()
                total_apodoxes = totals['ΑΠΟΔΟΧΕΣ'].sum()
                summary_row['ΑΠΟΔΟΧΕΣ'] = round(total_apodoxes, 2)
                summary_row['ΕΙΣΦΟΡΕΣ'] = round(totals['ΕΙΣΦΟΡΕΣ'].sum(), 2)

                # Σύνολο περικοπής: μία φορά ανά μήνα + ειδικές αποδοχές ανά γραμμή
                perikopi_month_sum = (
                    totals.loc[~totals['IS_SPECIAL']]
                    .groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΠΕΡΙΚΟΠΗ']
                    .max()
                    .fillna(0)
                    .sum()
                )
                perikopi_special_sum = totals.loc[totals['IS_SPECIAL'], 'ΠΕΡΙΚΟΠΗ'].fillna(0).sum()
                total_perikopi = perikopi_month_sum + perikopi_special_sum
                total_insurable = round(total_apodoxes - total_perikopi, 2)
                summary_row['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = total_insurable
                rows.append(summary_row)
                summary_flags.append(True)

                yearly_totals_rows.append({
                    'ΕΤΟΣ': year,
                    'ΗΜΕΡ. ΑΠΑΣΧ.': total_days,
                    'ΑΠΟΔΟΧΕΣ': round(total_apodoxes, 2),
                    'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ': total_insurable
                })

                blank_row = {col: '' for col in visible_columns}
                rows.append(blank_row)
                summary_flags.append(False)

            display_df_with_totals = pd.DataFrame(rows, columns=visible_columns)
            display_df_with_totals = round_float_columns(display_df_with_totals)
            display_df_with_totals = round_numeric_columns(
                display_df_with_totals,
                columns=[
                    'ΑΠΟΔΟΧΕΣ', 'ΕΙΣΦΟΡΕΣ', 'ΠΟΣΟΣΤΟ', 'ΑΠΟΔΟΧΕΣ ΜΗΝΑ',
                    'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ', 'ΠΕΡΙΚΟΠΗ', 'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'
                ],
                decimals=2
            )
            # Κρύβουμε τα μηδενικά μόνο στις συγκεκριμένες στήλες
            for col in ['ΗΜΕΡ. ΑΠΑΣΧ.', 'ΕΙΣΦΟΡΕΣ', 'ΠΟΣΟΣΤΟ']:
                if col in display_df_with_totals.columns:
                    display_df_with_totals[col] = display_df_with_totals[col].replace(0, '')

            st.dataframe(display_df_with_totals, use_container_width=True, hide_index=True)

            yearly_totals = pd.DataFrame(yearly_totals_rows)

        # --- Tab 2: Pensionable Earnings ---
        with tab2:
            st.header("Υπολογισμός Συντάξιμων Αποδοχών")

            if yearly_totals is not None and not yearly_totals.empty:
                pension_df = yearly_totals.copy()
                pension_df['ΕΤΟΣ'] = pd.to_numeric(pension_df['ΕΤΟΣ'])

                dtk_year_options = sorted(DTK_TABLE.keys(), reverse=True)
                default_dtk_index = dtk_year_options.index(2026) if 2026 in dtk_year_options else 0
                buyout_year_options = sorted(DTK_TABLE[dtk_year_options[0]].keys(), reverse=True)

                with st.form("pension_calc_form"):
                    col_i1, col_i2, col_i3, col_i4 = st.columns(4)
                    with col_i1:
                        selected_dtk_year = st.selectbox(
                            "Έτος Αναφοράς ΔΤΚ",
                            options=dtk_year_options,
                            index=default_dtk_index
                        )
                    with col_i2:
                        buyout_days = st.number_input("Ημέρες Εξαγοράς", min_value=0, step=1, value=0)
                    with col_i3:
                        buyout_year = st.selectbox("Έτος Εξαγοράς", options=buyout_year_options, index=0)
                    with col_i4:
                        buyout_amount = st.number_input("Ποσό Εξαγοράς", min_value=0.0, step=1.0, value=0.0)

                    calculate = st.form_submit_button("Υπολογισμός")

                if not calculate:
                    st.info("Πατήστε «Υπολογισμός» για να εφαρμοστούν οι αλλαγές.")
                else:
                    dtk_factors = DTK_TABLE[selected_dtk_year]
                    buyout_dtk = dtk_factors.get(buyout_year, 1.0)
                    buyout_insurable = buyout_amount * 5

                    # Υπολογισμοί
                    pension_df['ΣΥΝΤΕΛΕΣΤΗΣ ΔΤΚ'] = pension_df['ΕΤΟΣ'].map(dtk_factors).fillna(1.0)
                    pension_df['ΤΕΛΙΚΕΣ ΣΥΝΤΑΞΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = (
                        pension_df['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] * pension_df['ΣΥΝΤΕΛΕΣΤΗΣ ΔΤΚ']
                    )

                    # Γραμμή εξαγοράς
                    if buyout_days > 0 or buyout_amount > 0:
                        pension_df = pd.concat([
                            pension_df,
                            pd.DataFrame([{
                                'ΕΤΟΣ': buyout_year,
                                'ΗΜΕΡ. ΑΠΑΣΧ.': buyout_days,
                                'ΑΠΟΔΟΧΕΣ': 0,
                                'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ': buyout_insurable,
                                'ΣΥΝΤΕΛΕΣΤΗΣ ΔΤΚ': buyout_dtk,
                                'ΤΕΛΙΚΕΣ ΣΥΝΤΑΞΙΜΕΣ ΑΠΟΔΟΧΕΣ': buyout_insurable * buyout_dtk,
                            }])
                        ], ignore_index=True)
                        pension_df.loc[pension_df.index[-1], 'ΕΤΟΣ'] = "ΕΞΑΓΟΡΑ"

                    # Metrics
                    total_days = pension_df['ΗΜΕΡ. ΑΠΑΣΧ.'].sum()
                    total_pensionable_earnings = pension_df['ΤΕΛΙΚΕΣ ΣΥΝΤΑΞΙΜΕΣ ΑΠΟΔΟΧΕΣ'].sum()
                    months_from_2002 = total_days / 25 if total_days > 0 else 0
                    average_pensionable_salary = (
                        total_pensionable_earnings / months_from_2002 if months_from_2002 > 0 else 0
                    )

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Σύνολο Ημερών", format_number_gr(total_days, 0))
                    col2.metric("Μήνες από το 2002", format_number_gr(months_from_2002, 2))
                    col3.metric("Σύνολο Συντάξιμων Αποδοχών", format_currency_gr(total_pensionable_earnings))
                    col4.metric("Μέσος Συντάξιμος Μισθός", format_currency_gr(average_pensionable_salary))

                    pension_display = format_df_for_display(
                        pension_df,
                        currency_cols=['ΑΠΟΔΟΧΕΣ', 'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ', 'ΤΕΛΙΚΕΣ ΣΥΝΤΑΞΙΜΕΣ ΑΠΟΔΟΧΕΣ'],
                        int_cols=['ΗΜΕΡ. ΑΠΑΣΧ.'],
                        float_cols_decimals={'ΣΥΝΤΕΛΕΣΤΗΣ ΔΤΚ': 5},
                    )
                    styled_pension = pension_display.style.set_properties(**{'text-align': 'left'}).set_table_styles(
                        [{'selector': 'th', 'props': [('text-align', 'left')]}]
                    )
                    st.dataframe(styled_pension, use_container_width=True, hide_index=True)

                    # --- Εξαγωγή JSON για Syntaksi Pro ---
                    st.markdown("---")
                    st.subheader("Εξαγωγή για Syntaksi Pro")
                    
                    # Δημιουργία JSON - εξαιρούμε τη γραμμή ΕΞΑΓΟΡΑ
                    json_data = {}
                    for _, row in pension_df.iterrows():
                        year = row['ΕΤΟΣ']
                        if year == "ΕΞΑΓΟΡΑ":
                            continue
                        year_str = str(int(year)) if isinstance(year, (int, float)) else str(year)
                        
                        # ika_YYYY = ΗΜΕΡ. ΑΠΑΣΧ.
                        json_data[f"ika_{year_str}"] = {
                            "value": int(row['ΗΜΕΡ. ΑΠΑΣΧ.']),
                            "type": "number"
                        }
                        # apodoxes_YYYY = ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ
                        json_data[f"apodoxes_{year_str}"] = {
                            "value": round(row['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'], 2),
                            "type": "number"
                        }
                    
                    # Προσθήκη δεδομένων εξαγοράς
                    json_data["eksagorasmenes_imeres"] = {
                        "value": int(buyout_days),
                        "type": "number"
                    }
                    json_data["synoliko_poso_eksagoras"] = {
                        "value": round(buyout_amount, 2),
                        "type": "number"
                    }
                    json_data["dtk_eksagoras"] = {
                        "value": round(buyout_dtk, 5),
                        "type": "number"
                    }
                    
                    # Προσθήκη ΔΤΚ αναφοράς και έτους εθνικής
                    json_data["dtk"] = {
                        "value": int(selected_dtk_year),
                        "type": "number"
                    }
                    json_data["etos_ethnikis"] = {
                        "value": int(selected_dtk_year),
                        "type": "number"
                    }
                    
                    json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
                    
                    col_json1, col_json2, col_json3 = st.columns([1, 2, 1])
                    with col_json2:
                        st.download_button(
                            label="📥 Λήψη JSON για Syntaksi Pro",
                            data=json_str,
                            file_name="efka_syntaksi_pro.json",
                            mime="application/json",
                            use_container_width=True
                        )
                    
                    with st.expander("Προεπισκόπηση JSON"):
                        st.code(json_str, language="json")
            else:
                 st.warning("Δεν υπάρχουν συνοπτικά δεδομένα για τον υπολογισμό των συντάξιμων αποδοχών.")

        # --- Tab 3: Summary Data ---
        with tab3:
            st.header("Συνοπτικά Ετήσια Δεδομένα")
            if df_annual is not None and not df_annual.empty:
                st.dataframe(round_float_columns(df_annual), use_container_width=True, hide_index=True)
            else:
                st.warning("Δεν βρέθηκαν συνοπτικά ετήσια δεδομένα.")

        # --- Tab 4: Raw Data ---
        with tab4:
            st.header("Στοιχεία χωρίς επεξεργασία")
            st.dataframe(round_float_columns(df_monthly), use_container_width=True, hide_index=True)

    elif uploaded_file:
        st.error("Δεν ήταν δυνατή η εξαγωγή δεδομένων από το αρχείο PDF. Βεβαιωθείτε ότι το αρχείο είναι έγκυρο.")

