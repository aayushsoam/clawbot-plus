"""
📂 Smart Local File Search (RAG) Module
Index local documents and search them for instant AI-powered answers.
"""
import os
import json
import re
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()

INDEX_DIR = Path.home() / ".clawbot" / "rag_index"
INDEX_FILE = INDEX_DIR / "index.json"

# File types we can read
SUPPORTED_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.html',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.csv', '.xml', '.sql', '.sh', '.bat', '.ps1',
    '.java', '.c', '.cpp', '.h', '.go', '.rs', '.rb',
    '.env', '.gitignore', '.dockerfile',
}

# Extensions that need special parsers
PDF_EXT = {'.pdf'}
DOCX_EXT = {'.docx'}

CHUNK_SIZE = 500  # characters per chunk
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB max per file


def build_index(folders: list[str], progress_callback=None) -> dict:
    """
    Walk specified folders and index all supported files.
    
    Args:
        folders: List of folder paths to index
        progress_callback: Optional fn(message) for progress updates
        
    Returns:
        Index stats dict
    """
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    
    chunks = []
    files_indexed = 0
    errors = 0
    
    for folder in folders:
        folder_path = Path(folder)
        if not folder_path.exists():
            if progress_callback:
                progress_callback(f"⚠️ Folder not found: {folder}")
            continue
        
        if progress_callback:
            progress_callback(f"📂 Scanning: {folder}")
        
        for root, dirs, files in os.walk(folder_path):
            # Skip hidden/system directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                'node_modules', '__pycache__', '.git', 'venv', '.venv', 'dist', 'build'
            }]
            
            for filename in files:
                file_path = Path(root) / filename
                ext = file_path.suffix.lower()
                
                # Skip if not supported or too large
                try:
                    if file_path.stat().st_size > MAX_FILE_SIZE:
                        continue
                except Exception:
                    continue
                
                text = None
                
                if ext in SUPPORTED_EXTENSIONS:
                    text = _read_text_file(file_path)
                elif ext in PDF_EXT:
                    text = _read_pdf(file_path)
                elif ext in DOCX_EXT:
                    text = _read_docx(file_path)
                
                if text and text.strip():
                    file_chunks = _split_into_chunks(text, str(file_path), ext)
                    chunks.extend(file_chunks)
                    files_indexed += 1
                    
                    if progress_callback and files_indexed % 50 == 0:
                        progress_callback(f"📄 {files_indexed} files indexed...")
    
    # Save the index
    index_data = {
        "created_at": datetime.now().isoformat(),
        "folders": folders,
        "files_indexed": files_indexed,
        "total_chunks": len(chunks),
        "chunks": chunks,
    }
    
    INDEX_FILE.write_text(json.dumps(index_data, ensure_ascii=False), encoding='utf-8')
    
    stats = {
        "files_indexed": files_indexed,
        "total_chunks": len(chunks),
        "errors": errors,
        "index_path": str(INDEX_FILE),
    }
    
    if progress_callback:
        progress_callback(f"✅ Done! {files_indexed} files, {len(chunks)} chunks indexed.")
    
    return stats


def search(query: str, top_k: int = 5) -> list[dict]:
    """
    Search the local index for relevant chunks.
    Uses keyword + fuzzy matching.
    
    Returns:
        List of {file_path, chunk_text, score, line_hint} dicts
    """
    if not INDEX_FILE.exists():
        return []
    
    try:
        index_data = json.loads(INDEX_FILE.read_text(encoding='utf-8'))
        chunks = index_data.get("chunks", [])
    except Exception:
        return []
    
    if not chunks:
        return []
    
    # Tokenize query
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    scored_results = []
    
    for chunk in chunks:
        chunk_text = chunk.get("text", "").lower()
        chunk_words = set(re.findall(r'\w+', chunk_text))
        
        # Score: count matching words
        common = query_words & chunk_words
        if not common:
            continue
        
        score = len(common) / max(len(query_words), 1)
        
        # Bonus for exact phrase match
        if query_lower in chunk_text:
            score += 2.0
        
        # Bonus for filename matching query
        file_path = chunk.get("file_path", "").lower()
        if any(w in file_path for w in query_words):
            score += 0.5
        
        scored_results.append({
            "file_path": chunk.get("file_path", ""),
            "chunk_text": chunk.get("text", ""),
            "score": round(score, 2),
            "extension": chunk.get("extension", ""),
        })
    
    # Sort by score descending
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    
    return scored_results[:top_k]


def get_index_stats() -> dict | None:
    """Get stats about the current index."""
    if not INDEX_FILE.exists():
        return None
    try:
        data = json.loads(INDEX_FILE.read_text(encoding='utf-8'))
        return {
            "created_at": data.get("created_at"),
            "folders": data.get("folders", []),
            "files_indexed": data.get("files_indexed", 0),
            "total_chunks": data.get("total_chunks", 0),
        }
    except Exception:
        return None


# ════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ════════════════════════════════════════════════════════

def _read_text_file(path: Path) -> str | None:
    """Read a plain text file."""
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None


def _read_pdf(path: Path) -> str | None:
    """Read PDF text using pdfplumber."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages[:50]:  # Max 50 pages
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts) if text_parts else None
    except ImportError:
        return None
    except Exception:
        return None


def _read_docx(path: Path) -> str | None:
    """Read DOCX text using python-docx."""
    try:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs) if paragraphs else None
    except ImportError:
        return None
    except Exception:
        return None


def _split_into_chunks(text: str, file_path: str, extension: str) -> list[dict]:
    """Split text into overlapping chunks for search."""
    chunks = []
    text = text.strip()
    
    # Split by paragraphs first, then by size
    step = CHUNK_SIZE - 100  # 100 char overlap
    for i in range(0, len(text), step):
        chunk_text = text[i:i + CHUNK_SIZE]
        if len(chunk_text.strip()) < 20:  # Skip tiny chunks
            continue
        chunks.append({
            "text": chunk_text,
            "file_path": file_path,
            "extension": extension,
            "offset": i,
        })
    
    return chunks

