"""
Sample API responses and test data for Smart Document Parser tests.
"""

# Sample OpenAI API response for OCR processing
SAMPLE_OCR_RESPONSE = {
    "id": "chatcmpl-test123",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "qwen-vl-ocr",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": '{"invoice_number": "INV-2024-001", "date": "2024-01-15", "amount": "$1,250.00", "vendor": "ABC Company"}'
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 30,
        "total_tokens": 80
    }
}

# Sample text extraction results for different file types
SAMPLE_PDF_TEXT = """
Invoice
Invoice Number: INV-2024-001
Date: January 15, 2024
Vendor: ABC Company
Amount: $1,250.00

Item Description:
- Software License: $1,000.00
- Support Services: $250.00

Total: $1,250.00
"""

SAMPLE_DOCX_TEXT = """
Meeting Notes
Date: January 15, 2024
Attendees: John Doe (john@company.com), Jane Smith (jane@company.com)
Phone: 555-0123

Action Items:
1. Review proposal by February 1st
2. Schedule follow-up meeting for February 15th
3. Send contract to legal@company.com

Budget: $50,000 for Q1 2024
"""

SAMPLE_DOC_TEXT = """
Company Policy Document
Effective Date: 12/01/2023
Contact: hr@company.com
Phone: (555) 123-4567

Employee Guidelines:
- Work hours: 9:00 AM - 5:00 PM
- Lunch break: 12:00 PM - 1:00 PM
- Email: All communications must be professional

For questions, contact support@company.com
"""

# Expected field extraction results
EXPECTED_PDF_FIELDS = {
    "email": [],
    "phone": [],
    "date": ["January 15, 2024"],
    "amount": ["$1,250.00", "$1,000.00", "$250.00"]
}

EXPECTED_DOCX_FIELDS = {
    "email": ["john@company.com", "jane@company.com", "legal@company.com"],
    "phone": ["555-0123"],
    "date": ["January 15, 2024", "February 1st", "February 15th"],
    "amount": ["$50,000"]
}

EXPECTED_DOC_FIELDS = {
    "email": ["hr@company.com", "support@company.com"],
    "phone": ["(555) 123-4567"],
    "date": ["12/01/2023"],
    "amount": []
}

# Sample file URLs for testing
SAMPLE_FILE_URLS = {
    "pdf_text": "https://example.com/invoice.pdf",
    "pdf_scanned": "https://example.com/scanned_document.pdf", 
    "docx": "https://example.com/meeting_notes.docx",
    "doc": "https://example.com/policy.doc",
    "image_png": "https://example.com/screenshot.png",
    "image_jpg": "https://example.com/photo.jpg"
}

# Error response samples
ERROR_RESPONSES = {
    "missing_prompt": {
        "error": "missing_parameter",
        "detail": "Missing required parameter: prompt"
    },
    "missing_file_url": {
        "error": "missing_parameter", 
        "detail": "Missing required parameter: file_url"
    },
    "invalid_url": {
        "error": "invalid_file_url",
        "detail": "`file_url` must start with http:// or https://",
        "value": "invalid-url"
    },
    "download_failed": {
        "error": "download_failed",
        "detail": "Could not download or read the file"
    },
    "unsupported_file": {
        "error": "unsupported_file_type",
        "detail": "File type 'unknown' is not supported. Supported types: images, PDF, DOCX, DOC"
    },
    "ocr_api_error": {
        "error": "request_failed",
        "detail": "API request failed: Authentication error"
    }
}

# Expected output structures
EXPECTED_OUTPUT_STRUCTURE = {
    "pages": [
        {
            "page": 1,
            "content": {
                "raw_text": str,
                "extracted_fields": dict,
                "word_count": int,
                "character_count": int
            }
        }
    ],
    "extraction_method": str  # One of: "direct_pdf_text", "direct_docx_text", "direct_doc_text", "ocr_api"
}

# Test file metadata
TEST_FILES_METADATA = {
    "sample.pdf": {
        "size": 12345,
        "type": "application/pdf",
        "magic_bytes": b"%PDF-1.4",
        "expected_type": "pdf"
    },
    "sample.docx": {
        "size": 8765,
        "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
        "magic_bytes": b"PK\x03\x04",
        "expected_type": "docx"
    },
    "sample.doc": {
        "size": 15432,
        "type": "application/msword",
        "magic_bytes": b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',
        "expected_type": "doc"
    },
    "sample.png": {
        "size": 2048,
        "type": "image/png",
        "magic_bytes": b'\x89PNG\r\n\x1a\n',
        "expected_type": "image"
    },
    "sample.jpg": {
        "size": 3072,
        "type": "image/jpeg",
        "magic_bytes": b'\xff\xd8\xff',
        "expected_type": "image"
    }
}
