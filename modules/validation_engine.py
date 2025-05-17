# modules/validation_engine.py
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union


logger = logging.getLogger(__name__)

class ValidationRuleLoader:
    def __init__(self, rules_config_path: str):
        self.rules_config_path = rules_config_path
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        try:
            with open(self.rules_config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Successfully loaded validation rules from {self.rules_config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"Validation rules file not found at {self.rules_config_path}. Using empty ruleset.")
            return {"document_types": [], "template_rules": []}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.rules_config_path}. Using empty ruleset.")
            return {"document_types": [], "template_rules": []}
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading validation rules: {e}. Using empty ruleset.")
            return {"document_types": [], "template_rules": []}

    def get_rules_for_doc_type(self, doc_type_name: Optional[str]) -> Dict[str, Any]:
        if not doc_type_name:
            doc_type_name = "Default"
        
        specific_rules = self.rules.get("document_types", {}).get(doc_type_name)
        if specific_rules:
            logger.debug(f"Found specific rules for document type: {doc_type_name}")
            return specific_rules
        
        default_rules = self.rules.get("document_types", {}).get("Default")
        if default_rules:
            logger.debug(f"No specific rules for {doc_type_name}, using 'Default' rules.")
            return default_rules
            
        logger.warning(f"No validation rules found for document type '{doc_type_name}' or 'Default'. Returning empty rules.")
        return {"fields": [], "mandatory_fields": []}
        
    def get_rules_for_category_template(self, doc_category: Optional[str], template_id: Optional[str]) -> Dict[str, Any]:
        """Get validation rules for a specific template (simplified approach)
        
        Args:
            doc_category: Document category (from document categorization) - can be None in simplified approach
            template_id: Metadata template ID (from metadata template selection)
            
        Returns:
            Dict containing the validation rules specific to this template
        """
        if not template_id:
            logger.debug("Missing template ID, cannot get template-specific rules")
            return {"fields": [], "mandatory_fields": []}
        
        # Extract clean template ID if it's in the 'scope_template' format
        clean_template_id = template_id
        if '_' in template_id:
            parts = template_id.split('_')
            if len(parts) >= 2:
                clean_template_id = parts[-1]  # Take the last part after the underscore
        
        logger.info(f"Looking for rules with template_id='{template_id}' or '{clean_template_id}'")
        
        # Load the full ruleset to access the template_rules
        try:
            # Make sure we have the latest rules loaded
            if hasattr(self, 'rules') and self.rules:
                full_config = self.rules
            else:
                with open(self.rules_config_path, 'r') as f:
                    full_config = json.load(f)
                    self.rules = full_config
            
            # First check the template_rules array (new approach)
            template_rules = full_config.get("template_rules", [])
            logger.info(f"Found {len(template_rules)} template rules in config")
            
            # Find the matching template rule by trying both original ID and cleaned ID
            matching_rule = next((rule for rule in template_rules 
                                  if rule.get("template_id") == template_id), None)
            
            if not matching_rule:
                # Try with clean template ID
                matching_rule = next((rule for rule in template_rules 
                                     if rule.get("template_id") == clean_template_id), None)
            
            if matching_rule:
                logger.info(f"Found specific rules for template '{template_id}'")
                # Ensure we have all the expected keys, even if they're empty
                return {
                    "fields": matching_rule.get("fields", []),
                    "mandatory_fields": matching_rule.get("mandatory_fields", [])
                }
            
            # If no rules found in template_rules, check for document_types structure
            # This handles rules created with the original structure format
            document_types = full_config.get("document_types", [])
            logger.info(f"Found {len(document_types)} document types in config")
            
            # Check if we have a document type that matches our template_id (or clean version)
            template_doc_type = next((dt for dt in document_types if dt.get("name") == template_id), None)
            
            if not template_doc_type:
                # Try with clean template ID
                template_doc_type = next((dt for dt in document_types if dt.get("name") == clean_template_id), None)
            
            if template_doc_type:
                logger.info(f"Found specific document type rules for template '{template_id}'")
                return {
                    "fields": template_doc_type.get("fields", []),
                    "mandatory_fields": template_doc_type.get("mandatory_fields", [])
                }
                
        except Exception as e:
            logger.error(f"Error loading template rules: {e}")
        
        logger.warning(f"No specific rules found for template '{template_id}' or '{clean_template_id}'")
        return {"fields": [], "mandatory_fields": []}

class Validator:
    def __init__(self):
        pass
            
    def _validate_field(self, field_key: str, value: Any, rules: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Validate a field value against a list of validation rules
        
        Args:
            field_key: Field key
            value: Field value
            rules: List of validation rules
            
        Returns:
            Tuple with (passed, messages)
        """
        if not rules:
            return True, []
            
        all_passed = True
        messages = []
        
        for rule in rules:
            rule_type = rule.get("type")
            rule_name = rule.get("name", f"{rule_type} Rule")
            
            if rule_type == "regex":
                pattern = rule.get("pattern", "")
                if pattern:
                    try:
                        if value is None or (isinstance(value, str) and not re.match(pattern, value)):
                            all_passed = False
                            messages.append(f"{rule_name}: Value '{value}' does not match pattern '{pattern}'")
                    except Exception as e:
                        all_passed = False
                        messages.append(f"{rule_name}: Error validating regex: {e}")
                        
            elif rule_type == "enum":
                allowed_values = rule.get("values", "").split(",")
                cleaned_allowed_values = [v.strip() for v in allowed_values]
                if cleaned_allowed_values and value is not None:
                    str_value = str(value).strip()
                    if str_value not in cleaned_allowed_values:
                        all_passed = False
                        messages.append(f"{rule_name}: Value '{value}' is not in allowed values: {', '.join(cleaned_allowed_values)}")
                        
            elif rule_type == "min_length":
                min_length = rule.get("length", 0)
                try:
                    min_length = int(min_length)
                    if value is None or (isinstance(value, str) and len(value) < min_length):
                        all_passed = False
                        messages.append(f"{rule_name}: Value length ({0 if value is None else len(value)}) is less than minimum length ({min_length})")
                except ValueError:
                    all_passed = False
                    messages.append(f"{rule_name}: Invalid minimum length: {min_length}")
                    
            elif rule_type == "max_length":
                max_length = rule.get("length", 0)
                try:
                    max_length = int(max_length)
                    if value is not None and isinstance(value, str) and len(value) > max_length:
                        all_passed = False
                        messages.append(f"{rule_name}: Value length ({len(value)}) exceeds maximum length ({max_length})")
                except ValueError:
                    all_passed = False
                    messages.append(f"{rule_name}: Invalid maximum length: {max_length}")
                    
            elif rule_type == "dataType":
                type_name = rule.get("type", "")
                if not self._validate_data_type(value, type_name):
                    all_passed = False
                    messages.append(f"{rule_name}: Value '{value}' is not of type '{type_name}'")
                    
        return all_passed, messages
        
    def _validate_data_type(self, value: Any, type_name: str) -> bool:
        """Validate that a value is of the specified data type"""
        if value is None:
            return False
            
        if type_name == "string":
            return isinstance(value, str)
        elif type_name == "number":
            try:
                float(value)
                return True
            except (ValueError, TypeError):
                return False
        elif type_name == "boolean":
            return isinstance(value, bool) or (isinstance(value, str) and value.lower() in ("true", "false"))
        elif type_name == "date":
            if isinstance(value, str):
                try:
                    # Try to parse as ISO date
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return True
                except ValueError:
                    try:
                        # Try common date formats
                        datetime.strptime(value, "%Y-%m-%d")
                        return True
                    except ValueError:
                        try:
                            datetime.strptime(value, "%m/%d/%Y")
                            return True
                        except ValueError:
                            return False
            return False
        return True  # Unknown type, assume valid
        
    def _check_mandatory_fields(self, ai_response: Dict[str, Any], mandatory_fields: List[str]) -> Tuple[bool, List[str]]:
        """Check that all mandatory fields are present and not empty"""
        missing = []
        for field_key in mandatory_fields:
            field_present = False
            field_value = None
            
            # Check both direct field_key and normalized variations
            if field_key in ai_response:
                field_present = True
                field_value = ai_response[field_key]
            else:
                # Try case-insensitive match or with common variations (spaces, underscores, etc.)
                normalized_field_key = field_key.lower().replace(" ", "_").replace("-", "_")
                for response_key in ai_response.keys():
                    normalized_response_key = response_key.lower().replace(" ", "_").replace("-", "_")
                    if normalized_response_key == normalized_field_key:
                        field_present = True
                        field_value = ai_response[response_key]
                        break
            
            # If field is present, check if it has a value
            if field_present:
                # Handle both formats: direct values and dictionary with 'value' key
                if isinstance(field_value, dict) and "value" in field_value:
                    actual_value = field_value.get("value")
                else:
                    actual_value = field_value
                
                # Check if the value is empty
                if actual_value is None or (isinstance(actual_value, str) and actual_value.strip() == ""):
                    missing.append(field_key)
            else:
                missing.append(field_key)
        return not missing, missing
        
    def validate(self, ai_response: Dict[str, Any], doc_type: Optional[str] = None, doc_category: Optional[str] = None, template_id: Optional[str] = None) -> Dict[str, Any]:
        """Validate AI response against validation rules
        
        Args:
            ai_response: AI response to validate
            doc_type: Document type of the document being processed
            doc_category: Document category of the document
            template_id: Metadata template ID used for processing
        
        Returns:
            Validation results
        """
        # Load validation rules
        rules_loader = ValidationRuleLoader("config/validation_rules.json")
        
        # Get template-specific rules
        template_rules = rules_loader.get_rules_for_category_template(doc_category, template_id)
        
        # If AI response is not a dict, return validation error
        if not isinstance(ai_response, dict):
            logger.warning(f"AI response is not a dictionary. Cannot perform validation.")
            return {
                "field_validations": {},
                "mandatory_check": {"status": "Error", "message": "AI response not a dict"}
            }

        # Initialize field validations
        field_validations = {}

        # 1. Validate fields based on template rules
        template_fields = template_rules.get("fields", [])
        
        # Process each field in the template rules
        for field_def in template_fields:
            field_key = field_def.get("key")
            field_rules = field_def.get("rules", [])
            
            # Log the field we're checking for debugging
            logger.info(f"Checking validation rules for field '{field_key}' with {len(field_rules)} rules")
            
            # Check both direct field_key and normalized variations
            field_found = False
            actual_field_key = field_key
            field_value = None
            
            # Try exact match first
            if field_key and field_key in ai_response:
                field_found = True
                field_value = ai_response[field_key]
                logger.info(f"Field '{field_key}' found in response (exact match)")
            else:
                # Try case-insensitive match or with common variations (spaces, underscores, etc.)
                if field_key is not None:  # Skip if field_key is None
                    try:
                        normalized_field_key = field_key.lower().replace(" ", "_").replace("-", "_")
                        for response_key in ai_response.keys():
                            if response_key is not None:  # Skip None keys in response
                                try:
                                    normalized_response_key = response_key.lower().replace(" ", "_").replace("-", "_")
                                    if normalized_response_key == normalized_field_key:
                                        field_found = True
                                        actual_field_key = response_key  # Use the actual key from the response
                                        field_value = ai_response[response_key]
                                        logger.info(f"Field '{field_key}' found as '{response_key}' in response (normalized match)")
                                        break
                                except (AttributeError, TypeError):
                                    # Skip keys that can't be normalized
                                    continue
                    except (AttributeError, TypeError):
                        # Skip fields that can't be normalized
                        logger.warning(f"Skipping field with invalid key: {field_key}")
                        continue
            
            if field_found and field_value is not None:
                # Handle both formats: direct values and dictionary with 'value' key
                if isinstance(field_value, dict) and "value" in field_value:
                    actual_value = field_value.get("value")
                else:
                    actual_value = field_value
                
                is_valid, messages = self._validate_field(field_key, actual_value, field_rules)
                field_validations[field_key] = {
                    "is_valid": is_valid,
                    "status": "pass" if is_valid else "fail",
                    "messages": messages
                }
                logger.info(f"Validation result for '{field_key}': {'PASS' if is_valid else 'FAIL'}")
            else:
                # Field not found in response
                field_validations[field_key] = {
                    "is_valid": True,  # Not present = valid (skip)
                    "status": "skip",
                    "messages": [f"Field '{field_key}' not found in response"]
                }
                logger.info(f"Field '{field_key}' not found in response, marked as SKIP")
        
        # 2. Check mandatory fields
        mandatory_fields = template_rules.get("mandatory_fields", [])
        mandatory_passed, missing_fields = self._check_mandatory_fields(ai_response, mandatory_fields)
        
        mandatory_check_result = {
            "status": "Passed" if mandatory_passed else "Failed",
            "missing_fields": missing_fields
        }
        
        # Compile and return validation results
        return {
            "field_validations": field_validations,
            "mandatory_check": mandatory_check_result
        }

class ConfidenceAdjuster:
    def __init__(self, high_confidence_threshold=0.8, medium_confidence_threshold=0.5, low_confidence_penalty=0.2, validation_failure_penalty=0.3, mandatory_failure_penalty=0.4):
        self.high_confidence_threshold = high_confidence_threshold
        self.medium_confidence_threshold = medium_confidence_threshold
        self.low_confidence_penalty = low_confidence_penalty
        self.validation_failure_penalty = validation_failure_penalty
        self.mandatory_failure_penalty = mandatory_failure_penalty
    
    def _get_qualitative_confidence(self, score: float) -> str:
        """Convert numerical confidence score to qualitative value"""
        if score >= self.high_confidence_threshold:
            return "High"
        elif score >= self.medium_confidence_threshold:
            return "Medium"
        return "Low"

    def _get_numeric_confidence(self, confidence: Union[float, str, dict]) -> float:
        """Convert various confidence formats to numeric value"""
        if isinstance(confidence, (int, float)):
            return float(confidence)
        elif isinstance(confidence, str):
            confidence_map = {"High": 0.9, "Medium": 0.6, "Low": 0.3}
            return confidence_map.get(confidence, 0.0)
        elif isinstance(confidence, dict):
            if "confidence" in confidence:
                return self._get_numeric_confidence(confidence["confidence"])
            elif "value" in confidence:
                return self._get_numeric_confidence(confidence["value"])
        return 0.0
    
    def adjust_confidence(self, ai_response: Dict[str, Any], validation_output: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust confidence scores based on validation results"""
        field_validations = validation_output.get("field_validations", {})
        mandatory_check = validation_output.get("mandatory_check", {})
        
        # Create a deep copy to avoid modifying the original
        adjusted_output = {}
        
        for field_key, field_data in ai_response.items():
            # Skip metadata fields
            if field_key.startswith("_"):
                continue
            
            # Get original confidence (handle different formats)
            if isinstance(field_data, dict):
                original_confidence = self._get_numeric_confidence(field_data.get("confidence", 0.0))
                field_value = field_data.get("value")
            else:
                original_confidence = 0.0
                field_value = field_data
            
            # Start with original confidence
            adjusted_confidence = original_confidence
            
            # Apply validation penalties
            field_validation = field_validations.get(field_key, {})
            if field_validation.get("status") == "fail":
                adjusted_confidence = max(0.0, adjusted_confidence - self.validation_failure_penalty)
            
            # Apply mandatory field penalty
            if field_key in mandatory_check.get("missing_fields", []):
                adjusted_confidence = max(0.0, adjusted_confidence - self.mandatory_failure_penalty)
            
            # Apply low confidence penalty
            if original_confidence < self.medium_confidence_threshold:
                adjusted_confidence = max(0.0, adjusted_confidence - self.low_confidence_penalty)
            
            # Create adjusted field data
            adjusted_field = {
                "value": field_value,
                "original_confidence": original_confidence,
                "original_confidence_qualitative": self._get_qualitative_confidence(original_confidence),
                "confidence": adjusted_confidence,
                "confidence_qualitative": self._get_qualitative_confidence(adjusted_confidence)
            }
            
            adjusted_output[field_key] = adjusted_field
        
        return adjusted_output
    
    def get_overall_document_status(self, adjusted_confidence_output: Dict[str, Any], validation_output: Dict[str, Any]) -> Dict[str, str]:
        """Get the overall document confidence status after adjustments"""
        # Calculate the average adjusted confidence across all fields
        confidence_values = []
        for field_key, field_data in adjusted_confidence_output.items():
            if isinstance(field_data, dict) and "confidence" in field_data:
                confidence_values.append(field_data.get("confidence", 0.0))
        
        avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        overall_confidence_qualitative = self._get_qualitative_confidence(avg_confidence)
        
        # Factor in mandatory fields status
        mandatory_check = validation_output.get("mandatory_check", {})
        mandatory_status = mandatory_check.get("status", "Failed")
        
        messages = []
        if mandatory_status == "Failed":
            messages.append(f"Document is missing mandatory fields: {', '.join(mandatory_check.get('missing_fields', []))}.")
            if overall_confidence_qualitative != "low":
                overall_confidence_qualitative = "medium"  # Lower high confidence if mandatory fields missing
        
        if confidence_values:
            messages.append(f"Average confidence: {avg_confidence:.2f}.")
            messages.append(f"Document status is {overall_confidence_qualitative}.")
            
        return {"status": overall_confidence_qualitative, "messages": messages}
