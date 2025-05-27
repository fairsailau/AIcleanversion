import streamlit as st
import logging
import json
import requests
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# This function was previously named metadata_extraction
# Renaming it to get_extraction_functions to match the import in processing.py
def get_extraction_functions() -> Dict[str, Any]:
    """
    Returns a dictionary of available metadata extraction functions.
    
    Returns:
        dict: Dictionary mapping extraction method names to function objects.
    """

    def extract_structured_metadata(client: Any, file_id: str, fields: Optional[List[Dict[str, Any]]] = None, metadata_template: Optional[Dict[str, Any]] = None, ai_model: str = 'azure__openai__gpt_4o_mini') -> Dict[str, Any]:
        """
        Extract structured metadata from a file using Box AI API
        
        Args:
            client (Any): The Box API client.
            file_id (str): Box file ID
            fields (list, optional): List of field definitions for extraction
            metadata_template (dict, optional): Metadata template definition
            ai_model (str): AI model to use for extraction
            
        Returns:
            dict: Extracted metadata with confidence scores
        """
        try:
            # client = st.session_state.client # Client is now passed as an argument
            access_token = None
            if hasattr(client, '_oauth'):
                access_token = client._oauth.access_token
            elif hasattr(client, 'auth') and hasattr(client.auth, 'access_token'):
                access_token = client.auth.access_token
            if not access_token:
                raise ValueError('Could not retrieve access token from client')

            headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
            ai_agent = {
                'type': 'ai_agent_extract_structured',
                'long_text': {
                    'model': ai_model,
                    'mode': 'default',
                    'system_message': 'You are an AI assistant specialized in extracting metadata from documents based on provided field definitions. For each field, analyze the document content and extract the corresponding value. CRITICALLY IMPORTANT: Respond for EACH field with a JSON object containing two keys: 1. "value": The extracted metadata value as a string. 2. "confidence": Your confidence level for this specific extraction, chosen from ONLY these three options: "High", "Medium", or "Low". Base your confidence on how certain you are about the extracted value given the document content and field definition. Example Response for a field: {"value": "INV-12345", "confidence": "High"}'
                },
                'basic_text': {
                    'model': ai_model,
                    'mode': 'default',
                    'system_message': 'You are an AI assistant specialized in extracting metadata from documents based on provided field definitions. For each field, analyze the document content and extract the corresponding value. CRITICALLY IMPORTANT: Respond for EACH field with a JSON object containing two keys: 1. "value": The extracted metadata value as a string. 2. "confidence": Your confidence level for this specific extraction, chosen from ONLY these three options: "High", "Medium", or "Low". Base your confidence on how certain you are about the extracted value given the document content and field definition. Example Response for a field: {"value": "INV-12345", "confidence": "High"}'
                }
            }
            items = [{'id': file_id, 'type': 'file'}]
            api_url = 'https://api.box.com/2.0/ai/extract_structured'
            request_body: Dict[str, Any] = {'items': items, 'ai_agent': ai_agent}

            # Prioritize 'fields' if provided and not empty
            if fields and len(fields) > 0:
                api_fields = []
                for field_def in fields: # 'fields' is the function argument
                    # Assuming field_def is a dictionary like {'key': ..., 'displayName': ..., 'type': ..., 'description': ..., 'options': ...}
                    # This is the format produced by get_fields_for_ai_from_template
                    current_api_field = {
                        'key': field_def.get('key'),
                        'displayName': field_def.get('displayName', field_def.get('key')), # Default displayName to key
                        'type': field_def.get('type', 'string') # Default type to string
                    }
                    if 'description' in field_def and field_def.get('description'):
                        current_api_field['description'] = field_def['description']
                    if 'prompt' in field_def and field_def.get('prompt'): # If 'prompt' key exists from input
                        current_api_field['prompt'] = field_def['prompt']
                    if field_def.get('type') in ['enum', 'multiSelect'] and 'options' in field_def and field_def.get('options'):
                        current_api_field['options'] = field_def['options']
                    
                    if current_api_field.get('key'): # Only add if key is present
                        api_fields.append(current_api_field)
                    else:
                        logger.warning(f"Skipping field due to missing 'key': {field_def}")
                request_body['fields'] = api_fields
            elif metadata_template:
                # Construct the API-compliant metadata_template object
                input_id = metadata_template.get("id", "")
                input_scope = metadata_template.get("scope", "")
                api_scope = input_scope # Default to the provided scope

                if input_scope == "enterprise" and input_id.startswith("enterprise_"):
                    parts = input_id.split('_')
                    # Expected format: enterprise_NumericID_TemplateKey
                    if len(parts) >= 3 and parts[0] == "enterprise" and parts[1].isdigit():
                        api_scope = f"enterprise_{parts[1]}"
                    else:
                        # Log a warning if the format is not as expected but still try to use the provided scope
                        logger.warning(f"Enterprise template ID '{input_id}' does not match expected 'enterprise_ID_key' format. Using provided scope '{input_scope}' for API call.")
                
                api_metadata_template_object = {
                    "type": "metadata_template",
                    "template_key": metadata_template.get("template_key"),
                    "scope": api_scope
                }
                request_body['metadata_template'] = api_metadata_template_object
            else:
                raise ValueError('Either fields or metadata_template must be provided for structured extraction')

            logger.info(f'Making Box AI API call for structured extraction with request: {json.dumps(request_body)}')
            response = requests.post(api_url, headers=headers, json=request_body)

            if response.status_code != 200:
                box_request_id = "N/A"
                error_details = response.text
                try:
                    error_json = response.json()
                    if isinstance(error_json, dict):
                        box_request_id = error_json.get("request_id", "N/A")
                        # You could extract more details here if needed
                        error_details = json.dumps(error_json) 
                except json.JSONDecodeError:
                    # response.text is already set as error_details
                    pass
                logger.error(f'Box AI API error for structured extraction on file {file_id}: {response.status_code} {response.reason}. Request ID: {box_request_id}. Response: {error_details}')
                return {'error': f'Error in Box AI API call: {response.status_code} {response.reason}', 'request_id': box_request_id, 'details': error_details}

            response_data = response.json()
            logger.info(f'Raw Box AI structured extraction response data: {json.dumps(response_data)}')

            processed_response: Dict[str, Any] = {}
            if 'answer' in response_data and isinstance(response_data['answer'], dict):
                answer_dict = response_data['answer']
                if 'fields' in answer_dict and isinstance(answer_dict['fields'], list):
                    logger.info("Processing 'answer' with 'fields' array format.")
                    fields_array = answer_dict['fields']
                    for field_item in fields_array:
                        if isinstance(field_item, dict) and 'key' in field_item and ('value' in field_item):
                            field_key = field_item['key']
                            extracted_value = field_item['value']
                            origin = "default_no_confidence" # Default origin
                            if 'confidence' in field_item:
                                original_ai_confidence = field_item['confidence']
                                if original_ai_confidence not in ['High', 'Medium', 'Low']:
                                    confidence_level = 'Medium'
                                    origin = "default_invalid_confidence"
                                    logger.warning(f"Field {field_key}: AI returned invalid confidence '{original_ai_confidence}'. Defaulting to '{confidence_level}'. Origin: '{origin}'. Raw AI data for field: {field_item}")
                                else:
                                    confidence_level = original_ai_confidence
                                    origin = "ai_provided"
                            else:
                                confidence_level = 'Medium' # Default if 'confidence' key is missing
                                origin = "default_no_confidence"
                                logger.info(f"Field {field_key}: AI response missing 'confidence'. Defaulting to '{confidence_level}'. Origin: '{origin}'. Raw AI data for field: {field_item}")
                            
                            processed_response[field_key] = {
                                'value': extracted_value,
                                'confidence': confidence_level,
                                'confidence_origin': origin
                            }
                        else:
                            logger.warning(f"Skipping invalid item in 'fields' array: {field_item}")
                else:
                    logger.info("Processing 'answer' as standard key-value dictionary.")
                    for field_key, field_data in answer_dict.items():
                        extracted_value = None
                        confidence_level = 'Medium'
                        origin = "default_parsing_fallback" # Default origin, can be overridden
                        try:
                            if isinstance(field_data, dict) and 'value' in field_data and ('confidence' in field_data):
                                extracted_value = field_data['value']
                                original_ai_confidence = field_data['confidence']
                                if original_ai_confidence not in ['High', 'Medium', 'Low']:
                                    confidence_level = 'Medium'
                                    origin = "default_invalid_confidence"
                                    logger.warning(f"Field {field_key}: AI returned invalid confidence '{original_ai_confidence}'. Defaulting to '{confidence_level}'. Origin: '{origin}'. Raw AI data: {field_data}")
                                else:
                                    confidence_level = original_ai_confidence
                                    origin = "ai_provided"
                            elif field_data is None:
                                extracted_value = None
                                confidence_level = 'Low'
                                origin = "default_null_value"
                                logger.info(f"Field {field_key}: AI returned null value. Defaulting to value '{extracted_value}' and confidence '{confidence_level}'. Origin: '{origin}'. Raw AI data: {field_data}")
                            elif isinstance(field_data, dict) and 'value' in field_data and (len(field_data) == 1):
                                extracted_value = field_data['value']
                                confidence_level = 'Medium' # Default confidence if not provided
                                origin = "default_no_confidence"
                                logger.warning(f"Field {field_key}: AI response missing 'confidence' key. Defaulting to '{confidence_level}'. Origin: '{origin}'. Raw AI data: {field_data}")
                            else:
                                extracted_value = field_data
                                confidence_level = 'Medium'
                                origin = "default_parsing_fallback"
                                logger.warning(f"Field {field_key}: Unexpected AI data format. Defaulting to value '{extracted_value}' and confidence '{confidence_level}'. Origin: '{origin}'. Raw AI data: {field_data}")
                            
                            processed_response[field_key] = {
                                'value': extracted_value,
                                'confidence': confidence_level,
                                'confidence_origin': origin
                            }
                        except Exception as e:
                            logger.error(f"Error processing field {field_key} with data '{field_data}': {str(e)}. Assigning Low confidence and default_error_processing origin.")
                            processed_response[field_key] = {
                                'value': field_data, # Store raw data on error
                                'confidence': 'Low',
                                'confidence_origin': "default_error_processing"
                            }

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
                                extracted_value = None
                                confidence_level = 'Medium'
                                origin = "default_parsing_fallback"

                                if isinstance(field_data, dict) and 'value' in field_data and ('confidence' in field_data):
                                    extracted_value = field_data['value']
                                    original_ai_confidence = field_data['confidence']
                                    if original_ai_confidence not in ['High', 'Medium', 'Low']:
                                        confidence_level = 'Medium'
                                        origin = "default_invalid_confidence"
                                        logger.warning(f"Field {field_key}: AI returned invalid confidence '{original_ai_confidence}' in parsed JSON. Defaulting to '{confidence_level}'. Origin: '{origin}'. Raw AI data for field: {field_data}")
                                    else:
                                        confidence_level = original_ai_confidence
                                        origin = "ai_provided"
                                elif isinstance(field_data, dict) and 'value' in field_data: # Value present, confidence missing
                                    extracted_value = field_data['value']
                                    confidence_level = 'Medium'
                                    origin = "default_no_confidence"
                                    logger.warning(f"Field {field_key}: AI response missing 'confidence' in parsed JSON. Defaulting to '{confidence_level}'. Origin: '{origin}'. Raw AI data for field: {field_data}")
                                else: # Not a dict with 'value' or not the expected structure
                                    extracted_value = field_data
                                    confidence_level = 'Medium'
                                    origin = "default_parsing_fallback"
                                    logger.warning(f"Field {field_key}: Unexpected structure in parsed JSON. Defaulting to value '{extracted_value}' and confidence '{confidence_level}'. Origin: '{origin}'. Raw AI data for field: {field_data}")
                                
                                processed_response[field_key] = {
                                    'value': extracted_value,
                                    'confidence': confidence_level,
                                    'confidence_origin': origin
                                }
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
                        confidence_level = 'Medium' # Default confidence
                        origin = "default_parsing_fallback" # Default origin
                        try:
                            if isinstance(field_value, str) and field_value.strip().startswith('{') and field_value.strip().endswith('}'):
                                try:
                                    parsed_value = json.loads(field_value)
                                    if isinstance(parsed_value, dict) and 'value' in parsed_value and ('confidence' in parsed_value):
                                        extracted_value = parsed_value['value']
                                        confidence_level = parsed_value['confidence']
                                        original_ai_confidence = parsed_value['confidence']
                                        if original_ai_confidence not in ['High', 'Medium', 'Low']:
                                            confidence_level = 'Medium'
                                            origin = "default_invalid_confidence"
                                            logger.warning(f"Field {field_key}: AI returned invalid confidence '{original_ai_confidence}' in parsed JSON (from entries). Defaulting to '{confidence_level}'. Origin: '{origin}'. Raw parsed value: {parsed_value}")
                                        else:
                                            confidence_level = original_ai_confidence
                                            origin = "ai_provided"
                                    elif isinstance(parsed_value, dict) and 'value' in parsed_value: # Value present, confidence missing
                                        extracted_value = parsed_value['value']
                                        confidence_level = 'Medium'
                                        origin = "default_no_confidence"
                                        logger.warning(f"Field {field_key}: AI response missing 'confidence' in parsed JSON (from entries). Defaulting to '{confidence_level}'. Origin: '{origin}'. Raw parsed value: {parsed_value}")
                                    else: # Parsed JSON but not the expected structure
                                        extracted_value = field_value 
                                        confidence_level = 'Medium'
                                        origin = "default_parsing_fallback"
                                        logger.warning(f"Field {field_key}: Unexpected structure in parsed JSON (from entries). Defaulting to original value and confidence '{confidence_level}'. Origin: '{origin}'. Raw parsed value: {parsed_value}, Original field value: {field_value}")
                                except json.JSONDecodeError:
                                    extracted_value = field_value 
                                    confidence_level = 'Medium'
                                    origin = "default_parsing_fallback"
                                    logger.warning(f"Field {field_key}: Failed to parse potential JSON value (from entries). Defaulting to value '{extracted_value}' and confidence '{confidence_level}'. Origin: '{origin}'. Raw field value: '{field_value}'")
                            else:
                                extracted_value = field_value 
                                confidence_level = 'Medium'
                                origin = "default_no_confidence" # If not JSON, AI didn't provide confidence structure
                                logger.info(f"Field {field_key}: Value is not a JSON string (from entries). Defaulting to value '{extracted_value}' and confidence '{confidence_level}'. Origin: '{origin}'. Raw field value: '{field_value}'")
                            
                            processed_response[field_key] = {
                                'value': extracted_value,
                                'confidence': confidence_level,
                                'confidence_origin': origin
                            }
                        except Exception as e:
                            logger.error(f"Error processing field {field_key} with value '{field_value}' (from entries): {str(e)}. Assigning Low confidence and default_error_processing origin.")
                            processed_response[field_key] = {
                                'value': field_value, # Store raw data on error
                                'confidence': 'Low',
                                'confidence_origin': "default_error_processing"
                            }
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

    def extract_freeform_metadata(client: Any, file_id: str, prompt: str, ai_model: str = 'azure__openai__gpt_4o_mini') -> Dict[str, Any]:
        """
        Extract freeform metadata from a file using Box AI API
        
        Args:
            client (Any): The Box API client.
            file_id (str): Box file ID
            prompt (str): Extraction prompt
            ai_model (str): AI model to use for extraction
            
        Returns:
            dict: Extracted metadata with confidence scores
        """
        try:
            # client = st.session_state.client # Client is now passed as an argument
            access_token = None
            if hasattr(client, '_oauth'):
                access_token = client._oauth.access_token
            elif hasattr(client, 'auth') and hasattr(client.auth, 'access_token'):
                access_token = client.auth.access_token
            if not access_token:
                raise ValueError('Could not retrieve access token from client')

            headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
            
            enhanced_prompt = prompt
            # Ensure prompt asks for confidence if not already present
            # Refined prompt to be more explicit about the JSON structure for ALL fields.
            if not 'confidence' in prompt.lower(): # Keep the check to avoid redundant additions if user prompt already has it
                enhanced_prompt = prompt + " CRITICALLY IMPORTANT: For ALL pieces of information you extract, you MUST provide your confidence level (High, Medium, or Low) regarding the accuracy of that specific piece of information. Format your entire response as a single JSON object. Each key in this JSON object should correspond to an extracted field. The value for each key MUST be another JSON object containing two keys: 'value' (the extracted information as a string) and 'confidence' (your confidence level: 'High', 'Medium', or 'Low'). Example: { \"InvoiceNumber\": { \"value\": \"INV-123\", \"confidence\": \"High\" }, \"TotalAmount\": { \"value\": \"$500\", \"confidence\": \"Medium\" } }"
            else:
                # If 'confidence' is already in the prompt, ensure the structure is reinforced.
                # This is a lighter touch if the user is already asking for confidence.
                enhanced_prompt = prompt + " Ensure the entire response is a single JSON object where each field's value is a nested object like {\"value\": \"...\", \"confidence\": \"...\"}."


            ai_agent = {
                'type': 'ai_agent_text_gen',
                'basic_text': {
                    'model': ai_model,
                    'prompt': enhanced_prompt,
                    'system_message': 'You are an AI assistant that extracts information from documents. Your primary goal is to return a single, valid JSON object. Every piece of information you identify and extract MUST be structured as a key-value pair within this JSON object, where the key is the field name, and the value is *another* JSON object containing exactly two keys: "value" (the extracted data as a string) and "confidence" (your assessed confidence level: "High", "Medium", or "Low"). Adhere strictly to this format for all extracted data.'
                }
            }
            items = [{'id': file_id, 'type': 'file'}]
            api_url = 'https://api.box.com/2.0/ai/text_gen'
            request_body = {'items': items, 'ai_agent': ai_agent}

            logger.info(f'Making Box AI API call for freeform extraction with request: {json.dumps(request_body)}')
            response = requests.post(api_url, headers=headers, json=request_body)

            if response.status_code != 200:
                box_request_id = "N/A"
                error_details = response.text
                try:
                    error_json = response.json()
                    if isinstance(error_json, dict):
                        box_request_id = error_json.get("request_id", "N/A")
                        error_details = json.dumps(error_json)
                except json.JSONDecodeError:
                    pass
                logger.error(f'Box AI API error for freeform extraction on file {file_id}: {response.status_code} {response.reason}. Request ID: {box_request_id}. Response: {error_details}')
                return {'error': f'Error in Box AI API call: {response.status_code} {response.reason}', 'request_id': box_request_id, 'details': error_details}

            response_data = response.json()
            logger.info(f'Raw Box AI freeform extraction response data: {json.dumps(response_data)}')

            processed_response: Dict[str, Any] = {}
            if 'answer' in response_data and isinstance(response_data['answer'], str):
                response_text = response_data['answer']
                try:
                    # Attempt to find and parse JSON within the answer string
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    if json_start != -1 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        try:
                            parsed_json = json.loads(json_str)
                            if isinstance(parsed_json, dict):
                                for key, value_confidence_pair in parsed_json.items():
                                    extracted_val = None
                                    confidence_val = 'Medium'
                                    origin = "default_parsing_fallback" # Default, will be overridden

                                    if isinstance(value_confidence_pair, dict) and 'value' in value_confidence_pair and 'confidence' in value_confidence_pair:
                                        extracted_val = value_confidence_pair['value']
                                        original_ai_confidence = value_confidence_pair['confidence']
                                        if original_ai_confidence not in ['High', 'Medium', 'Low']:
                                            confidence_val = 'Medium'
                                            origin = "default_invalid_confidence"
                                            logger.warning(f"Field '{key}' (freeform, file_id: {file_id}): AI returned invalid confidence '{original_ai_confidence}'. Defaulting to '{confidence_val}'. Origin: '{origin}'. Raw AI data for field: {value_confidence_pair}")
                                        else:
                                            confidence_val = original_ai_confidence
                                            origin = "ai_provided"
                                    elif isinstance(value_confidence_pair, dict) and 'value' in value_confidence_pair: # Value present, confidence missing
                                        extracted_val = value_confidence_pair['value']
                                        confidence_val = 'Medium'
                                        origin = "default_no_confidence"
                                        logger.warning(f"Field '{key}' (freeform, file_id: {file_id}): AI response missing 'confidence'. Defaulting to '{confidence_val}'. Origin: '{origin}'. Raw AI data for field: {value_confidence_pair}")
                                    else:
                                        # If not in value/confidence format, take the value as is
                                        extracted_val = value_confidence_pair 
                                        confidence_val = 'Medium'
                                        origin = "default_parsing_fallback"
                                        logger.warning(f"Field '{key}' (freeform, file_id: {file_id}): Unexpected AI data format. Expected dict with 'value' and 'confidence', got {type(value_confidence_pair)}. Defaulting to value '{extracted_val}' and confidence '{confidence_val}'. Origin: '{origin}'. Raw AI data for field: {value_confidence_pair}")
                                    
                                    processed_response[key] = {
                                        'value': extracted_val,
                                        'confidence': confidence_val,
                                        'confidence_origin': origin
                                    }
                            else:
                                logger.warning(f"Parsed JSON from 'answer' string for file_id: {file_id} is not a dictionary. Type: {type(parsed_json)}. Parsed content: {parsed_json}. Storing raw answer.")
                                processed_response['_raw_answer'] = response_text
                                processed_response['_error_parsing_json'] = f"Parsed JSON is not a dict: {type(parsed_json)}"
                                processed_response['_confidence_processing_failed'] = True
                        except json.JSONDecodeError as e_json:
                            logger.error(f'Error parsing JSON from freeform answer string for file_id: {file_id}: {str(e_json)}. JSON string attempted: "{json_str}". Raw full answer: "{response_text}"')
                            processed_response['_raw_answer'] = response_text
                            processed_response['_error_parsing_json'] = str(e_json)
                            processed_response['_confidence_processing_failed'] = True
                    else:
                        logger.warning(f"No JSON object found in 'answer' string for file_id: {file_id}. Storing raw answer: \"{response_text}\"")
                        processed_response['_raw_answer'] = response_text
                        processed_response['_confidence_processing_failed'] = True
            elif 'entries' in response_data and len(response_data['entries']) > 0 and 'answer' in response_data['entries'][0]:
                 # Fallback for older API response structure if needed
                response_text = response_data['entries'][0]['answer']
                logger.info(f"Processing 'answer' from 'entries' (fallback) for file_id: {file_id}: {response_text}")
                # For this fallback, we'll assume it might not be structured JSON and store raw.
                # If it were expected to be JSON, the same parsing logic as above would be duplicated here.
                processed_response['_raw_answer_from_entries'] = response_text
                processed_response['_confidence_processing_failed'] = True 
                processed_response['_message'] = "Processed using fallback 'entries' structure, JSON parsing not attempted for this path."
            else:
                logger.warning(f"Neither 'answer' (string) nor 'entries[0].answer' field found in the freeform API response for file_id: {file_id}. Response data: {response_data}")
                processed_response['_error'] = "No 'answer' field in API response or not in expected format."
                processed_response['_confidence_processing_failed'] = True
            return processed_response
        except Exception as e:
            logger.error(f'Error in freeform metadata extraction call for file_id: {file_id}: {str(e)}')
            return {'error': str(e)}

    # Return the dictionary of functions
    return {
        'structured': extract_structured_metadata,
        'freeform': extract_freeform_metadata
    }

# Example of how it might be called (for testing, not part of the module's direct execution)
if __name__ == '__main__':
    # This part is for testing and won't run when imported
    class MockOAuth:
        def __init__(self, token):
            self.access_token = token

    class MockClient:
        def __init__(self, token):
            self._oauth = MockOAuth(token)
            # self.auth = MockOAuth(token) # Alternative way to store auth

    # Simulate Streamlit session state for testing
    st.session_state.client = MockClient("test_access_token")

    functions = get_extraction_functions()
    print(f"Available extraction functions: {list(functions.keys())}")

    # Mock a call (won't actually make an API request without a real token and file)
    # test_file_id = "12345"
    # test_prompt = "Extract the invoice number and total amount."
    # if 'freeform' in functions:
    #     result = functions['freeform'](client=st.session_state.client, file_id=test_file_id, prompt=test_prompt)
    #     print(f"Mock freeform call result: {result}")

    # test_fields = [{'key': 'invoice_number', 'displayName': 'Invoice Number', 'type': 'string'}]
    # if 'structured' in functions:
    #     result_structured = functions['structured'](client=st.session_state.client, file_id=test_file_id, fields=test_fields)
    #     print(f"Mock structured call result: {result_structured}")

