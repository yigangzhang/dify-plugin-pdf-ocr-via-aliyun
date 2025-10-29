"""
End-to-end tests for Smart Document Parser Plugin.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from tests.data.sample_responses import (
    SAMPLE_OCR_RESPONSE, SAMPLE_PDF_TEXT, SAMPLE_DOCX_TEXT, 
    SAMPLE_FILE_URLS, EXPECTED_OUTPUT_STRUCTURE
)

# Import is handled by conftest.py
from tools.smart_doc_parser import SmartDocParserTool


@pytest.mark.integration
class TestSmartDocParserE2E:
    """End-to-end tests simulating real user scenarios."""

    @pytest.fixture(autouse=True)
    def setup_tool(self, mock_runtime, mock_session):
        """Set up test tool instance automatically."""
        self.tool = SmartDocParserTool(runtime=mock_runtime, session=mock_session)
        yield
        # Cleanup if needed
        delattr(self, 'tool')

    @patch('requests.get')
    @patch('tools.smart_doc_parser.fitz')
    def test_complete_invoice_processing_workflow(self, mock_fitz, mock_get):
        """Test complete invoice processing from PDF to structured output."""
        # Simulate downloading invoice PDF
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"%PDF-1.4\nInvoice content here..."
        mock_get.return_value = mock_response
        
        # Mock PDF text extraction
        mock_doc = MagicMock()
        mock_page = Mock()
        mock_page.get_text.return_value = SAMPLE_PDF_TEXT
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = iter([mock_page])
        mock_doc.close.return_value = None
        mock_fitz.open.return_value = mock_doc
        
        # Mock message creation
        results = []
        
        def mock_create_text(text):
            msg = Mock(type="text", message=text)
            results.append(msg)
            return msg
            
        def mock_create_json(data):
            msg = Mock(type="json", data=data)
            results.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        self.tool.create_json_message = mock_create_json
        
        # Simulate user requesting invoice field extraction
        tool_parameters = {
            "prompt": "Extract invoice details: number, date, vendor, amount, and line items",
            "file_url": SAMPLE_FILE_URLS["pdf_text"]
        }
        
        # Execute complete workflow
        result_generator = self.tool._invoke(tool_parameters)
        list(result_generator)  # Consume generator
        
        # Verify complete workflow results
        assert len(results) == 2
        
        # Check text output for Direct Reply
        text_result = next(r for r in results if r.type == "text")
        assert text_result.message is not None
        
        # Check structured JSON output
        json_result = next(r for r in results if r.type == "json")
        data = json_result.data
        
        # Verify output structure matches expected format
        assert "pages" in data
        assert len(data["pages"]) == 1
        assert "content" in data["pages"][0]
        assert "extraction_method" in data
        assert data["extraction_method"] == "direct_pdf_text"
        
        # Verify extracted content
        content = data["pages"][0]["content"]
        assert "raw_text" in content
        assert "extracted_fields" in content
        assert SAMPLE_PDF_TEXT.strip() in content["raw_text"]

    @patch('requests.get')
    @patch('tools.smart_doc_parser.HAS_PYTHON_DOCX', True)
    @patch('tools.smart_doc_parser.Document')
    def test_complete_meeting_notes_workflow(self, mock_document, mock_get):
        """Test processing meeting notes from DOCX with contact extraction."""
        # Simulate downloading DOCX file
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"PK\x03\x04[Content_Types].xml"  # DOCX signature
        mock_get.return_value = mock_response
        
        # Mock DOCX processing
        mock_doc = Mock()
        
        # Create mock paragraphs with meeting content
        paragraphs = []
        for line in SAMPLE_DOCX_TEXT.strip().split('\n'):
            if line.strip():
                mock_para = Mock()
                mock_para.text = line.strip()
                paragraphs.append(mock_para)
        
        mock_doc.paragraphs = paragraphs
        mock_doc.tables = []  # No tables in this test
        mock_document.return_value = mock_doc
        
        # Mock message creation
        results = []
        
        def mock_create_text(text):
            msg = Mock(type="text", message=text)
            results.append(msg)
            return msg
            
        def mock_create_json(data):
            msg = Mock(type="json", data=data)
            results.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        self.tool.create_json_message = mock_create_json
        
        # Simulate extracting contacts and dates from meeting notes
        tool_parameters = {
            "prompt": "Extract email addresses, phone numbers, dates, and meeting action items",
            "file_url": SAMPLE_FILE_URLS["docx"]
        }
        
        # Execute workflow
        result_generator = self.tool._invoke(tool_parameters)
        list(result_generator)
        
        # Verify results
        assert len(results) == 2
        
        json_result = next(r for r in results if r.type == "json")
        data = json_result.data
        
        assert data["extraction_method"] == "direct_docx_text"
        
        content = data["pages"][0]["content"]
        assert "email" in content["extracted_fields"]
        assert len(content["extracted_fields"]["email"]) > 0

    @patch('tools.smart_doc_parser.HAS_PYMUPDF', True)
    @patch('requests.get')
    @patch('tools.smart_doc_parser.fitz')
    @patch('tools.smart_doc_parser.pdfium')
    @patch('tools.smart_doc_parser.OpenAI')
    def test_scanned_document_ocr_workflow(self, mock_openai, mock_pdfium, mock_fitz, mock_get):
        """Test OCR processing of scanned document with structured output."""
        # Simulate downloading scanned PDF
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"%PDF-1.4\n<scanned content>"
        mock_get.return_value = mock_response
        
        # Mock PyMuPDF for scanned detection - return no text (scanned)
        mock_doc = MagicMock()
        mock_page = Mock()
        mock_page.get_text.return_value = ""  # No text, detected as scanned
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = iter([mock_page])
        mock_doc.close.return_value = None
        mock_fitz.open.return_value = mock_doc
        
        # Mock PDF rendering to images
        from PIL import Image
        mock_pdf_doc = MagicMock()
        mock_pdf_page = Mock()
        mock_bitmap = Mock()

        # Mock PIL Image - use real Image instance
        mock_image = Image.new('RGB', (100, 100))
        import io
        def mock_save(buf, **kwargs):
            if isinstance(buf, io.BytesIO):
                buf.write(b"fake_png_data")
        mock_image.save = mock_save
        mock_bitmap.to_pil.return_value = mock_image
        mock_pdf_page.render.return_value = mock_bitmap
        mock_pdf_doc.__getitem__.return_value = mock_pdf_page
        mock_pdf_doc.__len__.return_value = 1
        mock_pdf_doc.__iter__.return_value = iter([mock_pdf_page])
        
        # Mock PdfDocument constructor
        def mock_pdf_document(bio):
            return mock_pdf_doc
        mock_pdfium.PdfDocument = mock_pdf_document
        
        # Mock OpenAI OCR response
        mock_client = Mock()
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        
        # Simulate structured OCR response
        mock_message.content = '''
        {
            "document_type": "invoice",
            "invoice_number": "INV-2024-001", 
            "date": "2024-01-15",
            "vendor": "ABC Company",
            "amount": "$1,250.00",
            "line_items": [
                {"description": "Software License", "amount": "$1,000.00"},
                {"description": "Support Services", "amount": "$250.00"}
            ]
        }
        '''
        
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        # Mock message creation
        results = []
        
        def mock_create_text(text):
            msg = Mock(type="text", message=text)
            results.append(msg)
            return msg
            
        def mock_create_json(data):
            msg = Mock(type="json", data=data)
            results.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        self.tool.create_json_message = mock_create_json
        
        # Simulate OCR processing request
        tool_parameters = {
            "prompt": "Extract structured data from this invoice: invoice number, date, vendor, total amount, and line items",
            "file_url": SAMPLE_FILE_URLS["pdf_scanned"],
            "api_key": "test-ocr-key",
            "model": "qwen-vl-ocr"
        }
        
        # Execute OCR workflow 
        result_generator = self.tool._invoke(tool_parameters)
        list(result_generator)
        
        # Verify OCR results
        assert len(results) == 2
        
        json_result = next(r for r in results if r.type == "json")
        data = json_result.data
        
        assert data["extraction_method"] == "ocr_api"
        assert "pages" in data
        assert len(data["pages"]) == 1
        
        # Verify structured OCR output
        page_data = data["pages"][0]
        assert "content" in page_data
        page_content = page_data["content"]
        assert "invoice_number" in page_content
        assert page_content["invoice_number"] == "INV-2024-001"

    def test_error_handling_workflow(self):
        """Test error handling across different failure scenarios."""
        # Mock message creation for errors
        results = []
        
        def mock_create_text(text):
            msg = Mock(type="text", message=text)
            results.append(msg)
            return msg
            
        def mock_create_json(data):
            msg = Mock(type="json", data=data)
            results.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        self.tool.create_json_message = mock_create_json
        
        # Test missing prompt
        tool_parameters = {"file_url": "https://example.com/test.pdf"}
        result_generator = self.tool._invoke(tool_parameters)
        list(result_generator)
        
        assert len(results) == 1
        assert "Missing required parameter: prompt" in results[0].message
        
        # Reset results
        results.clear()
        
        # Test missing file URL
        tool_parameters = {"prompt": "Extract text"}
        result_generator = self.tool._invoke(tool_parameters)
        list(result_generator)
        
        assert len(results) == 1
        assert "Missing required parameter: file_url" in results[0].message
        
        # Reset results
        results.clear()
        
        # Test invalid URL format
        tool_parameters = {
            "prompt": "Extract text",
            "file_url": "not-a-url"
        }
        result_generator = self.tool._invoke(tool_parameters)
        list(result_generator)
        
        assert len(results) == 1
        # URL validation can happen at different stages
        assert "error" in results[0].data
        assert results[0].data["error"] in ["invalid_file_url", "download_failed"]

    @patch('requests.get')
    def test_multi_page_document_workflow(self, mock_get):
        """Test processing multi-page documents."""
        # This test would verify handling of multi-page PDFs
        # For now, we simulate single-page processing as our current
        # implementation treats each page separately
        
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"%PDF-1.4\nMulti-page content"
        mock_get.return_value = mock_response
        
        # Mock message creation
        results = []
        
        def mock_create_json(data):
            msg = Mock(type="json", data=data)
            results.append(msg)
            return msg
        
        self.tool.create_json_message = mock_create_json
        
        # Would test multi-page processing here
        # Currently our implementation processes each page
        # This is a placeholder for future enhancement testing
