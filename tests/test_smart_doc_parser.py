"""
Unit tests for Smart Document Parser Tool.
"""
import pytest
import json
import io
from unittest.mock import Mock, patch, MagicMock

# Import is handled by conftest.py
from tools.smart_doc_parser import SmartDocParserTool


@pytest.mark.unit
class TestSmartDocParserTool:
    """Test cases for SmartDocParserTool main functionality."""

    @pytest.fixture(autouse=True)
    def setup_tool(self, mock_runtime, mock_session):
        """Set up test tool instance automatically."""
        self.tool = SmartDocParserTool(runtime=mock_runtime, session=mock_session)
        yield
        # Cleanup if needed
        delattr(self, 'tool')

    def test_file_type_detection_by_extension(self):
        """Test file type detection based on URL extensions."""
        # Test image extensions
        assert self.tool._detect_file_type("test.png", b"") == "image"
        assert self.tool._detect_file_type("test.jpg", b"") == "image"
        assert self.tool._detect_file_type("test.jpeg", b"") == "image"
        
        # Test PDF extension
        assert self.tool._detect_file_type("test.pdf", b"") == "pdf"
        
        # Test Word document extensions
        assert self.tool._detect_file_type("test.docx", b"") == "docx"
        assert self.tool._detect_file_type("test.doc", b"") == "doc"

    def test_file_type_detection_by_magic_bytes(self, sample_pdf_text_bytes, sample_doc_bytes):
        """Test file type detection based on file magic bytes."""
        # Test PDF magic bytes
        assert self.tool._detect_file_type("unknown", sample_pdf_text_bytes) == "pdf"
        
        # Test DOC magic bytes
        assert self.tool._detect_file_type("unknown", sample_doc_bytes) == "doc"
        
        # Test PNG magic bytes
        png_bytes = b'\x89PNG\r\n\x1a\n' + b'fake_png_data'
        assert self.tool._detect_file_type("unknown", png_bytes) == "image"
        
        # Test JPEG magic bytes
        jpeg_bytes = b'\xff\xd8\xff' + b'fake_jpeg_data'
        assert self.tool._detect_file_type("unknown", jpeg_bytes) == "image"

    def test_extract_file_url_string(self):
        """Test file URL extraction from string input."""
        url = "https://example.com/test.pdf"
        assert self.tool._extract_file_url(url) == url
        
        # Test with whitespace
        assert self.tool._extract_file_url("  " + url + "  ") == url
        
        # Test empty string
        assert self.tool._extract_file_url("") == ""

    def test_extract_file_url_dict(self):
        """Test file URL extraction from dictionary input."""
        test_dict = {"url": "https://example.com/test.pdf"}
        assert self.tool._extract_file_url(test_dict) == "https://example.com/test.pdf"
        
        # Test with different field names
        test_dict = {"file_url": "https://example.com/test.pdf"}
        assert self.tool._extract_file_url(test_dict) == "https://example.com/test.pdf"
        
        # Test with src field
        test_dict = {"src": "https://example.com/test.pdf"}
        assert self.tool._extract_file_url(test_dict) == "https://example.com/test.pdf"

    def test_extract_file_url_json_string(self):
        """Test file URL extraction from JSON string."""
        json_str = '{"url": "https://example.com/test.pdf"}'
        assert self.tool._extract_file_url(json_str) == "https://example.com/test.pdf"

    def test_extract_file_url_list(self):
        """Test file URL extraction from list input."""
        url_list = ["https://example.com/test1.pdf", "https://example.com/test2.pdf"]
        assert self.tool._extract_file_url(url_list) == "https://example.com/test1.pdf"

    def test_absolutize_url_already_absolute(self):
        """Test URL absolutization when URL is already absolute."""
        url = "https://example.com/test.pdf"
        assert self.tool._absolutize_url(url, "http://base.com") == url

    def test_absolutize_url_with_base(self):
        """Test URL absolutization with base URL."""
        relative_url = "/files/test.pdf"
        base_url = "https://example.com"
        expected = "https://example.com/files/test.pdf"
        assert self.tool._absolutize_url(relative_url, base_url) == expected

    def test_absolutize_url_strip_quotes(self):
        """Test URL absolutization strips quotes."""
        quoted_url = '"/files/test.pdf"'
        base_url = "https://example.com"
        expected = "https://example.com/files/test.pdf"
        assert self.tool._absolutize_url(quoted_url, base_url) == expected

    @patch.dict('os.environ', {'FILES_URL': 'https://files.dify.ai'})
    def test_get_auto_base_url_from_env(self):
        """Test getting base URL from environment variables."""
        base_url = self.tool._get_auto_base_url()
        assert base_url == "https://files.dify.ai"

    @patch.dict('os.environ', {'REMOTE_INSTALL_URL': 'http://localhost:5001'})
    def test_get_auto_base_url_localhost(self):
        """Test getting base URL for localhost development."""
        base_url = self.tool._get_auto_base_url()
        assert base_url == "http://localhost"

    def test_safe_json_loads_valid_json(self):
        """Test safe JSON loading with valid JSON."""
        valid_json = '{"key": "value"}'
        result = SmartDocParserTool.safe_json_loads(valid_json)
        assert result == {"key": "value"}

    def test_safe_json_loads_invalid_json(self):
        """Test safe JSON loading with invalid JSON."""
        invalid_json = 'invalid json string'
        result = SmartDocParserTool.safe_json_loads(invalid_json)
        assert result == {"raw": "invalid json string"}

    def test_bytes_to_data_url(self, sample_image_bytes):
        """Test converting bytes to data URL."""
        data_url = self.tool._bytes_to_data_url(sample_image_bytes, "image/png")
        assert data_url.startswith("data:image/png;base64,")

    @patch('tools.smart_doc_parser.fitz')
    def test_is_pdf_scanned_with_text(self, mock_fitz, sample_pdf_text_bytes):
        """Test PDF scanned detection with text content."""
        # Mock PyMuPDF document with text content
        mock_doc = MagicMock()
        mock_page = Mock()
        mock_page.get_text.return_value = "This is sample text content with more than 50 characters."
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = iter([mock_page])
        mock_doc.close.return_value = None
        mock_fitz.open.return_value = mock_doc
        
        result = self.tool._is_pdf_scanned(sample_pdf_text_bytes)
        assert result is False  # Has text, not scanned

    @patch('tools.smart_doc_parser.fitz')
    def test_is_pdf_scanned_without_text(self, mock_fitz, sample_pdf_scanned_bytes):
        """Test PDF scanned detection without text content."""
        # Mock PyMuPDF document without text content
        mock_doc = MagicMock()
        mock_page = Mock()
        mock_page.get_text.return_value = ""  # No text content
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = iter([mock_page])
        mock_doc.close.return_value = None
        mock_fitz.open.return_value = mock_doc
        
        result = self.tool._is_pdf_scanned(sample_pdf_scanned_bytes)
        assert result is True  # No text, scanned

    def test_process_extracted_text(self):
        """Test processing extracted text with prompt."""
        text = "Contact: john@example.com, Phone: 555-0123"
        prompt = "Extract email and phone"
        
        result = self.tool._process_extracted_text(text, prompt)
        
        assert "raw_text" in result
        assert "extracted_fields" in result
        assert "word_count" in result
        assert "character_count" in result
        assert result["raw_text"] == text

    def test_extract_basic_fields_email(self):
        """Test basic field extraction for email addresses."""
        text = "Contact us at support@example.com for help."
        prompt = "extract email addresses"
        
        result = self.tool._extract_basic_fields(text, prompt)
        
        assert "email" in result
        assert result["email"] == "support@example.com"

    def test_extract_basic_fields_phone(self):
        """Test basic field extraction for phone numbers."""
        text = "Call us at 555-123-4567 for support."
        prompt = "extract phone numbers"
        
        result = self.tool._extract_basic_fields(text, prompt)
        
        assert "phone" in result

    def test_extract_basic_fields_date(self):
        """Test basic field extraction for dates."""
        text = "The meeting is scheduled for 12/25/2024."
        prompt = "extract dates"
        
        result = self.tool._extract_basic_fields(text, prompt)
        
        assert "date" in result
        assert "12/25/2024" in result["date"]

    def test_extract_basic_fields_amount(self):
        """Test basic field extraction for amounts."""
        text = "The total cost is $1,234.56 USD."
        prompt = "extract amounts"
        
        result = self.tool._extract_basic_fields(text, prompt)
        
        assert "amount" in result

    def test_create_text_message(self):
        """Test creating text message."""
        with patch.object(self.tool, 'create_text_message') as mock_create:
            mock_create.return_value = Mock(type="text", message="test")
            
            message = self.tool.create_text_message("test")
            assert message.type == "text"
            assert message.message == "test"

    def test_create_json_message(self):
        """Test creating JSON message."""
        with patch.object(self.tool, 'create_json_message') as mock_create:
            mock_create.return_value = Mock(type="json", message={"key": "value"})
            
            message = self.tool.create_json_message({"key": "value"})
            assert message.type == "json"

    @patch('requests.get')
    def test_download_and_detect_file_success(self, mock_get, sample_pdf_text_bytes):
        """Test successful file download and detection."""
        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = sample_pdf_text_bytes
        mock_get.return_value = mock_response
        
        file_bytes, file_type = self.tool._download_and_detect_file("https://example.com/test.pdf")
        
        assert file_bytes == sample_pdf_text_bytes
        assert file_type == "pdf"

    @patch('requests.get')
    def test_download_and_detect_file_failure(self, mock_get):
        """Test file download failure handling."""
        # Mock failed response
        mock_get.side_effect = Exception("Network error")
        
        file_bytes, file_type = self.tool._download_and_detect_file("https://example.com/test.pdf")
        
        assert file_bytes is None
        assert file_type == "unknown"

    def test_format_text_output_valid_json(self):
        """Test formatting result as text output with valid JSON."""
        result = {"pages": [{"page": 1, "content": "test"}]}
        formatted = self.tool._format_text_output(result)
        
        # Should be valid JSON string
        parsed = json.loads(formatted)
        assert parsed == result

    def test_format_text_output_invalid_json(self):
        """Test formatting result as text output with invalid JSON data."""
        # Create an object that can't be JSON serialized
        class NonSerializable:
            pass
        
        result = {"pages": [{"page": 1, "obj": NonSerializable()}]}
        formatted = self.tool._format_text_output(result)
        
        # Should fall back to string representation
        assert isinstance(formatted, str)


@pytest.mark.unit
class TestSmartDocParserToolProcessing:
    """Test cases for file processing methods."""

    @pytest.fixture(autouse=True)
    def setup_tool(self, mock_runtime, mock_session):
        """Set up test tool instance automatically."""
        self.tool = SmartDocParserTool(runtime=mock_runtime, session=mock_session)
        yield
        # Cleanup if needed
        delattr(self, 'tool')

    def test_process_file_by_type_image(self):
        """Test processing image file type."""
        with patch.object(self.tool, '_process_image_with_ocr') as mock_process:
            mock_process.return_value = {"result": "success"}
            
            result = self.tool._process_file_by_type(b"image_data", "image", "prompt", {})
            
            assert result == {"result": "success"}
            mock_process.assert_called_once()

    def test_process_file_by_type_pdf(self):
        """Test processing PDF file type."""
        with patch.object(self.tool, '_process_pdf') as mock_process:
            mock_process.return_value = {"result": "success"}
            
            result = self.tool._process_file_by_type(b"pdf_data", "pdf", "prompt", {})
            
            assert result == {"result": "success"}
            mock_process.assert_called_once()

    def test_process_file_by_type_docx(self):
        """Test processing DOCX file type."""
        with patch.object(self.tool, '_process_docx') as mock_process:
            mock_process.return_value = {"result": "success"}
            
            result = self.tool._process_file_by_type(b"docx_data", "docx", "prompt", {})
            
            assert result == {"result": "success"}
            mock_process.assert_called_once()

    def test_process_file_by_type_doc(self):
        """Test processing DOC file type."""
        with patch.object(self.tool, '_process_doc') as mock_process:
            mock_process.return_value = {"result": "success"}
            
            result = self.tool._process_file_by_type(b"doc_data", "doc", "prompt", {})
            
            assert result == {"result": "success"}
            mock_process.assert_called_once()

    def test_process_file_by_type_unsupported(self):
        """Test processing unsupported file type."""
        result = self.tool._process_file_by_type(b"unknown_data", "unknown", "prompt", {})
        
        assert "error" in result
        assert result["error"] == "unsupported_file_type"

    @patch('tools.smart_doc_parser.HAS_PYTHON_DOCX', True)
    @patch('tools.smart_doc_parser.Document')
    def test_extract_text_from_docx_success(self, mock_document):
        """Test successful DOCX text extraction."""
        # Mock document with paragraphs
        mock_doc = Mock()
        mock_paragraph1 = Mock()
        mock_paragraph1.text = "First paragraph"
        mock_paragraph2 = Mock()
        mock_paragraph2.text = "Second paragraph"
        mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2]
        mock_doc.tables = []
        mock_document.return_value = mock_doc
        
        result = self.tool._extract_text_from_docx(b"docx_data", "extract all text")
        
        assert "pages" in result
        assert result["extraction_method"] == "direct_docx_text"
        assert "First paragraph\nSecond paragraph" in result["pages"][0]["content"]["raw_text"]

    @patch('tools.smart_doc_parser.HAS_PYTHON_DOCX', False)
    def test_extract_text_from_docx_missing_library(self):
        """Test DOCX processing when library is missing."""
        result = self.tool._process_docx(b"docx_data", "extract text")
        
        assert "error" in result
        assert result["error"] == "docx_not_supported"

    @patch('tools.smart_doc_parser.HAS_TEXTRACT', True)
    @patch('tempfile.NamedTemporaryFile')
    @patch('os.unlink')
    def test_extract_text_from_doc_success(self, mock_unlink, mock_tempfile):
        """Test successful DOC text extraction."""
        import sys
        
        # Create a mock textract module and inject it
        mock_textract = MagicMock()
        mock_textract.process.return_value = b"Extracted text from DOC file"
        
        # Inject textract into the module
        import tools.smart_doc_parser as parser_module
        original_textract = getattr(parser_module, 'textract', None)
        parser_module.textract = mock_textract
        
        try:
            # Mock temporary file (use MagicMock for context manager support)
            mock_temp = MagicMock()
            mock_temp.name = "/tmp/test.doc"
            mock_temp.__enter__.return_value = mock_temp
            mock_temp.__exit__.return_value = None
            mock_tempfile.return_value = mock_temp
            
            result = self.tool._extract_text_from_doc(b"doc_data", "extract all text")
            
            assert "pages" in result
            assert result["extraction_method"] == "direct_doc_text"
            assert "Extracted text from DOC file" in result["pages"][0]["content"]["raw_text"]
        finally:
            # Restore original
            if original_textract is not None:
                parser_module.textract = original_textract
            elif hasattr(parser_module, 'textract'):
                delattr(parser_module, 'textract')

    @patch('tools.smart_doc_parser.HAS_TEXTRACT', False)
    def test_extract_text_from_doc_missing_library(self):
        """Test DOC processing when library is missing."""
        result = self.tool._process_doc(b"doc_data", "extract text", {})
        
        assert "error" in result
        assert result["error"] == "doc_processing_requires_conversion"
