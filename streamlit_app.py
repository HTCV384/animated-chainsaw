import os
import pandas as pd
import glob
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np
from fuzzywuzzy import fuzz, process
import streamlit as st
import zipfile
import io
import tempfile
import shutil

# Set page configuration
st.set_page_config(
    page_title="Hospital Data Analyzer",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

def truncate_title(title, max_length=60):
    """
    Truncate plot title to fit within a reasonable character limit.
    
    Args:
        title: Original title string
        max_length: Maximum number of characters (default 60)
    
    Returns:
        Truncated title with ellipsis if needed
    """
    if len(title) <= max_length:
        return title
    return title[:max_length-3] + "..."

def wrap_legend_text(text, max_length=25):
    """
    Wrap legend text to prevent legend from taking too much space.
    Does not truncate - only wraps long text to multiple lines.
    
    Args:
        text: Original legend text
        max_length: Maximum characters per line (default 25)
    
    Returns:
        Wrapped text with line breaks
    """
    if len(text) <= max_length:
        return text
    
    # Find a good break point (prefer breaking at spaces, hyphens, or underscores)
    break_chars = [' ', '-', '_']
    best_break = max_length
    
    for char in break_chars:
        pos = text.rfind(char, 0, max_length)
        if pos > max_length // 2:  # Don't break too early
            best_break = pos
            break
    
    if best_break == max_length:
        # No good break point found, force break at max_length
        return text[:max_length] + '\n' + wrap_legend_text(text[max_length:], max_length)
    else:
        # Break at the good position and continue with next line
        return text[:best_break] + '\n' + wrap_legend_text(text[best_break+1:], max_length)

def create_sep1_plots(result_df, facility_list, output_folder):
    """
    Create scatter plots for SEP_1 measure data.
    
    Args:
        result_df: DataFrame containing aggregated facility data
        facility_list: List of facility names
        output_folder: Folder where plot should be saved
        
    Returns:
        Path to saved plot file or None if no data
    """
    # Filter for SEP_1 measure data only
    sep1_data = result_df[result_df['Measure ID'] == 'SEP_1'].copy()
    
    if sep1_data.empty:
        st.warning("No SEP_1 data found for plotting.")
        return None
    
    # Clean and convert score data
    # Remove rows where Score is "Not Available" or empty
    sep1_data = sep1_data[sep1_data['Score'] != 'Not Available']
    sep1_data = sep1_data.dropna(subset=['Score', 'End Date'])
    
    # Convert Score to numeric
    sep1_data['Score'] = pd.to_numeric(sep1_data['Score'], errors='coerce')
    sep1_data = sep1_data.dropna(subset=['Score'])
    
    if sep1_data.empty:
        st.warning("No valid SEP_1 score data found for plotting.")
        return None
    
    # Parse End Date
    try:
        sep1_data['End_Date_Parsed'] = pd.to_datetime(sep1_data['End Date'], format='%m/%d/%y')
    except:
        try:
            sep1_data['End_Date_Parsed'] = pd.to_datetime(sep1_data['End Date'], infer_datetime_format=True)
        except:
            st.error("Error parsing dates for plotting.")
            return None
    
    # Set up plot style for scientific conference
    plt.style.use('seaborn-v0_8-whitegrid')
    sns.set_palette("husl")
    
    # Create figure with 3W x 2H aspect ratio
    fig, ax = plt.subplots(figsize=(9, 6))
    
    if len(facility_list) == 1:
        # Single facility plot
        facility_name = facility_list[0]
        facility_data = sep1_data[sep1_data['Facility Name'] == facility_name].sort_values('End_Date_Parsed')
        
        if not facility_data.empty:
            ax.scatter(facility_data['End_Date_Parsed'], facility_data['Score'], 
                      s=80, alpha=0.7, edgecolors='black', linewidth=0.5)
            ax.plot(facility_data['End_Date_Parsed'], facility_data['Score'], 
                   alpha=0.6, linewidth=2)
            
            # Format plot
            title = truncate_title(f'{facility_name}_SEP_1')
            ax.set_title(title, fontsize=12, fontweight='bold', pad=20)
            ax.set_xlabel('End Date', fontsize=14, fontweight='bold')
            ax.set_ylabel('SEP_1 Score (%)', fontsize=14, fontweight='bold')
            
            # Use the passed output_folder
            safe_facility_name = facility_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            plot_filename = f"{output_folder}/{safe_facility_name}_SEP_1_plot.png"
        else:
            st.warning(f"No SEP_1 data found for {facility_name}")
            return None
    else:
        # Multiple facilities plot
        colors = plt.cm.Set3(np.linspace(0, 1, len(facility_list)))
        
        for i, facility in enumerate(facility_list):
            facility_data = sep1_data[sep1_data['Facility Name'] == facility].sort_values('End_Date_Parsed')
            if not facility_data.empty:
                wrapped_label = wrap_legend_text(facility)
                ax.scatter(facility_data['End_Date_Parsed'], facility_data['Score'], 
                          label=wrapped_label, s=80, alpha=0.7, color=colors[i],
                          edgecolors='black', linewidth=0.5)
                ax.plot(facility_data['End_Date_Parsed'], facility_data['Score'], 
                       color=colors[i], alpha=0.6, linewidth=2)
        
        # Format plot for multiple facilities
        first_three = facility_list[:3]
        remaining_count = len(facility_list) - 3
        if remaining_count > 0:
            facilities_title = f"{', '.join(first_three)} and {remaining_count} others_SEP_1"
        else:
            facilities_title = f"{', '.join(first_three)}_SEP_1"
            
        truncated_title = truncate_title(facilities_title)
        ax.set_title(truncated_title, fontsize=12, fontweight='bold', pad=20)
        ax.set_xlabel('End Date', fontsize=14, fontweight='bold')
        ax.set_ylabel('SEP_1 Score (%)', fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=12)
        
        plot_filename = f"{output_folder}/Multiple_Facilities_SEP_1_plot.png"
    
    # Common formatting for both single and multiple facility plots
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='both', which='major', labelsize=12)
    
    # Format x-axis dates
    fig.autofmt_xdate()
    
    # Set fixed y-axis limits from 0 to 100
    ax.set_ylim(0, 100)
    
    # Tight layout to ensure everything fits
    plt.tight_layout()
    
    # Save plot with high DPI for publication quality
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    return plot_filename

def create_op18b_plots(result_df, facility_list, output_folder):
    """
    Create scatter plots for OP_18b measure data (Time in ED).
    
    Args:
        result_df: DataFrame containing aggregated facility data
        facility_list: List of facility names
        output_folder: Folder where plot should be saved
        
    Returns:
        Path to saved plot file or None if no data
    """
    # Filter for OP_18b measure data only
    op18b_data = result_df[result_df['Measure ID'] == 'OP_18b'].copy()
    
    if op18b_data.empty:
        st.warning("No OP_18b data found for plotting.")
        return None
    
    # Clean and convert score data
    # Remove rows where Score is "Not Available" or empty
    op18b_data = op18b_data[op18b_data['Score'] != 'Not Available']
    op18b_data = op18b_data.dropna(subset=['Score', 'End Date'])
    
    # Convert Score to numeric
    op18b_data['Score'] = pd.to_numeric(op18b_data['Score'], errors='coerce')
    op18b_data = op18b_data.dropna(subset=['Score'])
    
    if op18b_data.empty:
        st.warning("No valid OP_18b score data found for plotting.")
        return None
    
    # Parse End Date
    try:
        op18b_data['End_Date_Parsed'] = pd.to_datetime(op18b_data['End Date'], format='%m/%d/%y')
    except:
        try:
            op18b_data['End_Date_Parsed'] = pd.to_datetime(op18b_data['End Date'], infer_datetime_format=True)
        except:
            st.error("Error parsing dates for plotting.")
            return None
    
    # Set up plot style for scientific conference
    plt.style.use('seaborn-v0_8-whitegrid')
    sns.set_palette("husl")
    
    # Create figure with 3W x 2H aspect ratio
    fig, ax = plt.subplots(figsize=(9, 6))
    
    if len(facility_list) == 1:
        # Single facility plot
        facility_name = facility_list[0]
        facility_data = op18b_data[op18b_data['Facility Name'] == facility_name].sort_values('End_Date_Parsed')
        
        if not facility_data.empty:
            ax.scatter(facility_data['End_Date_Parsed'], facility_data['Score'], 
                      s=80, alpha=0.7, edgecolors='black', linewidth=0.5)
            ax.plot(facility_data['End_Date_Parsed'], facility_data['Score'], 
                   alpha=0.6, linewidth=2)
            
            # Format plot
            title = truncate_title(f'{facility_name}_Time in the ED')
            ax.set_title(title, fontsize=12, fontweight='bold', pad=20)
            ax.set_xlabel('End Date', fontsize=14, fontweight='bold')
            ax.set_ylabel('Time in ED (minutes)', fontsize=14, fontweight='bold')
            
            # Use the passed output_folder
            safe_facility_name = facility_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            plot_filename = f"{output_folder}/{safe_facility_name}_Time_in_ED_plot.png"
        else:
            st.warning(f"No OP_18b data found for {facility_name}")
            return None
    else:
        # Multiple facilities plot
        colors = plt.cm.Set3(np.linspace(0, 1, len(facility_list)))
        
        for i, facility in enumerate(facility_list):
            facility_data = op18b_data[op18b_data['Facility Name'] == facility].sort_values('End_Date_Parsed')
            if not facility_data.empty:
                wrapped_label = wrap_legend_text(facility)
                ax.scatter(facility_data['End_Date_Parsed'], facility_data['Score'], 
                          label=wrapped_label, s=80, alpha=0.7, color=colors[i],
                          edgecolors='black', linewidth=0.5)
                ax.plot(facility_data['End_Date_Parsed'], facility_data['Score'], 
                       color=colors[i], alpha=0.6, linewidth=2)
        
        # Format plot for multiple facilities
        first_three = facility_list[:3]
        remaining_count = len(facility_list) - 3
        if remaining_count > 0:
            facilities_title = f"{', '.join(first_three)} and {remaining_count} others_Time in the ED"
        else:
            facilities_title = f"{', '.join(first_three)}_Time in the ED"
            
        truncated_title = truncate_title(facilities_title)
        ax.set_title(truncated_title, fontsize=12, fontweight='bold', pad=20)
        ax.set_xlabel('End Date', fontsize=14, fontweight='bold')
        ax.set_ylabel('Time in ED (minutes)', fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=12)
        
        plot_filename = f"{output_folder}/Multiple_Facilities_Time_in_ED_plot.png"
    
    # Common formatting for both single and multiple facility plots
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='both', which='major', labelsize=12)
    
    # Format x-axis dates
    fig.autofmt_xdate()
    
    # Set fixed y-axis limits from 60 to 250 for Time in ED
    ax.set_ylim(60, 250)
    
    # Tight layout to ensure everything fits
    plt.tight_layout()
    
    # Save plot with high DPI for publication quality
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    return plot_filename

def create_severe_sepsis_plots(result_df, facility_list, output_folder):
    """
    Create combined scatter plots for SEV_SH_3HR & SEV_SEP_6HR measure data.
    
    Args:
        result_df: DataFrame containing aggregated facility data
        facility_list: List of facility names
        output_folder: Folder where plot should be saved
        
    Returns:
        Path to saved plot file or None if no data
    """
    # Filter for severe sepsis measure data
    severe_sepsis_data = result_df[result_df['Measure ID'].isin(['SEV_SH_3HR', 'SEV_SEP_6HR'])].copy()
    
    if severe_sepsis_data.empty:
        st.warning("No severe sepsis data found for plotting.")
        return None
    
    # Clean and convert score data
    severe_sepsis_data = severe_sepsis_data[severe_sepsis_data['Score'] != 'Not Available']
    severe_sepsis_data = severe_sepsis_data.dropna(subset=['Score', 'End Date'])
    
    # Convert Score to numeric
    severe_sepsis_data['Score'] = pd.to_numeric(severe_sepsis_data['Score'], errors='coerce')
    severe_sepsis_data = severe_sepsis_data.dropna(subset=['Score'])
    
    if severe_sepsis_data.empty:
        st.warning("No valid severe sepsis score data found for plotting.")
        return None
    
    # Parse End Date
    try:
        severe_sepsis_data['End_Date_Parsed'] = pd.to_datetime(severe_sepsis_data['End Date'], format='%m/%d/%y')
    except:
        try:
            severe_sepsis_data['End_Date_Parsed'] = pd.to_datetime(severe_sepsis_data['End Date'], infer_datetime_format=True)
        except:
            st.error("Error parsing dates for plotting.")
            return None
    
    # Set up plot style for scientific conference
    plt.style.use('seaborn-v0_8-whitegrid')
    sns.set_palette("husl")
    
    # Create figure with 3W x 2H aspect ratio
    fig, ax = plt.subplots(figsize=(9, 6))
    
    # Plot both measures with different markers
    measures = ['SEV_SH_3HR', 'SEV_SEP_6HR']
    markers = ['o', 's']
    
    if len(facility_list) == 1:
        # Single facility plot
        facility_name = facility_list[0]
        
        for i, measure in enumerate(measures):
            measure_data = severe_sepsis_data[
                (severe_sepsis_data['Facility Name'] == facility_name) & 
                (severe_sepsis_data['Measure ID'] == measure)
            ].sort_values('End_Date_Parsed')
            if not measure_data.empty:
                ax.scatter(measure_data['End_Date_Parsed'], measure_data['Score'], 
                          label=measure, s=80, alpha=0.7, marker=markers[i],
                          edgecolors='black', linewidth=0.5)
                ax.plot(measure_data['End_Date_Parsed'], measure_data['Score'], 
                       alpha=0.6, linewidth=2)
        
        title = f'{facility_name}_Severe_Sepsis'
        safe_facility_name = facility_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        plot_filename = f"{output_folder}/{safe_facility_name}_Severe_Sepsis_plot.png"
    else:
        # Multiple facilities combined plot with facility-specific colors
        colors = plt.cm.Set3(np.linspace(0, 1, len(facility_list)))
        
        for i, facility in enumerate(facility_list):
            for j, measure in enumerate(measures):
                measure_data = severe_sepsis_data[
                    (severe_sepsis_data['Facility Name'] == facility) & 
                    (severe_sepsis_data['Measure ID'] == measure)
                ].sort_values('End_Date_Parsed')
                if not measure_data.empty:
                    label = f"{facility} - {measure}"
                    wrapped_label = wrap_legend_text(label)
                    ax.scatter(measure_data['End_Date_Parsed'], measure_data['Score'], 
                              label=wrapped_label, s=80, alpha=0.7, color=colors[i], 
                              marker=markers[j], edgecolors='black', linewidth=0.5)
                    ax.plot(measure_data['End_Date_Parsed'], measure_data['Score'], 
                           color=colors[i], alpha=0.6, linewidth=2, linestyle='-' if j == 0 else '--')
        
        first_three = facility_list[:3]
        remaining_count = len(facility_list) - 3
        if remaining_count > 0:
            title = f"{', '.join(first_three)} and {remaining_count} others_Severe_Sepsis"
        else:
            title = f"{', '.join(first_three)}_Severe_Sepsis"
            
        plot_filename = f"{output_folder}/Multiple_Facilities_Severe_Sepsis_plot.png"
    
    # Format plot
    truncated_title = truncate_title(title)
    ax.set_title(truncated_title, fontsize=12, fontweight='bold', pad=20)
    ax.set_xlabel('End Date', fontsize=14, fontweight='bold')
    ax.set_ylabel('Score (%)', fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=12)
    
    # Common formatting
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='both', which='major', labelsize=12)
    fig.autofmt_xdate()
    ax.set_ylim(0, 100)
    
    plt.tight_layout()
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    return plot_filename

def create_sepsis_plots(result_df, facility_list, output_folder):
    """
    Create combined scatter plots for SEP_SH_3HR & SEP_SH_6HR measure data.
    
    Args:
        result_df: DataFrame containing aggregated facility data
        facility_list: List of facility names
        output_folder: Folder where plot should be saved
        
    Returns:
        Path to saved plot file or None if no data
    """
    # Filter for sepsis measure data
    sepsis_data = result_df[result_df['Measure ID'].isin(['SEP_SH_3HR', 'SEP_SH_6HR'])].copy()
    
    if sepsis_data.empty:
        st.warning("No sepsis data found for plotting.")
        return None
    
    # Clean and convert score data
    sepsis_data = sepsis_data[sepsis_data['Score'] != 'Not Available']
    sepsis_data = sepsis_data.dropna(subset=['Score', 'End Date'])
    
    # Convert Score to numeric
    sepsis_data['Score'] = pd.to_numeric(sepsis_data['Score'], errors='coerce')
    sepsis_data = sepsis_data.dropna(subset=['Score'])
    
    if sepsis_data.empty:
        st.warning("No valid sepsis score data found for plotting.")
        return None
    
    # Parse End Date
    try:
        sepsis_data['End_Date_Parsed'] = pd.to_datetime(sepsis_data['End Date'], format='%m/%d/%y')
    except:
        try:
            sepsis_data['End_Date_Parsed'] = pd.to_datetime(sepsis_data['End Date'], infer_datetime_format=True)
        except:
            st.error("Error parsing dates for plotting.")
            return None
    
    # Set up plot style for scientific conference
    plt.style.use('seaborn-v0_8-whitegrid')
    sns.set_palette("husl")
    
    # Create figure with 3W x 2H aspect ratio
    fig, ax = plt.subplots(figsize=(9, 6))
    
    # Plot both measures with different markers
    measures = ['SEP_SH_3HR', 'SEP_SH_6HR']
    markers = ['o', '^']
    
    if len(facility_list) == 1:
        # Single facility plot
        facility_name = facility_list[0]
        
        for i, measure in enumerate(measures):
            measure_data = sepsis_data[
                (sepsis_data['Facility Name'] == facility_name) & 
                (sepsis_data['Measure ID'] == measure)
            ].sort_values('End_Date_Parsed')
            if not measure_data.empty:
                ax.scatter(measure_data['End_Date_Parsed'], measure_data['Score'], 
                          label=measure, s=80, alpha=0.7, marker=markers[i],
                          edgecolors='black', linewidth=0.5)
                ax.plot(measure_data['End_Date_Parsed'], measure_data['Score'], 
                       alpha=0.6, linewidth=2)
        
        title = f'{facility_name}_Sepsis_Shock'
        safe_facility_name = facility_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        plot_filename = f"{output_folder}/{safe_facility_name}_Sepsis_Shock_plot.png"
    else:
        # Multiple facilities combined plot with facility-specific colors
        colors = plt.cm.Set3(np.linspace(0, 1, len(facility_list)))
        
        for i, facility in enumerate(facility_list):
            for j, measure in enumerate(measures):
                measure_data = sepsis_data[
                    (sepsis_data['Facility Name'] == facility) & 
                    (sepsis_data['Measure ID'] == measure)
                ].sort_values('End_Date_Parsed')
                if not measure_data.empty:
                    label = f"{facility} - {measure}"
                    wrapped_label = wrap_legend_text(label)
                    ax.scatter(measure_data['End_Date_Parsed'], measure_data['Score'], 
                              label=wrapped_label, s=80, alpha=0.7, color=colors[i], 
                              marker=markers[j], edgecolors='black', linewidth=0.5)
                    ax.plot(measure_data['End_Date_Parsed'], measure_data['Score'], 
                           color=colors[i], alpha=0.6, linewidth=2, linestyle='-' if j == 0 else '--')
        
        first_three = facility_list[:3]
        remaining_count = len(facility_list) - 3
        if remaining_count > 0:
            title = f"{', '.join(first_three)} and {remaining_count} others_Sepsis"
        else:
            title = f"{', '.join(first_three)}_Sepsis_Shock"
            
        plot_filename = f"{output_folder}/Multiple_Facilities_Sepsis_Shock_plot.png"
    
    # Format plot
    truncated_title = truncate_title(title)
    ax.set_title(truncated_title, fontsize=12, fontweight='bold', pad=20)
    ax.set_xlabel('End Date', fontsize=14, fontweight='bold')
    ax.set_ylabel('Score (%)', fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=12)
    
    # Common formatting
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='both', which='major', labelsize=12)
    fig.autofmt_xdate()
    ax.set_ylim(0, 100)
    
    plt.tight_layout()
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    return plot_filename

def find_facility_matches(user_facilities, available_facilities):
    """
    Find exact or fuzzy matches for user-provided facility names.
    
    Args:
        user_facilities: List of facility names provided by user
        available_facilities: Set of all available facility names from the data
    
    Returns:
        List of matched facility names (original names from data)
    """
    matched_facilities = []
    
    for user_facility in user_facilities:
        # First try exact match
        if user_facility in available_facilities:
            matched_facilities.append(user_facility)
            st.success(f"✓ Exact match found: '{user_facility}'")
        else:
            # Try fuzzy matching
            best_match = process.extractOne(user_facility, available_facilities, scorer=fuzz.ratio)
            if best_match and best_match[1] > 70:  # Score > 70%
                matched_facilities.append(best_match[0])
                st.success(f"✓ Fuzzy match found: '{user_facility}' → '{best_match[0]}' (Score: {best_match[1]}%)")
            else:
                st.error(f"✗ No suitable match found for: '{user_facility}' (Best match: {best_match[0] if best_match else 'None'}, Score: {best_match[1] if best_match else 0}%)")
    
    return matched_facilities

def create_download_zip(output_folder):
    """
    Create a zip file containing all generated files for download.
    
    Args:
        output_folder: Path to folder containing generated files
        
    Returns:
        BytesIO object containing the zip file
    """
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(output_folder):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name = os.path.relpath(file_path, output_folder)
                zip_file.write(file_path, arc_name)
    
    zip_buffer.seek(0)
    return zip_buffer

def main():
    """
    Main Streamlit application function.
    """
    st.title("🏥 Hospital Data Analyzer")
    st.markdown("### Analyze Hospital Timely and Effective Care Data")
    
    # Sidebar for input options
    with st.sidebar:
        st.header("📋 Configuration")
        
        # File upload option
        uploaded_files = st.file_uploader(
            "Upload CSV Files",
            type=['csv'],
            accept_multiple_files=True,
            help="Upload one or more 'Timely_and_Effective_Care-Hospital.csv' files"
        )
        
        # Option to use local files
        use_local_files = st.checkbox(
            "Use local CSV files",
            help="Search for CSV files in the current directory and subdirectories"
        )
        
        # Facility name input
        facilities_input = st.text_area(
            "Facility Names",
            placeholder="Enter facility names, separated by commas",
            help="Enter the names of hospitals/facilities you want to analyze"
        )
        
        # Analysis options
        st.subheader("📊 Analysis Options")
        generate_sep1 = st.checkbox("SEP_1 Analysis", value=True)
        generate_op18b = st.checkbox("OP_18b (Time in ED) Analysis", value=True)
        generate_severe_sepsis = st.checkbox("Severe Sepsis Analysis", value=True)
        generate_sepsis = st.checkbox("Sepsis Shock Analysis", value=True)
        
    # Main content area
    if st.button("🔍 Analyze Data", type="primary"):
        if not facilities_input.strip():
            st.error("Please enter at least one facility name.")
            return
            
        if not uploaded_files and not use_local_files:
            st.error("Please either upload CSV files or enable 'Use local files' option.")
            return
        
        # Parse facility names
        user_facility_list = [name.strip() for name in facilities_input.split(',')]
        
        with st.spinner("Processing data..."):
            # Create temporary directory for processing
            temp_dir = tempfile.mkdtemp()
            
            try:
                csv_files = []
                
                # Handle uploaded files
                if uploaded_files:
                    for uploaded_file in uploaded_files:
                        # Save uploaded file to temp directory
                        temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(temp_file_path, 'wb') as f:
                            f.write(uploaded_file.read())
                        csv_files.append(temp_file_path)
                
                # Handle local files
                if use_local_files:
                    local_csv_files = glob.glob("**/Timely_and_Effective_Care-Hospital.csv", recursive=True)
                    csv_files.extend(local_csv_files)
                
                if not csv_files:
                    st.error("No CSV files found to process.")
                    return
                
                st.info(f"Found {len(csv_files)} CSV files to process.")
                
                # First pass: collect all available facility names for fuzzy matching
                st.info("Collecting available facility names for matching...")
                all_facilities = set()
                
                for csv_file in csv_files:
                    try:
                        df = pd.read_csv(csv_file)
                        if 'Facility Name' in df.columns:
                            all_facilities.update(df['Facility Name'].dropna().unique())
                    except Exception as e:
                        st.warning(f"Error reading {csv_file} for facility names: {e}")
                
                st.info(f"Found {len(all_facilities)} unique facility names across all files.")
                
                # Find matches for user-provided facility names
                st.subheader("🔍 Facility Matching Results")
                facility_list = find_facility_matches(user_facility_list, all_facilities)
                
                if not facility_list:
                    st.error("No suitable facility matches found. Please check facility names and try again.")
                    return
                
                st.success(f"Proceeding with {len(facility_list)} matched facilities:")
                for facility in facility_list:
                    st.write(f"• {facility}")
                
                # Process data
                st.subheader("📊 Processing Hospital Data")
                aggregated_data = []
                
                progress_bar = st.progress(0)
                for i, csv_file in enumerate(csv_files):
                    try:
                        df = pd.read_csv(csv_file)
                        # Filter rows where Facility Name is in the matched list
                        filtered_df = df[df['Facility Name'].isin(facility_list)]
                        if not filtered_df.empty:
                            aggregated_data.append(filtered_df)
                            st.write(f"✓ Found {len(filtered_df)} rows in {os.path.basename(csv_file)}")
                        else:
                            st.write(f"⚠ No matching rows in {os.path.basename(csv_file)}")
                    except Exception as e:
                        st.error(f"Error processing {csv_file}: {e}")
                    
                    progress_bar.progress((i + 1) / len(csv_files))
                
                if not aggregated_data:
                    st.error("No data found for the specified facilities.")
                    return
                
                # Concatenate all filtered data
                result_df = pd.concat(aggregated_data, ignore_index=True)
                result_df.drop_duplicates(inplace=True)
                
                st.success(f"Successfully aggregated {len(result_df)} rows of data!")
                
                # Create output folder and determine filenames based on number of facilities
                if len(facility_list) == 1:
                    # Single facility: create folder named after facility
                    facility_name = facility_list[0].replace(" ", "_").replace("/", "_").replace("\\", "_")
                    output_folder = os.path.join(temp_dir, facility_name)
                    output_filename = f"{facility_name}_aggregate.csv"
                else:
                    # Multiple facilities: create folder with first three facility names
                    first_three = [f.replace(" ", "_").replace("/", "_").replace("\\", "_") for f in facility_list[:3]]
                    if len(facility_list) > 3:
                        folder_name = f"{'_'.join(first_three)}_and_{len(facility_list)-3}_others"
                    else:
                        folder_name = '_'.join(first_three)
                    output_folder = os.path.join(temp_dir, folder_name)
                    output_filename = "Aggregated_Facilities_Data.csv"
                
                # Create output folder
                os.makedirs(output_folder, exist_ok=True)
                
                # Save CSV in the output folder
                csv_path = os.path.join(output_folder, output_filename)
                result_df.to_csv(csv_path, index=False)
                
                # Display data summary
                st.subheader("📈 Data Summary")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Records", len(result_df))
                with col2:
                    st.metric("Facilities", len(facility_list))
                with col3:
                    st.metric("Measure Types", result_df['Measure ID'].nunique())
                
                # Show data preview
                st.subheader("📋 Data Preview")
                st.dataframe(result_df.head(10), use_container_width=True)
                
                # Generate plots
                st.subheader("📊 Generated Visualizations")
                plot_files = []
                
                # Generate selected plots
                if generate_sep1:
                    with st.spinner("Generating SEP_1 plots..."):
                        sep1_plot = create_sep1_plots(result_df, facility_list, output_folder)
                        if sep1_plot and os.path.exists(sep1_plot):
                            st.subheader("SEP_1 Analysis")
                            st.image(sep1_plot, caption="SEP_1 Score Over Time")
                            plot_files.append(sep1_plot)
                
                if generate_op18b:
                    with st.spinner("Generating OP_18b plots..."):
                        op18b_plot = create_op18b_plots(result_df, facility_list, output_folder)
                        if op18b_plot and os.path.exists(op18b_plot):
                            st.subheader("OP_18b Analysis (Time in ED)")
                            st.image(op18b_plot, caption="Time in Emergency Department")
                            plot_files.append(op18b_plot)
                
                if generate_severe_sepsis:
                    with st.spinner("Generating severe sepsis plots..."):
                        severe_sepsis_plot = create_severe_sepsis_plots(result_df, facility_list, output_folder)
                        if severe_sepsis_plot and os.path.exists(severe_sepsis_plot):
                            st.subheader("Severe Sepsis Analysis")
                            st.image(severe_sepsis_plot, caption="Severe Sepsis Measures Over Time")
                            plot_files.append(severe_sepsis_plot)
                
                if generate_sepsis:
                    with st.spinner("Generating sepsis plots..."):
                        sepsis_plot = create_sepsis_plots(result_df, facility_list, output_folder)
                        if sepsis_plot and os.path.exists(sepsis_plot):
                            st.subheader("Sepsis Shock Analysis")
                            st.image(sepsis_plot, caption="Sepsis Shock Measures Over Time")
                            plot_files.append(sepsis_plot)
                
                # Create download section
                st.subheader("📥 Download Results")
                
                # Create download buttons for individual files
                col1, col2 = st.columns(2)
                
                with col1:
                    # Download CSV
                    with open(csv_path, 'rb') as f:
                        st.download_button(
                            label="📊 Download CSV Data",
                            data=f.read(),
                            file_name=output_filename,
                            mime="text/csv"
                        )
                
                with col2:
                    # Download all results as ZIP
                    zip_buffer = create_download_zip(output_folder)
                    st.download_button(
                        label="📦 Download All Results (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name=f"{os.path.basename(output_folder)}_results.zip",
                        mime="application/zip"
                    )
                
                st.success("✅ Analysis completed successfully!")
                
            except Exception as e:
                st.error(f"An error occurred during processing: {str(e)}")
                
            finally:
                # Clean up temporary directory
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
    
    # Display information about the app
    with st.expander("ℹ️ About this Application"):
        st.markdown("""
        **Hospital Data Analyzer** helps you analyze hospital performance data from CMS (Centers for Medicare & Medicaid Services).
        
        **Features:**
        - Upload CSV files or use local files
        - Fuzzy matching for facility names
        - Multiple analysis types (SEP_1, OP_18b, Sepsis measures)
        - Interactive visualizations
        - Download results as CSV or ZIP
        
        **Supported Measures:**
        - **SEP_1**: Sepsis care performance
        - **OP_18b**: Time spent in Emergency Department
        - **SEV_SH_3HR & SEV_SEP_6HR**: Severe sepsis care
        - **SEP_SH_3HR & SEP_SH_6HR**: Sepsis shock care
        
        **File Format:** Upload 'Timely_and_Effective_Care-Hospital.csv' files from CMS Hospital Compare.
        """)

if __name__ == "__main__":
    main()
