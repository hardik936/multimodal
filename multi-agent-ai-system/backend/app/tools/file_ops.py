"""
File operations tool for managing uploads and file storage.
Provides a FileManager class for CRUD operations on files.
"""
import logging
from pathlib import Path
from typing import List
from datetime import datetime
from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)


class FileManager:
    """
    Manages file operations within a base directory.
    Provides methods for saving, reading, listing, deleting, and getting file info.
    """
    
    def __init__(self, base_path: str = None):
        """
        Initialize FileManager with a base directory.
        
        Args:
            base_path: Base directory for file operations (defaults to settings.UPLOAD_DIR)
        """
        self.base_path = Path(base_path or settings.UPLOAD_DIR)
        
        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileManager initialized with base_path: {self.base_path}")
    
    def save_file(self, content: str, filename: str, subfolder: str = "") -> str:
        """
        Save text content to a file.
        
        Args:
            content: Text content to save
            filename: Name of the file
            subfolder: Optional subfolder within base_path
        
        Returns:
            Absolute path of the saved file
        """
        try:
            # Construct full path
            if subfolder:
                target_dir = self.base_path / subfolder
                target_dir.mkdir(parents=True, exist_ok=True)
            else:
                target_dir = self.base_path
            
            file_path = target_dir / filename
            
            # Write content
            file_path.write_text(content, encoding="utf-8")
            
            logger.info(f"File saved successfully: {file_path}")
            return str(file_path.absolute())
            
        except Exception as e:
            logger.error(f"Error saving file {filename}: {str(e)}")
            raise
    
    def read_file(self, filename: str, subfolder: str = "") -> str:
        """
        Read text content from a file.
        
        Args:
            filename: Name of the file
            subfolder: Optional subfolder within base_path
        
        Returns:
            File content as string
        
        Raises:
            FileNotFoundError: If file does not exist
        """
        try:
            # Construct full path
            if subfolder:
                file_path = self.base_path / subfolder / filename
            else:
                file_path = self.base_path / filename
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            content = file_path.read_text(encoding="utf-8")
            logger.info(f"File read successfully: {file_path}")
            return content
            
        except FileNotFoundError:
            logger.error(f"File not found: {filename} in subfolder: {subfolder}")
            raise
        except Exception as e:
            logger.error(f"Error reading file {filename}: {str(e)}")
            raise
    
    def list_files(self, subfolder: str = "", pattern: str = "*") -> List[str]:
        """
        List files in a directory matching a pattern.
        
        Args:
            subfolder: Optional subfolder within base_path
            pattern: Glob pattern for filtering files (default: "*")
        
        Returns:
            Sorted list of filenames (not full paths)
        """
        try:
            # Construct directory path
            if subfolder:
                target_dir = self.base_path / subfolder
            else:
                target_dir = self.base_path
            
            if not target_dir.exists():
                logger.warning(f"Directory does not exist: {target_dir}")
                return []
            
            # List files matching pattern
            files = [f.name for f in target_dir.glob(pattern) if f.is_file()]
            files.sort()
            
            logger.info(f"Found {len(files)} files in {target_dir} matching pattern '{pattern}'")
            return files
            
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            return []
    
    def delete_file(self, filename: str, subfolder: str = "") -> bool:
        """
        Delete a file.
        
        Args:
            filename: Name of the file
            subfolder: Optional subfolder within base_path
        
        Returns:
            True if file was deleted, False if file not found
        """
        try:
            # Construct full path
            if subfolder:
                file_path = self.base_path / subfolder / filename
            else:
                file_path = self.base_path / filename
            
            if not file_path.exists():
                logger.warning(f"File not found for deletion: {file_path}")
                return False
            
            file_path.unlink()
            logger.info(f"File deleted successfully: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {filename}: {str(e)}")
            return False
    
    def get_file_info(self, filename: str, subfolder: str = "") -> dict:
        """
        Get metadata about a file.
        
        Args:
            filename: Name of the file
            subfolder: Optional subfolder within base_path
        
        Returns:
            Dict with keys: name, path, size_bytes, created, modified
        
        Raises:
            FileNotFoundError: If file does not exist
        """
        try:
            # Construct full path
            if subfolder:
                file_path = self.base_path / subfolder / filename
            else:
                file_path = self.base_path / filename
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            stat = file_path.stat()
            
            info = {
                "name": file_path.name,
                "path": str(file_path.absolute()),
                "size_bytes": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
            
            logger.info(f"Retrieved file info for: {file_path}")
            return info
            
        except FileNotFoundError:
            logger.error(f"File not found: {filename} in subfolder: {subfolder}")
            raise
        except Exception as e:
            logger.error(f"Error getting file info for {filename}: {str(e)}")
            raise


# Global instance
file_manager = FileManager()
