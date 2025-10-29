"""
Integration tests for Smart Document Parser Tool.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock

# Import is handled by conftest.py
from tools.smart_doc_parser import SmartDocParserTool


@pytest.mark.integration
class TestSmartDocParserIntegration:
    """Integration tests for complete workflows."""

    @pytest.fixture(autouse=True)
    def setup_tool(self, mock_runtime, mock_session):
        """Set up test tool instance automatically."""
        self.tool = SmartDocParserTool(runtime=mock_runtime, session=mock_session)
        yield
        # Cleanup if needed
        delattr(self, 'tool')

    @patch('tools.smart_doc_parser.HAS_PYMUPDF', True)
    @patch('requests.get')
    @patch('tools.smart_doc_parser.fitz')
    def test_pdf_text_extraction_workflow(self, mock_fitz, mock_get, sample_pdf_text_bytes):
        """Test complete PDF text extraction workflow."""
        # Mock file download
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = sample_pdf_text_bytes
        mock_get.return_value = mock_response
        
        # Mock PyMuPDF for text extraction
        # Need to mock fitz.open for both _is_pdf_scanned and _extract_text_from_pdf calls
        def create_mock_doc(text_content):
            """Helper to create a mock document with specified text."""
            mock_doc = MagicMock()
            mock_page = Mock()
            mock_page.get_text.return_value = text_content
            mock_doc.__getitem__.return_value = mock_page
            mock_doc.__len__.return_value = 1
            mock_doc.__iter__.return_value = iter([mock_page])
            mock_doc.close.return_value = None
            return mock_doc
        
        # Create mock docs for both calls (scanned check and extraction)
        mock_doc_scanned_check = create_mock_doc("This is extracted PDF text content." * 2)  # > 50 chars
        mock_doc_extraction = create_mock_doc("This is extracted PDF text content.")
        # Return different docs for different calls - fitz.open() is called twice
        calls = [mock_doc_scanned_check, mock_doc_extraction]
        def fitz_open_side_effect(*args, **kwargs):
            return calls.pop(0) if calls else mock_doc_extraction
        mock_fitz.open.side_effect = fitz_open_side_effect
        
        # Mock create_text_message and create_json_message
        text_messages = []
        json_messages = []
        
        def mock_create_text(text):
            msg = Mock()
            msg.type = "text"
            msg.message = text
            text_messages.append(msg)
            return msg
            
        def mock_create_json(data):
            msg = Mock()
            msg.type = "json"
            msg.data = data
            json_messages.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        self.tool.create_json_message = mock_create_json
        
        # Test parameters
        tool_parameters = {
            "prompt": "Extract all text content",
            "file_url": "https://example.com/test.pdf"
        }
        
        # Execute the workflow
        result_generator = self.tool._invoke(tool_parameters)
        results = list(result_generator)
        
        # Verify results
        assert len(results) == 2
        assert any(msg.type == "text" for msg in results)
        assert any(msg.type == "json" for msg in results)
        
        # Verify the JSON result contains expected structure
        json_result = next(msg for msg in results if msg.type == "json")
        assert "pages" in json_result.data
        # Check that the page has content (structure may vary based on processing)
        page_data = json_result.data["pages"][0]
        assert "content" in page_data
        # The content should have the extracted text in raw_text field
        content = page_data["content"]
        assert "raw_text" in content
        assert content["raw_text"] == "This is extracted PDF text content."

    @patch('tools.smart_doc_parser.HAS_PYMUPDF', True)
    @patch('requests.get')
    @patch('tools.smart_doc_parser.fitz')
    @patch('tools.smart_doc_parser.pdfium')
    @patch('tools.smart_doc_parser.OpenAI')
    def test_pdf_ocr_workflow(self, mock_openai, mock_pdfium, mock_fitz, mock_get, sample_pdf_scanned_bytes):
        """Test complete PDF OCR workflow for scanned documents."""
        # Mock file download
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = sample_pdf_scanned_bytes
        mock_get.return_value = mock_response
        
        # Mock PyMuPDF to return no text (scanned PDF) 
        # fitz.open() is only called once in _is_pdf_scanned for scanned PDFs
        mock_doc_scanned = MagicMock()
        mock_page_scanned = Mock()
        mock_page_scanned.get_text.return_value = ""  # No text, will be detected as scanned
        mock_doc_scanned.__getitem__.return_value = mock_page_scanned
        mock_doc_scanned.__len__.return_value = 1
        mock_doc_scanned.__iter__.return_value = iter([mock_page_scanned])
        mock_doc_scanned.close.return_value = None
        mock_fitz.open.return_value = mock_doc_scanned
        
        # Mock pypdfium2 for PDF to image conversion
        from PIL import Image
        mock_pdf_doc = MagicMock()
        mock_pdf_page = Mock()
        mock_bitmap = Mock()

        # Mock PIL Image - need to ensure it's a real Image instance or properly mocked
        mock_image = Image.new('RGB', (100, 100))
        mock_buffer = Mock()
        mock_buffer.getvalue.return_value = b"fake_png_data"
        # Use BytesIO for saving
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
        
        # Mock PdfDocument constructor - it's called with BytesIO
        def mock_pdf_document(bio):
            return mock_pdf_doc
        mock_pdfium.PdfDocument = mock_pdf_document
        
        # Mock OpenAI client response
        mock_client = Mock()
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = '{"extracted_text": "OCR extracted text", "confidence": 0.95}'
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        # Mock create_text_message and create_json_message
        text_messages = []
        json_messages = []
        
        def mock_create_text(text):
            msg = Mock()
            msg.type = "text"
            msg.message = text
            text_messages.append(msg)
            return msg
            
        def mock_create_json(data):
            msg = Mock()
            msg.type = "json"
            msg.data = data
            json_messages.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        self.tool.create_json_message = mock_create_json
        
        # Test parameters
        tool_parameters = {
            "prompt": "Extract text using OCR",
            "file_url": "https://example.com/scanned.pdf",
            "api_key": "override-key",
            "model": "qwen-vl-ocr"
        }
        
        # Execute the workflow
        result_generator = self.tool._invoke(tool_parameters)
        results = list(result_generator)
        
        # Verify results
        assert len(results) == 2
        assert any(msg.type == "text" for msg in results)
        assert any(msg.type == "json" for msg in results)

    @patch('requests.get')
    @patch('tools.smart_doc_parser.HAS_PYTHON_DOCX', True)
    @patch('tools.smart_doc_parser.Document')
    def test_docx_workflow(self, mock_document, mock_get, sample_docx_bytes):
        """Test complete DOCX processing workflow."""
        # Mock file download
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = sample_docx_bytes
        mock_get.return_value = mock_response
        
        # Mock Document processing
        mock_doc = Mock()
        mock_paragraph = Mock()
        mock_paragraph.text = "This is a DOCX document with text content."
        mock_doc.paragraphs = [mock_paragraph]
        mock_doc.tables = []
        mock_document.return_value = mock_doc
        
        # Mock create_text_message and create_json_message
        text_messages = []
        json_messages = []
        
        def mock_create_text(text):
            msg = Mock()
            msg.type = "text"
            msg.message = text
            text_messages.append(msg)
            return msg
            
        def mock_create_json(data):
            msg = Mock()
            msg.type = "json"
            msg.data = data
            json_messages.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        self.tool.create_json_message = mock_create_json
        
        # Test parameters
        tool_parameters = {
            "prompt": "Extract all content from DOCX",
            "file_url": "https://example.com/document.docx"
        }
        
        # Execute the workflow
        result_generator = self.tool._invoke(tool_parameters)
        results = list(result_generator)
        
        # Verify results
        assert len(results) == 2
        json_result = next(msg for msg in results if msg.type == "json")
        assert "pages" in json_result.data
        assert json_result.data["extraction_method"] == "direct_docx_text"

    @patch('requests.get')
    @patch('tools.smart_doc_parser.HAS_TEXTRACT', True)
    @patch('tempfile.NamedTemporaryFile')
    @patch('os.unlink')
    def test_doc_workflow(self, mock_unlink, mock_tempfile, mock_get, sample_doc_bytes):
        """Test complete DOC processing workflow."""
        import tools.smart_doc_parser as parser_module
        
        # Create and inject mock textract
        mock_textract = MagicMock()
        mock_textract.process.return_value = b"This is extracted DOC content."
        original_textract = getattr(parser_module, 'textract', None)
        parser_module.textract = mock_textract
        
        try:
            # Mock file download
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.content = sample_doc_bytes
            mock_get.return_value = mock_response
            
            # Mock temporary file handling
            mock_temp = MagicMock()
            mock_temp.name = "/tmp/test.doc"
            mock_temp.__enter__.return_value = mock_temp
            mock_temp.__exit__.return_value = None
            mock_tempfile.return_value = mock_temp
            
            # Mock create_text_message and create_json_message
            text_messages = []
            json_messages = []
            
            def mock_create_text(text):
                msg = Mock()
                msg.type = "text"
                msg.message = text
                text_messages.append(msg)
                return msg
                
            def mock_create_json(data):
                msg = Mock()
                msg.type = "json"
                msg.data = data
                json_messages.append(msg)
                return msg
            
            self.tool.create_text_message = mock_create_text
            self.tool.create_json_message = mock_create_json
            
            # Test parameters
            tool_parameters = {
                "prompt": "Extract all content from DOC",
                "file_url": "https://example.com/document.doc"
            }
            
            # Execute the workflow
            result_generator = self.tool._invoke(tool_parameters)
            results = list(result_generator)
            
            # Verify results
            assert len(results) == 2
            json_result = next(msg for msg in results if msg.type == "json")
            assert "pages" in json_result.data
            assert json_result.data["extraction_method"] == "direct_doc_text"
        finally:
            # Restore original textract
            if original_textract is not None:
                parser_module.textract = original_textract
            elif hasattr(parser_module, 'textract'):
                delattr(parser_module, 'textract')

    @patch('requests.get')
    def test_image_ocr_workflow(self, mock_get, sample_image_bytes, mock_openai_client):
        """Test complete image OCR workflow."""
        # Mock file download
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = sample_image_bytes
        mock_get.return_value = mock_response
        
        # Mock create_text_message and create_json_message
        text_messages = []
        json_messages = []
        
        def mock_create_text(text):
            msg = Mock()
            msg.type = "text"
            msg.message = text
            text_messages.append(msg)
            return msg
            
        def mock_create_json(data):
            msg = Mock()
            msg.type = "json"
            msg.data = data
            json_messages.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        self.tool.create_json_message = mock_create_json
        
        # Mock OpenAI client
        with patch('openai.OpenAI', return_value=mock_openai_client):
            # Test parameters
            tool_parameters = {
                "prompt": "Extract text from image using OCR",
                "file_url": "https://example.com/image.png",
                "api_key": "test-key"
            }
            
            # Execute the workflow
            result_generator = self.tool._invoke(tool_parameters)
            results = list(result_generator)
            
            # Verify results
            assert len(results) == 2
            json_result = next(msg for msg in results if msg.type == "json")
            assert "pages" in json_result.data
            assert json_result.data["extraction_method"] == "ocr_api"

    def test_missing_prompt_error(self):
        """Test error handling when prompt is missing."""
        # Mock create_text_message
        text_messages = []
        
        def mock_create_text(text):
            msg = Mock()
            msg.type = "text"
            msg.message = text
            text_messages.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        
        # Test parameters without prompt
        tool_parameters = {
            "file_url": "https://example.com/test.pdf"
        }
        
        # Execute the workflow
        result_generator = self.tool._invoke(tool_parameters)
        results = list(result_generator)
        
        # Verify error message
        assert len(results) == 1
        assert results[0].message == "Missing required parameter: prompt"

    def test_missing_file_url_error(self):
        """Test error handling when file_url is missing."""
        # Mock create_text_message
        text_messages = []
        
        def mock_create_text(text):
            msg = Mock()
            msg.type = "text"
            msg.message = text
            text_messages.append(msg)
            return msg
        
        self.tool.create_text_message = mock_create_text
        
        # Test parameters without file_url
        tool_parameters = {
            "prompt": "Extract text"
        }
        
        # Execute the workflow
        result_generator = self.tool._invoke(tool_parameters)
        results = list(result_generator)
        
        # Verify error message
        assert len(results) == 1
        assert results[0].message == "Missing required parameter: file_url"

    def test_invalid_url_error(self):
        """Test error handling for invalid URLs."""
        # Mock create_json_message
        json_messages = []
        
        def mock_create_json(data):
            msg = Mock()
            msg.type = "json"
            msg.data = data
            json_messages.append(msg)
            return msg
        
        self.tool.create_json_message = mock_create_json
        
        # Test parameters with invalid URL (no http/https prefix)
        tool_parameters = {
            "prompt": "Extract text",
            "file_url": "invalid-url"
        }
        
        # Execute the workflow
        result_generator = self.tool._invoke(tool_parameters)
        results = list(result_generator)
        
        # Verify error message - should catch invalid URL before download attempt
        assert len(results) == 1
        # The code validates URL format early, so it should return invalid_file_url
        # If it passed validation but download failed, it would be download_failed
        assert "error" in results[0].data
        # Check if it's either invalid_file_url (early validation) or download_failed (after absolutization)
        assert results[0].data["error"] in ["invalid_file_url", "download_failed"]

    @patch('requests.get')
    def test_download_failure_error(self, mock_get):
        """Test error handling for file download failures."""
        # Mock failed download
        mock_get.side_effect = Exception("Network error")
        
        # Mock create_json_message
        json_messages = []
        
        def mock_create_json(data):
            msg = Mock()
            msg.type = "json"
            msg.data = data
            json_messages.append(msg)
            return msg
        
        self.tool.create_json_message = mock_create_json
        
        # Test parameters
        tool_parameters = {
            "prompt": "Extract text",
            "file_url": "https://example.com/test.pdf"
        }
        
        # Execute the workflow
        result_generator = self.tool._invoke(tool_parameters)
        results = list(result_generator)
        
        # Verify error message
        assert len(results) == 1
        assert results[0].data["error"] == "download_failed"


@pytest.mark.integration
@pytest.mark.requires_api
class TestSmartDocParserAPIIntegration:
    """Integration tests requiring actual API credentials (optional)."""

    @pytest.fixture(autouse=True)
    def setup_tool(self, mock_session):
        """Set up test tool instance with real API credentials if available."""
        import os
        
        # Skip if no API key available
        api_key = os.getenv("ALIYUN_API_KEY")
        if not api_key:
            pytest.skip("ALIYUN_API_KEY not available for API integration tests")
        
        from dify_plugin.entities.tool import ToolRuntime
        
        runtime = ToolRuntime(
            credentials={
                "api_key": api_key,
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-vl-ocr"
            },
            user_id="test-user",
            session_id="test-session"
        )
        self.tool = SmartDocParserTool(runtime=runtime, session=mock_session)
        yield
        # Cleanup if needed
        delattr(self, 'tool')

    @pytest.mark.slow
    def test_real_image_ocr(self):
        """Test with real image using actual OCR API (requires credentials)."""
        # This test would use actual API calls and real images
        # Skip for now to avoid API costs during testing
        pytest.skip("Real API test - uncomment to test with actual credentials")
        
        # Example implementation:
        # tool_parameters = {
        #     "prompt": "Extract all text from this image",
        #     "file_url": "https://example.com/real-image.png"
        # }
        # 
        # result_generator = self.tool._invoke(tool_parameters)
        # results = list(result_generator)
        # 
        # assert len(results) == 2
        # json_result = next(msg for msg in results if msg.type == "json")
        # assert "pages" in json_result.data
