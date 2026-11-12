import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="ავტოპარკის ხარჯების დეშბორდი | შპს ენგადი",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS STYLING ---
st.markdown("""
<style>
    .main-header {
        font-size: 26px;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 4px;
    }
    .sub-header {
        font-size: 14px;
        color: #64748B;
        margin-bottom: 20px;
    }
    .metric-card {
        background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px 18px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-val {
        font-size: 24px;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-lbl {
        font-size: 12px;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        font-weight: 600;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# Standard months ordering and mapping
ALL_GEO_MONTHS = [
    'იანვარი', 'თებერვალი', 'მარტი', 'აპრილი', 'მაისი', 'ივნისი',
    'ივლისი', 'აგვისტო', 'სექტემბერი', 'ოქტომბერი', 'ნოემბერი', 'დეკემბერი'
]

MONTH_MAP_TO_GEO = {
    'january': 'იანვარი', 'jan': 'იანვარი', 'იანვარი': 'იანვარი',
    'february': 'თებერვალი', 'feb': 'თებერვალი', 'თებერვალი': 'თებერვალი',
    'march': 'მარტი', 'mar': 'მარტი', 'მარტი': 'მარტი',
    'april': 'აპრილი', 'apr': 'აპრილი', 'აპრილი': 'აპრილი',
    'may': 'მაისი', 'მაისი': 'მაისი',
    'june': 'ივნისი', 'jun': 'ივნისი', 'ივნისი': 'ივნისი',
    'july': 'ივლისი', 'jul': 'ივლისი', 'ივლისი': 'ივლისი',
    'august': 'აგვისტო', 'aug': 'აგვისტო', 'აგვისტო': 'აგვისტო',
    'september': 'სექტემბერი', 'sep': 'სექტემბერი', 'სექტემბერი': 'სექტემბერი',
    'october': 'ოქტომბერი', 'oct': 'ოქტომბერი', 'ოქტომბერი': 'ოქტომბერი',
    'november': 'ნოემბერი', 'nov': 'ნოემბერი', 'ნოემბერი': 'ნოემბერი',
    'december': 'დეკემბერი', 'dec': 'დეკემბერი', 'დეკემბერი': 'დეკემბერი',
}

def clean_number(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).replace('₾', '').replace('GEL', '').replace('gel', '').replace(' ', '').replace(',', '').strip()
    try:
        return float(val_str)
    except Exception:
        return 0.0

def normalize_month(val):
    if pd.isna(val):
        return 'უცნობი'
    s = str(val).strip().lower()
    return MONTH_MAP_TO_GEO.get(s, str(val).strip())

# --- ADAPTIVE COLUMN MAPPER ---
def standardize_dataframe(df):
    if df is None or df.empty:
        cols = ['თანხა_GEL', 'ხარჯის_დასახელება', 'თვე', 'ავტომობილის_№', 'მოდელი', 'გამოშვების_წელი', 'მომწოდებელი', 'სერია_№', 'კატეგორია']
        return pd.DataFrame(columns=cols)

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # If both 'მოდელი' and 'მარკა' exist (like in old CSV), rename 'მარკა' to brand and other to spec
    if 'მოდელი' in df.columns and 'მარკა' in df.columns:
        df = df.rename(columns={'მოდელი': 'სპეციფიკაცია', 'მარკა': 'მოდელი'})

    col_map = {}
    
    # 1. Amount
    for c in ['ფასი დღგ და აქციზის', 'ფასი დღგ და აქციზით', 'ფასი', 'თანხა_GEL', 'თანხა', 'თანხა (GEL)', 'Amount']:
        if c in df.columns:
            col_map[c] = 'თანხა_GEL'
            break

    # 2. Description
    for c in ['საქონელი / მომსახურება', 'საქონელი/მომსახურება', 'ხარჯის_დასახელება', 'აღწერა', 'საქონელი', 'მომსახურება', 'Description']:
        if c in df.columns:
            col_map[c] = 'ხარჯის_დასახელება'
            break

    # 3. Month
    for c in ['month', 'Month', 'თვე', 'Months']:
        if c in df.columns:
            col_map[c] = 'თვე'
            break

    # 4. Vehicle Plate
    for c in ['სრული ნომერი', 'ავტომობილის_№', 'ნომერი', 'მანქანის ნომერი', 'Plate']:
        if c in df.columns:
            col_map[c] = 'ავტომობილის_№'
            break

    # 5. Model / Brand
    if 'მოდელი' not in df.columns:
        for c in ['მარკა', 'Model', 'Brand']:
            if c in df.columns:
                col_map[c] = 'მოდელი'
                break

    # 6. Year
    for c in ['გამოშვების წელი', 'წელი', 'Year']:
        if c in df.columns:
            col_map[c] = 'გამოშვების_წელი'
            break

    # 7. Supplier
    for c in ['მომწოდებელი', 'კომპანია', 'Supplier']:
        if c in df.columns:
            col_map[c] = 'მომწოდებელი'
            break

    # 8. Invoice / Series
    for c in ['სერია №', 'სერია_№', 'ინვოისის_№', 'ინვოისი', 'Invoice']:
        if c in df.columns:
            col_map[c] = 'სერია_№'
            break

    # 9. Date
    for c in ['თარიღი', 'Date']:
        if c in df.columns:
            col_map[c] = 'თარიღი'
            break

    df = df.rename(columns=col_map)

    # Standardize types and fill missing
    if 'თანხა_GEL' not in df.columns:
        df['თანხა_GEL'] = 0.0
    else:
        df['თანხა_GEL'] = df['თანხა_GEL'].apply(clean_number)

    if 'ხარჯის_დასახელება' not in df.columns:
        df['ხარჯის_დასახელება'] = 'ხარჯი'
    else:
        df['ხარჯის_დასახელება'] = df['ხარჯის_დასახელება'].fillna('სხვა').astype(str)

    if 'თვე' not in df.columns:
        df['თვე'] = 'უცნობი'
    else:
        df['თვე'] = df['თვე'].apply(normalize_month)

    if 'ავტომობილის_№' not in df.columns:
        df['ავტომობილის_№'] = 'უცნობი'
    else:
        df['ავტომობილის_№'] = df['ავტომობილის_№'].fillna('უცნობი').astype(str).str.strip().str.upper()

    if 'მოდელი' not in df.columns:
        df['მოდელი'] = 'სხვა'
    else:
        df['მოდელი'] = df['მოდელი'].fillna('სხვა').astype(str).str.strip().str.upper()

    if 'გამოშვების_წელი' not in df.columns:
        df['გამოშვების_წელი'] = '—'
    else:
        df['გამოშვების_წელი'] = df['გამოშვების_წელი'].fillna('—').astype(str).str.replace('.0', '', regex=False).str.strip()

    if 'მომწოდებელი' not in df.columns:
        df['მომწოდებელი'] = 'თეგეტა მოტორსი'
    else:
        df['მომწოდებელი'] = df['მომწოდებელი'].fillna('სხვა').astype(str).str.strip()

    if 'სერია_№' not in df.columns:
        df['სერია_№'] = '—'
    else:
        df['სერია_№'] = df['სერია_№'].fillna('—').astype(str).str.strip()

    # Determine Category (Service vs Parts/Consumables)
    if 'კატეგორია' not in df.columns:
        def infer_category(txt):
            t = str(txt).lower()
            keywords_service = ['შეცვლა', 'მონტაჟი', 'მ/დ', 'დ/ა', 'სერვისი', 'რემონტი', 'გასწორება', 'შეკეთება', 'დიაგნოსტიკა', 'ჩარხვა', 'გარეცხვა', 'დაკერება', 'ბალანსირება', 'შეყრა']
            if any(k in t for k in keywords_service):
                return 'მომსახურება'
            return 'სათადარიგო ნაწილები / მასალები'
        df['კატეგორია'] = df['ხარჯის_დასახელება'].apply(infer_category)

    return df

# --- DATA LOADING (Google Sheets or Local CSV) ---
@st.cache_data(ttl=60)
def load_data():
    raw_source_df = None
    
    # 1. Try Google Sheets Connection via streamlit-gsheets
    try:
        from streamlit_gsheets import GSheetsConnection
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_sheet = conn.read(ttl=30)
        if df_sheet is not None and not df_sheet.empty:
            raw_source_df = df_sheet
    except Exception:
        pass

    # 2. Try direct public CSV URL if configured in secrets
    if raw_source_df is None or raw_source_df.empty:
        try:
            if "gsheet_url" in st.secrets:
                url = st.secrets["gsheet_url"]
                if "/edit" in url or "/view" in url:
                    sheet_id = url.split("/d/")[1].split("/")[0]
                    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                df_url = pd.read_csv(url)
                if not df_url.empty:
                    raw_source_df = df_url
        except Exception:
            pass

    # 3. Fallback to bundled local CSV
    if raw_source_df is None or raw_source_df.empty:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_csv = os.path.join(script_dir, "engadi_fleet_data.csv")
        if os.path.exists(local_csv):
            raw_source_df = pd.read_csv(local_csv)

    if raw_source_df is not None and not raw_source_df.empty:
        std_df = standardize_dataframe(raw_source_df)
        return std_df, raw_source_df.columns.tolist()

    # Empty fallback
    cols = ['თანხა_GEL', 'ხარჯის_დასახელება', 'თვე', 'ავტომობილის_№', 'მოდელი', 'გამოშვების_წელი', 'მომწოდებელი', 'სერია_№', 'კატეგორია']
    return pd.DataFrame(columns=cols), []

df_filtered_raw, original_cols = load_data()

# --- HEADER SECTION ---
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.markdown('<div class="main-header">🚛 შპს „ენგადი“ — ავტოპარკის ხარჯების მართვის პანელი</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">ავტოპარკის მომსახურებისა და შეძენილი ნაწილების კონსოლიდირებული ანალიტიკა</div>', unsafe_allow_html=True)

with col_head2:
    st.write("")
    if st.button("🔄 მონაცემების განახლება", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- SIDEBAR: NEW RECORD FORM ---
st.sidebar.markdown("### ➕ ახალი ხარჯის დამატება")
st.sidebar.caption("შეიყვანეთ ახალი ინვოისი ან ხარჯი პირდაპირ საიტიდან:")

# Extract unique existing values for smooth dropdowns
existing_models = sorted([m for m in df_filtered_raw['მოდელი'].unique() if m not in ['სხვა', '']]) if not df_filtered_raw.empty else ['MAN', 'FORD', 'FOTON', 'HYUNDAI', 'MERCEDES-BENZ', 'TOYOTA', 'ნახევარმისაბმელი']
existing_plates = sorted([p for p in df_filtered_raw['ავტომობილის_№'].unique() if p not in ['უცნობი', '']]) if not df_filtered_raw.empty else ['LA435AL', 'LA436AL', 'LA438AL', 'NA088BE', 'NA100BE', 'NA110BE']
existing_suppliers = sorted([s for s in df_filtered_raw['მომწოდებელი'].unique() if s not in ['სხვა', '']]) if not df_filtered_raw.empty else ['შპს თეგეტა მოტორსი', 'შპს ასკ-გრუპი', 'შპს ქ-მოტორსი']

with st.sidebar.form("add_record_form", clear_on_submit=True):
    new_month = st.selectbox("თვე (month)*", ALL_GEO_MONTHS, index=datetime.now().month - 1)
    new_inv = st.text_input("სერია / ინვოისის №*", placeholder="მაგ. 3004019125 ან ვა-ზე 9190611")
    new_date = st.date_input("თარიღი*", datetime.now())
    
    selected_p = st.selectbox("ავტომობილის № (სრული ნომერი)*", existing_plates + ["➕ ახალი ნომერი"])
    if selected_p == "➕ ახალი ნომერი":
        plate_val = st.text_input("ჩაწერეთ ახალი სახელმწიფო ნომერი*").strip().upper()
    else:
        plate_val = selected_p

    selected_m = st.selectbox("მოდელი / მარკა*", existing_models + ["➕ ახალი მოდელი"])
    if selected_m == "➕ ახალი მოდელი":
        model_val = st.text_input("ჩაწერეთ ახალი მოდელი/მარკა*").strip().upper()
    else:
        model_val = selected_m

    year_val = st.text_input("გამოშვების წელი*", "2021")
    
    selected_s = st.selectbox("მომწოდებელი*", existing_suppliers + ["➕ ახალი მომწოდებელი"])
    if selected_s == "➕ ახალი მომწოდებელი":
        supplier_val = st.text_input("ჩაწერეთ ახალი მომწოდებელი*").strip()
    else:
        supplier_val = selected_s

    new_desc = st.text_area("საქონელი / მომსახურება*", placeholder="მაგ. ზეთის შეცვლა, ჰაერის ფილტრი...")
    new_amount = st.number_input("ფასი დღგ და აქციზის (GEL)*", min_value=0.0, step=10.0, format="%.2f")

    submit_btn = st.form_submit_button("💾 ბაზაში შენახვა", use_container_width=True)

    if submit_btn:
        if not plate_val or not new_desc or new_amount <= 0:
            st.sidebar.error("გთხოვთ შეავსოთ ყველა სავალდებულო ველი სწორად!")
        else:
            # Check which column format the remote source uses
            has_gsheet_style = any('საქონელი' in c for c in original_cols)
            
            if has_gsheet_style or not original_cols:
                new_row = {
                    'საქონელი / მომსახურება': new_desc,
                    'ზომის ერთე': 'ცალი',
                    'რაოდ.': 1,
                    'ფასი დღგ და აქციზის': round(float(new_amount), 2),
                    'სერია №': str(new_inv),
                    'მომწოდებელი': str(supplier_val),
                    'month': new_month,
                    'თარიღი': str(new_date),
                    'ოპერაციის თარ.': str(new_date),
                    'სრული ნომერი': plate_val,
                    'გამოშვების წელი': str(year_val),
                    'ასაკი': '',
                    'მოდელი': model_val
                }
            else:
                new_row = {
                    'თვე': new_month,
                    'ინვოისის_№': str(new_inv),
                    'თარიღი': str(new_date),
                    'მარკა': model_val,
                    'წელი': str(year_val),
                    'ავტომობილის_№': plate_val,
                    'მოდელი': model_val,
                    'კატეგორია': 'მომსახურება' if any(k in new_desc.lower() for k in ['შეცვლა', 'სერვისი', 'მ/დ']) else 'სათადარიგო ნაწილები',
                    'ხარჯის_დასახელება': new_desc,
                    'თანხა_GEL': round(float(new_amount), 2)
                }
            
            # Try saving to Google Sheets
            try:
                from streamlit_gsheets import GSheetsConnection
                conn = st.connection("gsheets", type=GSheetsConnection)
                existing_data = conn.read()
                updated_df = pd.concat([existing_data, pd.DataFrame([new_row])], ignore_index=True)
                conn.update(data=updated_df)
            except Exception:
                pass

            # Always save to local backup CSV as well
            script_dir = os.path.dirname(os.path.abspath(__file__))
            backup_csv = os.path.join(script_dir, "engadi_fleet_data.csv")
            local_row = {
                'თვე': new_month,
                'ინვოისის_№': str(new_inv),
                'თარიღი': str(new_date),
                'მარკა': model_val,
                'წელი': str(year_val),
                'ავტომობილის_№': plate_val,
                'მოდელი': model_val,
                'კატეგორია': 'მომსახურება' if any(k in new_desc.lower() for k in ['შეცვლა', 'სერვისი', 'მ/დ']) else 'სათადარიგო ნაწილები',
                'ხარჯის_დასახელება': new_desc,
                'თანხა_GEL': round(float(new_amount), 2)
            }
            pd.DataFrame([local_row]).to_csv(backup_csv, mode='a', header=not os.path.exists(backup_csv), index=False, encoding='utf-8')

            st.sidebar.success(f"✅ ხარჯი წარმატებით დაემატა ({new_amount:,.2f} ₾)!")
            st.cache_data.clear()
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("💡 **ინსტრუქცია:** საიტზე შეყვანილი ახალი ხარჯი მომენტალურად ჩაიწერება Google Sheet-ში და აისახება დეშბორდზე.")

# --- TOP SLICERS / FILTERS (EXACTLY AS IN SCREENSHOT) ---
st.markdown("##### 🔍 ფილტრები (Slicers)")
f_col1, f_col2, f_col3, f_col4 = st.columns([2, 3, 2, 2])

with f_col1:
    all_models = sorted(df_filtered_raw['მოდელი'].dropna().unique().tolist())
    selected_models = st.multiselect("მოდელი (Model / Brand)", all_models, default=all_models)

with f_col2:
    months_in_data = [m for m in ALL_GEO_MONTHS if m in df_filtered_raw['თვე'].unique()]
    if not months_in_data:
        months_in_data = sorted(df_filtered_raw['თვე'].dropna().unique().tolist())
    selected_months = st.multiselect("Months (თვეები)", ALL_GEO_MONTHS, default=months_in_data)

with f_col3:
    all_plates = sorted(df_filtered_raw['ავტომობილის_№'].dropna().unique().tolist())
    selected_plates = st.multiselect("სრული ნომერი (Plate)", all_plates, default=all_plates)

with f_col4:
    all_suppliers = sorted(df_filtered_raw['მომწოდებელი'].dropna().unique().tolist())
    selected_suppliers = st.multiselect("მომწოდებელი (Supplier)", all_suppliers, default=all_suppliers)

# Apply Filters
df_view = df_filtered_raw.copy()
if selected_models:
    df_view = df_view[df_view['მოდელი'].isin(selected_models)]
if selected_months:
    df_view = df_view[df_view['თვე'].isin(selected_months)]
if selected_plates:
    df_view = df_view[df_view['ავტომობილის_№'].isin(selected_plates)]
if selected_suppliers:
    df_view = df_view[df_view['მომწოდებელი'].isin(selected_suppliers)]

# --- KPI METRIC CARDS ---
total_spend = df_view['თანხა_GEL'].sum() if not df_view.empty else 0.0
service_spend = df_view[df_view['კატეგორია'] == 'მომსახურება']['თანხა_GEL'].sum() if not df_view.empty else 0.0
parts_spend = df_view[df_view['კატეგორია'] != 'მომსახურება']['თანხა_GEL'].sum() if not df_view.empty else 0.0

top_car = "—"
if not df_view.empty:
    top_car_series = df_view.groupby('ავტომობილის_№')['თანხა_GEL'].sum().sort_values(ascending=False)
    if not top_car_series.empty:
        top_car = f"{top_car_series.index[0]} ({top_car_series.iloc[0]:,.2f} ₾)"

m1, m2, m3, m4 = st.columns(4)
m1.markdown(f'<div class="metric-card"><div class="metric-lbl">სულ ხარჯი (GEL)</div><div class="metric-val">{total_spend:,.2f} ₾</div></div>', unsafe_allow_html=True)
m2.markdown(f'<div class="metric-card"><div class="metric-lbl">მომსახურება (სერვისი)</div><div class="metric-val" style="color:#0284C7;">{service_spend:,.2f} ₾</div></div>', unsafe_allow_html=True)
m3.markdown(f'<div class="metric-card"><div class="metric-lbl">სათადარიგო ნაწილები</div><div class="metric-val" style="color:#D97706;">{parts_spend:,.2f} ₾</div></div>', unsafe_allow_html=True)
m4.markdown(f'<div class="metric-card"><div class="metric-lbl">ყველაზე ხარჯიანი მანქანა</div><div class="metric-val" style="font-size:17px; margin-top:5px; color:#DC2626;">{top_car}</div></div>', unsafe_allow_html=True)

st.write("")

# --- TABS FOR VIEWS ---
tab_matrix, tab_charts, tab_raw = st.tabs([
    "📊 კრებსითი მატრიცა (Pivot Table)",
    "📈 გრაფიკული ანალიტიკა",
    "📋 დეტალური რეესტრი (მონაცემები)"
])

# === TAB 1: PIVOT MATRIX (SCREENSHOT STYLE) ===
with tab_matrix:
    view_mode = st.radio(
        "ჩაშლის დონე:",
        ["სტანდარტული (მოდელი ➔ წელი ➔ ნომერი)", "სრული ჩაშლა (ხარჯის კონკრეტული სახეობებით)"],
        horizontal=True
    )
    
    active_months = [m for m in ALL_GEO_MONTHS if m in selected_months]

    if df_view.empty:
        st.warning("არჩეული ფილტრებით მონაცემები არ მოიძებნა.")
    else:
        if view_mode == "სტანდარტული (მოდელი ➔ წელი ➔ ნომერი)":
            index_cols = ['მოდელი', 'გამოშვების_წელი', 'ავტომობილის_№']
        else:
            index_cols = ['მოდელი', 'გამოშვების_წელი', 'ავტომობილის_№', 'ხარჯის_დასახელება']

        pivot = pd.pivot_table(
            df_view,
            values='თანხა_GEL',
            index=index_cols,
            columns='თვე',
            aggfunc='sum',
            fill_value=0.0
        )

        # Reorder month columns according to calendar order
        existing_cols = [c for c in active_months if c in pivot.columns]
        other_cols = [c for c in pivot.columns if c not in active_months and c != 'Grand Total']
        ordered_cols = existing_cols + other_cols
        pivot = pivot[ordered_cols]

        # Add Grand Total column
        pivot['Grand Total'] = pivot.sum(axis=1)

        # Sort by Grand Total descending
        pivot = pivot.sort_values(by='Grand Total', ascending=False)

        # Style table
        format_dict = {col: "{:,.2f} ₾" for col in pivot.columns}
        styled_pivot = pivot.style.format(format_dict).background_gradient(
            cmap="Blues", subset=['Grand Total']
        )

        st.dataframe(styled_pivot, use_container_width=True, height=520)

        # Summary Row block
        st.markdown("#### 📌 თვიური ჯამები:")
        totals_dict = {"პარამეტრი": "სულ თვეში (GEL)"}
        for col in ordered_cols:
            totals_dict[col] = f"{pivot[col].sum():,.2f} ₾"
        totals_dict["Grand Total"] = f"{pivot['Grand Total'].sum():,.2f} ₾"
        st.table(pd.DataFrame([totals_dict]).set_index("პარამეტრი"))

# === TAB 2: VISUAL CHARTS ===
with tab_charts:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 📅 თვიური ხარჯების დინამიკა")
        month_agg = df_view.groupby(['თვე', 'კატეგორია'])['თანხა_GEL'].sum().reset_index()
        month_agg['თვე_idx'] = month_agg['თვე'].apply(lambda x: ALL_GEO_MONTHS.index(x) if x in ALL_GEO_MONTHS else 99)
        month_agg = month_agg.sort_values('თვე_idx')

        fig_month = px.bar(
            month_agg,
            x='თვე',
            y='თანხა_GEL',
            color='კატეგორია',
            barmode='stack',
            color_discrete_map={'მომსახურება': '#0284C7', 'სათადარიგო ნაწილები / მასალები': '#F59E0B'},
            labels={'თანხა_GEL': 'თანხა (GEL)', 'თვე': 'თვე'}
        )
        fig_month.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_month, use_container_width=True)

    with c2:
        st.markdown("##### 🚛 ხარჯების განაწილება ავტომობილების მიხედვით")
        car_agg = df_view.groupby('ავტომობილის_№')['თანხა_GEL'].sum().reset_index().sort_values('თანხა_GEL', ascending=True)
        fig_car = px.bar(
            car_agg,
            x='თანხა_GEL',
            y='ავტომობილის_№',
            orientation='h',
            text_auto='.2s',
            color='თანხა_GEL',
            color_continuous_scale='Blues',
            labels={'თანხა_GEL': 'თანხა (GEL)', 'ავტომობილის_№': 'ავტომობილის №'}
        )
        fig_car.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
        st.plotly_chart(fig_car, use_container_width=True)

    st.markdown("---")
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("##### ⚙️ მომსახურება vs სათადარიგო ნაწილები")
        cat_pie = df_view.groupby('კატეგორია')['თანხა_GEL'].sum().reset_index()
        fig_pie = px.pie(
            cat_pie,
            names='კატეგორია',
            values='თანხა_GEL',
            hole=0.45,
            color='კატეგორია',
            color_discrete_map={'მომსახურება': '#0284C7', 'სათადარიგო ნაწილები / მასალები': '#F59E0B'}
        )
        fig_pie.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with c4:
        st.markdown("##### 🏷️ ხარჯები მოდელების / მარკების მიხედვით")
        brand_pie = df_view.groupby('მოდელი')['თანხა_GEL'].sum().reset_index()
        fig_brand = px.pie(
            brand_pie,
            names='მოდელი',
            values='თანხა_GEL',
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_brand.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_brand, use_container_width=True)

# === TAB 3: RAW DATA TABLE & EXPORT ===
with tab_raw:
    st.markdown("##### 📄 გაფილტრული რეესტრი")
    st.dataframe(df_view, use_container_width=True, height=450)
    
    csv_bytes = df_view.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 გაფილტრული მონაცემების გადმოწერა (CSV)",
        data=csv_bytes,
        file_name="engadi_filtered_expenses.csv",
        mime="text/csv"
    )
