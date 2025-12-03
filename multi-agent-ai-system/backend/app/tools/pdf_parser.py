"""
PDF parser tool for extracting text and tables from PDF files.
Provides both simple text extraction and advanced table extraction.
"""
import logging
from typing import Dict, List
from pypdf import PdfReader
import pdfplumber

# Configure logging
logger = logging.getLogger(__name__)


class PDFParser:
    """
    Handles PDF parsing operations including text and table extraction.
    """
    
    def extract_text_simple(self, file_path: str, max_pages: int = None) -> str:
        """
        Extract text from a PDF using pypdf (simple extraction).
        
        Args:
            file_path: Path to the PDF file
            max_pages: Optional limit on number of pages to read
        
        Returns:
            Extracted text with page markers
        """
        try:
            logger.info(f"Starting simple text extraction from: {file_path}")
            
            with open(file_path, 'rb') as file:
                reader = PdfReader(file)
                total_pages = len(reader.pages)
                
                # Determine how many pages to read
                pages_to_read = total_pages
                if max_pages is not None:
                    pages_to_read = min(total_pages, max_pages)
                
                extracted_text = []
                
                for page_num in range(pages_to_read):
                    page = reader.pages[page_num]
                    text = page.extract_text()
                    
                    # Add page marker
                    extracted_text.append(f"--- Page {page_num + 1} ---")
                    extracted_text.append(text)
                
                result = "\n".join(extracted_text)
                char_count = len(result)
                
                logger.info(f"Extracted text from {pages_to_read}/{total_pages} pages, ~{char_count} characters")
                return result
                
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
            raise
    
    def extract_with_tables(self, file_path: str, max_pages: int = None) -> Dict:
        """
        Extract text and tables from a PDF using pdfplumber.
        
        Args:
            file_path: Path to the PDF file
            max_pages: Optional limit on number of pages to read
        
        Returns:
            Dict with keys:
                - "text": Extracted text with page markers
                - "tables": List of table data with page and index info
                - "metadata": Dict with total_pages, pages_read, pdf_metadata
        """
        try:
            logger.info(f"Starting text+table extraction from: {file_path}")
            
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                
                # Determine how many pages to read
                pages_to_read = total_pages
                if max_pages is not None:
                    pages_to_read = min(total_pages, max_pages)
                
                extracted_text = []
                extracted_tables = []
                
                for page_num in range(pages_to_read):
                    page = pdf.pages[page_num]
                    
                    # Extract text
                    text = page.extract_text() or ""
                    extracted_text.append(f"--- Page {page_num + 1} ---")
                    extracted_text.append(text)
                    
                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for table_idx, table_data in enumerate(tables):
                            extracted_tables.append({
                                "page": page_num + 1,
                                "table_index": table_idx,
                                "data": table_data
                            })
                
                # Build metadata
                pdf_metadata = pdf.metadata or {}
                metadata = {
                    "total_pages": total_pages,
                    "pages_read": pages_to_read,
                    "pdf_metadata": pdf_metadata
                }
                
                result = {
                    "text": "\n".join(extracted_text),
                    "tables": extracted_tables,
                    "metadata": metadata
                }
                
                logger.info(f"Processed {pages_to_read}/{total_pages} pages, found {len(extracted_tables)} tables")
                return result
                
        except Exception as e:
            logger.error(f"Error extracting from PDF {file_path}: {str(e)}")
            raise


# Global instance
pdf_parser = PDFParser()
