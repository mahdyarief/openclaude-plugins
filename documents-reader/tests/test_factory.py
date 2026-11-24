"""Tests for the DocumentReaderFactory class.

Coverage:
- get_reader method
- is_supported method
- Supported file types
- Unsupported file type handling
"""

import pytest

from mcp_documents_reader import (
    DocumentReaderFactory,
    DocxReader,
    ExcelReader,
    PdfReader,
    TxtReader,
    XlsReader,
)


class TestDocumentReaderFactory:
    """Test class for DocumentReaderFactory."""

    # ==================== get_reader method tests ====================

    @pytest.mark.parametrize(
        "file_path,expected_reader",
        [
            ("test.txt", TxtReader),
            ("test.TXT", TxtReader),
            ("document.docx", DocxReader),
            ("document.DOCX", DocxReader),
            ("report.pdf", PdfReader),
            ("report.PDF", PdfReader),
            ("data.xlsx", ExcelReader),
            ("data.XLSX", ExcelReader),
            ("data.xls", XlsReader),
            ("data.XLS", XlsReader),
        ],
    )
    def test_get_reader_supported_types(
        self, file_path: str, expected_reader: type
    ) -> None:
        """Test getting the Reader for supported file types.

        Args:
            file_path: File path
            expected_reader: Expected Reader type
        """
        reader = DocumentReaderFactory.get_reader(file_path)
        assert isinstance(reader, expected_reader)

    def test_get_reader_unsupported_type(self) -> None:
        """Test that unsupported file types raise an exception."""
        with pytest.raises(ValueError) as exc_info:
            DocumentReaderFactory.get_reader("test.unknown")

        assert "Unsupported document type" in str(exc_info.value)

    @pytest.mark.parametrize(
        "file_path",
        [
            "test.json",
            "test.xml",
            "test.csv",
            "test.html",
            "test.md",
            "test.rtf",
            "test.odt",
            "test.ods",
            "test",
            "test.",
        ],
    )
    def test_get_reader_various_unsupported_types(self, file_path: str) -> None:
        """Test various unsupported file types.

        Args:
            file_path: Unsupported file path
        """
        with pytest.raises(ValueError):
            DocumentReaderFactory.get_reader(file_path)

    def test_get_reader_with_path_containing_dots(self) -> None:
        """Test a filename that contains multiple dots."""
        reader = DocumentReaderFactory.get_reader("my.document.final.txt")
        assert isinstance(reader, TxtReader)

    def test_get_reader_with_directory_path(self) -> None:
        """Test a file path that includes directories."""
        reader = DocumentReaderFactory.get_reader("/path/to/document.pdf")
        assert isinstance(reader, PdfReader)

    def test_get_reader_with_windows_path(self) -> None:
        """Test Windows path format."""
        reader = DocumentReaderFactory.get_reader(r"C:\Users\test\document.xlsx")
        assert isinstance(reader, ExcelReader)

    # ==================== is_supported method tests ====================

    @pytest.mark.parametrize(
        "file_path",
        [
            "test.txt",
            "test.TXT",
            "test.docx",
            "test.DOCX",
            "test.pdf",
            "test.PDF",
            "test.xlsx",
            "test.XLSX",
            "test.xls",
            "test.XLS",
        ],
    )
    def test_is_supported_returns_true(self, file_path: str) -> None:
        """Test that supported file types return True.

        Args:
            file_path: Supported file path
        """
        assert DocumentReaderFactory.is_supported(file_path) is True

    @pytest.mark.parametrize(
        "file_path",
        [
            "test.json",
            "test.xml",
            "test.csv",
            "test.html",
            "test.md",
            "test.unknown",
            "test",
            "test.",
            "",
        ],
    )
    def test_is_supported_returns_false(self, file_path: str) -> None:
        """Test that unsupported file types return False.

        Args:
            file_path: Unsupported file path
        """
        assert DocumentReaderFactory.is_supported(file_path) is False

    def test_is_supported_case_insensitive(self) -> None:
        """Test that file extension matching is case-insensitive."""
        assert DocumentReaderFactory.is_supported("test.TXT") is True
        assert DocumentReaderFactory.is_supported("test.Docx") is True
        assert DocumentReaderFactory.is_supported("test.PdF") is True

    def test_is_supported_with_complex_paths(self) -> None:
        """Test support detection for complex paths."""
        assert DocumentReaderFactory.is_supported("/a/b/c/d/file.txt") is True
        assert DocumentReaderFactory.is_supported(r"C:\Users\test\file.docx") is True
        assert DocumentReaderFactory.is_supported("./relative/path/file.pdf") is True

    # ==================== New instance tests ====================

    def test_get_reader_returns_new_instance(self) -> None:
        """Test that each call returns a new Reader instance."""
        reader1 = DocumentReaderFactory.get_reader("test.txt")
        reader2 = DocumentReaderFactory.get_reader("test.txt")

        assert reader1 is not reader2
        assert isinstance(reader1, TxtReader)
        assert isinstance(reader2, TxtReader)

    # ==================== Internal mapping tests ====================

    def test_readers_mapping_contains_expected_types(self) -> None:
        """Test that the internal mapping contains all expected file types."""
        readers = DocumentReaderFactory._readers

        assert ".txt" in readers
        assert ".docx" in readers
        assert ".pdf" in readers
        assert ".xlsx" in readers
        assert ".xls" in readers

        assert readers[".txt"] == TxtReader
        assert readers[".docx"] == DocxReader
        assert readers[".pdf"] == PdfReader
        assert readers[".xlsx"] == ExcelReader
        assert readers[".xls"] == XlsReader
