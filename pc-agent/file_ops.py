"""
File operations for the PC agent.

All operations are scoped to allowed folders — any path outside the allowlist is rejected.
Prevents path traversal attacks and limits access to safe directories.
"""

import os
import time
import base64
import hashlib
import mimetypes
import logging
import asyncio
import math
from pathlib import Path
from typing import Optional

logger = logging.getLogger("pc-agent.file_ops")

# Maximum file size for single-shot fetch (5 MB) — above this, use chunked transfer
MAX_FILE_SIZE = 5 * 1024 * 1024

# Chunk size for large file transfer (256 KB)
CHUNK_SIZE = 256 * 1024

# Preview size (chars)
PREVIEW_SIZE = 500


class FileOperations:
    """Folder-scoped file operations."""

    def __init__(self, allowed_folders: list[str]):
        """Initialize with a list of allowed folder paths.

        Args:
            allowed_folders: List of paths like ['~/Desktop', '~/Documents', '~/Downloads', '/mnt']
        """
        self.allowed_folders = []
        for folder in allowed_folders:
            folder_str = folder.strip()
            if folder_str in ("/", "*"):
                self.allowed_folders.append("/")
                logger.info("Allowed folder: / (Full system access enabled)")
                continue
            expanded = os.path.expanduser(folder_str)
            resolved = os.path.realpath(expanded)
            if os.path.isdir(resolved):
                self.allowed_folders.append(resolved)
                logger.info(f"Allowed folder: {resolved}")
            else:
                logger.warning(f"Allowed folder does not exist, skipping: {expanded}")

        if not self.allowed_folders:
            logger.error("No valid allowed folders configured!")

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a path is within any allowed folder."""
        try:
            real_path = os.path.realpath(os.path.expanduser(path))
            for folder in self.allowed_folders:
                if folder in ("/", "*"):
                    return True
                prefix = folder if folder.endswith(os.sep) else folder + os.sep
                if real_path.startswith(prefix) or real_path == folder:
                    return True
            return False
        except Exception:
            return False

    def _validate_path(self, path: str) -> tuple[bool, str, str]:
        """Validate and resolve a path.

        Returns:
            (is_valid, resolved_path, error_message)
        """
        if not path:
            return False, "", "Path is empty."

        resolved = os.path.realpath(os.path.expanduser(path))

        if not self._is_path_allowed(resolved):
            return False, "", f"Access denied: path '{path}' is outside allowed folders."

        return True, resolved, ""

    def list_directory(self, path: str = "~/Downloads") -> dict:
        """List files and directories in a specific folder on the PC.

        Args:
            path: Path to directory (e.g. '~/Downloads', '~/Desktop', '~/Documents', '/mnt').

        Returns:
            dict with 'items' list sorted by modification date (newest first) or 'error'.
        """
        valid, resolved, error = self._validate_path(path)
        if not valid:
            return {"error": error}

        if not os.path.isdir(resolved):
            return {"error": f"Directory not found: {path}"}

        try:
            items = []
            for fname in os.listdir(resolved):
                if fname.startswith("."):
                    continue
                full_path = os.path.join(resolved, fname)
                try:
                    stat = os.stat(full_path)
                    is_dir = os.path.isdir(full_path)
                    items.append({
                        "name": fname,
                        "path": full_path,
                        "is_dir": is_dir,
                        "size": stat.st_size if not is_dir else 0,
                        "mtime": stat.st_mtime,
                        "modified": time.strftime(
                            "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)
                        ),
                    })
                except OSError:
                    continue

            # Sort by modified time descending (newest first)
            items.sort(key=lambda x: x["mtime"], reverse=True)

            for item in items:
                item.pop("mtime", None)

            return {
                "directory": resolved,
                "items": items[:50],
                "total": len(items),
                "message": f"Found {len(items)} item(s) in {resolved}.",
            }

        except Exception as e:
            logger.error(f"list_directory error: {e}")
            return {"error": f"Failed to list directory: {str(e)}"}

    def search_files(
        self,
        keyword: str = "",
        file_type: str = "",
        days_back: int = 0,
        folder: str = "",
    ) -> dict:
        """Search for files across allowed folders or a specific folder.

        Args:
            keyword: Case-insensitive substring match against file names.
            file_type: File extension filter (without dot), e.g. 'pdf', 'xlsx'.
            days_back: Only include files modified within this many days. 0 = no filter.
            folder: Optional specific folder to search inside (e.g. '~/Downloads').

        Returns:
            dict with 'files' list or 'error' string.
        """
        results = []
        now = time.time()
        cutoff = now - (days_back * 86400) if days_back > 0 else 0
        file_ext = f".{file_type.lower().strip('.')}" if file_type else ""

        keyword_lower = keyword.lower() if keyword else ""

        # Determine target folders to walk
        target_folders = self.allowed_folders
        if folder:
            valid, resolved_folder, err = self._validate_path(folder)
            if not valid:
                return {"error": err}
            if os.path.isdir(resolved_folder):
                target_folders = [resolved_folder]

        try:
            for fpath in target_folders:
                for root, dirs, files in os.walk(fpath):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith(".")]

                    for fname in files:
                        # Skip hidden files
                        if fname.startswith("."):
                            continue

                        # Keyword filter
                        if keyword_lower and keyword_lower not in fname.lower():
                            continue

                        # Extension filter
                        if file_ext and not fname.lower().endswith(file_ext):
                            continue

                        full_path = os.path.join(root, fname)

                        try:
                            stat = os.stat(full_path)
                        except OSError:
                            continue

                        # Date filter
                        if cutoff and stat.st_mtime < cutoff:
                            continue

                        results.append({
                            "path": full_path,
                            "name": fname,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                            "modified": time.strftime(
                                "%Y-%m-%d %H:%M:%S",
                                time.localtime(stat.st_mtime),
                            ),
                        })

                        if len(results) >= 100:
                            break
                    if len(results) >= 100:
                        break
                if len(results) >= 100:
                    break

            if not results:
                search_desc = []
                if keyword:
                    search_desc.append(f"keyword='{keyword}'")
                if file_type:
                    search_desc.append(f"type='{file_type}'")
                if days_back:
                    search_desc.append(f"within {days_back} days")
                if folder:
                    search_desc.append(f"folder='{folder}'")
                return {
                    "files": [],
                    "message": f"No files found matching: {', '.join(search_desc) or 'any criteria'}.",
                }

            # Sort by mtime descending (newest first)
            results.sort(key=lambda x: x["mtime"], reverse=True)
            for r in results:
                r.pop("mtime", None)

            results = results[:50]

            return {
                "files": results,
                "count": len(results),
                "message": f"Found {len(results)} file(s).",
            }

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {"error": f"Search failed: {str(e)}"}

    def search_file_content(
        self,
        query: str,
        folder: str = "",
        file_type: str = "",
        max_results: int = 10,
    ) -> dict:
        """Search inside file contents for a query string.

        Uses grep for text files. Useful when search_files (filename-based) fails.

        Args:
            query: Text to search for inside files (case-insensitive).
            folder: Specific folder to search inside. Defaults to all allowed folders.
            file_type: File extension filter (without dot), e.g. 'txt', 'py', 'pdf'.
            max_results: Maximum number of matching files to return.

        Returns:
            dict with 'files' list (each with path, name, matching_lines) or 'error'.
        """
        import subprocess

        if not query or not query.strip():
            return {"error": "Query string is required."}

        # Determine target folders
        target_folders = self.allowed_folders
        if folder:
            valid, resolved_folder, err = self._validate_path(folder)
            if not valid:
                return {"error": err}
            if os.path.isdir(resolved_folder):
                target_folders = [resolved_folder]

        results = []

        # Text file extensions to search (skip binaries)
        text_exts = {
            '.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.css', '.js',
            '.py', '.java', '.c', '.cpp', '.h', '.go', '.rs', '.ts', '.tsx', '.jsx',
            '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.log', '.sh', '.bat',
            '.sql', '.r', '.rb', '.php', '.pl', '.lua', '.swift', '.kt', '.dart',
            '.tex', '.bib', '.rst', '.org', '.env', '.gitignore', '.dockerfile',
        }

        file_ext = f".{file_type.lower().strip('.')}" if file_type else ""

        try:
            for fpath in target_folders:
                for root, dirs, files in os.walk(fpath):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith(".")]

                    for fname in files:
                        if fname.startswith("."):
                            continue

                        # Extension filter
                        if file_ext and not fname.lower().endswith(file_ext):
                            continue

                        # Only search text-like files (by extension)
                        ext = os.path.splitext(fname)[1].lower()
                        if not file_ext and ext not in text_exts:
                            continue

                        full_path = os.path.join(root, fname)

                        # Skip large files (>2MB)
                        try:
                            if os.path.getsize(full_path) > 2 * 1024 * 1024:
                                continue
                        except OSError:
                            continue

                        # Search inside the file
                        try:
                            with open(full_path, 'r', errors='ignore') as f:
                                matching_lines = []
                                for line_no, line in enumerate(f, 1):
                                    if query.lower() in line.lower():
                                        snippet = line.strip()[:200]
                                        matching_lines.append({
                                            "line": line_no,
                                            "text": snippet,
                                        })
                                        if len(matching_lines) >= 3:
                                            break

                                if matching_lines:
                                    stat = os.stat(full_path)
                                    results.append({
                                        "path": full_path,
                                        "name": fname,
                                        "size": stat.st_size,
                                        "modified": time.strftime(
                                            "%Y-%m-%d %H:%M:%S",
                                            time.localtime(stat.st_mtime),
                                        ),
                                        "matching_lines": matching_lines,
                                    })

                                    if len(results) >= max_results:
                                        break
                        except (IOError, UnicodeDecodeError):
                            continue

                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break

            if not results:
                search_desc = [f"query='{query}'"]
                if folder:
                    search_desc.append(f"folder='{folder}'")
                if file_type:
                    search_desc.append(f"type='{file_type}'")
                return {
                    "files": [],
                    "message": f"No files found with content matching: {', '.join(search_desc)}.",
                }

            return {
                "files": results,
                "count": len(results),
                "message": f"Found {len(results)} file(s) containing '{query}'.",
            }

        except Exception as e:
            logger.error(f"search_file_content error: {e}")
            return {"error": f"Content search failed: {str(e)}"}

    def read_file_preview(self, path: str) -> dict:
        """Read a short preview of a file.

        For text files: first ~500 chars.
        For binary files: metadata only.

        Args:
            path: Absolute path to the file.

        Returns:
            dict with 'preview' and metadata, or 'error'.
        """
        valid, resolved, error = self._validate_path(path)
        if not valid:
            return {"error": error}

        if not os.path.isfile(resolved):
            return {"error": f"File not found: {path}"}

        try:
            stat = os.stat(resolved)
            info = {
                "path": resolved,
                "name": os.path.basename(resolved),
                "size": stat.st_size,
                "modified": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)
                ),
                "type": mimetypes.guess_type(resolved)[0] or "unknown",
            }

            # Try reading as text
            try:
                with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(PREVIEW_SIZE)
                    if len(content) == PREVIEW_SIZE:
                        content += "\n... [truncated]"
                    info["preview"] = content
            except (UnicodeDecodeError, IOError):
                info["preview"] = "[Binary file — preview not available]"

            return info

        except Exception as e:
            logger.error(f"Preview error: {e}")
            return {"error": f"Failed to read file: {str(e)}"}

    def fetch_file(self, path: str) -> dict:
        """Fetch a file and return its base64-encoded content.

        Args:
            path: Absolute path to the file.

        Returns:
            dict with 'data' (base64), 'name', 'size', 'type', or 'error'.
        """
        valid, resolved, error = self._validate_path(path)
        if not valid:
            return {"error": error}

        if not os.path.isfile(resolved):
            return {"error": f"File not found: {path}"}

        try:
            stat = os.stat(resolved)
            mime = mimetypes.guess_type(resolved)[0] or "application/octet-stream"

            # Large file → signal chunked transfer instead of error
            if stat.st_size > MAX_FILE_SIZE:
                total_chunks = math.ceil(stat.st_size / CHUNK_SIZE)
                # Pre-compute MD5 checksum
                md5 = hashlib.md5()
                with open(resolved, "rb") as f:
                    while True:
                        block = f.read(CHUNK_SIZE)
                        if not block:
                            break
                        md5.update(block)
                return {
                    "chunked": True,
                    "path": resolved,
                    "name": os.path.basename(resolved),
                    "size": stat.st_size,
                    "type": mime,
                    "total_chunks": total_chunks,
                    "checksum": md5.hexdigest(),
                }

            with open(resolved, "rb") as f:
                data = f.read()

            return {
                "data": base64.b64encode(data).decode("ascii"),
                "name": os.path.basename(resolved),
                "size": stat.st_size,
                "type": mime,
            }

        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return {"error": f"Failed to fetch file: {str(e)}"}

    def delete_file(self, path: str) -> dict:
        """Delete a file (confirmation should already be obtained by relay).

        Args:
            path: Absolute path to the file.

        Returns:
            dict with 'message' or 'error'.
        """
        valid, resolved, error = self._validate_path(path)
        if not valid:
            return {"error": error}

        if not os.path.isfile(resolved):
            return {"error": f"File not found: {path}"}

        try:
            fname = os.path.basename(resolved)
            fsize = os.path.getsize(resolved)
            os.remove(resolved)
            logger.info(f"Deleted: {resolved}")
            return {
                "message": f"Deleted '{fname}' ({fsize} bytes).",
                "deleted_path": resolved,
            }

        except Exception as e:
            logger.error(f"Delete error: {e}")
            return {"error": f"Failed to delete file: {str(e)}"}

    def write_file(self, path: str, content: str) -> dict:
        """Write/overwrite content to a file at the specified path.

        Args:
            path: Absolute path to the file.
            content: Text content to write into the file.

        Returns:
            dict with 'message', 'path', and 'size', or 'error'.
        """
        valid, resolved, error = self._validate_path(path)
        if not valid:
            return {"error": error}

        try:
            parent_dir = os.path.dirname(resolved)
            if parent_dir and not os.path.exists(parent_dir):
                if self._is_path_allowed(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                else:
                    return {"error": f"Access denied: parent directory '{parent_dir}' is outside allowed folders."}

            overwritten = os.path.exists(resolved)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)

            action_str = "Overwrote" if overwritten else "Wrote"
            fname = os.path.basename(resolved)
            byte_count = len(content.encode("utf-8"))
            logger.info(f"{action_str} file: {resolved} ({byte_count} bytes)")

            return {
                "message": f"Successfully {action_str.lower()} '{fname}' ({byte_count} bytes).",
                "path": resolved,
                "size": byte_count,
            }

        except PermissionError:
            logger.error(f"Permission error writing file: {path}")
            return {"error": f"Permission denied: cannot write to '{path}' (file may be read-only or locked)."}
        except Exception as e:
            logger.error(f"Write error for {path}: {e}")
            return {"error": f"Failed to write file: {str(e)}"}

    def append_to_file(self, path: str, content: str) -> dict:
        """Append content to the end of a file at the specified path.

        Args:
            path: Absolute path to the file.
            content: Text content to append.

        Returns:
            dict with 'message', 'path', and 'size', or 'error'.
        """
        valid, resolved, error = self._validate_path(path)
        if not valid:
            return {"error": error}

        try:
            parent_dir = os.path.dirname(resolved)
            if parent_dir and not os.path.exists(parent_dir):
                if self._is_path_allowed(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                else:
                    return {"error": f"Access denied: parent directory '{parent_dir}' is outside allowed folders."}

            with open(resolved, "a", encoding="utf-8") as f:
                f.write(content)

            fname = os.path.basename(resolved)
            byte_count = len(content.encode("utf-8"))
            logger.info(f"Appended {byte_count} bytes to: {resolved}")

            return {
                "message": f"Successfully appended {byte_count} bytes to '{fname}'.",
                "path": resolved,
                "size": os.path.getsize(resolved),
            }

        except PermissionError:
            logger.error(f"Permission error appending to file: {path}")
            return {"error": f"Permission denied: cannot write to '{path}' (file may be read-only or locked)."}
        except Exception as e:
            logger.error(f"Append error for {path}: {e}")
            return {"error": f"Failed to append to file: {str(e)}"}

    def create_file(self, path: str, content: str = "") -> dict:
        """Create a new file at the specified path with initial content.

        Fails if the file already exists to prevent accidental overwrites.

        Args:
            path: Absolute path to the file.
            content: Initial text content for the file.

        Returns:
            dict with 'message', 'path', and 'size', or 'error'.
        """
        valid, resolved, error = self._validate_path(path)
        if not valid:
            return {"error": error}

        if os.path.exists(resolved):
            return {"error": f"File already exists at '{path}'. Use write_file to overwrite."}

        try:
            parent_dir = os.path.dirname(resolved)
            if parent_dir and not os.path.exists(parent_dir):
                if self._is_path_allowed(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                else:
                    return {"error": f"Access denied: parent directory '{parent_dir}' is outside allowed folders."}

            with open(resolved, "x", encoding="utf-8") as f:
                f.write(content)

            fname = os.path.basename(resolved)
            byte_count = len(content.encode("utf-8"))
            logger.info(f"Created file: {resolved} ({byte_count} bytes)")

            return {
                "message": f"Successfully created '{fname}' ({byte_count} bytes).",
                "path": resolved,
                "size": byte_count,
            }

        except FileExistsError:
            return {"error": f"File already exists at '{path}'. Use write_file to overwrite."}
        except PermissionError:
            logger.error(f"Permission error creating file: {path}")
            return {"error": f"Permission denied: cannot create file at '{path}'."}
        except Exception as e:
            logger.error(f"Create error for {path}: {e}")
            return {"error": f"Failed to create file: {str(e)}"}

    async def stream_file_chunks(self, path: str, websocket) -> None:
        """Stream a file in chunks over the WebSocket connection.

        Sends file_transfer_start, multiple file_transfer_chunk, and
        file_transfer_end messages. Designed for files larger than MAX_FILE_SIZE.

        Args:
            path: Absolute path to the file to stream.
            websocket: The websocket connection to send chunks through.
        """
        import json

        valid, resolved, error = self._validate_path(path)
        if not valid:
            await websocket.send(json.dumps({
                "type": "file_transfer_error",
                "error": error,
            }))
            return

        if not os.path.isfile(resolved):
            await websocket.send(json.dumps({
                "type": "file_transfer_error",
                "error": f"File not found: {path}",
            }))
            return

        try:
            stat = os.stat(resolved)
            total_chunks = math.ceil(stat.st_size / CHUNK_SIZE)
            fname = os.path.basename(resolved)
            mime = mimetypes.guess_type(resolved)[0] or "application/octet-stream"

            # Compute MD5 checksum
            md5 = hashlib.md5()
            with open(resolved, "rb") as f:
                while True:
                    block = f.read(CHUNK_SIZE)
                    if not block:
                        break
                    md5.update(block)
            checksum = md5.hexdigest()

            # Send start message
            await websocket.send(json.dumps({
                "type": "file_transfer_start",
                "name": fname,
                "size": stat.st_size,
                "total_chunks": total_chunks,
                "mime": mime,
                "checksum": checksum,
            }))
            logger.info(f"Chunked transfer started: {fname} ({stat.st_size} bytes, {total_chunks} chunks)")

            # Send chunks
            with open(resolved, "rb") as f:
                chunk_index = 0
                while True:
                    chunk_data = f.read(CHUNK_SIZE)
                    if not chunk_data:
                        break
                    await websocket.send(json.dumps({
                        "type": "file_transfer_chunk",
                        "index": chunk_index,
                        "data": base64.b64encode(chunk_data).decode("ascii"),
                    }))
                    chunk_index += 1
                    # Yield control to allow other async tasks
                    await asyncio.sleep(0)

            # Send end message
            await websocket.send(json.dumps({
                "type": "file_transfer_end",
                "checksum": checksum,
                "name": fname,
                "size": stat.st_size,
            }))
            logger.info(f"Chunked transfer complete: {fname}")

        except Exception as e:
            logger.error(f"Chunked transfer error: {e}", exc_info=True)
            try:
                await websocket.send(json.dumps({
                    "type": "file_transfer_error",
                    "error": f"Transfer failed: {str(e)}",
                }))
            except Exception:
                pass
