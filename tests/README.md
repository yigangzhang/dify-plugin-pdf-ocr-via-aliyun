# Smart Document Parser Plugin - Test Suite

This directory contains comprehensive tests for the Smart Document Parser Plugin, following Dify plugin testing guidelines.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Shared fixtures and configuration
├── test_smart_doc_parser.py    # Unit tests for core functionality
├── test_integration.py         # Integration tests for complete workflows  
├── test_end_to_end.py          # End-to-end tests for user scenarios
├── data/                       # Test data and mock responses
│   └── sample_responses.py     # Sample API responses and test data
└── README.md                   # This file
```

## Test Categories

### Unit Tests (`test_smart_doc_parser.py`)
Tests individual functions and methods in isolation:
- File type detection
- URL processing
- Text extraction methods
- Field extraction patterns
- Error handling
- Message creation

**Run with:** `pytest tests/test_smart_doc_parser.py -v -m unit`

### Integration Tests (`test_integration.py`)  
Tests complete workflows and component interactions:
- PDF text extraction workflow
- PDF OCR workflow for scanned documents
- DOCX processing workflow
- DOC processing workflow
- Image OCR workflow
- Error handling across workflows

**Run with:** `pytest tests/test_integration.py -v -m integration`

### End-to-End Tests (`test_end_to_e.py`)
Tests realistic user scenarios:
- Invoice processing from PDF
- Meeting notes extraction from DOCX
- Scanned document OCR with structured output
- Multi-page document handling
- Complete error handling workflows

**Run with:** `pytest tests/test_end_to_end.py -v`

### API Tests (Optional)
Tests requiring actual API credentials:
- Real OCR API calls
- Actual file processing

**Run with:** `pytest tests/ -v -m requires_api`

## Running Tests

### Quick Start
```bash
# Run all tests
python run_tests.py

# Run specific test categories
python run_tests.py --unit
python run_tests.py --integration
python run_tests.py --e2e

# Run with coverage
python run_tests.py --coverage
```

### Manual Pytest Commands
```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/ -v -m unit

# Integration tests only  
pytest tests/ -v -m integration

# Skip slow tests
pytest tests/ -v -m "not slow"

# Tests requiring API credentials
pytest tests/ -v -m requires_api

# With coverage report
pytest tests/ --cov=tools --cov=provider --cov-report=html
```

## Test Configuration

### Pytest Configuration (`pytest.ini`)
- Test discovery patterns
- Coverage settings
- Test markers
- Output formatting

### Test Markers
- `unit`: Unit tests
- `integration`: Integration tests  
- `slow`: Tests that take longer to run
- `requires_api`: Tests needing API credentials

## Fixtures and Mock Data

### Core Fixtures (`conftest.py`)
- `mock_runtime`: Mock Dify plugin runtime
- `sample_*_bytes`: Sample file content for testing
- `mock_openai_client`: Mock OpenAI client for OCR tests
- `sample_tool_parameters`: Standard test parameters

### Mock Data (`data/sample_responses.py`)
- Sample API responses
- Expected output structures  
- Error response templates
- Test file metadata

## Environment Variables

### Required for API Tests
```bash
export ALIYUN_API_KEY="your-api-key-here"
```

### Optional for Development
```bash
export PYTEST_CURRENT_TEST="1"  # Enable test mode
export TEST_DEBUG="1"           # Enable debug output
```

## Coverage Requirements

- **Minimum Coverage**: 80%
- **Target Coverage**: 90%+ 
- **Critical Paths**: 95%+ (file processing, error handling)

## CI/CD Integration

### GitHub Actions (`.github/workflows/test.yml`)
- Runs on Python 3.11 and 3.12
- Tests on Ubuntu latest
- Includes linting, unit tests, integration tests
- Generates coverage reports
- Optional API tests with secrets

### Local Development
```bash
# Install test dependencies
pip install -r requirements.txt

# Run linting
flake8 tools/ provider/ --max-line-length=120

# Run full test suite
python run_tests.py --all
```

## Test Development Guidelines

### Writing New Tests
1. **Unit Tests**: Test individual functions with clear inputs/outputs
2. **Integration Tests**: Test complete workflows with mocked external dependencies
3. **E2E Tests**: Test realistic user scenarios with comprehensive mocking

### Best Practices
- Use descriptive test names that explain what's being tested
- Mock external dependencies (API calls, file I/O)
- Test both success and failure scenarios
- Use appropriate test markers
- Keep tests independent and isolated
- Include edge cases and boundary conditions

### Mock Strategy
- **HTTP Requests**: Mock with `responses` or `requests-mock`
- **File Operations**: Use `tempfile` or mock file objects
- **API Clients**: Mock client methods and responses
- **External Libraries**: Mock import and method calls

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Make sure you're in the project root
cd /path/to/pdf-ocr-aliyun

# Install in development mode
pip install -e .
```

**Missing Dependencies**  
```bash
# Install all dependencies including test ones
pip install -r requirements.txt
```

**Coverage Too Low**
- Check which files/lines are not covered: `pytest --cov-report=html`
- Add tests for uncovered code paths
- Remove unnecessary code or mark as no-cover

**API Tests Failing**
- Verify API credentials are set
- Check network connectivity
- Ensure API quota/limits not exceeded

## Contributing

When adding new functionality:
1. Write unit tests first (TDD approach)
2. Add integration tests for workflows
3. Update end-to-end tests for user scenarios  
4. Ensure coverage remains above 80%
5. Update this README if adding new test categories

## Resources

- [Dify Plugin Testing Guidelines](https://docs.dify.ai/plugins/testing)
- [Pytest Documentation](https://docs.pytest.org/)
- [Python Mock Library](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
