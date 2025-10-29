"""
Tests for Chinese character support in Smart Document Parser.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import io

from tools.smart_doc_parser import SmartDocParserTool


@pytest.mark.unit
class TestChineseCharacterSupport:
    """Test Chinese character support across all file types."""
    
    @pytest.fixture(autouse=True)
    def setup_tool(self, mock_runtime, mock_session):
        """Set up test tool instance automatically."""
        self.tool = SmartDocParserTool(runtime=mock_runtime, session=mock_session)
        yield
        delattr(self, 'tool')
    
    @patch('tools.smart_doc_parser.HAS_PYMUPDF', True)
    @patch('requests.get')
    @patch('tools.smart_doc_parser.fitz')
    def test_pdf_chinese_text_extraction(self, mock_fitz, mock_get):
        """Test PDF text extraction with Chinese characters."""
        # Chinese text sample
        chinese_text = "这是一个测试文档。包含中文内容。\n标题：智能文档解析器\n内容：支持中文、英文等多种语言。"
        
        # Mock file download
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"%PDF-1.4\n<fake pdf content>"
        mock_get.return_value = mock_response
        
        # Mock PyMuPDF with Chinese text
        def create_mock_doc(text_content):
            mock_doc = MagicMock()
            mock_page = Mock()
            mock_page.get_text.return_value = text_content
            mock_doc.__getitem__.return_value = mock_page
            mock_doc.__len__.return_value = 1
            mock_doc.__iter__.return_value = iter([mock_page])
            mock_doc.close.return_value = None
            return mock_doc
        
        mock_doc_scanned = create_mock_doc(chinese_text * 2)  # > 50 chars
        mock_doc_extraction = create_mock_doc(chinese_text)
        
        calls = [mock_doc_scanned, mock_doc_extraction]
        def fitz_open_side_effect(*args, **kwargs):
            return calls.pop(0) if calls else mock_doc_extraction
        mock_fitz.open.side_effect = fitz_open_side_effect
        
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
        
        # Execute
        tool_parameters = {
            "prompt": "提取所有文本内容",
            "file_url": "https://example.com/chinese.pdf"
        }
        
        result_generator = self.tool._invoke(tool_parameters)
        list(result_generator)
        
        # Verify Chinese text is preserved
        assert len(results) == 2
        json_result = next(r for r in results if r.type == "json")
        page_data = json_result.data["pages"][0]
        assert "content" in page_data
        assert "raw_text" in page_data["content"]
        assert "测试文档" in page_data["content"]["raw_text"]
        assert "智能文档解析器" in page_data["content"]["raw_text"]
    
    @patch('tools.smart_doc_parser.HAS_PYTHON_DOCX', True)
    @patch('requests.get')
    @patch('tools.smart_doc_parser.Document')
    def test_docx_chinese_text_extraction(self, mock_document_class, mock_get):
        """Test DOCX text extraction with Chinese characters."""
        # Chinese text sample
        chinese_text = "这是Word文档测试。\n包含中文内容。\n标题：文档处理\n作者：测试用户"
        
        # Mock file download
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"<fake docx content>"
        mock_get.return_value = mock_response
        
        # Mock python-docx Document
        mock_doc = Mock()
        mock_para1 = Mock()
        mock_para1.text = "这是Word文档测试。"
        mock_para2 = Mock()
        mock_para2.text = "包含中文内容。"
        mock_para3 = Mock()
        mock_para3.text = ""
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_doc.tables = []
        mock_document_class.return_value = mock_doc
        
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
        
        # Execute
        tool_parameters = {
            "prompt": "提取所有文本",
            "file_url": "https://example.com/chinese.docx"
        }
        
        result_generator = self.tool._invoke(tool_parameters)
        list(result_generator)
        
        # Verify Chinese text is preserved
        assert len(results) == 2
        json_result = next(r for r in results if r.type == "json")
        page_data = json_result.data["pages"][0]
        assert "content" in page_data
        assert "raw_text" in page_data["content"]
        assert "Word文档测试" in page_data["content"]["raw_text"]
        assert "中文内容" in page_data["content"]["raw_text"]
    
    @patch('tools.smart_doc_parser.HAS_TEXTRACT', True)
    def test_doc_chinese_text_extraction_encoding(self):
        """Test DOC text extraction with various Chinese encodings."""
        # Manually inject textract mock (since it's conditionally imported)
        import tools.smart_doc_parser
        mock_textract = MagicMock()
        original_textract = getattr(tools.smart_doc_parser, 'textract', None)
        tools.smart_doc_parser.textract = mock_textract
        
        try:
            # Mock textract.process to return UTF-8 encoded bytes
            utf8_text = "这是UTF-8编码的文本。"
            mock_textract.process.return_value = utf8_text.encode('utf-8')
            
            utf8_bytes = b"<fake doc content>"
            result = self.tool._extract_text_from_doc(utf8_bytes, "测试")
            
            # Verify the method handles UTF-8
            assert result is not None
            assert "pages" in result
            assert result["pages"][0]["content"]["raw_text"] == utf8_text
            
            # Test GBK encoding
            gbk_text = "这是GBK编码的文本。"
            mock_textract.process.return_value = gbk_text.encode('gbk')
            
            gbk_bytes = b"<fake doc content>"
            result = self.tool._extract_text_from_doc(gbk_bytes, "测试")
            
            # Verify the method handles GBK
            assert result is not None
            assert "pages" in result
            assert result["pages"][0]["content"]["raw_text"] == gbk_text
            
        finally:
            # Restore original textract
            if original_textract is not None:
                tools.smart_doc_parser.textract = original_textract
            elif hasattr(tools.smart_doc_parser, 'textract'):
                delattr(tools.smart_doc_parser, 'textract')
    
    def test_json_output_chinese_characters(self):
        """Test JSON output preserves Chinese characters."""
        chinese_data = {
            "title": "智能文档解析器",
            "content": "支持中文、英文等多种语言。",
            "metadata": {"author": "测试用户", "date": "2024年1月"}
        }
        
        output = self.tool._format_text_output(chinese_data)
        
        # Verify Chinese characters are preserved
        assert "智能文档解析器" in output
        assert "支持中文" in output
        assert "测试用户" in output
        # Verify it's valid JSON (not escaped)
        import json
        parsed = json.loads(output)
        assert parsed["title"] == "智能文档解析器"
        assert parsed["content"] == "支持中文、英文等多种语言。"
    
    def test_json_parsing_chinese_characters(self):
        """Test JSON parsing preserves Chinese characters from OCR responses."""
        chinese_json = '''{
            "extracted_text": "这是OCR提取的中文文本。",
            "confidence": 0.95,
            "fields": {
                "标题": "测试文档",
                "内容": "包含中文内容"
            }
        }'''
        
        parsed = self.tool.safe_json_loads(chinese_json)
        
        # Verify Chinese characters are preserved
        assert parsed["extracted_text"] == "这是OCR提取的中文文本。"
        assert parsed["fields"]["标题"] == "测试文档"
        assert parsed["fields"]["内容"] == "包含中文内容"
    
    @patch('tools.smart_doc_parser.HAS_PYMUPDF', True)
    @patch('tools.smart_doc_parser.OpenAI')
    @patch('requests.get')
    @patch('tools.smart_doc_parser.fitz')
    @patch('tools.smart_doc_parser.pdfium')
    def test_ocr_chinese_characters(self, mock_pdfium, mock_fitz, mock_get, mock_openai):
        """Test OCR workflow with Chinese characters in response."""
        # Mock file download
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"%PDF-1.4\n<scanned>"
        mock_get.return_value = mock_response
        
        # Mock scanned PDF
        mock_doc = MagicMock()
        mock_page = Mock()
        mock_page.get_text.return_value = ""
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = iter([mock_page])
        mock_doc.close.return_value = None
        mock_fitz.open.return_value = mock_doc
        
        # Mock PDF to image
        from PIL import Image
        mock_pdf_doc = MagicMock()
        mock_pdf_page = Mock()
        mock_bitmap = Mock()
        mock_image = Image.new('RGB', (100, 100))
        import io
        def mock_save(buf, **kwargs):
            if isinstance(buf, io.BytesIO):
                buf.write(b"fake_png")
        mock_image.save = mock_save
        mock_bitmap.to_pil.return_value = mock_image
        mock_pdf_page.render.return_value = mock_bitmap
        mock_pdf_doc.__getitem__.return_value = mock_pdf_page
        mock_pdf_doc.__len__.return_value = 1
        mock_pdf_doc.__iter__.return_value = iter([mock_pdf_page])
        def mock_pdf_document(bio):
            return mock_pdf_doc
        mock_pdfium.PdfDocument = mock_pdf_document
        
        # Mock OCR response with Chinese
        mock_client = Mock()
        mock_api_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = '''{
            "extracted_text": "这是扫描文档的中文内容。包含各种中文字符。",
            "confidence": 0.95
        }'''
        mock_choice.message = mock_message
        mock_api_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_api_response
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
        
        # Execute
        tool_parameters = {
            "prompt": "提取中文文本",
            "file_url": "https://example.com/chinese_scanned.pdf",
            "api_key": "test-key"
        }
        
        result_generator = self.tool._invoke(tool_parameters)
        list(result_generator)
        
        # Verify Chinese characters in OCR response
        assert len(results) == 2
        json_result = next(r for r in results if r.type == "json")
        page_data = json_result.data["pages"][0]
        assert "content" in page_data
        content = page_data["content"]
        assert "extracted_text" in content or "扫描文档" in str(content)

