# modules/validation_engine.py
import json
import re
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ValidationRuleLoader:
    def __init__(self, rules_filepath="/home/ubuntu/AIcleanversion/config/validation_rules.json"):
        self.rules_filepath = rules_filepath
        self.rules = self._load_rules()

    def _load_rules(self):
        try:
            with open(self.rules_filepath, 'r') as f:
                rules_data = json.load(f)
                logger.info(f"Successfully loaded validation rules from {self.rules_filepath}")
                return rules_data.get("document_types", [])
        except FileNotFoundError:
            logger.error(f"Validation rules file not found at {self.rules_filepath}. Returning empty rules.")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.rules_filepath}: {e}. Returning empty rules.")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading validation rules: {e}. Returning empty rules.")
            return []

    def get_rules_for_document_type(self, doc_type_name):
        for doc_type_rules in self.rules:
            if doc_type_rules.get("name") == doc_type_name:
                return doc_type_rules
        logger.warning(f"No validation rules found for document type: {doc_type_name}")
        return None

class Validator:
    def __init__(self, rules_for_doc_type):
        self.rules_for_doc_type = rules_for_doc_type if rules_for_doc_type else {"fields": [], "cross_field_rules": []}
        self.field_rules_map = {field_rule["field_name"]: field_rule for field_rule in self.rules_for_doc_type.get("fields", [])}

    def validate_field(self, field_name, value):
        """Applies all validation rules for a specific field and returns validation results."""
        validation_results = []
        field_specific_rules_config = self.field_rules_map.get(field_name)
        
        if not field_specific_rules_config: # No rules defined for this field
            return {"status": "pass", "details": [], "is_mandatory": False, "is_present": value is not None}

        rules_to_apply = field_specific_rules_config.get("validation_rules", [])
        is_mandatory = field_specific_rules_config.get("is_mandatory", False)
        is_present = value is not None and str(value).strip() != ""

        if is_mandatory and not is_present:
            validation_results.append({
                "rule_type": "mandatory_check",
                "status": "fail",
                "message": field_specific_rules_config.get("message_mandatory", f"{field_name} is mandatory but not present."),
                "severity": field_specific_rules_config.get("severity_mandatory", "critical")
            })
            # If mandatory and not present, further value-based validations might not be meaningful or might fail misleadingly
            overall_status = "fail"
            return {"status": overall_status, "details": validation_results, "is_mandatory": is_mandatory, "is_present": is_present}

        # If present or not mandatory, proceed with other rules
        for rule in rules_to_apply:
            rule_type = rule.get("type")
            result = {"rule_type": rule_type, "status": "pass", "message": rule.get("message", "Validation passed."), "severity": rule.get("severity", "medium")}
            
            # Skip value-based validations if value is None/empty and field is not mandatory (or mandatory check already handled)
            if not is_present and rule_type not in ["not_empty", "mandatory_check"]:
                # For optional fields that are empty, most rules (regex, date_format etc.) pass by default or are not applicable
                validation_results.append(result) # Assume pass for non-applicable rules on empty optional fields
                continue

            try:
                if rule_type == "not_empty":
                    if not is_present:
                        result["status"] = "fail"
                elif rule_type == "regex":
                    if not re.match(rule["pattern"], str(value)):
                        result["status"] = "fail"
                elif rule_type == "date_format":
                    datetime.strptime(str(value), rule["format"])
                elif rule_type == "date_range":
                    date_val = datetime.strptime(str(value), rule.get("format", "%Y-%m-%d")) # Assume a default format if not specified for range check
                    now = datetime.now()
                    if "max_days_past" in rule and (now - date_val).days > rule["max_days_past"]:
                        result["status"] = "fail"
                    if "max_days_future" in rule and (date_val - now).days > rule["max_days_future"]:
                        result["status"] = "fail"
                elif rule_type == "numeric":
                    parsed_val = float(str(value).replace(",","")) # basic cleaning
                    if rule.get("allow_negative") is False and parsed_val < 0:
                        result["status"] = "fail"
                elif rule_type == "min_value":
                    if float(str(value).replace(",","")) < rule["value"]:
                        result["status"] = "fail"
                # Add more rule types here (e.g., length, allowed_values)
                else:
                    logger.warning(f"Unknown validation rule type: {rule_type} for field {field_name}")
                    result["status"] = "error"
                    result["message"] = f"Unknown rule type: {rule_type}"
            except Exception as e:
                logger.error(f"Error validating field {field_name} with rule {rule}: {e}")
                result["status"] = "error"
                result["message"] = f"Validation error: {str(e)}"
            
            validation_results.append(result)

        overall_status = "pass"
        for res in validation_results:
            if res["status"] == "fail":
                overall_status = "fail"
                break
            if res["status"] == "error": # If any rule execution had an error, mark overall as error
                overall_status = "error"

        return {"status": overall_status, "details": validation_results, "is_mandatory": is_mandatory, "is_present": is_present}

    def check_mandatory_fields(self, all_extracted_data):
        """Checks if all mandatory fields are present in the extracted data."""
        missing_mandatory_fields = []
        for field_config in self.rules_for_doc_type.get("fields", []):
            field_name = field_config.get("field_name")
            is_mandatory = field_config.get("is_mandatory", False)
            # Check presence in the actual extracted data keys, and that value is not None or empty string
            value = all_extracted_data.get(field_name)
            is_present = value is not None and str(value).strip() != ""
            if is_mandatory and not is_present:
                missing_mandatory_fields.append(field_name)
        
        if not missing_mandatory_fields:
            return {"status": "pass", "message": "All mandatory fields present."}
        else:
            return {"status": "fail", "message": f"Missing mandatory fields: {', '.join(missing_mandatory_fields)}", "missing_fields": missing_mandatory_fields}

    def validate_cross_fields(self, all_extracted_data):
        """Applies cross-field validation rules."""
        cross_field_results = []
        for rule in self.rules_for_doc_type.get("cross_field_rules", []):
            rule_name = rule.get("name")
            fields_involved = rule.get("fields_involved", [])
            condition_str = rule.get("condition") # e.g., "DueDate > InvoiceDate"
            message = rule.get("message", f"Cross-field rule '{rule_name}' failed.")
            severity = rule.get("severity", "medium")
            result = {"rule_name": rule_name, "status": "pass", "message": message, "severity": severity}

            try:
                # Basic condition parsing - This needs to be more robust for complex conditions
                # For now, supports simple comparisons like FieldA > FieldB
                if len(fields_involved) == 2 and ">" in condition_str: # Example
                    field_a_name, field_b_name = fields_involved[0], fields_involved[1]
                    # Ensure field names in condition match fields_involved for safety
                    if field_a_name in condition_str and field_b_name in condition_str:
                        val_a_str = all_extracted_data.get(field_a_name)
                        val_b_str = all_extracted_data.get(field_b_name)

                        if val_a_str is None or val_b_str is None:
                            # If any field involved is missing, rule cannot be evaluated or should be considered a pass/skip
                            result["status"] = "skip" # or 'pass' depending on desired logic for missing data
                            result["message"] = f"Rule '{rule_name}' skipped, one or more fields missing: {field_a_name if val_a_str is None else ''} {field_b_name if val_b_str is None else ''}"
                        else:
                            # Attempt to convert to dates if they look like dates, otherwise string comparison
                            try:
                                # This is a very basic date conversion attempt, assumes YYYY-MM-DD or similar
                                val_a = datetime.strptime(str(val_a_str), "%Y-%m-%d")
                                val_b = datetime.strptime(str(val_b_str), "%Y-%m-%d")
                                if not (val_a > val_b): # Condition: DueDate > InvoiceDate
                                    result["status"] = "fail"
                            except ValueError:
                                # Fallback to string comparison or handle as error if types are incompatible
                                if not (str(val_a_str) > str(val_b_str)):
                                     result["status"] = "fail"
                    else:
                        result["status"] = "error"
                        result["message"] = f"Condition string '{condition_str}' does not match fields_involved for rule '{rule_name}'."
                else:
                    logger.warning(f"Cross-field rule '{rule_name}' condition '{condition_str}' not supported by basic parser.")
                    result["status"] = "skip" # Or error, depending on how strict this should be
                    result["message"] = f"Rule '{rule_name}' condition not supported by basic parser."

            except Exception as e:
                logger.error(f"Error evaluating cross-field rule {rule_name}: {e}")
                result["status"] = "error"
                result["message"] = f"Error evaluating rule: {str(e)}"
            cross_field_results.append(result)
        return cross_field_results

class ConfidenceAdjuster:
    def __init__(self):
        self.confidence_map = {"High": 3, "Medium": 2, "Low": 1}
        self.severity_impact = {"critical": -2, "high": -1.5, "medium": -1, "low": -0.5}

    def adjust_confidence(self, ai_confidence_label, field_validation_results):
        ai_score = self.confidence_map.get(ai_confidence_label, 2) # Default to Medium if unknown
        total_impact = 0

        for validation_detail in field_validation_results.get("details", []):
            if validation_detail.get("status") == "fail":
                severity = validation_detail.get("severity", "medium")
                total_impact += self.severity_impact.get(severity, -1) # Default impact for unknown severity
        
        adjusted_score = ai_score + total_impact
        
        # Cap the scores
        if adjusted_score > 3: adjusted_score = 3
        if adjusted_score < 1: adjusted_score = 1
        
        # Map back to label
        if adjusted_score >= 2.5: return "High"
        if adjusted_score >= 1.5: return "Medium"
        return "Low"

    def suggest_overall_document_confidence(self, all_field_adjusted_confidences, mandatory_check_result, cross_field_check_results):
        """Suggests an overall document confidence based on field confidences and other checks."""
        if not all_field_adjusted_confidences: return "Low" # No fields, low confidence

        # Convert labels to scores for averaging
        scores = [self.confidence_map.get(conf, 1) for conf in all_field_adjusted_confidences.values()]
        avg_score = sum(scores) / len(scores) if scores else 1

        if mandatory_check_result.get("status") == "fail":
            avg_score -= 1 # Significant penalty for missing mandatory fields
        
        for cross_field_res in cross_field_check_results:
            if cross_field_res.get("status") == "fail":
                avg_score -= 0.5 # Penalty for each failed cross-field check
        
        # Cap and map back
        if avg_score > 3: avg_score = 3
        if avg_score < 1: avg_score = 1
        if avg_score >= 2.5: return "High"
        if avg_score >= 1.5: return "Medium"
        return "Low"

# Example Usage (for testing purposes)
if __name__ == '__main__':
    # Setup
    rule_loader = ValidationRuleLoader()
    invoice_rules = rule_loader.get_rules_for_document_type("Invoice")
    
    if invoice_rules:
        validator = Validator(invoice_rules)
        adjuster = ConfidenceAdjuster()

        # --- Test Case 1: Valid InvoiceNumber ---
        print("\n--- Test Case 1: Valid InvoiceNumber ---")
        invoice_num_val_res = validator.validate_field("InvoiceNumber", "INV-123456")
        print(f"Validation for InvoiceNumber ('INV-123456'): {invoice_num_val_res}")
        adjusted_conf = adjuster.adjust_confidence("High", invoice_num_val_res)
        print(f"AI Conf: High, Adjusted Conf: {adjusted_conf}")

        # --- Test Case 2: Invalid InvoiceNumber (format) ---
        print("\n--- Test Case 2: Invalid InvoiceNumber (format) ---")
        invoice_num_val_res_fail = validator.validate_field("InvoiceNumber", "INV-123")
        print(f"Validation for InvoiceNumber ('INV-123'): {invoice_num_val_res_fail}")
        adjusted_conf_fail = adjuster.adjust_confidence("High", invoice_num_val_res_fail)
        print(f"AI Conf: High, Adjusted Conf: {adjusted_conf_fail}")

        # --- Test Case 3: Missing Mandatory InvoiceNumber ---
        print("\n--- Test Case 3: Missing Mandatory InvoiceNumber ---")
        invoice_num_val_res_missing = validator.validate_field("InvoiceNumber", None)
        print(f"Validation for InvoiceNumber (None): {invoice_num_val_res_missing}")
        adjusted_conf_missing = adjuster.adjust_confidence("High", invoice_num_val_res_missing)
        print(f"AI Conf: High, Adjusted Conf: {adjusted_conf_missing}")

        # --- Test Case 4: Valid InvoiceDate ---
        print("\n--- Test Case 4: Valid InvoiceDate ---")
        date_val_res = validator.validate_field("InvoiceDate", "2023-10-26")
        print(f"Validation for InvoiceDate ('2023-10-26'): {date_val_res}")
        adjusted_conf_date = adjuster.adjust_confidence("Medium", date_val_res)
        print(f"AI Conf: Medium, Adjusted Conf: {adjusted_conf_date}")

        # --- Test Case 5: Invalid TotalAmount (negative) ---
        print("\n--- Test Case 5: Invalid TotalAmount (negative) ---")
        amount_val_res = validator.validate_field("TotalAmount", "-100.00")
        print(f"Validation for TotalAmount ('-100.00'): {amount_val_res}")
        adjusted_conf_amount = adjuster.adjust_confidence("High", amount_val_res)
        print(f"AI Conf: High, Adjusted Conf: {adjusted_conf_amount}")

        # --- Test Case 6: Full Extracted Data for an Invoice ---
        print("\n--- Test Case 6: Full Extracted Data for an Invoice ---")
        extracted_data_invoice = {
            "InvoiceNumber": "INV-98765",
            "InvoiceDate": "2023-01-15",
            "DueDate": "2023-01-10", # Intentionally before InvoiceDate for cross-field fail
            "TotalAmount": "1250.75"
            # Missing other mandatory fields if any were defined beyond these
        }
        all_field_confidences = {}
        all_field_validation_statuses = {}

        for field, value in extracted_data_invoice.items():
            val_res = validator.validate_field(field, value)
            all_field_validation_statuses[field] = val_res
            # Assume AI confidence is 'High' for all for this test
            adj_c = adjuster.adjust_confidence("High", val_res)
            all_field_confidences[field] = adj_c
            print(f"Field: {field}, Value: {value}, Validation: {val_res['status']}, AI Conf: High, Adj. Conf: {adj_c}")
        
        mandatory_check = validator.check_mandatory_fields(extracted_data_invoice)
        print(f"Mandatory Fields Check: {mandatory_check}")
        
        cross_field_check = validator.validate_cross_fields(extracted_data_invoice)
        print(f"Cross-Field Checks: {cross_field_check}")

        overall_doc_conf = adjuster.suggest_overall_document_confidence(all_field_confidences, mandatory_check, cross_field_check)
        print(f"Suggested Overall Document Confidence: {overall_doc_conf}")

    else:
        print("Could not load Invoice rules for testing.")


