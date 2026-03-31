import os
import sqlite3
from pathlib import Path
from datetime import datetime

# Centralized Workspace Paths mirroring OpenClaw
WORKSPACE_DIR = Path.home() / ".clawbot"
MEMORY_DIR = WORKSPACE_DIR / "memory"
SESSIONS_DIR = WORKSPACE_DIR / "sessions"
VAULT_DIR = WORKSPACE_DIR / "vault"
MEMORY_MD = WORKSPACE_DIR / "MEMORY.md"

DB_PATH = WORKSPACE_DIR / "memory.db"

def init_db():
    """Initialize the SQLite memory database with FTS5 for fast semantic search."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Create an FTS5 virtual table for full-text search
    c.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            path, content, last_modified,
            tokenize = 'porter'
        )
    ''')
    conn.commit()
    conn.close()

def index_memory():
    """Scan all markdown files in memory, sessions, and vault and index them."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # We clear and rebuild the index for simplicity, 
    # OpenClaw tracks mtimes natively but this is very fast.
    c.execute('DELETE FROM memory_fts')
    
    directories = [MEMORY_DIR, SESSIONS_DIR, VAULT_DIR]
    files_to_index = []
    
    if MEMORY_MD.exists():
        files_to_index.append(MEMORY_MD)
        
    for d in directories:
        if d.exists():
            for p in d.glob("**/*.md"):
                files_to_index.append(p)
                
    count = 0
    for p in files_to_index:
        try:
            content = p.read_text(encoding='utf-8')
            mtime = os.path.getmtime(p)
            c.execute('INSERT INTO memory_fts (path, content, last_modified) VALUES (?, ?, ?)',
                      (str(p), content, mtime))
            count += 1
        except Exception:
            pass
            
    conn.commit()
    conn.close()
    return count

def search_memory(query: str, limit: int = 5) -> str:
    """Perform a BM25 Full-Text Search on the ClawBot Memory layer."""
    init_db()
    try:
        # Before searching, do a quick index update
        index_memory()
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # We craft a near/match query for FTS5
        # replace basic spacing with OR to make it highly permissive
        fts_query = " OR ".join(query.split())
        
        c.execute('''
            SELECT path, snippet(memory_fts, 1, '[', ']', '...', 15) as preview
            FROM memory_fts 
            WHERE memory_fts MATCH ? 
            ORDER BY rank 
            LIMIT ?
        ''', (fts_query, limit))
        
        results = c.fetchall()
        conn.close()
        
        if not results:
            return f"No memory results found for '{query}'."
            
        output = f"🧠 Memory Search Results for '{query}':\n\n"
        for path, preview in results:
            name = Path(path).name
            output += f"📄 **{name}**\n... {preview} ...\n\n"
            
        return output.strip()
    except Exception as e:
        return f"Memory Database Error: {str(e)}"
