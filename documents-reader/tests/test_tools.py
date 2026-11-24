"""Tests for the MCP tool functions.

Coverage:
- read_document MCP tool function
"""

import os
from pathlib import Path
from unittest import mock

from mcp_documents_reader import read_document

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestReadDocument:
    """Test class for the read_document MCP tool function."""

    def test_read_document_txt_file(self) -> None:
        """Test reading a TXT document."""
        file_path = FIXTURES_DIR / "sample.txt"
        result = read_document(str(file_path))

        assert "测试文本文件" in result
        assert "多行内容" in result

    def test_read_document_docx_file(self) -> None:
        """Test reading a DOCX document."""
        file_path = FIXTURES_DIR / "sample.docx"
        result = read_document(str(file_path))

        assert "测试文档标题" in result

    def test_read_document_pdf_file(self) -> None:
        """Test reading a PDF document."""
        file_path = FIXTURES_DIR / "sample.pdf"
        result = read_document(str(file_path))

        assert "test PDF document" in result

    def test_read_document_excel_file(self) -> None:
        """Test reading an Excel document."""
        file_path = FIXTURES_DIR / "sample.xlsx"
        result = read_document(str(file_path))

        assert "Sheet" in result
        assert "姓名" in result

    def test_read_document_file_not_found(self) -> None:
        """Test reading a nonexistent file."""
        result = read_document("nonexistent.txt")

        assert "Error:" in result
        assert "not found" in result

    def test_read_document_unsupported_type(self) -> None:
        """Test reading an unsupported file type."""
        unsupported_file = FIXTURES_DIR / "test.unsupported"
        unsupported_file.write_text("test content")

        try:
            result = read_document(str(unsupported_file))

            assert "Error:" in result
            assert "Unsupported document type" in result
        finally:
            unsupported_file.unlink()

    def test_read_document_empty_file(self) -> None:
        """Test reading an empty file."""
        file_path = FIXTURES_DIR / "empty.txt"
        result = read_document(str(file_path))

        assert "No text found" in result

    def test_read_document_with_corrupted_file(self) -> None:
        """Test reading a corrupted file."""
        file_path = FIXTURES_DIR / "corrupted.docx"
        result = read_document(str(file_path))

        assert "Error reading DOCX" in result

    def test_read_document_with_gbk_encoding(self) -> None:
        """Test reading a GBK-encoded file."""
        file_path = FIXTURES_DIR / "sample_gbk.txt"
        result = read_document(str(file_path))

        assert "GBK 编码" in result
        assert "中文内容" in result

    def test_read_document_with_special_characters_in_filename(
        self, temp_document_dir: str
    ) -> None:
        """Test a filename containing special characters."""
        special_file = Path(temp_document_dir) / "test file (1).txt"
        special_file.write_text("special content", encoding="utf-8")

        result = read_document(str(special_file))

        assert "special content" in result


class TestReadDocumentWithPathTypes:
    """Tests for read_document with different path types."""

    def test_read_document_with_absolute_path(self) -> None:
        """Test reading a file with an absolute path."""
        file_path = FIXTURES_DIR / "sample.txt"
        absolute_path = file_path.resolve()

        result = read_document(str(absolute_path))

        assert "测试文本文件" in result

    def test_read_document_with_relative_path(self) -> None:
        """Test reading a file with a relative path."""
        original_cwd = os.getcwd()
        try:
            os.chdir(FIXTURES_DIR)
            result = read_document("sample.txt")

            assert "测试文本文件" in result
        finally:
            os.chdir(original_cwd)

    def test_read_document_with_path_object(self) -> None:
        """Test reading a file with a Path object."""
        file_path = FIXTURES_DIR / "sample.txt"
        result = read_document(str(file_path))

        assert "测试文本文件" in result


class TestReadDocumentWithMockedFilesystem:
    """Test class for read_document using a mocked filesystem."""

    @mock.patch("mcp_documents_reader.Path.exists")
    @mock.patch("mcp_documents_reader.DocumentReaderFactory.is_supported")
    @mock.patch("mcp_documents_reader.DocumentReaderFactory.get_reader")
    def test_read_document_calls_reader_correctly(
        self,
        mock_get_reader: mock.MagicMock,
        mock_is_supported: mock.MagicMock,
        mock_exists: mock.MagicMock,
    ) -> None:
        """Test that read_document calls the Reader correctly."""
        mock_exists.return_value = True
        mock_is_supported.return_value = True
        mock_reader = mock.MagicMock()
        mock_reader.read.return_value = "test content"
        mock_get_reader.return_value = mock_reader

        result = read_document("test.txt")

        mock_exists.assert_called_once()
        mock_is_supported.assert_called_once()
        mock_get_reader.assert_called_once()
        mock_reader.read.assert_called_once()

        assert result == "test content"

    @mock.patch("mcp_documents_reader.Path.exists")
    def test_read_document_file_not_exists_mock(
        self, mock_exists: mock.MagicMock
    ) -> None:
        """Test the nonexistent-file case (using mocks)."""
        mock_exists.return_value = False

        result = read_document("test.txt")

        assert "Error:" in result
        assert "not found" in result

    @mock.patch("mcp_documents_reader.Path.exists")
    @mock.patch("mcp_documents_reader.DocumentReaderFactory.is_supported")
    def test_read_document_unsupported_type_mock(
        self, mock_is_supported: mock.MagicMock, mock_exists: mock.MagicMock
    ) -> None:
        """Test an unsupported file type (using mocks)."""
        mock_exists.return_value = True
        mock_is_supported.return_value = False

        result = read_document("test.xyz")

        assert "Error:" in result
        assert "Unsupported document type" in result

    @mock.patch("mcp_documents_reader.Path.exists")
    @mock.patch("mcp_documents_reader.DocumentReaderFactory.is_supported")
    @mock.patch("mcp_documents_reader.DocumentReaderFactory.get_reader")
    def test_read_document_reader_exception(
        self,
        mock_get_reader: mock.MagicMock,
        mock_is_supported: mock.MagicMock,
        mock_exists: mock.MagicMock,
    ) -> None:
        """Test the case where the Reader raises an exception."""
        mock_exists.return_value = True
        mock_is_supported.return_value = True
        mock_get_reader.side_effect = Exception("Reader error")

        result = read_document("test.txt")

        assert "Error reading document" in result
