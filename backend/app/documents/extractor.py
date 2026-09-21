"""Document text extraction for PDF, DOCX, and TXT files, preserving page numbers."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.exceptions import DocumentProcessingError, InvalidFileTypeError
from app.core.logging import logger


@dataclass
class PageContent:
    page_number: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentExtractor:
    """Extracts raw text and per-page metadata from documents."""

    @staticmethod
    def extract_pdf(file_path: Path) -> list[PageContent]:
        """Extract text from PDF preserving page numbers using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise DocumentProcessingError("PyMuPDF (fitz) is not installed.")

        pages: list[PageContent] = []
        try:
            doc = fitz.open(str(file_path))
            total_pages = len(doc)

            for page_idx in range(total_pages):
                page = doc.load_page(page_idx)
                text = page.get_text("text")
                page_number = page_idx + 1  # 1-indexed

                pages.append(
                    PageContent(
                        page_number=page_number,
                        text=text or "",
                        metadata={
                            "total_pages": total_pages,
                            "page_width": page.rect.width,
                            "page_height": page.rect.height,
                        },
                    )
                )
            doc.close()
            return pages
        except Exception as e:
            logger.error(f"Error extracting PDF {file_path}: {e}")
            raise DocumentProcessingError(f"Failed to extract text from PDF: {e}")

    @staticmethod
    def extract_docx(file_path: Path) -> list[PageContent]:
        """Extract text from DOCX documents with synthetic pagination based on paragraph blocks."""
        try:
            import docx
        except ImportError:
            raise DocumentProcessingError("python-docx is not installed.")

        try:
            doc = docx.Document(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

            # Approximate page boundaries (~500 words or 3000 chars per page)
            pages: list[PageContent] = []
            current_page_text: list[str] = []
            current_char_count = 0
            page_num = 1

            for para in paragraphs:
                current_page_text.append(para)
                current_char_count += len(para)
                if current_char_count >= 3000:
                    pages.append(
                        PageContent(
                            page_number=page_num,
                            text="\n\n".join(current_page_text),
                            metadata={"paragraph_count": len(current_page_text)},
                        )
                    )
                    current_page_text = []
                    current_char_count = 0
                    page_num += 1

            if current_page_text:
                pages.append(
                    PageContent(
                        page_number=page_num,
                        text="\n\n".join(current_page_text),
                        metadata={"paragraph_count": len(current_page_text)},
                    )
                )

            return pages or [PageContent(page_number=1, text="", metadata={})]
        except Exception as e:
            logger.error(f"Error extracting DOCX {file_path}: {e}")
            raise DocumentProcessingError(f"Failed to extract text from DOCX: {e}")

    @staticmethod
    def extract_txt(file_path: Path) -> list[PageContent]:
        """Extract text from TXT files with synthetic pagination."""
        try:
            # Try utf-8 first, fallback to latin-1
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = file_path.read_text(encoding="latin-1")

            lines = content.splitlines()
            pages: list[PageContent] = []
            lines_per_page = 60
            page_num = 1

            for i in range(0, max(len(lines), 1), lines_per_page):
                page_lines = lines[i : i + lines_per_page]
                pages.append(
                    PageContent(
                        page_number=page_num,
                        text="\n".join(page_lines),
                        metadata={"line_start": i, "line_end": i + len(page_lines)},
                    )
                )
                page_num += 1

            return pages
        except Exception as e:
            logger.error(f"Error extracting TXT {file_path}: {e}")
            raise DocumentProcessingError(f"Failed to extract text from TXT: {e}")

    @classmethod
    def extract(cls, file_path: Path, file_type: str) -> list[PageContent]:
        """Dispatch extraction based on file extension / type."""
        ext = file_path.suffix.lower() or f".{file_type.lower()}"
        if ext == ".pdf":
            return cls.extract_pdf(file_path)
        elif ext == ".docx":
            return cls.extract_docx(file_path)
        elif ext == ".txt":
            return cls.extract_txt(file_path)
        else:
            raise InvalidFileTypeError(f"Unsupported file type: {ext}")
