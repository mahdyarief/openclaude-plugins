"""pytest configuration and shared fixtures.

Provides the shared configuration and fixture objects used by the tests:
- Test document file paths
- Temporary directory management
"""

import tempfile
from pathlib import Path
from typing import Generator

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the test fixtures directory path.

    Returns:
        Path: Path object for the fixtures directory
    """
    return FIXTURES_DIR


@pytest.fixture
def sample_txt_file(fixtures_dir: Path) -> Path:
    """Get the sample TXT file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Sample TXT file path
    """
    return fixtures_dir / "sample.txt"


@pytest.fixture
def sample_txt_gbk_file(fixtures_dir: Path) -> Path:
    """Get the sample GBK-encoded TXT file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Sample GBK-encoded TXT file path
    """
    return fixtures_dir / "sample_gbk.txt"


@pytest.fixture
def sample_docx_file(fixtures_dir: Path) -> Path:
    """Get the sample DOCX file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Sample DOCX file path
    """
    return fixtures_dir / "sample.docx"


@pytest.fixture
def sample_pdf_file(fixtures_dir: Path) -> Path:
    """Get the sample PDF file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Sample PDF file path
    """
    return fixtures_dir / "sample.pdf"


@pytest.fixture
def sample_excel_file(fixtures_dir: Path) -> Path:
    """Get the sample Excel file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Sample Excel file path
    """
    return fixtures_dir / "sample.xlsx"


@pytest.fixture
def sample_xls_file(fixtures_dir: Path) -> Path:
    """Get the sample legacy Excel (.xls) file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Sample .xls file path
    """
    return fixtures_dir / "sample.xls"


@pytest.fixture
def empty_txt_file(fixtures_dir: Path) -> Path:
    """Get the empty TXT file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Empty TXT file path
    """
    return fixtures_dir / "empty.txt"


@pytest.fixture
def empty_docx_file(fixtures_dir: Path) -> Path:
    """Get the empty DOCX file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Empty DOCX file path
    """
    return fixtures_dir / "empty.docx"


@pytest.fixture
def empty_pdf_file(fixtures_dir: Path) -> Path:
    """Get the empty PDF file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Empty PDF file path
    """
    return fixtures_dir / "empty.pdf"


@pytest.fixture
def empty_excel_file(fixtures_dir: Path) -> Path:
    """Get the empty Excel file path.

    Args:
        fixtures_dir: Fixtures directory path

    Returns:
        Path: Empty Excel file path
    """
    return fixtures_dir / "empty.xlsx"


@pytest.fixture
def temp_document_dir() -> Generator[str, None, None]:
    """Create a temporary document directory.

    Yields:
        str: Temporary directory path
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
