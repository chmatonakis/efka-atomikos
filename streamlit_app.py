import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import html
import re
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

def dataframe_to_printable_html(df, title="Πίνακας", person_name=None):
    """Δημιουργεί πλήρες HTML αρχείο για προβολή/εκτύπωση (οριζόντιο προσανατολισμός, hover ανά γραμμή)."""
    if df is None or df.empty:
        return None
    df_clean = df.fillna("")
    table_html = df_clean.to_html(index=False, classes="print-table", border=0)
    # Γραμμές που περιέχουν ΣΥΝΟΛΟ: ελαφρύ γκρι φόντο
    table_html = re.sub(
        r'<tr[^>]*>((?:(?!</tr>).)*?ΣΥΝΟΛΟ(?:(?!</tr>).)*?)</tr>',
        r'<tr class="row-total">\1</tr>',
        table_html, flags=re.DOTALL | re.IGNORECASE
    )

    safe_title = html.escape(str(title))
    safe_name = html.escape(str(person_name)) if person_name else ""
    name_block = f'<p class="print-name">{safe_name}</p>' if safe_name else ""

    doc = f"""<!DOCTYPE html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
body {{ font-family: sans-serif; margin: 1rem; color: #262730; }}
.print-name {{ text-align: center; font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem; }}
.print-title {{ font-size: 1.25rem; font-weight: 700; margin-bottom: 1rem; text-align: left; }}
.print-table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem; }}
.print-table th, .print-table td {{ padding: 10px 12px; text-align: left; border: none; border-bottom: 1px solid #d1d5db; }}
.print-table th {{ background: #f9fafb; font-weight: 700; font-size: 0.8rem; }}
.print-table td:nth-child(1), .print-table td:nth-child(2), .print-table th:nth-child(1), .print-table th:nth-child(2) {{ font-weight: 700; }}
.print-table tr.row-total {{ background: #e5e7eb; font-weight: 700; }}
.print-table tbody tr:hover {{ background: #fff4e6; }}
.header-row {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem; }}
.header-row .print-title {{ margin: 0; }}
.btn-print {{ background: #dc3545; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-size: 0.9rem; font-weight: 600; cursor: pointer; }}
.btn-print:hover {{ background: #c82333; }}
@media print {{
  @page {{ size: landscape; }}
  body {{ margin: 1.5cm; }}
  .no-print {{ display: none !important; }}
  .print-title {{ margin-bottom: 12px; }}
  .print-table {{ page-break-inside: auto; }}
  .print-table tr {{ page-break-inside: avoid; page-break-after: auto; }}
  .print-footer {{ margin-top: 1.5rem; }}
}}
.print-footer {{ margin-top: 1.5rem; padding-top: 0.75rem; border-top: 1px solid #d1d5db; font-size: 0.75rem; color: #6b7280; line-height: 1.4; }}
</style>
</head>
<body>
{name_block}
<div class="header-row">
  <h1 class="print-title">{safe_title}</h1>
  <div class="no-print" style="display:flex;gap:8px;">
    <button type="button" class="btn-print" onclick="window.print();">🖨 Εκτύπωση</button>
  </div>
</div>
{table_html}
<div class="print-footer"><strong>ΣΗΜΑΝΤΙΚΉ ΣΗΜΕΙΩΣΗ:</strong> Η παρούσα αναφορά βασίζεται αποκλειστικά στα δεδομένα που εμφανίζονται στο αρχείο ΑΤΟΜΙΚΟΣ ΛΟΓΑΡΙΑΣΜΟΣ/e-ΕΦΚΑ και αποτελεί απλή επεξεργασία των καταγεγραμμένων εγγραφών με σκοπό τη διευκόλυνση μελέτης του ασφ. ιστορικού του ασφαλισμένου. Η πλατφόρμα ΑΤΟΜΙΚΟΣ ΛΟΓΑΡΙΑΣΜΟΣ ή η ανάλυση από την εφαρμογή αυτή μπορεί να περιέχει κενά ή σφάλματα, και η αναφορά που εξάγεται δεν υποκαθιστά νομική ή οικονομική συμβουλή σε καμία περίπτωση. Αποκλειστικά υπεύθυνος για την επαλήθευση των στοιχείων είναι ο χρήστης. Για θέματα συνταξιοδότησης και οριστικές απαντήσεις αρμόδιος παραμένει αποκλειστικά ο e-ΕΦΚΑ.</div>
</body>
</html>"""
    return doc

def html_open_in_new_tab_component(html_content):
    """Επιστρέφει HTML snippet για iframe: κουμπί Εκτύπωση που ανοίγει το html_content σε νέα καρτέλα (blob URL)."""
    if not html_content:
        return ""
    # Ενσωμάτωση ως JS string: json.dumps + escape </script> ώστε να μην κλείνει το <script> του wrapper
    js_content = json.dumps(html_content).replace("</script>", "<\\/script>")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:6px 0;font-family:sans-serif;display:flex;justify-content:flex-end;">
<button type="button" id="openTabBtn" style="background:#dc3545;color:white;border:none;padding:14px 28px;border-radius:8px;cursor:pointer;font-weight:700;font-size:1.15rem;">Εκτύπωση</button>
<script>
(function() {{
  var htmlContent = {js_content};
  document.getElementById('openTabBtn').onclick = function() {{
    var blob = new Blob([htmlContent], {{ type: 'text/html;charset=utf-8' }});
    var url = URL.createObjectURL(blob);
    window.open(url, '_blank');
  }};
}})();
</script>
</body></html>"""

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

def load_dtk_table():
    """Φόρτωση πίνακα ΔΤΚ από εξωτερικό JSON αρχείο (dtk_table.json)."""
    import os
    dtk_path = os.path.join(os.path.dirname(__file__), "dtk_table.json")
    with open(dtk_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Μετατροπή κλειδιών σε int (έτος αναφοράς & έτος εισφοράς)
    return {int(ref_year): {int(k): v for k, v in factors.items()} for ref_year, factors in raw["data"].items()}

DTK_TABLE = load_dtk_table()


# --- Helper Functions ---
def load_data(uploaded_file):
    """Loads and parses the PDF file, returns two dataframes."""
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        df_monthly, df_annual = parse_efka_pdf(file_bytes)
        return df_monthly, df_annual
    return None, None

# --- Dialog: Επιβεβαίωση πακέτων πριν τον υπολογισμό ---
def _render_package_confirmation(all_pkgs, sel_pkgs, target_key):
    """Κοινή λογική για dialog επιβεβαίωσης πακέτων κάλυψης."""
    params = st.session_state.get(f"pension_params_{target_key}", {})

    # --- Πακέτα κάλυψης ---
    if sel_pkgs:
        included = sel_pkgs
        excluded = [p for p in all_pkgs if p not in sel_pkgs]
    else:
        included = all_pkgs
        excluded = []

    st.markdown("**Επιλεγμένα πακέτα κάλυψης για τον υπολογισμό:**")
    for p in included:
        st.markdown(f"&nbsp;&nbsp; ✅ &ensp;{p}")

    if excluded:
        st.markdown("**Αποκλεισμένα πακέτα κάλυψης:**")
        for p in excluded:
            st.markdown(f"&nbsp;&nbsp; ❌ &ensp;{p}")
    else:
        st.info("Συμπεριλαμβάνονται όλα τα διαθέσιμα πακέτα κάλυψης.")

    # --- Παράμετροι υπολογισμού ---
    st.markdown("---")
    st.markdown("**Παράμετροι υπολογισμού:**")
    dtk_year = params.get("dtk_year", "—")
    buyout_days = params.get("buyout_days", 0)
    buyout_amount = params.get("buyout_amount", 0.0)

    col_p1, col_p2, col_p3 = st.columns(3)
    col_p1.metric("Έτος αναφοράς ΔΤΚ", str(dtk_year))
    col_p2.metric("Ημέρες εξαγοράς", str(buyout_days) if buyout_days else "—")
    col_p3.metric("Ποσό εξαγοράς", format_currency_gr(buyout_amount) if buyout_amount else "—")

    st.markdown("---")
    st.markdown("**Θα συνεχίσετε με τον υπολογισμό;**")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Συνέχεια", use_container_width=True, type="primary", key=f"confirm_{target_key}"):
            st.session_state[f"pension_confirmed_{target_key}"] = True
            st.rerun()
    with col2:
        if st.button("Ακύρωση", use_container_width=True, key=f"cancel_{target_key}"):
            st.session_state.pop(f"pension_params_{target_key}", None)
            st.rerun()


@st.dialog("Επιβεβαίωση Υπολογισμού Κύριας", width="large")
def confirm_pension_kyrias():
    all_pkgs = st.session_state.get("all_packages_kyrias", [])
    sel_pkgs = st.session_state.get("selected_packages_kyrias", [])
    _render_package_confirmation(all_pkgs, sel_pkgs, "kyrias")


@st.dialog("Επιβεβαίωση Υπολογισμού Επικουρικής", width="large")
def confirm_pension_epik():
    all_pkgs = st.session_state.get("all_packages_epik", [])
    sel_pkgs = st.session_state.get("selected_packages_epik", [])
    _render_package_confirmation(all_pkgs, sel_pkgs, "epik")


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
    /* Hide Streamlit menu */
    #MainMenu {visibility: hidden;}
    header[data-testid="stHeader"] {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden;}
    button[title="View app source"] {display: none;}
    button[title="Report a bug"] {display: none;}
    button[title="Manage app"] {display: none;}
    div[data-testid="stDecoration"] {display: none;}
    footer {visibility: hidden;}
    /* DataFrame toolbar: above table + larger buttons */
    [data-testid="stElementToolbar"] {
        z-index: 9999 !important;
    }
    [data-testid="stElementToolbar"] button {
        min-width: 40px !important;
        min-height: 40px !important;
        padding: 10px !important;
    }
    [data-testid="stElementToolbar"] button svg {
        width: 22px !important;
        height: 22px !important;
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
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "Ανάλυση Κύριας",
            "Συντ. Αποδοχές Κύριας",
            "Ανάλυση Επικουρικής",
            "Συντ. Αποδοχές Επικουρικής",
            "Συνοπτικά Δεδομένα",
            "Στοιχεία χωρίς επεξεργασία"
        ])

        yearly_totals = None

        # --- Tab 1: Full Analysis ---
        with tab1:
            _col_title1, _col_warn1 = st.columns([3, 4])
            with _col_title1:
                st.header("Ανάλυση Κύριας Αποδοχών / Εισφορών / Πλαφόν")
            with _col_warn1:
                st.warning("⚠️ **Πριν προχωρήσετε, βεβαιωθείτε ότι έχετε επιλέξει τα σωστά Πακέτα Κάλυψης στο φίλτρο παρακάτω.** Η ανάλυση βασίζεται στα επιλεγμένα πακέτα.")

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

                # Αποθήκευση φιλτραρισμένων δεδομένων στο session_state
                st.session_state["filtered_analysis"] = filtered.copy()
                st.session_state["all_packages_kyrias"] = package_options
                st.session_state["selected_packages_kyrias"] = list(selected_package_labels)
                df_analysis = filtered.copy()
            elif "filtered_analysis" in st.session_state:
                # Χρήση αποθηκευμένων φιλτραρισμένων δεδομένων
                df_analysis = st.session_state["filtered_analysis"].copy()
            else:
                df_analysis = filtered.copy()

            # Αρχικοποίηση πακέτων αν δεν έχουν αποθηκευτεί ακόμα
            if "all_packages_kyrias" not in st.session_state:
                st.session_state["all_packages_kyrias"] = package_options
                st.session_state["selected_packages_kyrias"] = []

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
            # Περιγραφή πακέτου κάλυψης από τα ετήσια δεδομένα
            _pkg_map = {str(k): (v or '') for k, v in package_desc_map.items()}
            display_df['ΠΕΡΙΓΡΑΦΗ ΠΑΚΕΤΟΥ'] = (
                display_df['ΚΩΔ. ΠΑΚΕΤΟ ΚΑΛΥΨΗΣ'].astype(str).replace('nan', '').map(_pkg_map).fillna('')
            )
            # Κρατάμε σταθερά keys για την ομαδοποίηση πριν "κενώσουμε" τα πεδία
            display_df['ΕΤΟΣ_KEY'] = display_df['ΕΤΟΣ']
            display_df['ΠΕΡΙΟΔΟΣ_KEY'] = display_df['ΠΕΡΙΟΔΟΣ']

            # Ταξινόμηση για ομαδοποίηση ανά έτος και περίοδο
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
                'ΕΤΟΣ', 'ΠΕΡΙΟΔΟΣ', 'ΚΩΔ. ΠΑΚΕΤΟ ΚΑΛΥΨΗΣ', 'ΠΕΡΙΓΡΑΦΗ ΠΑΚΕΤΟΥ', 'ΗΜΕΡ. ΑΠΑΣΧ.', 'ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ',
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
            html_analysis = dataframe_to_printable_html(display_df_with_totals, "Ανάλυση Κύριας Αποδοχών / Εισφορών / Πλαφόν")
            if html_analysis:
                components.html(html_open_in_new_tab_component(html_analysis), height=56)

            yearly_totals = pd.DataFrame(yearly_totals_rows)
            # Αποθήκευση στο session_state μόνο αν εφαρμόστηκαν φίλτρα ή αν δεν υπάρχει ακόμα
            if apply_filters or "yearly_totals" not in st.session_state:
                st.session_state["yearly_totals"] = yearly_totals

        # --- Tab 2: Pensionable Earnings ---
        with tab2:
            st.header("Συντ. Αποδοχές Κύριας")

            # Διάβασμα από session_state
            yearly_totals = st.session_state.get("yearly_totals")

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

                # Ροή με dialog επιβεβαίωσης πακέτων
                if calculate:
                    # Αποθήκευση παραμέτρων φόρμας στο session_state
                    st.session_state["pension_params_kyrias"] = {
                        "dtk_year": selected_dtk_year,
                        "buyout_days": buyout_days,
                        "buyout_year": buyout_year,
                        "buyout_amount": buyout_amount,
                    }
                    confirm_pension_kyrias()

                run_kyrias = st.session_state.pop("pension_confirmed_kyrias", False)
                if not calculate and not run_kyrias:
                    st.info("Πατήστε «Υπολογισμός» για να εφαρμοστούν οι αλλαγές.")
                elif run_kyrias:
                    _p = st.session_state.get("pension_params_kyrias", {})
                    selected_dtk_year = _p.get("dtk_year", 2026)
                    buyout_days = _p.get("buyout_days", 0)
                    buyout_year = _p.get("buyout_year", 2026)
                    buyout_amount = _p.get("buyout_amount", 0.0)
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
                    html_pension = dataframe_to_printable_html(pension_display, "Συντάξιμες Αποδοχές Κύριας")
                    if html_pension:
                        components.html(html_open_in_new_tab_component(html_pension), height=56)

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
            else:
                st.warning("Δεν υπάρχουν συνοπτικά δεδομένα για τον υπολογισμό των συντάξιμων αποδοχών.")

        # --- Tab 3: Επικουρική Ανάλυση (2002-2014) ---
        yearly_totals_epik = None

        with tab3:
            _col_title3, _col_warn3 = st.columns([3, 4])
            with _col_title3:
                st.header("Ανάλυση Επικουρικής (2002-2014)")
            with _col_warn3:
                st.warning("⚠️ **Πριν προχωρήσετε, βεβαιωθείτε ότι έχετε επιλέξει τα σωστά Πακέτα Κάλυψης στο φίλτρο παρακάτω.** Η ανάλυση βασίζεται στα επιλεγμένα πακέτα.")

            df_analysis_epik = df_monthly.copy()
            period_str_epik = df_analysis_epik['ΠΕΡΙΟΔΟΣ'].astype(str).str.strip()
            period_str_epik = period_str_epik.str.replace(r'^(\d{1})/', r'0\1/', regex=True)
            df_analysis_epik['ΠΕΡΙΟΔΟΣ'] = period_str_epik
            period_dt_epik = pd.to_datetime(period_str_epik, format='%m/%Y', errors='coerce')
            df_analysis_epik['ΕΤΟΣ'] = period_dt_epik.dt.year.astype('Int64').astype(str)

            # Φιλτράρισμα μόνο για 2002-2014
            df_analysis_epik = df_analysis_epik[df_analysis_epik['ΕΤΟΣ'].isin([str(y) for y in range(2002, 2015)])]

            if df_analysis_epik.empty:
                st.warning("Δεν υπάρχουν δεδομένα για την περίοδο 2002-2014.")
            else:
                # Φίλτρα προβολής (κενό = όλα)
                available_years_epik = sorted([y for y in df_analysis_epik['ΕΤΟΣ'].dropna().unique()])
                year_options_epik = ['(Όλα)'] + available_years_epik

                type_codes_epik = sorted([str(t) for t in df_analysis_epik['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].dropna().unique()])
                type_label_map_epik = {
                    code: f"{code} - {APODOXES_DESCRIPTIONS.get(code, 'Άγνωστη Περιγραφή')}"
                    for code in type_codes_epik
                }
                type_options_epik = [type_label_map_epik[code] for code in type_codes_epik]
                type_label_to_code_epik = {label: code for code, label in type_label_map_epik.items()}

                package_codes_epik = sorted([str(p) for p in df_analysis_epik['ΚΩΔ. ΠΑΚΕΤΟ ΚΑΛΥΨΗΣ'].dropna().unique()])
                package_desc_map_epik = {}
                if df_annual is not None and not df_annual.empty:
                    package_desc_map_epik = (
                        df_annual.dropna(subset=['ΠΑΚ. ΚΑΛ.'])
                        .groupby('ΠΑΚ. ΚΑΛ.')['ΠΕΡΙΓΡΑΦΗ']
                        .first()
                        .to_dict()
                    )
                package_label_map_epik = {
                    code: f"{code} - {package_desc_map_epik.get(code, '').strip()}" if package_desc_map_epik.get(code) else code
                    for code in package_codes_epik
                }
                package_options_epik = [package_label_map_epik[code] for code in package_codes_epik]
                package_label_to_code_epik = {label: code for code, label in package_label_map_epik.items()}

                # Initialize session state for ceiling_type_epik
                if "ceiling_type_epik" not in st.session_state:
                    st.session_state["ceiling_type_epik"] = 'Παλιός'

                with st.form("filters_form_epik"):
                    col_e1, col_e2, col_e3, col_e4, col_e5, col_btn_e = st.columns([1, 1, 1, 2, 2, 1.5])
                    with col_e1:
                        ceiling_type_epik = st.selectbox(
                            "Πλαφόν",
                            ('Παλιός', 'Νέος'),
                            index=0 if st.session_state["ceiling_type_epik"] == 'Παλιός' else 1,
                            key="ceiling_type_select_epik"
                        )
                        st.session_state["ceiling_type_epik"] = ceiling_type_epik
                    with col_e2:
                        year_from_epik = st.selectbox("Έτος από", options=year_options_epik, index=0, key="year_from_epik")
                    with col_e3:
                        year_to_epik = st.selectbox("Έτος έως", options=year_options_epik, index=0, key="year_to_epik")
                    with col_e4:
                        selected_type_labels_epik = st.multiselect("Τύπος Αποδοχών", options=type_options_epik, default=[], key="type_epik")
                    with col_e5:
                        selected_package_labels_epik = st.multiselect("Πακέτο Κάλυψης", options=package_options_epik, default=[], key="package_epik")
                    with col_btn_e:
                        st.write("")  # Empty space for alignment
                        st.write("")  # Empty space for alignment
                        apply_filters_epik = st.form_submit_button("Εφαρμογή φίλτρων", use_container_width=True)

                # Εφαρμογή φίλτρων
                filtered_epik = df_analysis_epik.copy()
                if apply_filters_epik:
                    if year_from_epik != '(Όλα)' or year_to_epik != '(Όλα)':
                        min_year_epik = available_years_epik[0] if available_years_epik else None
                        max_year_epik = available_years_epik[-1] if available_years_epik else None
                        from_year_epik = year_from_epik if year_from_epik != '(Όλα)' else min_year_epik
                        to_year_epik = year_to_epik if year_to_epik != '(Όλα)' else max_year_epik
                        if from_year_epik and to_year_epik and from_year_epik > to_year_epik:
                            from_year_epik, to_year_epik = to_year_epik, from_year_epik
                        if from_year_epik and to_year_epik:
                            filtered_epik = filtered_epik[(filtered_epik['ΕΤΟΣ'] >= from_year_epik) & (filtered_epik['ΕΤΟΣ'] <= to_year_epik)]

                    if selected_type_labels_epik:
                        selected_types_epik = [type_label_to_code_epik[label] for label in selected_type_labels_epik]
                        filtered_epik = filtered_epik[filtered_epik['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str).isin(selected_types_epik)]

                    if selected_package_labels_epik:
                        selected_packages_epik = [package_label_to_code_epik[label] for label in selected_package_labels_epik]
                        filtered_epik = filtered_epik[filtered_epik['ΚΩΔ. ΠΑΚΕΤΟ ΚΑΛΥΨΗΣ'].astype(str).isin(selected_packages_epik)]

                    # Αποθήκευση φιλτραρισμένων δεδομένων στο session_state
                    st.session_state["filtered_analysis_epik"] = filtered_epik.copy()
                    st.session_state["all_packages_epik"] = package_options_epik
                    st.session_state["selected_packages_epik"] = list(selected_package_labels_epik)
                    df_analysis_epik = filtered_epik.copy()
                elif "filtered_analysis_epik" in st.session_state:
                    # Χρήση αποθηκευμένων φιλτραρισμένων δεδομένων
                    df_analysis_epik = st.session_state["filtered_analysis_epik"].copy()
                else:
                    df_analysis_epik = filtered_epik.copy()

                # Αρχικοποίηση πακέτων αν δεν έχουν αποθηκευτεί ακόμα
                if "all_packages_epik" not in st.session_state:
                    st.session_state["all_packages_epik"] = package_options_epik
                    st.session_state["selected_packages_epik"] = []

                # Υπολογισμός ΒΑΣΙΚΟ ΠΛΑΦΟΝ
                ceiling_type_epik = st.session_state.get("ceiling_type_epik", "Παλιός")
                ceiling_dict_epik = insurable_ceiling_old if ceiling_type_epik == 'Παλιός' else insurable_ceiling_new
                df_analysis_epik['ΒΑΣΙΚΟ ΠΛΑΦΟΝ'] = df_analysis_epik['ΕΤΟΣ'].map(ceiling_dict_epik).fillna(0)

                # Αποδοχές μήνα
                excluded_mask_epik = df_analysis_epik['ΠΕΡΙΓΡΑΦΗ_ΑΠΟΔΟΧΩΝ'].astype(str).str.contains(
                    r'δώρο|επίδομα\s+αδείας', case=False, regex=True
                ) | df_analysis_epik['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str).isin(['03', '04', '05'])
                df_analysis_epik['IS_SPECIAL'] = excluded_mask_epik
                monthly_earnings_epik = (
                    df_analysis_epik.loc[~excluded_mask_epik]
                    .groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΑΠΟΔΟΧΕΣ']
                    .sum()
                )
                df_analysis_epik['ΑΠΟΔΟΧΕΣ ΜΗΝΑ'] = df_analysis_epik['ΠΕΡΙΟΔΟΣ'].map(monthly_earnings_epik)

                # Υπολογισμός πλαφόν
                days_map_epik = (
                    df_analysis_epik.loc[df_analysis_epik['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str) == '01']
                    .groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΗΜΕΡ. ΑΠΑΣΧ.']
                    .max()
                )
                base_plafon_map_epik = (
                    df_analysis_epik.groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΒΑΣΙΚΟ ΠΛΑΦΟΝ']
                    .max()
                )
                plafon_month_map_epik = (base_plafon_map_epik / 25 * days_map_epik).clip(upper=base_plafon_map_epik)
                plafon_month_map_epik = plafon_month_map_epik.fillna(base_plafon_map_epik)

                df_analysis_epik['ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'] = df_analysis_epik['ΠΕΡΙΟΔΟΣ'].map(plafon_month_map_epik)
                df_analysis_epik.loc[df_analysis_epik['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str) == '03', 'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'] = df_analysis_epik['ΒΑΣΙΚΟ ΠΛΑΦΟΝ']
                df_analysis_epik.loc[df_analysis_epik['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str).isin(['04', '05']), 'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'] = df_analysis_epik['ΒΑΣΙΚΟ ΠΛΑΦΟΝ'] / 2

                monthly_plafon_epik = df_analysis_epik.groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'].max()
                monthly_insurable_epik = (df_analysis_epik['ΠΕΡΙΟΔΟΣ'].map(monthly_earnings_epik)
                                          .combine(df_analysis_epik['ΠΕΡΙΟΔΟΣ'].map(monthly_plafon_epik), min))
                df_analysis_epik['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = monthly_insurable_epik

                perikopi_map_epik = (df_analysis_epik['ΠΕΡΙΟΔΟΣ'].map(monthly_earnings_epik) -
                                     df_analysis_epik['ΠΕΡΙΟΔΟΣ'].map(monthly_plafon_epik))
                df_analysis_epik['ΠΕΡΙΚΟΠΗ'] = perikopi_map_epik.where(perikopi_map_epik > 0, None)

                df_analysis_epik.loc[df_analysis_epik['IS_SPECIAL'], 'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = df_analysis_epik.loc[
                    df_analysis_epik['IS_SPECIAL'], ['ΑΠΟΔΟΧΕΣ', 'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ']
                ].min(axis=1)
                df_analysis_epik.loc[df_analysis_epik['IS_SPECIAL'], 'ΠΕΡΙΚΟΠΗ'] = (
                    df_analysis_epik.loc[df_analysis_epik['IS_SPECIAL'], 'ΑΠΟΔΟΧΕΣ'] -
                    df_analysis_epik.loc[df_analysis_epik['IS_SPECIAL'], 'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ']
                ).where(lambda s: s > 0, None)

                df_analysis_epik['ΠΟΣΟΣΤΟ'] = df_analysis_epik.apply(
                    lambda row: (row['ΕΙΣΦΟΡΕΣ'] / row['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ']) * 100 if row['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] > 0 else 0,
                    axis=1
                )

                display_df_epik = df_analysis_epik.copy()
                # Περιγραφή πακέτου κάλυψης από τα ετήσια δεδομένα
                _pkg_map_epik = {str(k): (v or '') for k, v in package_desc_map_epik.items()}
                display_df_epik['ΠΕΡΙΓΡΑΦΗ ΠΑΚΕΤΟΥ'] = (
                    display_df_epik['ΚΩΔ. ΠΑΚΕΤΟ ΚΑΛΥΨΗΣ'].astype(str).replace('nan', '').map(_pkg_map_epik).fillna('')
                )
                display_df_epik['ΕΤΟΣ_KEY'] = display_df_epik['ΕΤΟΣ']
                display_df_epik['ΠΕΡΙΟΔΟΣ_KEY'] = display_df_epik['ΠΕΡΙΟΔΟΣ']
                display_df_epik['ΤΥΠΟΣ_SORT'] = display_df_epik['ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ'].astype(str)
                display_df_epik = display_df_epik.sort_values([
                    'ΕΤΟΣ_KEY', 'IS_SPECIAL', 'ΠΕΡΙΟΔΟΣ_KEY', 'ΤΥΠΟΣ_SORT'
                ])

                display_df_epik['ΕΤΟΣ'] = display_df_epik['ΕΤΟΣ'].where(~display_df_epik.duplicated(['ΕΤΟΣ_KEY']), '')
                display_df_epik['ΠΕΡΙΟΔΟΣ'] = display_df_epik['ΠΕΡΙΟΔΟΣ'].where(~display_df_epik.duplicated(['ΕΤΟΣ_KEY', 'ΠΕΡΙΟΔΟΣ_KEY']), '')

                show_month_total_epik = ~display_df_epik.duplicated(['ΕΤΟΣ_KEY', 'ΠΕΡΙΟΔΟΣ_KEY'])
                display_df_epik['ΑΠΟΔΟΧΕΣ ΜΗΝΑ'] = display_df_epik['ΑΠΟΔΟΧΕΣ ΜΗΝΑ'].where(show_month_total_epik, '')
                display_df_epik['ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'] = display_df_epik['ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ'].where(
                    show_month_total_epik | display_df_epik['IS_SPECIAL'], ''
                )
                display_df_epik['ΠΕΡΙΚΟΠΗ'] = display_df_epik['ΠΕΡΙΚΟΠΗ'].where(
                    show_month_total_epik | display_df_epik['IS_SPECIAL'], ''
                )
                display_df_epik['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = display_df_epik['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'].where(
                    show_month_total_epik | display_df_epik['IS_SPECIAL'], ''
                )

                visible_columns_epik = [
                    'ΕΤΟΣ', 'ΠΕΡΙΟΔΟΣ', 'ΚΩΔ. ΠΑΚΕΤΟ ΚΑΛΥΨΗΣ', 'ΠΕΡΙΓΡΑΦΗ ΠΑΚΕΤΟΥ', 'ΗΜΕΡ. ΑΠΑΣΧ.', 'ΤΥΠΟΣ ΑΠΟΔΟΧΩΝ',
                    'ΠΕΡΙΓΡΑΦΗ_ΑΠΟΔΟΧΩΝ', 'ΑΠΟΔΟΧΕΣ', 'ΕΙΣΦΟΡΕΣ', 'ΠΟΣΟΣΤΟ', 'ΑΠΟΔΟΧΕΣ ΜΗΝΑ',
                    'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ', 'ΠΕΡΙΚΟΠΗ', 'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'
                ]
                display_df_visible_epik = display_df_epik[visible_columns_epik]

                # Προσθήκη γραμμών σύνοψης ανά έτος
                rows_epik = []
                summary_flags_epik = []
                yearly_totals_rows_epik = []
                years_epik = sorted([y for y in display_df_epik['ΕΤΟΣ_KEY'].dropna().unique()])

                for year in years_epik:
                    year_mask = display_df_epik['ΕΤΟΣ_KEY'] == year
                    year_rows = display_df_visible_epik[year_mask]
                    for _, row in year_rows.iterrows():
                        rows_epik.append(row.to_dict())
                        summary_flags_epik.append(False)

                    totals_epik = df_analysis_epik[df_analysis_epik['ΕΤΟΣ'] == str(year)]
                    summary_row_epik = {col: '' for col in visible_columns_epik}
                    summary_row_epik['ΕΤΟΣ'] = f"ΣΥΝΟΛΟ {year}"
                    total_days_epik = totals_epik['ΗΜΕΡ. ΑΠΑΣΧ.'].sum()
                    total_apodoxes_epik = totals_epik['ΑΠΟΔΟΧΕΣ'].sum()
                    summary_row_epik['ΑΠΟΔΟΧΕΣ'] = round(total_apodoxes_epik, 2)
                    summary_row_epik['ΕΙΣΦΟΡΕΣ'] = round(totals_epik['ΕΙΣΦΟΡΕΣ'].sum(), 2)

                    perikopi_month_sum_epik = (
                        totals_epik.loc[~totals_epik['IS_SPECIAL']]
                        .groupby('ΠΕΡΙΟΔΟΣ', dropna=False)['ΠΕΡΙΚΟΠΗ']
                        .max()
                        .fillna(0)
                        .sum()
                    )
                    perikopi_special_sum_epik = totals_epik.loc[totals_epik['IS_SPECIAL'], 'ΠΕΡΙΚΟΠΗ'].fillna(0).sum()
                    total_perikopi_epik = perikopi_month_sum_epik + perikopi_special_sum_epik
                    total_insurable_epik = round(total_apodoxes_epik - total_perikopi_epik, 2)
                    summary_row_epik['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = total_insurable_epik
                    rows_epik.append(summary_row_epik)
                    summary_flags_epik.append(True)

                    yearly_totals_rows_epik.append({
                        'ΕΤΟΣ': year,
                        'ΗΜΕΡ. ΑΠΑΣΧ.': total_days_epik,
                        'ΑΠΟΔΟΧΕΣ': round(total_apodoxes_epik, 2),
                        'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ': total_insurable_epik
                    })

                    blank_row_epik = {col: '' for col in visible_columns_epik}
                    rows_epik.append(blank_row_epik)
                    summary_flags_epik.append(False)

                display_df_with_totals_epik = pd.DataFrame(rows_epik, columns=visible_columns_epik)
                display_df_with_totals_epik = round_float_columns(display_df_with_totals_epik)
                display_df_with_totals_epik = round_numeric_columns(
                    display_df_with_totals_epik,
                    columns=[
                        'ΑΠΟΔΟΧΕΣ', 'ΕΙΣΦΟΡΕΣ', 'ΠΟΣΟΣΤΟ', 'ΑΠΟΔΟΧΕΣ ΜΗΝΑ',
                        'ΕΙΣΦΟΡΙΣΙΜΟ ΠΛΑΦΟΝ', 'ΠΕΡΙΚΟΠΗ', 'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'
                    ],
                    decimals=2
                )
                for col in ['ΗΜΕΡ. ΑΠΑΣΧ.', 'ΕΙΣΦΟΡΕΣ', 'ΠΟΣΟΣΤΟ']:
                    if col in display_df_with_totals_epik.columns:
                        display_df_with_totals_epik[col] = display_df_with_totals_epik[col].replace(0, '')

                st.dataframe(display_df_with_totals_epik, use_container_width=True, hide_index=True)
                html_analysis_epik = dataframe_to_printable_html(display_df_with_totals_epik, "Ανάλυση Επικουρικής (2002-2014)")
                if html_analysis_epik:
                    components.html(html_open_in_new_tab_component(html_analysis_epik), height=56)

                yearly_totals_epik = pd.DataFrame(yearly_totals_rows_epik)
                if apply_filters_epik or "yearly_totals_epik" not in st.session_state:
                    st.session_state["yearly_totals_epik"] = yearly_totals_epik

        # --- Tab 4: Συντάξιμες Αποδοχές Επικουρικής ---
        with tab4:
            st.header("Συντ. Αποδοχές Επικουρικής")

            # Διάβασμα από session_state
            yearly_totals_epik = st.session_state.get("yearly_totals_epik")

            if yearly_totals_epik is not None and not yearly_totals_epik.empty:
                pension_df_epik = yearly_totals_epik.copy()
                pension_df_epik['ΕΤΟΣ'] = pd.to_numeric(pension_df_epik['ΕΤΟΣ'])

                dtk_year_options_epik = sorted(DTK_TABLE.keys(), reverse=True)
                default_dtk_index_epik = dtk_year_options_epik.index(2026) if 2026 in dtk_year_options_epik else 0
                buyout_year_options_epik = sorted([y for y in DTK_TABLE[dtk_year_options_epik[0]].keys() if y <= 2014], reverse=True)

                with st.form("pension_calc_form_epik"):
                    col_i1e, col_i2e, col_i3e, col_i4e = st.columns(4)
                    with col_i1e:
                        selected_dtk_year_epik = st.selectbox(
                            "Έτος Αναφοράς ΔΤΚ",
                            options=dtk_year_options_epik,
                            index=default_dtk_index_epik,
                            key="dtk_year_epik"
                        )
                    with col_i2e:
                        buyout_days_epik = st.number_input("Ημέρες Εξαγοράς", min_value=0, step=1, value=0, key="buyout_days_epik")
                    with col_i3e:
                        buyout_year_epik = st.selectbox("Έτος Εξαγοράς", options=buyout_year_options_epik, index=0, key="buyout_year_epik")
                    with col_i4e:
                        buyout_amount_epik = st.number_input("Ποσό Εξαγοράς", min_value=0.0, step=1.0, value=0.0, key="buyout_amount_epik")

                    calculate_epik = st.form_submit_button("Υπολογισμός")

                # Ροή με dialog επιβεβαίωσης πακέτων
                if calculate_epik:
                    st.session_state["pension_params_epik"] = {
                        "dtk_year": selected_dtk_year_epik,
                        "buyout_days": buyout_days_epik,
                        "buyout_year": buyout_year_epik,
                        "buyout_amount": buyout_amount_epik,
                    }
                    confirm_pension_epik()

                run_epik = st.session_state.pop("pension_confirmed_epik", False)
                if not calculate_epik and not run_epik:
                    st.info("Πατήστε «Υπολογισμός» για να εφαρμοστούν οι αλλαγές.")
                elif run_epik:
                    _pe = st.session_state.get("pension_params_epik", {})
                    selected_dtk_year_epik = _pe.get("dtk_year", 2026)
                    buyout_days_epik = _pe.get("buyout_days", 0)
                    buyout_year_epik = _pe.get("buyout_year", 2026)
                    buyout_amount_epik = _pe.get("buyout_amount", 0.0)
                    dtk_factors_epik = DTK_TABLE[selected_dtk_year_epik]
                    buyout_dtk_epik = dtk_factors_epik.get(buyout_year_epik, 1.0)
                    buyout_insurable_epik = buyout_amount_epik / 0.06

                    pension_df_epik['ΣΥΝΤΕΛΕΣΤΗΣ ΔΤΚ'] = pension_df_epik['ΕΤΟΣ'].map(dtk_factors_epik).fillna(1.0)
                    pension_df_epik['ΤΕΛΙΚΕΣ ΣΥΝΤΑΞΙΜΕΣ ΑΠΟΔΟΧΕΣ'] = (
                        pension_df_epik['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'] * pension_df_epik['ΣΥΝΤΕΛΕΣΤΗΣ ΔΤΚ']
                    )

                    if buyout_days_epik > 0 or buyout_amount_epik > 0:
                        pension_df_epik = pd.concat([
                            pension_df_epik,
                            pd.DataFrame([{
                                'ΕΤΟΣ': buyout_year_epik,
                                'ΗΜΕΡ. ΑΠΑΣΧ.': buyout_days_epik,
                                'ΑΠΟΔΟΧΕΣ': 0,
                                'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ': buyout_insurable_epik,
                                'ΣΥΝΤΕΛΕΣΤΗΣ ΔΤΚ': buyout_dtk_epik,
                                'ΤΕΛΙΚΕΣ ΣΥΝΤΑΞΙΜΕΣ ΑΠΟΔΟΧΕΣ': buyout_insurable_epik * buyout_dtk_epik,
                            }])
                        ], ignore_index=True)
                        pension_df_epik.loc[pension_df_epik.index[-1], 'ΕΤΟΣ'] = "ΕΞΑΓΟΡΑ"

                    total_days_epik_sum = pension_df_epik['ΗΜΕΡ. ΑΠΑΣΧ.'].sum()
                    total_pensionable_earnings_epik = pension_df_epik['ΤΕΛΙΚΕΣ ΣΥΝΤΑΞΙΜΕΣ ΑΠΟΔΟΧΕΣ'].sum()
                    months_from_2002_epik = total_days_epik_sum / 25 if total_days_epik_sum > 0 else 0
                    average_pensionable_salary_epik = (
                        total_pensionable_earnings_epik / months_from_2002_epik if months_from_2002_epik > 0 else 0
                    )

                    col1e, col2e, col3e, col4e = st.columns(4)
                    col1e.metric("Σύνολο Ημερών", format_number_gr(total_days_epik_sum, 0))
                    col2e.metric("Μήνες (2002-2014)", format_number_gr(months_from_2002_epik, 2))
                    col3e.metric("Σύνολο Συντάξιμων Αποδοχών", format_currency_gr(total_pensionable_earnings_epik))
                    col4e.metric("Μέσος Συντάξιμος Μισθός", format_currency_gr(average_pensionable_salary_epik))

                    pension_display_epik = format_df_for_display(
                        pension_df_epik,
                        currency_cols=['ΑΠΟΔΟΧΕΣ', 'ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ', 'ΤΕΛΙΚΕΣ ΣΥΝΤΑΞΙΜΕΣ ΑΠΟΔΟΧΕΣ'],
                        int_cols=['ΗΜΕΡ. ΑΠΑΣΧ.'],
                        float_cols_decimals={'ΣΥΝΤΕΛΕΣΤΗΣ ΔΤΚ': 5},
                    )
                    styled_pension_epik = pension_display_epik.style.set_properties(**{'text-align': 'left'}).set_table_styles(
                        [{'selector': 'th', 'props': [('text-align', 'left')]}]
                    )
                    st.dataframe(styled_pension_epik, use_container_width=True, hide_index=True)
                    html_pension_epik = dataframe_to_printable_html(pension_display_epik, "Συντάξιμες Αποδοχές Επικουρικής")
                    if html_pension_epik:
                        components.html(html_open_in_new_tab_component(html_pension_epik), height=56)

                    # --- Εξαγωγή JSON για Syntaksi Pro (Επικουρική) ---
                    st.markdown("---")
                    st.subheader("Εξαγωγή για Syntaksi Pro (Επικουρική)")

                    json_data_epik = {}
                    for _, row in pension_df_epik.iterrows():
                        year = row['ΕΤΟΣ']
                        if year == "ΕΞΑΓΟΡΑ":
                            continue
                        year_str = str(int(year)) if isinstance(year, (int, float)) else str(year)

                        json_data_epik[f"ika_{year_str}"] = {
                            "value": int(row['ΗΜΕΡ. ΑΠΑΣΧ.']),
                            "type": "number"
                        }
                        json_data_epik[f"apodoxes_{year_str}"] = {
                            "value": round(row['ΕΙΣΦΟΡΙΣΙΜΕΣ ΑΠΟΔΟΧΕΣ'], 2),
                            "type": "number"
                        }

                    json_data_epik["eksagorasmenes_imeres"] = {
                        "value": int(buyout_days_epik),
                        "type": "number"
                    }
                    json_data_epik["synoliko_poso_eksagoras"] = {
                        "value": round(buyout_amount_epik, 2),
                        "type": "number"
                    }
                    json_data_epik["dtk_eksagoras"] = {
                        "value": round(buyout_dtk_epik, 5),
                        "type": "number"
                    }
                    json_data_epik["dtk"] = {
                        "value": int(selected_dtk_year_epik),
                        "type": "number"
                    }
                    json_data_epik["etos_ethnikis"] = {
                        "value": int(selected_dtk_year_epik),
                        "type": "number"
                    }

                    json_str_epik = json.dumps(json_data_epik, indent=2, ensure_ascii=False)

                    col_json1e, col_json2e, col_json3e = st.columns([1, 2, 1])
                    with col_json2e:
                        st.download_button(
                            label="📥 Λήψη JSON Επικουρικής",
                            data=json_str_epik,
                            file_name="efka_epikouriki_syntaksi_pro.json",
                            mime="application/json",
                            use_container_width=True,
                            key="download_json_epik"
                        )
            else:
                st.warning("Δεν υπάρχουν δεδομένα για την περίοδο 2002-2014.")

        # --- Tab 5: Συνοπτικά Δεδομένα ---
        with tab5:
            st.header("Συνοπτικά Ετήσια Δεδομένα")
            if df_annual is not None and not df_annual.empty:
                df_annual_display = round_float_columns(df_annual)
                st.dataframe(df_annual_display, use_container_width=True, hide_index=True)
                html_annual = dataframe_to_printable_html(df_annual_display, "Συνοπτικά Ετήσια Δεδομένα")
                if html_annual:
                    components.html(html_open_in_new_tab_component(html_annual), height=56)
            else:
                st.warning("Δεν βρέθηκαν συνοπτικά ετήσια δεδομένα.")

        # --- Tab 6: Στοιχεία χωρίς επεξεργασία ---
        with tab6:
            st.header("Στοιχεία χωρίς επεξεργασία")
            df_monthly_display = round_float_columns(df_monthly)
            st.dataframe(df_monthly_display, use_container_width=True, hide_index=True)
            html_monthly = dataframe_to_printable_html(df_monthly_display, "Στοιχεία χωρίς επεξεργασία")
            if html_monthly:
                components.html(html_open_in_new_tab_component(html_monthly), height=56)

    elif uploaded_file:
        st.error("Δεν ήταν δυνατή η εξαγωγή δεδομένων από το αρχείο PDF. Βεβαιωθείτε ότι το αρχείο είναι έγκυρο.")

st.markdown("---")
st.markdown(
    """
    <div style="background:#f8f9fa; border-left:4px solid #6b73ff; padding:12px 16px; font-size:0.8rem; color:#374151; line-height:1.5;">
        <strong>ΣΗΜΑΝΤΙΚΉ ΣΗΜΕΙΩΣΗ:</strong> Η παρούσα αναφορά βασίζεται αποκλειστικά στα δεδομένα που εμφανίζονται στο αρχείο ΑΤΟΜΙΚΟΣ ΛΟΓΑΡΙΑΣΜΟΣ/e-ΕΦΚΑ και αποτελεί απλή επεξεργασία των καταγεγραμμένων εγγραφών με σκοπό τη διευκόλυνση μελέτης του ασφ. ιστορικού του ασφαλισμένου. Η πλατφόρμα ΑΤΟΜΙΚΟΣ ΛΟΓΑΡΙΑΣΜΟΣ ή η ανάλυση από την εφαρμογή αυτή μπορεί να περιέχει κενά ή σφάλματα, και η αναφορά που εξάγεται δεν υποκαθιστά νομική ή οικονομική συμβουλή σε καμία περίπτωση. Αποκλειστικά υπεύθυνος για την επαλήθευση των στοιχείων είναι ο χρήστης. Για θέματα συνταξιοδότησης και οριστικές απαντήσεις αρμόδιος παραμένει αποκλειστικά ο e-ΕΦΚΑ.
    </div>
    """,
    unsafe_allow_html=True,
)
