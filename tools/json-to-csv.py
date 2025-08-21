from collections.abc import Generator
from collections import OrderedDict
from typing import Any, List, Dict, Union
import json
import csv
import io
import tempfile
import os
from datetime import datetime

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class JsonToCsvTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        json_data_raw = tool_parameters.get("json_data")
        filename = str(tool_parameters.get("filename") or "").strip()
        
        if not json_data_raw:
            yield self.create_text_message("Missing required parameter: json_data")
            return
        
        # Parse the input as a JSON array
        try:
            if isinstance(json_data_raw, str):
                json_data_list = json.loads(json_data_raw.strip())
            else:
                json_data_list = json_data_raw
        except Exception as e:
            yield self.create_text_message(f"Invalid JSON array format: {str(e)}")
            return
            
        # Ensure we have a list
        if not isinstance(json_data_list, list):
            yield self.create_text_message("json_data must be a JSON array of JSON strings")
            return
            
        if len(json_data_list) == 0:
            yield self.create_text_message("json_data array cannot be empty")
            return
            
        # Parse all JSON strings and collect data
        all_data = []
        for i, json_str in enumerate(json_data_list):
            try:
                if isinstance(json_str, str):
                    parsed_data = json.loads(json_str.strip())
                else:
                    parsed_data = json_str
                    
                # Convert single objects to list for consistent processing
                if isinstance(parsed_data, dict):
                    all_data.append(parsed_data)
                elif isinstance(parsed_data, list):
                    all_data.extend(parsed_data)
                else:
                    # Primitive values
                    all_data.append({"value": parsed_data, "source_index": i})
                    
            except Exception as e:
                yield self.create_text_message(f"Invalid JSON in item {i}: {str(e)}")
                return
        
        json_data = all_data
        
        # Convert to CSV format
        try:
            csv_content = self._convert_to_csv(json_data)
        except Exception as e:
            yield self.create_text_message(f"Failed to convert JSON to CSV: {str(e)}")
            return
        
        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}"
        
        # Ensure .csv extension
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        
        # Create temporary file
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig', newline='') as f:
                f.write(csv_content)
                temp_path = f.name
            
            # Read file content as bytes for file message
            with open(temp_path, 'rb') as f:
                file_content = f.read()
            
            # Clean up temp file
            os.unlink(temp_path)
            
            # Return file message
            yield self.create_blob_message(
                blob=file_content,
                meta={'mime_type': 'text/csv', 'filename': filename}
            )
            
            # Also return text summary
            total_input_items = len(json_data_list)
            total_output_rows = len(csv_content.splitlines()) - 1  # Subtract header row
            yield self.create_text_message(
                f"CSV file '{filename}' generated successfully. "
                f"Processed {total_input_items} JSON input(s) into {total_output_rows} CSV rows."
            )
            
        except Exception as e:
            yield self.create_text_message(f"Failed to create CSV file: {str(e)}")
            return
    
    def _convert_to_csv(self, data: Any) -> str:
        """Convert JSON data to CSV format"""
        output = io.StringIO(newline='')
        
        if isinstance(data, list):
            if not data:
                # Empty list
                writer = csv.writer(output)
                writer.writerow(['no_data'])
                csv_content = output.getvalue().strip()
                csv_content = csv_content.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
                return csv_content
            
            # Check if it's a list of objects/dictionaries
            if all(isinstance(item, dict) for item in data):
                # Get fieldnames in order from first item, then add any additional keys
                first_item_flattened = self._flatten_dict(data[0])
                fieldnames = list(first_item_flattened.keys())
                
                # Add any additional keys from other items that weren't in the first item
                all_keys = set(fieldnames)
                for item in data[1:]:
                    item_keys = set(self._flatten_dict(item).keys())
                    new_keys = item_keys - all_keys
                    fieldnames.extend(sorted(new_keys))  # Sort only the new keys
                    all_keys.update(new_keys)
                
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for item in data:
                    flattened = self._flatten_dict(item)
                    # Fill missing keys with empty string
                    row = {key: flattened.get(key, '') for key in fieldnames}
                    writer.writerow(row)
            else:
                # List of primitives or mixed types
                writer = csv.writer(output)
                writer.writerow(['value'])
                for item in data:
                    if isinstance(item, (dict, list)):
                        writer.writerow([json.dumps(item, ensure_ascii=False)])
                    else:
                        writer.writerow([str(item)])
        
        elif isinstance(data, dict):
            # Single object - flatten and create one row
            flattened = self._flatten_dict(data)
            fieldnames = list(flattened.keys())  # Preserve order from the dict
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(flattened)
        
        else:
            # Single primitive value
            writer = csv.writer(output)
            writer.writerow(['value'])
            writer.writerow([str(data)])
        
        # Get the CSV content and clean up any extra line endings
        csv_content = output.getvalue()
        # Remove any trailing whitespace and normalize line endings
        csv_content = csv_content.strip()
        # Ensure consistent line endings (use \r\n for Excel compatibility)
        csv_content = csv_content.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
        return csv_content
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, str]:
        """Flatten nested dictionary into dot-notation keys, preserving key order"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                # Recursively flatten nested dict and preserve order
                nested_items = self._flatten_dict(v, new_key, sep=sep)
                items.extend(nested_items.items())
            elif isinstance(v, list):
                # Convert list to JSON string
                items.append((new_key, json.dumps(v, ensure_ascii=False)))
            else:
                items.append((new_key, str(v) if v is not None else ''))
        # Use OrderedDict to preserve insertion order (though regular dict in Python 3.7+ also preserves order)
        return OrderedDict(items)
