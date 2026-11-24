"""Tests for the DocumentReader abstract base class and each Reader implementation.

Coverage:
- DocumentReader abstract base class
- DocxReader unit tests
- PdfReader unit tests
- TxtReader unit tests (multiple encodings)
- ExcelReader unit tests
- XlsReader unit tests
"""

from pathlib import Path

import pytest

from mcp_documents_reader import (
    DocumentReader,
    DocxReader,
    ExcelReader,
    PdfReader,
    TxtReader,
    XlsReader,
)


class TestDocumentReader:
    """Test class for the DocumentReader abstract base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that the abstract base class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DocumentReader()  # type: ignore[abstract]

    def test_subclass_must_implement_read(self) -> None:
        """Test that subclasses must implement the read method."""

        class IncompleteReader(DocumentReader):
            """Incomplete Reader implementation."""

            pass

        with pytest.raises(TypeError):
            IncompleteReader()  # type: ignore[abstract]

    def test_subclass_with_read_implementation(self) -> None:
        """Test that a subclass implementing read can be instantiated."""

        class CompleteReader(DocumentReader):
            """Complete Reader implementation."""

            def read(self, file_path: str) -> str:  # noqa: ARG002
                """Read the file content."""
                return "test content"

        reader = CompleteReader()
        assert reader.read("test.txt") == "test content"


class TestDocxReader:
    """Test class for DocxReader."""

    def test_read_docx_with_content(self, sample_docx_file: Path) -> None:
        """Test reading a DOCX file with content.

        Args:
            sample_docx_file: Sample DOCX file path
        """
        reader = DocxReader()
        result = reader.read(str(sample_docx_file))

        # Verify the extracted content contains the expected text
        assert "测试文档标题" in result
        assert "第一段文本内容" in result
        assert "第二段文本内容" in result

    def test_read_docx_with_table(self, sample_docx_file: Path) -> None:
        """Test reading a DOCX file containing a table.

        Args:
            sample_docx_file: Sample DOCX file path
        """
        reader = DocxReader()
        result = reader.read(str(sample_docx_file))

        # Verify the table content is extracted
        assert "姓名" in result
        assert "年龄" in result
        assert "张三" in result
        assert "李四" in result

    def test_read_empty_docx(self, empty_docx_file: Path) -> None:
        """Test reading an empty DOCX file.

        Args:
            empty_docx_file: Empty DOCX file path
        """
        reader = DocxReader()
        result = reader.read(str(empty_docx_file))

        # An empty document should return a prompt message
        assert "No text found" in result

    def test_read_corrupted_docx(self, fixtures_dir: Path) -> None:
        """Test reading a corrupted DOCX file.

        Args:
            fixtures_dir: Fixtures directory path
        """
        reader = DocxReader()
        corrupted_file = fixtures_dir / "corrupted.docx"
        result = reader.read(str(corrupted_file))

        # A corrupted file should return an error message
        assert "Error reading DOCX" in result

    def test_read_nonexistent_file(self) -> None:
        """Test reading a nonexistent file."""
        reader = DocxReader()
        result = reader.read("/nonexistent/path/file.docx")

        assert "Error reading DOCX" in result


class TestPdfReader:
    """Test class for PdfReader."""

    def test_read_pdf_with_content(self, sample_pdf_file: Path) -> None:
        """Test reading a PDF file with content.

        Args:
            sample_pdf_file: Sample PDF file path
        """
        reader = PdfReader()
        result = reader.read(str(sample_pdf_file))

        # Verify the extracted content contains the expected text
        assert "test PDF document" in result
        assert "multiple lines" in result

    def test_read_empty_pdf(self, empty_pdf_file: Path) -> None:
        """Test reading an empty PDF file.

        Args:
            empty_pdf_file: Empty PDF file path
        """
        reader = PdfReader()
        result = reader.read(str(empty_pdf_file))

        # An empty PDF should return a prompt message
        assert "No text found" in result

    def test_read_corrupted_pdf(self, fixtures_dir: Path) -> None:
        """Test reading a corrupted PDF file.

        Args:
            fixtures_dir: Fixtures directory path
        """
        reader = PdfReader()
        corrupted_file = fixtures_dir / "corrupted.pdf"
        result = reader.read(str(corrupted_file))

        # A corrupted file should return an error message
        assert "Error reading PDF" in result

    def test_read_nonexistent_file(self) -> None:
        """Test reading a nonexistent file."""
        reader = PdfReader()
        result = reader.read("/nonexistent/path/file.pdf")

        assert "Error reading PDF" in result


class TestTxtReader:
    """Test class for TxtReader."""

    def test_read_utf8_txt(self, sample_txt_file: Path) -> None:
        """Test reading a UTF-8 encoded TXT file.

        Args:
            sample_txt_file: Sample TXT file path
        """
        reader = TxtReader()
        result = reader.read(str(sample_txt_file))

        # Verify the extracted content
        assert "测试文本文件" in result
        assert "多行内容" in result
        assert "中文" in result

    def test_read_gbk_txt(self, sample_txt_gbk_file: Path) -> None:
        """Test reading a GBK encoded TXT file.

        Args:
            sample_txt_gbk_file: Sample GBK encoded TXT file path
        """
        reader = TxtReader()
        result = reader.read(str(sample_txt_gbk_file))

        # Verify the GBK encoded file is read correctly
        assert "GBK 编码" in result
        assert "中文内容" in result

    def test_read_empty_txt(self, empty_txt_file: Path) -> None:
        """Test reading an empty TXT file.

        Args:
            empty_txt_file: Empty TXT file path
        """
        reader = TxtReader()
        result = reader.read(str(empty_txt_file))

        # An empty file should return a prompt message
        assert "No text found" in result

    def test_read_binary_file(self, fixtures_dir: Path) -> None:
        """Test reading a binary file.

        Note: latin-1 can decode any byte sequence, so a binary file
        will be read successfully by latin-1 and its decoded content returned.

        Args:
            fixtures_dir: Fixtures directory path
        """
        reader = TxtReader()
        binary_file = fixtures_dir / "binary.txt"
        result = reader.read(str(binary_file))

        # latin-1 can decode any byte, so the decoded content is returned
        # Verify that decoded content is returned rather than an error message
        assert result != ""
        assert "Error reading TXT" not in result

    def test_read_nonexistent_file(self) -> None:
        """Test reading a nonexistent file."""
        reader = TxtReader()
        result = reader.read("/nonexistent/path/file.txt")

        # A nonexistent file should return an error message
        assert "Error reading TXT" in result


class TestExcelReader:
    """Test class for ExcelReader."""

    def test_read_excel_with_content(self, sample_excel_file: Path) -> None:
        """Test reading an Excel file with content.

        Args:
            sample_excel_file: Sample Excel file path
        """
        reader = ExcelReader()
        result = reader.read(str(sample_excel_file))

        # Verify the extracted content contains worksheet titles
        assert "=== Sheet: Sheet1 ===" in result
        assert "=== Sheet: Sheet2 ===" in result

    def test_read_excel_sheet1_data(self, sample_excel_file: Path) -> None:
        """Test reading Excel Sheet1 data.

        Args:
            sample_excel_file: Sample Excel file path
        """
        reader = ExcelReader()
        result = reader.read(str(sample_excel_file))

        # Verify Sheet1 data
        assert "姓名" in result
        assert "年龄" in result
        assert "张三" in result
        assert "李四" in result

    def test_read_excel_sheet2_data(self, sample_excel_file: Path) -> None:
        """Test reading Excel Sheet2 data.

        Args:
            sample_excel_file: Sample Excel file path
        """
        reader = ExcelReader()
        result = reader.read(str(sample_excel_file))

        # Verify Sheet2 data
        assert "产品" in result
        assert "价格" in result
        assert "苹果" in result
        assert "香蕉" in result

    def test_read_empty_excel(self, empty_excel_file: Path) -> None:
        """Test reading an empty Excel file.

        Args:
            empty_excel_file: Empty Excel file path
        """
        reader = ExcelReader()
        result = reader.read(str(empty_excel_file))

        # An empty Excel file should return a prompt message or worksheet titles
        # Because there is an empty worksheet, titles may be returned with no data
        assert "Sheet" in result or "No text found" in result

    def test_read_corrupted_excel(self, fixtures_dir: Path) -> None:
        """Test reading a corrupted Excel file.

        Args:
            fixtures_dir: Fixtures directory path
        """
        reader = ExcelReader()
        corrupted_file = fixtures_dir / "corrupted.xlsx"
        result = reader.read(str(corrupted_file))

        # A corrupted file should return an error message
        assert "Error reading Excel" in result

    def test_read_nonexistent_file(self) -> None:
        """Test reading a nonexistent file."""
        reader = ExcelReader()
        result = reader.read("/nonexistent/path/file.xlsx")

        assert "Error reading Excel" in result

class TestXlsReader:
    """Test class for XlsReader."""

    def test_read_xls_with_content(self, sample_xls_file: Path) -> None:
        """Test reading a legacy XLS file with content.

        Args:
            sample_xls_file: Sample XLS file path
        """
        reader = XlsReader()
        result = reader.read(str(sample_xls_file))

        assert "=== Sheet: Sheet1 ===" in result
        assert "Name" in result
        assert "Value" in result
        assert "A" in result
        assert "2" in result

    def test_read_corrupted_xls(self, fixtures_dir: Path) -> None:
        """Test reading a corrupted XLS file.

        Args:
            fixtures_dir: Fixtures directory path
        """
        reader = XlsReader()
        result = reader.read(str(fixtures_dir / "corrupted.xls"))

        assert "Error reading Excel" in result

    def test_read_nonexistent_xls(self) -> None:
        """Test reading a nonexistent XLS file."""
        reader = XlsReader()
        result = reader.read("/nonexistent/path/file.xls")

        assert "Error reading Excel" in result
