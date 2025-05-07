import streamlit as st
import logging
import json
import requests
from typing import Dict, Any, List, Optional
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def metadata_extraction():
    """
    Implement metadata extraction using Box AI API
    
    Returns:
        dict: Dictionary of extraction functions
    """

    def extract_structured_metadata(file_id, fields=None, metadata_template=None, ai_model='azure__openai__gpt_4o_mini'):
        """
        Extract structured metadata from a file using Box AI API
        
        Args:
            file_id (str): Box file ID
            fields (list): List of field definitions for extraction
            metadata_template (dict): Metadata template definition
            ai_model (str): AI model to use for extraction
            
        Returns:
            dict: Extracted metadata with confidence scores
        """
        try:
            client = st.session_state.client
            access_token = None
            if hasattr(client, '_oauth'):
                access_token = client._oauth.access_token
            elif hasattr(client, 'auth') and hasattr(client.auth, 'access_token'):
                access_token = client.auth.access_token
            if not access_token:
                raise ValueError('Could not retrieve access token from client')
            headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
            ai_agent = {'type': 'ai_agent_extract_structured', 'long_text': {'model': ai_model, 'mode': 'default', 'system_message': 'You are an AI assistant specialized in extracting metadata from documents based on provided field definitions. For each field, analyze the document content and extract the corresponding value. CRITICALLY IMPORTANT: Respond for EACH field with a JSON object containing two keys: 1. \\"value\\": The extracted metadata value as a string. 2. \\"confidence\\": Your confidence level for this specific extraction, chosen from ONLY these three options: \\"High\\", \\"Medium\\", or \\"Low\\". Base your confidence on how certain you are about the extracted value given the document content and field definition. Example Response for a field: {\\"value\\": \\"INV-12345\\", \\"confidence\\": \\"High\\"}'}, 'basic_text': {'model': ai_model, 'mode': 'default', 'system_message': 'You are an AI assistant specialized in extracting metadata from documents based on provided field definitions. For each field, analyze the document content and extract the corresponding value. CRITICALLY IMPORTANT: Respond for EACH field with a JSON object containing two keys: 1. \\"value\\": The extracted metadata value as a string. 2. \\"confidence\\": Your confidence level for this specific extraction, chosen from ONLY these three options: \\"High\\", \\"Medium\\", or \\"Low\\". Base your confidence on how certain you are about the extracted value given the document content and field definition. Example Response for a field: {\\"value\\": \\"INV-12345\\", \\"confidence\\": \\"High\\"}'}}
            items = [{'id': file_id, 'type': 'file'}]
            api_url = 'https://api.box.com/2.0/ai/extract_structured'
            request_body = {'items': items, 'ai_agent': ai_agent}
            if metadata_template:
                request_body['metadata_template'] = metadata_template
            elif fields:
                api_fields = []
                for field in fields:
                    if 'key' in field:
                        api_fields.append(field)
                    else:
                        api_field = {'key': field.get('name', ''), 'displayName': field.get('display_name', field.get('name', '')), 'type': field.get('type', 'string')}
                        if 'description' in field:
                            api_field['description'] = field['description']
                        if 'prompt' in field:
                            api_field['prompt'] = field['prompt']
                        if field.get('type') == 'enum' and 'options' in field:
                            api_field['options'] = field['options']
                        api_fields.append(api_field)
                request_body['fields'] = api_fields
            else:
                raise ValueError('Either fields or metadata_template must be provided')
            logger.info(f'Making Box AI API call for structured extraction with request: {json.dumps(request_body)}')
            response = requests.post(api_url, headers=headers, json=request_body)
            if response.status_code != 200:
                logger.error(f'Box AI API error response: {response.text}')
                return {'error': f'Error in Box AI API call: {response.status_code} {response.reason}'}
            response_data = response.json()
            logger.info(f'Raw Box AI structured extraction response data: {json.dumps(response_data)}')
            processed_response = {}
            if 'answer' in response_data and isinstance(response_data['answer'], dict):
                answer_dict = response_data['answer']
                if 'fields' in answer_dict and isinstance(answer_dict['fields'], list):
                    logger.info("Processing 'answer' with 'fields' array format.")
                    fields_array = answer_dict['fields']
                    for field_item in fields_array:
                        if isinstance(field_item, dict) and 'key' in field_item and ('value' in field_item):
                            field_key = field_item['key']
                            extracted_value = field_item['value']
                            confidence_level = field_item.get('confidence', 'Medium')
                            if confidence_level not in ['High', 'Medium', 'Low']:
                                logger.warning(f"Field {field_key}: Unexpected confidence value '{confidence_level}', defaulting to Medium.")
                                confidence_level = 'Medium'
                            processed_response[field_key] = extracted_value
                            processed_response[f'{field_key}_confidence'] = confidence_level
                        else:
                            logger.warning(f"Skipping invalid item in 'fields' array: {field_item}")
                else:
                    logger.info("Processing 'answer' as standard key-value dictionary.")
                    for field_key, field_data in answer_dict.items():
                        extracted_value = None
                        confidence_level = 'Medium'
                        try:
                            if isinstance(field_data, dict) and 'value' in field_data and ('confidence' in field_data):
                                extracted_value = field_data['value']
                                confidence_level = field_data['confidence']
                                if confidence_level not in ['High', 'Medium', 'Low']:
                                    logger.warning(f"Field {field_key}: Unexpected confidence value '{confidence_level}', defaulting to Medium.")
                                    confidence_level = 'Medium'
                            elif field_data is None:
                                logger.info(f'Field {field_key}: Received null value. Setting value to None and confidence to Low.')
                                extracted_value = None
                                confidence_level = 'Low'
                            elif isinstance(field_data, dict) and 'value' in field_data and (len(field_data) == 1):
                                logger.warning(f"Field {field_key}: Found dict with only 'value' key: {field_data}. Extracting value directly.")
                                extracted_value = field_data['value']
                                confidence_level = 'Medium'
                            else:
                                logger.warning(f'Field {field_key}: Unexpected data format: {field_data}. Using raw data as value and Medium confidence.')
                                extracted_value = field_data
                                confidence_level = 'Medium'
                            processed_response[field_key] = extracted_value
                            processed_response[f'{field_key}_confidence'] = confidence_level
                        except Exception as e:
                            logger.error(f"Error processing field {field_key} with data '{field_data}': {str(e)}")
                            processed_response[field_key] = field_data
                            processed_response[f'{field_key}_confidence'] = 'Low'
            elif 'answer' in response_data and isinstance(response_data['answer'], str):
                logger.info("Processing 'answer' as string (potential freeform JSON).")
                response_text = response_data['answer']
                try:
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    if json_start != -1 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        parsed_json = json.loads(json_str)
                        if isinstance(parsed_json, dict):
                            for field_key, field_data in parsed_json.items():
                                if isinstance(field_data, dict) and 'value' in field_data and ('confidence' in field_data):
                                    extracted_value = field_data['value']
                                    confidence_level = field_data['confidence']
                                    if confidence_level not in ['High', 'Medium', 'Low']:
                                        confidence_level = 'Medium'
                                    processed_response[field_key] = extracted_value
                                    processed_response[f'{field_key}_confidence'] = confidence_level
                                else:
                                    processed_response[field_key] = field_data
                                    processed_response[f'{field_key}_confidence'] = 'Medium'
                        else:
                            logger.warning(f"Parsed JSON from 'answer' string is not a dictionary: {parsed_json}")
                            processed_response['_raw_response'] = response_text
                            processed_response['_confidence_processing_failed'] = True
                    else:
                        logger.warning("No JSON object found in 'answer' string.")
                        processed_response['_raw_response'] = response_text
                        processed_response['_confidence_processing_failed'] = True
                except Exception as e:
                    logger.error(f'Error parsing JSON from answer string: {str(e)}')
                    processed_response['_raw_response'] = response_text
                    processed_response['_confidence_processing_failed'] = True
            elif 'entries' in response_data and len(response_data['entries']) > 0:
                logger.info("Processing response using fallback 'entries' format.")
                entry = response_data['entries'][0]
                if 'metadata' in entry:
                    metadata = entry['metadata']
                    for field_key, field_value in metadata.items():
                        extracted_value = field_value
                        confidence_level = 'Medium'
                        try:
                            if isinstance(field_value, str) and field_value.strip().startswith('{') and field_value.strip().endswith('}'):
                                try:
                                    parsed_value = json.loads(field_value)
                                    if isinstance(parsed_value, dict) and 'value' in parsed_value and ('confidence' in parsed_value):
                                        extracted_value = parsed_value['value']
                                        confidence_level = parsed_value['confidence']
                                        if confidence_level not in ['High', 'Medium', 'Low']:
                                            logger.warning(f"Field {field_key}: Unexpected confidence value '{confidence_level}', defaulting to Medium.")
                                            confidence_level = 'Medium'
                                    else:
                                        logger.warning(f"Field {field_key}: Parsed JSON but keys 'value' and 'confidence' not found. Using raw value.")
                                        extracted_value = field_value
                                        confidence_level = 'Medium'
                                except json.JSONDecodeError:
                                    logger.warning(f"Field {field_key}: Failed to parse potential JSON value '{field_value}'. Using raw value.")
                                    extracted_value = field_value
                                    confidence_level = 'Medium'
                            else:
                                extracted_value = field_value
                                confidence_level = 'Medium'
                                logger.info(f'Field {field_key}: Value is not the expected JSON format. Using raw value and Medium confidence.')
                            processed_response[field_key] = extracted_value
                            processed_response[f'{field_key}_confidence'] = confidence_level
                        except Exception as e:
                            logger.error(f"Error processing field {field_key} with value '{field_value}': {str(e)}")
                            processed_response[field_key] = field_value
                            processed_response[f'{field_key}_confidence'] = 'Low'
                else:
                    logger.warning(f"No 'metadata' field found in the structured API entry: {entry}")
                    processed_response['_error'] = "No 'metadata' field in API entry"
                    processed_response['_confidence_processing_failed'] = True
            else:
                logger.warning(f"Neither 'answer' nor 'entries' field found in the structured API response: {response_data}")
                processed_response['_error'] = "Neither 'answer' nor 'entries' field in API response"
                processed_response['_confidence_processing_failed'] = True
            return processed_response
        except Exception as e:
            logger.error(f'Error in structured metadata extraction call: {str(e)}')
            return {'error': str(e)}

    def extract_freeform_metadata(file_id, prompt, ai_model='azure__openai__gpt_4o_mini'):
        """
        Extract freeform metadata from a file using Box AI API
        
        Args:
            file_id (str): Box file ID
            prompt (str): Extraction prompt
            ai_model (str): AI model to use for extraction
            
        Returns:
            dict: Extracted metadata with confidence scores
        """
        try:
            client = st.session_state.client
            access_token = None
            if hasattr(client, '_oauth'):
                access_token = client._oauth.access_token
            elif hasattr(client, 'auth') and hasattr(client.auth, 'access_token'):
                access_token = client.auth.access_token
            if not access_token:
                raise ValueError('Could not retrieve access token from client')
            headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
            enhanced_prompt = prompt
            if not 'confidence' in prompt.lower():
                enhanced_prompt = prompt + " For each extracted field, provide your confidence level (High, Medium, or Low) in the accuracy of the extraction. Format your response as a JSON object with each field having a nested object containing 'value' and 'confidence' keys."
            ai_agent = {'type': 'ai_agent_extract', 'long_text': {'model': ai_model, 'system_message': 'You are an AI assistant specialized in extracting metadata from documents. Extract the requested information and for EACH extracted field, provide both the value and your confidence level (High, Medium, or Low). Format your response as a JSON object where each field has a nested object containing \\"value\\" and \\"confidence\\" keys. Example: {\\"InvoiceNumber\\": {\\"value\\": \\"INV-12345\\", \\"confidence\\": \\"High\\"}, \\"Date\\": {\\"value\\": \\"2023-04-15\\", \\"confidence\\": \\"Medium\\"}}'}, 'basic_text': {'model': ai_model, 'system_message': 'You are an AI assistant specialized in extracting metadata from documents. Extract the requested information and for EACH extracted field, provide both the value and your confidence level (High, Medium, or Low). Format your response as a JSON object where each field has a nested object containing \\"value\\" and \\"confidence\\" keys. Example: {\\"InvoiceNumber\\": {\\"value\\": \\"INV-12345\\", \\"confidence\\": \\"High\\"}, \\"Date\\": {\\"value\\": \\"2023-04-15\\", \\"confidence\\": \\"Medium\\"}}'}}
            items = [{'id': file_id, 'type': 'file'}]
            api_url = 'https://api.box.com/2.0/ai/extract'
            request_body = {'items': items, 'prompt': enhanced_prompt, 'ai_agent': ai_agent}
            logger.info(f'Making Box AI API call for freeform extraction with request: {json.dumps(request_body)}')
            response = requests.post(api_url, headers=headers, json=request_body)
            if response.status_code != 200:
                logger.error(f'Box AI API error response: {response.text}')
                return {'error': f'Error in Box AI API call: {response.status_code} {response.reason}'}
            response_data = response.json()
            logger.info(f'Raw Box AI freeform extraction response data: {json.dumps(response_data)}')
            processed_response = {}
            if 'answer' in response_data:
                if isinstance(response_data['answer'], str):
                    logger.info("Processing freeform 'answer' as string.")
                    response_text = response_data['answer']
                    parsed_successfully = False
                    try:
                        json_start = response_text.find('{')
                        json_end = response_text.rfind('}') + 1
                        if json_start != -1 and json_end > json_start:
                            json_str = response_text[json_start:json_end]
                            parsed_json = json.loads(json_str)
                            if isinstance(parsed_json, dict):
                                for field_key, field_data in parsed_json.items():
                                    if isinstance(field_data, dict) and 'value' in field_data and ('confidence' in field_data):
                                        extracted_value = field_data['value']
                                        confidence_level = field_data['confidence']
                                        if confidence_level not in ['High', 'Medium', 'Low']:
                                            confidence_level = 'Medium'
                                        processed_response[field_key] = extracted_value
                                        processed_response[f'{field_key}_confidence'] = confidence_level
                                    else:
                                        processed_response[field_key] = field_data
                                        processed_response[f'{field_key}_confidence'] = 'Medium'
                                parsed_successfully = True
                            else:
                                logger.warning(f"Parsed JSON from freeform 'answer' string is not a dictionary: {parsed_json}")
                        else:
                            logger.warning(f"No JSON object found in freeform 'answer' string.")
                        if not parsed_successfully:
                            processed_response['_raw_response'] = response_text
                            processed_response['_confidence_processing_failed'] = True
                    except Exception as e:
                        logger.error(f'Error parsing JSON from freeform answer string: {str(e)}')
                        processed_response['_raw_response'] = response_text
                        processed_response['_confidence_processing_failed'] = True
                elif isinstance(response_data['answer'], dict):
                    logger.info("Processing freeform 'answer' as dictionary.")
                    for field_key, field_data in response_data['answer'].items():
                        if isinstance(field_data, dict) and 'value' in field_data and ('confidence' in field_data):
                            extracted_value = field_data['value']
                            confidence_level = field_data['confidence']
                            if confidence_level not in ['High', 'Medium', 'Low']:
                                confidence_level = 'Medium'
                            processed_response[field_key] = extracted_value
                            processed_response[f'{field_key}_confidence'] = confidence_level
                        elif isinstance(field_data, dict) and 'value' in field_data and (len(field_data) == 1):
                            extracted_value = field_data['value']
                            confidence_level = 'Medium'
                            processed_response[field_key] = extracted_value
                            processed_response[f'{field_key}_confidence'] = confidence_level
                        else:
                            processed_response[field_key] = field_data
                            processed_response[f'{field_key}_confidence'] = 'Medium'
                else:
                    logger.warning(f"Unexpected freeform 'answer' format: {response_data['answer']}")
                    processed_response['_error'] = "Unexpected freeform 'answer' format"
                    processed_response['_confidence_processing_failed'] = True
            elif 'entries' in response_data and len(response_data['entries']) > 0:
                logger.info("Processing freeform response using fallback 'entries' format.")
                entry = response_data['entries'][0]
                if 'response' in entry:
                    response_text = entry['response']
                    parsed_successfully = False
                    try:
                        json_start = response_text.find('{')
                        json_end = response_text.rfind('}') + 1
                        if json_start != -1 and json_end > json_start:
                            json_str = response_text[json_start:json_end]
                            parsed_json = json.loads(json_str)
                            if isinstance(parsed_json, dict):
                                for field_key, field_data in parsed_json.items():
                                    if isinstance(field_data, dict) and 'value' in field_data and ('confidence' in field_data):
                                        extracted_value = field_data['value']
                                        confidence_level = field_data['confidence']
                                        if confidence_level not in ['High', 'Medium', 'Low']:
                                            logger.warning(f"Field {field_key}: Unexpected confidence value '{confidence_level}', defaulting to Medium.")
                                            confidence_level = 'Medium'
                                        processed_response[field_key] = extracted_value
                                        processed_response[f'{field_key}_confidence'] = confidence_level
                                    else:
                                        logger.warning(f'Field {field_key}: Unexpected structure in parsed JSON: {field_data}. Storing as is with Medium confidence.')
                                        processed_response[field_key] = field_data
                                        processed_response[f'{field_key}_confidence'] = 'Medium'
                                parsed_successfully = True
                            else:
                                logger.warning(f"Parsed JSON from 'entries' response string is not a dictionary: {json_str}. Storing raw response.")
                        else:
                            logger.warning(f"No JSON object found in 'entries' response string. Storing raw response.")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON from 'entries' response string. Error: {e}. Storing raw response.")
                    except Exception as e:
                        logger.error(f"Error processing freeform 'entries' response. Error: {e}. Storing raw response.")
                    if not parsed_successfully:
                        processed_response['_raw_response'] = response_text
                        processed_response['_confidence_processing_failed'] = True
                else:
                    logger.warning(f"No 'response' field found in the freeform API entry: {entry}")
                    processed_response['_error'] = "No 'response' field in API entry"
                    processed_response['_confidence_processing_failed'] = True
            else:
                logger.warning(f"Neither 'answer' nor 'entries' field found in the freeform API response: {response_data}")
                processed_response['_error'] = "Neither 'answer' nor 'entries' field in API response"
                processed_response['_confidence_processing_failed'] = True
            return processed_response
        except Exception as e:
            logger.error(f'Error in freeform metadata extraction call: {str(e)}')
            return {'error': str(e)}
    return {'extract_structured_metadata': extract_structured_metadata, 'extract_freeform_metadata': extract_freeform_metadata}
if __name__ == '__main__':
    extraction_funcs = metadata_extraction()
    pass