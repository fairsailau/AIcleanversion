import streamlit as st
import pandas as pd
from typing import Dict, List, Any, Union # Added Union
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_confidence_color(confidence_level):
    """Get color based on confidence level."""
    if confidence_level == 'High':
        return 'green'
    elif confidence_level == 'Medium':
        return 'orange'
    elif confidence_level == 'Low':
        return 'red'
    else:
        return 'gray'

def view_results():
    """
    View and manage extraction results.
    Handles the new structure in st.session_state.extraction_results where each item is a dict
    with "ai_response" and "template_id_used_for_extraction".
    """
    st.title('View Results')

    #region Session State Initializations
    if not hasattr(st.session_state, 'authenticated') or not hasattr(st.session_state, 'client') or \
       (not st.session_state.authenticated) or (not st.session_state.client):
        st.error('Please authenticate with Box first')
        return

    if not hasattr(st.session_state, 'extraction_results'):
        st.session_state.extraction_results = {}
        logger.info('Initialized extraction_results in view_results')

    if not hasattr(st.session_state, 'selected_result_ids'):
        st.session_state.selected_result_ids = []
        logger.info('Initialized selected_result_ids in view_results')

    if not hasattr(st.session_state, 'metadata_config'):
        st.session_state.metadata_config = {
            'extraction_method': 'freeform', 
            'freeform_prompt': 'Extract key metadata from this document.', 
            'use_template': False, 
            'template_id': '', 
            'custom_fields': [], 
            'ai_model': 'azure__openai__gpt_4o_mini', 
            'batch_size': 5
        }
        logger.info('Initialized metadata_config in view_results')
    #endregion

    if not st.session_state.extraction_results:
        st.warning('No extraction results available. Please process files first.')
        if st.button('Go to Process Files', key='go_to_process_files_btn_vr'):
            st.session_state.current_page = 'Process Files'
            st.rerun()
        return

    st.write('Review and manage the metadata extraction results.')

    #region Filters Initialization
    if not hasattr(st.session_state, 'results_filter_text'): # Renamed to avoid conflict if old key exists
        st.session_state.results_filter_text = ''
    if not hasattr(st.session_state, 'confidence_filter_selection'): # Renamed
        st.session_state.confidence_filter_selection = ['High', 'Medium', 'Low']
    #endregion

    #region New Filters for Adjusted Confidence and Validation Status
    if not hasattr(st.session_state, 'adjusted_confidence_filter_selection'):
        st.session_state.adjusted_confidence_filter_selection = ['High', 'Medium', 'Low']
    if not hasattr(st.session_state, 'validation_status_filter_selection'):
        st.session_state.validation_status_filter_selection = ['Pass', 'Fail', 'Error', 'Skipped'] # Added Skipped for rules not run
    #endregion

    st.subheader("Filter Results")
    row1_filter_col1, row1_filter_col2 = st.columns(2)
    with row1_filter_col1:
        st.session_state.results_filter_text = st.text_input('Filter by file name', value=st.session_state.results_filter_text, key='filter_text_input_vr')
    with row1_filter_col2:
        st.session_state.confidence_filter_selection = st.multiselect('Filter by AI Confidence', options=['High', 'Medium', 'Low'], default=st.session_state.confidence_filter_selection, key='ai_confidence_filter_multiselect_vr')

    row2_filter_col1, row2_filter_col2 = st.columns(2)
    with row2_filter_col1:
        st.session_state.adjusted_confidence_filter_selection = st.multiselect('Filter by Adjusted Confidence', options=['High', 'Medium', 'Low'], default=st.session_state.adjusted_confidence_filter_selection, key='adj_confidence_filter_multiselect_vr')
    with row2_filter_col2:
        st.session_state.validation_status_filter_selection = st.multiselect('Filter by Field Validation Status', options=['pass', 'fail', 'error', 'skip'], default=['pass', 'fail', 'error', 'skip'], key='validation_status_filter_multiselect_vr') # Default to all

    processed_and_filtered_results = {}
    # The st.session_state.extraction_results structure is now assumed to be:
    # file_id: {
    #     "file_name": str,
    #     "document_type": str,
    #     "template_id_used_for_extraction": str,
    #     "fields": {
    #         field_key: {
    #             "value": any,
    #             "ai_confidence": str, # Original from Box AI
    #             "validations": list_of_validation_details, # From validation_engine
    #             "field_validation_status": str, # Overall for this field (pass/fail/error)
    #             "adjusted_confidence": str, # After validation
    #             "is_mandatory": bool,
    #             "is_present": bool
    #         }
    #     },
    #     "document_validation_summary": { # From validation_engine
    #         "mandatory_fields_status": str,
    #         "missing_mandatory_fields": list_of_str,
    #         "cross_field_status": str,
    #         "cross_field_results": list_of_cross_field_validation_details,
    #         "overall_document_confidence_suggestion": str
    #     },
    #     "raw_ai_response": dict # The original full response from Box AI if needed
    # }

    for file_id, result_data_for_file in st.session_state.extraction_results.items():
        if not isinstance(result_data_for_file, dict): # Skip if data is not in expected format
            logger.warning(f"Skipping file_id {file_id} in results_viewer due to unexpected data format: {type(result_data_for_file)}")
            continue

        file_name = result_data_for_file.get('file_name', 'Unknown')
        fields_data = result_data_for_file.get('fields', {})

        # Apply filters
        name_match = st.session_state.results_filter_text.lower() in file_name.lower()
        
        ai_confidence_match = False
        if not st.session_state.confidence_filter_selection:
            ai_confidence_match = True
        else:
            for field_detail in fields_data.values():
                if field_detail.get('ai_confidence') in st.session_state.confidence_filter_selection:
                    ai_confidence_match = True
                    break
        
        adj_confidence_match = False
        if not st.session_state.adjusted_confidence_filter_selection:
            adj_confidence_match = True
        else:
            for field_detail in fields_data.values():
                if field_detail.get('adjusted_confidence') in st.session_state.adjusted_confidence_filter_selection:
                    adj_confidence_match = True
                    break

        validation_status_match = False
        if not st.session_state.validation_status_filter_selection:
            validation_status_match = True
        else:
            for field_detail in fields_data.values():
                if field_detail.get('field_validation_status') in st.session_state.validation_status_filter_selection:
                    validation_status_match = True
                    break
        
        if name_match and ai_confidence_match and adj_confidence_match and validation_status_match:
            processed_and_filtered_results[file_id] = result_data_for_file

    # Prepare data for DataFrame
    table_data_for_df = []
    for file_id, data_item in processed_and_filtered_results.items():
        row = {'File Name': data_item.get('file_name', 'Unknown'), 'File ID': file_id}
        doc_summary = data_item.get('document_validation_summary', {})
        row['Overall Doc Status'] = doc_summary.get('overall_document_confidence_suggestion', 'N/A') # Example of doc level info
        row['Mandatory Fields'] = doc_summary.get('mandatory_fields_status', 'N/A')
        row['Cross-field Valid.'] = doc_summary.get('cross_field_status', 'N/A')

        fields_in_item = data_item.get('fields', {})
        for key, field_details in fields_in_item.items():
            row[key] = field_details.get('value', '')
            row[f'{key} AI Conf.'] = field_details.get('ai_confidence', 'N/A')
            row[f'{key} Valid. Status'] = field_details.get('field_validation_status', 'N/A')
            row[f'{key} Adj. Conf.'] = field_details.get('adjusted_confidence', 'N/A')
        table_data_for_df.append(row)
    
    df_results = pd.DataFrame(table_data_for_df)

    if not df_results.empty:
        base_cols = ['File Name', 'File ID', 'Overall Doc Status', 'Mandatory Fields', 'Cross-field Valid.']
        
        # Dynamically get field names from the first data item if possible, to create sorted field columns
        field_cols_sorted = []
        if processed_and_filtered_results:
            first_item_fields = list(list(processed_and_filtered_results.values())[0].get('fields', {}).keys())
            field_cols_sorted = sorted(first_item_fields)
        
        # Construct the final column order
        final_ordered_cols = base_cols[:]
        for field_name_key in field_cols_sorted:
            final_ordered_cols.append(field_name_key) # Value
            final_ordered_cols.append(f'{field_name_key} AI Conf.')
            final_ordered_cols.append(f'{field_name_key} Valid. Status')
            final_ordered_cols.append(f'{field_name_key} Adj. Conf.')
        
        # Filter df_results to only include columns that actually exist to prevent KeyError
        existing_cols_in_df = [col for col in final_ordered_cols if col in df_results.columns]
        df_results = df_results[existing_cols_in_df]

    st.subheader('Extraction Results')
    tab_table, tab_detailed = st.tabs(['Table View', 'Detailed View'])

    with tab_table:
        st.write(f'Showing {len(df_results)} of {len(st.session_state.extraction_results)} results based on filters.')
        if not df_results.empty:
            # Define a function for styling
            def style_confidence_and_status(val):
                color = 'black' # Default color
                if isinstance(val, str):
                    if val in ['High', 'Medium', 'Low']:
                        color = get_confidence_color(val)
                    elif val == 'pass':
                        color = 'green'
                    elif val == 'fail':
                        color = 'red'
                    elif val == 'error':
                        color = 'purple' # Or some other distinct color for error
                    elif val == 'skip':
                        color = 'grey'
                return f'color: {color}'

            st.dataframe(df_results.style.applymap(
                style_confidence_and_status, 
                subset=[col for col in df_results.columns if col.endswith(' AI Conf.') or col.endswith(' Adj. Conf.') or col.endswith(' Valid. Status') or col in ['Overall Doc Status', 'Mandatory Fields', 'Cross-field Valid.']]
            ), use_container_width=True, hide_index=True)
            
            # Export buttons (functionality not fully implemented here)
            col_export1, col_export2 = st.columns(2)
            with col_export1:
                if st.button('Export as CSV', use_container_width=True, key='export_csv_btn_vr'):
                    st.info('CSV export would be implemented here.') 
            with col_export2:
                if st.button('Export as Excel', use_container_width=True, key='export_excel_btn_vr'):
                    st.info('Excel export would be implemented here.')
        else:
            st.info('No results match the current filter criteria.')

    with tab_detailed:
        if not processed_and_filtered_results:
            st.info('No results to display based on current filters.')
        else:
            detailed_view_file_options = {
                result_item.get('file_name', 'Unknown File'): file_id 
                for file_id, result_item in processed_and_filtered_results.items()
            }
            selected_file_name_for_detail = st.selectbox(
                'Select a file to view details:', 
                options=list(detailed_view_file_options.keys()),
                key='detailed_view_select_vr'
            )

            if selected_file_name_for_detail:
                selected_file_id_for_detail = detailed_view_file_options[selected_file_name_for_detail]
                detailed_data = processed_and_filtered_results[selected_file_id_for_detail]
                
                st.write(f"**File Name:** {detailed_data.get('file_name', 'N/A')}")
                st.write(f"**File ID:** {selected_file_id_for_detail}")
                st.write(f"**Document Type:** {detailed_data.get('document_type', 'N/A')}")
                
                doc_summary = detailed_data.get('document_validation_summary', {})
                st.markdown(f"**Overall Document Suggested Confidence:** <span style='color:{get_confidence_color(doc_summary.get('overall_document_confidence_suggestion', 'N/A'))};'>{doc_summary.get('overall_document_confidence_suggestion', 'N/A')}</span>", unsafe_allow_html=True)
                st.markdown(f"**Mandatory Fields Status:** <span style='color:{'green' if doc_summary.get('mandatory_fields_status', '').lower() == 'passed' else 'red'};'>{doc_summary.get('mandatory_fields_status', 'N/A')}</span>", unsafe_allow_html=True)
                if doc_summary.get('mandatory_fields_status', '').lower() == 'failed':
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;*Missing*: {', '.join(doc_summary.get('missing_mandatory_fields', []))}")
                st.markdown(f"**Cross-Field Validation Status:** <span style='color:{'green' if doc_summary.get('cross_field_status') == 'pass' else 'red'};'>{doc_summary.get('cross_field_status', 'N/A')}</span>", unsafe_allow_html=True)
                if doc_summary.get('cross_field_status') == 'fail':
                    with st.expander("Failed Cross-Field Rule Details"):
                        for cross_val_res in doc_summary.get('cross_field_results', []):
                            if cross_val_res.get('status') == 'fail':
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- Rule: **{cross_val_res.get('rule_name')}**: {cross_val_res.get('message')}")

                st.write("**Extracted Metadata Fields:**")
                fields_to_display = detailed_data.get('fields', {})
                for key, field_info in fields_to_display.items():
                    val = field_info.get('value', '')
                    ai_conf = field_info.get('ai_confidence', 'N/A')
                    adj_conf = field_info.get('adjusted_confidence', 'N/A')
                    val_status = field_info.get('field_validation_status', 'N/A')
                    
                    # Display field value and confidences
                    st.markdown(f"**{key}**: `{val}`")
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;AI Confidence: <span style='color:{get_confidence_color(ai_conf)};'>{ai_conf}</span> | Validation Status: <span style='color:{style_confidence_and_status(val_status).split(':')[1].strip()};'>{val_status}</span> | Adjusted Confidence: <span style='color:{get_confidence_color(adj_conf)};'>{adj_conf}</span>", unsafe_allow_html=True)
                    
                    # Display validation rule details for this field
                    validations = field_info.get('validations', [])
                    if validations:
                        with st.expander(f"Validation Details for {key}", expanded=(val_status != 'pass')):
                            for v_rule in validations:
                                rule_msg = v_rule.get('message', 'No message')
                                rule_status_color = 'green' if v_rule.get('status') == 'pass' else ('red' if v_rule.get('status') == 'fail' else 'purple')
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- {v_rule.get('rule_type')}: <span style='color:{rule_status_color};'>{v_rule.get('status')}</span> - {rule_msg}", unsafe_allow_html=True)
                
                # Display raw AI response if available
                raw_ai_resp = detailed_data.get('raw_ai_response')
                if raw_ai_resp:
                    with st.expander("View Raw AI Response"):
                        st.json(raw_ai_resp)

    st.subheader('Batch Operations')
    col_select_all, col_deselect_all = st.columns(2)
    with col_select_all:
        if st.button('Select All Displayed', use_container_width=True, key='select_all_btn_vr'):
            st.session_state.selected_result_ids = list(processed_and_filtered_results.keys())
            st.rerun()
    with col_deselect_all:
        if st.button('Deselect All', use_container_width=True, key='deselect_all_btn_vr'):
            st.session_state.selected_result_ids = []
            st.rerun()
    
    st.write(f"Selected {len(st.session_state.selected_result_ids)} of {len(processed_and_filtered_results)} displayed results for metadata application.")

    if st.button('Apply Metadata', use_container_width=True, key='apply_metadata_btn_vr'):
        if not st.session_state.selected_result_ids:
            st.warning('Please select at least one file to apply metadata.')
        else:
            # Ensure the correct function is called for metadata application
            # This part assumes direct_metadata_application_v3_fixed.py is correctly imported in app.py or handled by navigation
            st.session_state.current_page = "Apply Metadata" # Navigate to the application page
            logger.info(f"View Results: Navigating to Apply Metadata page with {len(st.session_state.selected_result_ids)} selected files.")
            st.rerun()


