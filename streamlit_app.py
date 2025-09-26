import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np
from fuzzywuzzy import fuzz, process
import streamlit as st
import requests
import io
from urllib.parse import quote
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Set page configuration
st.set_page_config(
    page_title="Hospital Data Analyzer",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for modern UI
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f4e79 0%, #2e86c1 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1.2rem;
        opacity: 0.9;
    }
    .facility-input-container {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        margin-bottom: 2rem;
    }
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
        border: 1px solid #e9ecef;
    }
    .metrics-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
    }
    .download-section {
        background: #e8f5e8;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #c3e6c3;
        margin-top: 2rem;
    }
    .stButton > button {
        background: linear-gradient(90deg, #1f4e79 0%, #2e86c1 100%);
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_azure_blob_data(debug_mode=False):
    """
    Fetch CSV files from Azure Blob Storage for hospital data.
    Uses Azure Blob SDK to properly list and access container contents.
    Returns a dictionary of dataframes keyed by folder name.
    """
    try:
        # Get Azure configuration from secrets
        azure_config = st.secrets.get("azure_blob", {})
        account_name = azure_config.get("account_name", "sthenry1117a697874616865")
        container_name = azure_config.get("container_name", "cmstest")
        sas_token = azure_config.get("sas_token")
        
        if not sas_token:
            st.error("❌ SAS token is required for container listing and data access")
            st.info("💡 Please add your SAS token to the Streamlit secrets configuration")
            return {}
        
        # Import Azure SDK
        from azure.storage.blob import BlobServiceClient
        
        # Create blob service client with SAS token
        account_url = f"https://{account_name}.blob.core.windows.net"
        blob_service_client = BlobServiceClient(account_url=account_url, credential=sas_token)
        container_client = blob_service_client.get_container_client(container_name)
        
        if debug_mode:
            st.info("🔍 Discovering hospital folders in Azure Blob Storage...")
        
        # List all blobs in the container to find hospital folders
        hospital_folders = set()
        all_blobs = []
        
        try:
            blob_list = container_client.list_blobs()
            
            import re
            # Updated pattern to account for container prefix and look for specific file
            hospital_pattern = re.compile(r'^cmstest/hospitals_\d{2}_\d{4}/Timely_and_Effective_Care-Hospital\.csv$')
            
            for blob in blob_list:
                all_blobs.append(blob.name)
                # Check if blob path matches the specific CSV file we need
                if hospital_pattern.match(blob.name):
                    # Extract folder name (remove cmstest/ prefix and keep hospitals_XX_XXXX)
                    folder_path = blob.name.replace('cmstest/', '').split('/')[0]
                    hospital_folders.add(folder_path)
            
            hospital_folders = sorted(list(hospital_folders))
            
            # Enhanced debug information for debug mode
            if debug_mode:
                st.info(f"🔍 Found {len(all_blobs)} total blobs in container")
                if len(all_blobs) > 0:
                    st.info(f"📁 Sample blob names: {', '.join(all_blobs[:5])}")
                    if len(all_blobs) > 5:
                        st.info(f"... and {len(all_blobs) - 5} more blobs")
                
                if hospital_folders:
                    st.success(f"✓ Found {len(hospital_folders)} hospital folders: {', '.join(hospital_folders)}")
                else:
                    st.warning("⚠ No hospital folders found matching pattern 'hospitals_XX_XXXX'")
                    st.info("💡 **Debug Info:**")
                    st.info(f"- Total blobs found: {len(all_blobs)}")
                    if all_blobs:
                        st.info(f"- First few blob names: {all_blobs[:10]}")
                        st.info("- Expected pattern: folders named like 'hospitals_01_2021/', 'hospitals_02_2022/', etc.")
                        st.info("- Check if your data is organized in folders or if folder names follow a different pattern")
                    else:
                        st.info("- Container appears to be empty")
                    return {}
            else:
                # Minimal info for non-debug mode
                if hospital_folders:
                    st.info(f"🔍 Found {len(hospital_folders)} hospital data folders")
                else:
                    st.warning("⚠ No hospital folders found")
                    return {}
                
        except Exception as e:
            st.error(f"❌ Error listing blobs: {str(e)}")
            return {}
        
        # Load data from discovered hospital folders
        data_dict = {}
        
        for folder in hospital_folders:
            # Use the full blob path including the container prefix
            csv_blob_name = f"cmstest/{folder}/Timely_and_Effective_Care-Hospital.csv"
            
            try:
                blob_client = container_client.get_blob_client(csv_blob_name)
                
                # Download blob content
                blob_data = blob_client.download_blob()
                csv_content = blob_data.content_as_text()
                
                # Parse CSV
                df = pd.read_csv(io.StringIO(csv_content))
                data_dict[folder] = df
                
                if debug_mode:
                    st.success(f"✓ Loaded {folder} ({len(df)} records) via Azure SDK")
                
            except UnicodeDecodeError as e:
                if debug_mode:
                    st.warning(f"⚠ Could not load {csv_blob_name}: 'utf-8' codec can't decode byte {hex(e.args[2])} in position {e.args[3]}: invalid start byte")
                continue
            except Exception as e:
                if debug_mode:
                    st.warning(f"⚠ Could not load {csv_blob_name}: {str(e)}")
                continue
        
        if not data_dict:
            st.error("❌ No hospital data files found")
            st.info("💡 Ensure each hospital folder contains 'Timely_and_Effective_Care-Hospital.csv'")
        elif debug_mode:
            # Show comprehensive debug summary
            st.markdown("### 📊 Available Data Analysis")
            if data_dict:
                # Combine all data for analysis
                all_data = pd.concat(list(data_dict.values()), ignore_index=True)
                available_measures = sorted(all_data['Measure ID'].dropna().unique())
                st.info(f"🔍 Found {len(available_measures)} measure types in data:")
                st.info(f"📋 Measure IDs: {', '.join(available_measures[:10])}")
                if len(available_measures) > 10:
                    st.info(f"... and {len(available_measures) - 10} more measures")
                
                # Show which target measures we're looking for
                target_measures = ['SEP_1', 'OP_18b', 'SEV_SH_3HR', 'SEV_SEP_6HR', 'SEP_SH_3HR', 'SEP_SH_6HR']
                found_targets = [m for m in target_measures if m in available_measures]
                missing_targets = [m for m in target_measures if m not in available_measures]
                
                if found_targets:
                    st.success(f"✅ Found target measures: {', '.join(found_targets)}")
                if missing_targets:
                    st.warning(f"⚠️ Missing target measures: {', '.join(missing_targets)}")
        
        return data_dict
        
    except Exception as e:
        st.error(f"❌ Error accessing Azure Blob Storage: {str(e)}")
        st.info("💡 **Troubleshooting:**")
        st.info("1. Verify SAS token has 'read' and 'list' permissions")
        st.info("2. Check that SAS token has not expired")
        st.info("3. Ensure container name and account name are correct")
        return {}

def find_facility_matches(user_facilities, available_facilities):
    """Find exact or fuzzy matches for user-provided facility names."""
    matched_facilities = []
    
    for user_facility in user_facilities:
        if user_facility in available_facilities:
            matched_facilities.append(user_facility)
            st.success(f"✓ Exact match: '{user_facility}'")
        else:
            best_match = process.extractOne(user_facility, available_facilities, scorer=fuzz.ratio)
            if best_match and best_match[1] > 70:
                matched_facilities.append(best_match[0])
                st.success(f"✓ Fuzzy match: '{user_facility}' → '{best_match[0]}' ({best_match[1]}%)")
            else:
                st.error(f"✗ No match for: '{user_facility}'")
    
    return matched_facilities

def create_interactive_plot(data, measure_id, title, y_label, y_range, selected_facilities=None, verbose=False):
    """Create interactive Plotly chart with facility selection."""
    
    # Debug: Show what we're looking for vs what we have
    if verbose:
        st.write(f"🔍 DEBUG: Looking for measure '{measure_id}'")
        st.write(f"📊 DEBUG: Available measures in data: {sorted(data['Measure ID'].unique())[:10]}...")
        st.write(f"📏 DEBUG: Total rows in data: {len(data)}")
    
    # Filter data for the specific measure
    measure_data = data[data['Measure ID'] == measure_id].copy()
    if verbose:
        st.write(f"📋 DEBUG: Found {len(measure_data)} rows for measure '{measure_id}'")
    
    if measure_data.empty:
        if verbose:
            st.write(f"❌ DEBUG: No data found for measure '{measure_id}'")
        return None
    
    # Clean data with detailed debugging
    if verbose:
        st.write(f"🧹 DEBUG: Before cleaning - {len(measure_data)} rows")
        
        # Check Score values
        score_values = measure_data['Score'].value_counts()
        st.write(f"📊 DEBUG: Score values: {dict(score_values.head())}")
    
    measure_data = measure_data[measure_data['Score'] != 'Not Available']
    if verbose:
        st.write(f"🚫 DEBUG: After removing 'Not Available' - {len(measure_data)} rows")
    
    measure_data = measure_data.dropna(subset=['Score', 'End Date'])
    if verbose:
        st.write(f"💧 DEBUG: After dropping NaN Score/End Date - {len(measure_data)} rows")
        
        # Check what Score values look like before conversion
        if not measure_data.empty:
            st.write(f"🔢 DEBUG: Sample Score values before conversion: {measure_data['Score'].head().tolist()}")
    
    measure_data['Score'] = pd.to_numeric(measure_data['Score'], errors='coerce')
    if verbose:
        st.write(f"🔄 DEBUG: After numeric conversion - {len(measure_data)} rows")
    
    measure_data = measure_data.dropna(subset=['Score'])
    if verbose:
        st.write(f"🧮 DEBUG: After dropping NaN converted scores - {len(measure_data)} rows")
    
    if measure_data.empty:
        if verbose:
            st.write(f"❌ DEBUG: All data filtered out during cleaning process")
        return None
    
    # Parse dates with debugging
    if verbose:
        st.write(f"📅 DEBUG: Before date parsing - {len(measure_data)} rows")
        if not measure_data.empty:
            st.write(f"📅 DEBUG: Sample End Date values: {measure_data['End Date'].head().tolist()}")
    
    try:
        # Try multiple date formats to handle both 2-digit and 4-digit years
        measure_data['End_Date_Parsed'] = pd.to_datetime(measure_data['End Date'], 
                                                        format='%m/%d/%Y', errors='coerce')
        
        # If 4-digit year format fails, try 2-digit year format
        if measure_data['End_Date_Parsed'].isna().all():
            measure_data['End_Date_Parsed'] = pd.to_datetime(measure_data['End Date'], 
                                                            format='%m/%d/%y', errors='coerce')
        
        # If both specific formats fail, try automatic inference
        if measure_data['End_Date_Parsed'].isna().all():
            measure_data['End_Date_Parsed'] = pd.to_datetime(measure_data['End Date'], 
                                                            infer_datetime_format=True, errors='coerce')
        
        if verbose:
            st.write(f"📅 DEBUG: After date parsing - {len(measure_data)} rows")
            
            # Check how many valid dates we got
            valid_dates = measure_data['End_Date_Parsed'].notna().sum()
            st.write(f"📅 DEBUG: Valid dates found: {valid_dates}")
        
        measure_data = measure_data.dropna(subset=['End_Date_Parsed'])
        if verbose:
            st.write(f"📅 DEBUG: After dropping invalid dates - {len(measure_data)} rows")
    except Exception as e:
        if verbose:
            st.write(f"❌ DEBUG: Date parsing failed with error: {str(e)}")
        return None
    
    if measure_data.empty:
        if verbose:
            st.write(f"❌ DEBUG: All data lost after date parsing")
        return None
    
    # Create Plotly figure with 3:2 aspect ratio
    fig = go.Figure()
    
    # Get unique facilities
    facilities = measure_data['Facility Name'].unique()
    colors = px.colors.qualitative.Set3
    
    # Add traces for each facility
    for i, facility in enumerate(facilities):
        facility_data = measure_data[measure_data['Facility Name'] == facility].sort_values('End_Date_Parsed')
        
        if not facility_data.empty:
            # Determine visibility based on selection
            visible = True
            if selected_facilities is not None:
                visible = facility in selected_facilities
                
            fig.add_trace(go.Scatter(
                x=facility_data['End_Date_Parsed'],
                y=facility_data['Score'],
                mode='lines+markers',
                name=facility,
                line=dict(color=colors[i % len(colors)], width=3),
                marker=dict(size=8, line=dict(width=2, color='white')),
                visible=visible,
                hovertemplate=f'<b>{facility}</b><br>' +
                            'Date: %{x}<br>' +
                            f'{y_label}: %{{y}}<br>' +
                            '<extra></extra>'
            ))
    
    # Update layout with 3:2 aspect ratio
    fig.update_layout(
        title={
            'text': title,
            'x': 0.5,
            'font': {'size': 18, 'color': '#1f4e79'}
        },
        xaxis_title="End Date",
        yaxis_title=y_label,
        yaxis=dict(range=y_range),
        width=900,  # 3:2 ratio
        height=600,
        template="plotly_white",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            font=dict(size=12)
        ),
        margin=dict(r=150)  # Extra space for legend
    )
    
    return fig

def create_combined_sepsis_plot(data, measures, title, selected_facilities=None, y_range=[0, 100]):
    """Create combined plot for multiple sepsis measures."""
    
    # Filter for sepsis measures
    sepsis_data = data[data['Measure ID'].isin(measures)].copy()
    
    if sepsis_data.empty:
        return None
    
    # Clean data
    sepsis_data = sepsis_data[sepsis_data['Score'] != 'Not Available']
    sepsis_data = sepsis_data.dropna(subset=['Score', 'End Date'])
    sepsis_data['Score'] = pd.to_numeric(sepsis_data['Score'], errors='coerce')
    sepsis_data = sepsis_data.dropna(subset=['Score'])
    
    if sepsis_data.empty:
        return None
    
    # Parse dates with multiple format support
    try:
        # Try 4-digit year format first (matches your data)
        sepsis_data['End_Date_Parsed'] = pd.to_datetime(sepsis_data['End Date'], 
                                                       format='%m/%d/%Y', errors='coerce')
        
        # If 4-digit year format fails, try 2-digit year format
        if sepsis_data['End_Date_Parsed'].isna().all():
            sepsis_data['End_Date_Parsed'] = pd.to_datetime(sepsis_data['End Date'], 
                                                           format='%m/%d/%y', errors='coerce')
        
        # If both specific formats fail, try automatic inference
        if sepsis_data['End_Date_Parsed'].isna().all():
            sepsis_data['End_Date_Parsed'] = pd.to_datetime(sepsis_data['End Date'], 
                                                           infer_datetime_format=True, errors='coerce')
        
        sepsis_data = sepsis_data.dropna(subset=['End_Date_Parsed'])
    except:
        return None
    
    if sepsis_data.empty:
        return None
    
    # Create figure
    fig = go.Figure()
    
    facilities = sepsis_data['Facility Name'].unique()
    colors = px.colors.qualitative.Set3
    
    # Line styles for different measures
    line_styles = ['solid', 'dash', 'dot', 'dashdot']
    
    for i, facility in enumerate(facilities):
        for j, measure in enumerate(measures):
            measure_data = sepsis_data[
                (sepsis_data['Facility Name'] == facility) & 
                (sepsis_data['Measure ID'] == measure)
            ].sort_values('End_Date_Parsed')
            
            if not measure_data.empty:
                visible = True
                if selected_facilities is not None:
                    visible = facility in selected_facilities
                
                fig.add_trace(go.Scatter(
                    x=measure_data['End_Date_Parsed'],
                    y=measure_data['Score'],
                    mode='lines+markers',
                    name=f"{facility} - {measure}",
                    line=dict(
                        color=colors[i % len(colors)], 
                        width=3,
                        dash=line_styles[j % len(line_styles)]
                    ),
                    marker=dict(size=8, line=dict(width=2, color='white')),
                    visible=visible,
                    hovertemplate=f'<b>{facility} - {measure}</b><br>' +
                                'Date: %{x}<br>' +
                                'Score: %{y}%<br>' +
                                '<extra></extra>'
                ))
    
    # Update layout
    fig.update_layout(
        title={
            'text': title,
            'x': 0.5,
            'font': {'size': 18, 'color': '#1f4e79'}
        },
        xaxis_title="End Date",
        yaxis_title="Score (%)",
        yaxis=dict(range=y_range),
        width=900,
        height=600,
        template="plotly_white",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            font=dict(size=10)
        ),
        margin=dict(r=200)
    )
    
    return fig

def main():
    # Main header
    st.markdown("""
    <div class="main-header">
        <h1>🏥 Hospital Data Analyzer</h1>
        <p>Analyze Hospital Performance Data from Azure Blob Storage</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Facility input section
    st.markdown("""
    <div class="facility-input-container">
        <h3 style="margin-top: 0; color: #1f4e79;">🏥 Select Healthcare Facilities</h3>
        <p style="margin-bottom: 1rem; color: #6c757d;">Enter the names of hospitals/facilities you want to analyze (separated by commas)</p>
    </div>
    """, unsafe_allow_html=True)
    
    facilities_input = st.text_area(
        "Facility Names",
        placeholder="Enter facility names, separated by commas (e.g., Mayo Clinic, Johns Hopkins Hospital, Cleveland Clinic)",
        help="Enter the names of hospitals/facilities you want to analyze",
        key="facilities",
        label_visibility="collapsed"
    )
    
    # Debug mode toggle
    with st.expander("⚙️ Advanced Settings", expanded=False):
        verbose_mode = st.checkbox("🔍 Enable Verbose Debug Output", value=False, 
                                 help="Show detailed debugging information during data processing")
    
    # Analysis button
    analyze_button = st.button("🔍 Analyze Hospital Data", type="primary", use_container_width=True)
    
    if analyze_button:
        if not facilities_input.strip():
            st.error("⚠️ Please enter at least one facility name.")
            return
        
        # Parse facility names
        user_facility_list = [name.strip() for name in facilities_input.split(',') if name.strip()]
        
        with st.spinner("🔄 Fetching data from Azure Blob Storage..."):
            # Fetch data from Azure Blob
            data_dict = fetch_azure_blob_data(debug_mode=verbose_mode)
            
            if not data_dict:
                st.error("❌ No data could be loaded from Azure Blob Storage.")
                return
            
            # Combine all data
            all_data = []
            for folder, df in data_dict.items():
                all_data.append(df)
            
            if not all_data:
                st.error("❌ No valid data found.")
                return
            
            combined_data = pd.concat(all_data, ignore_index=True)
            combined_data.drop_duplicates(inplace=True)
            
            # Get all available facilities
            all_facilities = set(combined_data['Facility Name'].dropna().unique())
            
            # Debug: Show available measure IDs
            st.markdown("### 📊 Available Data Analysis")
            available_measures = sorted(combined_data['Measure ID'].dropna().unique())
            st.info(f"🔍 Found {len(available_measures)} measure types in data:")
            st.info(f"📋 Measure IDs: {', '.join(available_measures[:10])}")
            if len(available_measures) > 10:
                st.info(f"... and {len(available_measures) - 10} more measures")
            
            # Show which target measures we're looking for
            target_measures = ['SEP_1', 'OP_18b', 'SEV_SH_3HR', 'SEV_SEP_6HR', 'SEP_SH_3HR', 'SEP_SH_6HR']
            found_targets = [m for m in target_measures if m in available_measures]
            missing_targets = [m for m in target_measures if m not in available_measures]
            
            if found_targets:
                st.success(f"✅ Found target measures: {', '.join(found_targets)}")
            if missing_targets:
                st.warning(f"⚠️ Missing target measures: {', '.join(missing_targets)}")
            
            st.markdown("### 🔍 Facility Matching Results")
            facility_list = find_facility_matches(user_facility_list, all_facilities)
            
            if not facility_list:
                st.error("❌ No suitable facility matches found. Please check facility names and try again.")
                return
            
            # Filter data for selected facilities
            result_df = combined_data[combined_data['Facility Name'].isin(facility_list)]
            
            if result_df.empty:
                st.error("❌ No data found for the selected facilities.")
                return
            
            # Display metrics
            st.markdown("### 📊 Data Overview")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("""
                <div class="metrics-container">
                    <h3 style="margin: 0;">{}</h3>
                    <p style="margin: 0;">Total Records</p>
                </div>
                """.format(len(result_df)), unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div class="metrics-container">
                    <h3 style="margin: 0;">{}</h3>
                    <p style="margin: 0;">Facilities</p>
                </div>
                """.format(len(facility_list)), unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                <div class="metrics-container">
                    <h3 style="margin: 0;">{}</h3>
                    <p style="margin: 0;">Measure Types</p>
                </div>
                """.format(result_df['Measure ID'].nunique()), unsafe_allow_html=True)
            
            with col4:
                st.markdown("""
                <div class="metrics-container">
                    <h3 style="margin: 0;">{}</h3>
                    <p style="margin: 0;">Data Sources</p>
                </div>
                """.format(len(data_dict)), unsafe_allow_html=True)
            
            # Facility selection for charts
            st.markdown("### 🎯 Select Facilities for Visualization")
            selected_facilities = st.multiselect(
                "Choose which facilities to display in charts:",
                options=facility_list,
                default=facility_list[:3] if len(facility_list) > 3 else facility_list,
                help="Select specific facilities to display in the charts. You can select/deselect by clicking on the legend items."
            )
            
            if not selected_facilities:
                st.warning("⚠️ Please select at least one facility for visualization.")
                return
            
            # Filter data for selected facilities
            chart_data = result_df[result_df['Facility Name'].isin(selected_facilities)]
            
            # Generate interactive charts
            st.markdown("### 📈 Interactive Visualizations")
            
            # SEP_1 Analysis
            st.markdown("""
            <div class="chart-container">
                <h4 style="margin-top: 0; color: #1f4e79;">🔬 SEP_1 Analysis - Sepsis Care Performance</h4>
            </div>
            """, unsafe_allow_html=True)
            
            sep1_fig = create_interactive_plot(
                chart_data, 'SEP_1', 'SEP_1 Score Over Time', 'SEP_1 Score (%)', [0, 100], selected_facilities, verbose_mode
            )
            
            if sep1_fig:
                st.plotly_chart(sep1_fig, use_container_width=True)
                
                # Pre-generate PNG content to avoid re-runs and ensure kaleido is working
                try:
                    # Import and configure kaleido/plotly
                    import plotly.io as pio
                    
                    # Try to generate PNG image in advance
                    sep1_png_bytes = sep1_fig.to_image(format="png", width=900, height=600, scale=2, engine="kaleido")
                    png_success = True
                    png_error = None
                except Exception as e:
                    png_success = False
                    png_error = str(e)
                    # Generate HTML as fallback
                    sep1_html_str = pio.to_html(sep1_fig, include_plotlyjs='cdn')
                
                # Download button for SEP_1
                col1, col2 = st.columns([1, 4])
                with col1:
                    if png_success:
                        st.download_button(
                            label="💾 Save SEP_1 Chart",
                            data=sep1_png_bytes,
                            file_name=f"SEP_1_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                            mime="image/png",
                            key="download_sep1",
                            help="Click to save the SEP_1 chart as a high-quality PNG image"
                        )
                    else:
                        st.download_button(
                            label="💾 Save SEP_1 Chart (HTML)",
                            data=sep1_html_str,
                            file_name=f"SEP_1_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                            mime="text/html",
                            key="download_sep1",
                            help="PNG generation failed - downloading as interactive HTML chart"
                        )
                        st.warning(f"⚠️ PNG generation failed: {png_error}")
                        st.info("💡 Install kaleido with: `pip install kaleido` for PNG support")
            else:
                st.warning("⚠️ No SEP_1 data available for selected facilities.")
            
            # OP_18b Analysis
            st.markdown("""
            <div class="chart-container">
                <h4 style="margin-top: 0; color: #1f4e79;">⏱️ OP_18b Analysis - Time in Emergency Department</h4>
            </div>
            """, unsafe_allow_html=True)
            
            op18b_fig = create_interactive_plot(
                chart_data, 'OP_18b', 'Time in Emergency Department', 'Time in ED (minutes)', [60, 250], selected_facilities, verbose_mode
            )
            
            if op18b_fig:
                st.plotly_chart(op18b_fig, use_container_width=True)
                
                # Pre-generate PNG content to avoid re-runs and ensure kaleido is working
                try:
                    # Import and configure kaleido/plotly
                    import plotly.io as pio
                    
                    # Try to generate PNG image in advance
                    op18b_png_bytes = op18b_fig.to_image(format="png", width=900, height=600, scale=2, engine="kaleido")
                    png_success = True
                    png_error = None
                except Exception as e:
                    png_success = False
                    png_error = str(e)
                    # Generate HTML as fallback
                    op18b_html_str = pio.to_html(op18b_fig, include_plotlyjs='cdn')
                
                # Download button for OP_18b
                col1, col2 = st.columns([1, 4])
                with col1:
                    if png_success:
                        st.download_button(
                            label="💾 Save OP_18b Chart",
                            data=op18b_png_bytes,
                            file_name=f"OP_18b_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                            mime="image/png",
                            key="download_op18b",
                            help="Click to save the OP_18b chart as a high-quality PNG image"
                        )
                    else:
                        st.download_button(
                            label="💾 Save OP_18b Chart (HTML)",
                            data=op18b_html_str,
                            file_name=f"OP_18b_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                            mime="text/html",
                            key="download_op18b",
                            help="PNG generation failed - downloading as interactive HTML chart"
                        )
                        st.warning(f"⚠️ PNG generation failed: {png_error}")
                        st.info("💡 Install kaleido with: `pip install kaleido` for PNG support")
            else:
                st.warning("⚠️ No OP_18b data available for selected facilities.")
            
            # Severe Sepsis Analysis
            st.markdown("""
            <div class="chart-container">
                <h4 style="margin-top: 0; color: #1f4e79;">🚨 Severe Sepsis Analysis - Critical Care Measures</h4>
            </div>
            """, unsafe_allow_html=True)
            
            severe_sepsis_fig = create_combined_sepsis_plot(
                chart_data, ['SEV_SH_3HR', 'SEV_SEP_6HR'], 'Severe Sepsis Measures Over Time', selected_facilities, [0, 150]
            )
            
            if severe_sepsis_fig:
                st.plotly_chart(severe_sepsis_fig, use_container_width=True)
                
                # Pre-generate PNG content to avoid re-runs and ensure kaleido is working
                try:
                    # Import and configure kaleido/plotly
                    import plotly.io as pio
                    
                    # Try to generate PNG image in advance
                    severe_sepsis_png_bytes = severe_sepsis_fig.to_image(format="png", width=900, height=600, scale=2, engine="kaleido")
                    png_success = True
                    png_error = None
                except Exception as e:
                    png_success = False
                    png_error = str(e)
                    # Generate HTML as fallback
                    severe_sepsis_html_str = pio.to_html(severe_sepsis_fig, include_plotlyjs='cdn')
                
                # Download button for Severe Sepsis
                col1, col2 = st.columns([1, 4])
                with col1:
                    if png_success:
                        st.download_button(
                            label="💾 Save Severe Sepsis Chart",
                            data=severe_sepsis_png_bytes,
                            file_name=f"Severe_Sepsis_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                            mime="image/png",
                            key="download_severe",
                            help="Click to save the Severe Sepsis chart as a high-quality PNG image"
                        )
                    else:
                        st.download_button(
                            label="💾 Save Severe Sepsis Chart (HTML)",
                            data=severe_sepsis_html_str,
                            file_name=f"Severe_Sepsis_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                            mime="text/html",
                            key="download_severe",
                            help="PNG generation failed - downloading as interactive HTML chart"
                        )
                        st.warning(f"⚠️ PNG generation failed: {png_error}")
                        st.info("💡 Install kaleido with: `pip install kaleido` for PNG support")
            else:
                st.warning("⚠️ No severe sepsis data available for selected facilities.")
            
            # Sepsis Shock Analysis
            st.markdown("""
            <div class="chart-container">
                <h4 style="margin-top: 0; color: #1f4e79;">💔 Sepsis Shock Analysis - Emergency Response Measures</h4>
            </div>
            """, unsafe_allow_html=True)
            
            sepsis_fig = create_combined_sepsis_plot(
                chart_data, ['SEP_SH_3HR', 'SEP_SH_6HR'], 'Sepsis Shock Measures Over Time', selected_facilities
            )
            
            if sepsis_fig:
                st.plotly_chart(sepsis_fig, use_container_width=True)
                
                # Pre-generate PNG content to avoid re-runs and ensure kaleido is working
                try:
                    # Import and configure kaleido/plotly
                    import plotly.io as pio
                    
                    # Try to generate PNG image in advance
                    sepsis_png_bytes = sepsis_fig.to_image(format="png", width=900, height=600, scale=2, engine="kaleido")
                    png_success = True
                    png_error = None
                except Exception as e:
                    png_success = False
                    png_error = str(e)
                    # Generate HTML as fallback
                    sepsis_html_str = pio.to_html(sepsis_fig, include_plotlyjs='cdn')
                
                # Download button for Sepsis Shock
                col1, col2 = st.columns([1, 4])
                with col1:
                    if png_success:
                        st.download_button(
                            label="💾 Save Sepsis Shock Chart",
                            data=sepsis_png_bytes,
                            file_name=f"Sepsis_Shock_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                            mime="image/png",
                            key="download_sepsis",
                            help="Click to save the Sepsis Shock chart as a high-quality PNG image"
                        )
                    else:
                        st.download_button(
                            label="💾 Save Sepsis Shock Chart (HTML)",
                            data=sepsis_html_str,
                            file_name=f"Sepsis_Shock_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                            mime="text/html",
                            key="download_sepsis",
                            help="PNG generation failed - downloading as interactive HTML chart"
                        )
                        st.warning(f"⚠️ PNG generation failed: {png_error}")
                        st.info("💡 Install kaleido with: `pip install kaleido` for PNG support")
            else:
                st.warning("⚠️ No sepsis shock data available for selected facilities.")
            
            # Download aggregated data
            st.markdown("""
            <div class="download-section">
                <h4 style="margin-top: 0; color: #1f4e79;">📥 Download Aggregated Data</h4>
                <p>Download the complete aggregated dataset for the selected facilities.</p>
            </div>
            """, unsafe_allow_html=True)
            
            csv_data = result_df.to_csv(index=False)
            st.download_button(
                label="📊 Download Complete Dataset (CSV)",
                data=csv_data,
                file_name=f"Hospital_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # Data preview
            with st.expander("👀 Preview Data (First 10 Rows)", expanded=False):
                st.dataframe(result_df.head(10), use_container_width=True)
            
            st.success("✅ Analysis completed successfully!")
    
    # Information section
    with st.expander("ℹ️ About This Application", expanded=False):
        st.markdown("""
        ### 🏥 Hospital Data Analyzer
        
        **Features:**
        - 🔗 **Azure Blob Integration**: Automatically fetches data from Azure Blob Storage
        - 🎯 **Smart Facility Matching**: Fuzzy search for hospital names
        - 📊 **Interactive Charts**: Click legend items to show/hide facilities
        - 💾 **Individual Downloads**: Save each chart separately
        - 📱 **Responsive Design**: Works on desktop and mobile
        
        **Supported Measures:**
        - **SEP_1**: Sepsis care performance metrics
        - **OP_18b**: Emergency department wait times
        - **SEV_SH_3HR & SEV_SEP_6HR**: Severe sepsis care protocols
        - **SEP_SH_3HR & SEP_SH_6HR**: Sepsis shock response times
        
        **Data Source:** CMS Hospital Compare data stored in Azure Blob Storage
        
        **Chart Features:**
        - 3:2 aspect ratio for professional presentation
        - Interactive legends for facility selection
        - Hover tooltips for detailed information
        - High-resolution downloads (300 DPI)
        """)

if __name__ == "__main__":
    main()
