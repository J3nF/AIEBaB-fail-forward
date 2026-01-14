import sqlite3
from datetime import datetime
from typing import Optional, List, Dict

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT,
                researcher TEXT,
                expressed TEXT,
                date TEXT,
                protocol_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create full-text search virtual table
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS samples_fts USING fts5(
                sample_id, researcher, expressed, protocol_name,
                content=samples,
                content_rowid=id
            )
        """)
        
        # Create triggers to keep FTS table in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS samples_ai AFTER INSERT ON samples BEGIN
                INSERT INTO samples_fts(rowid, sample_id, researcher, expressed, protocol_name)
                VALUES (new.id, new.sample_id, new.researcher, new.expressed, new.protocol_name);
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS samples_ad AFTER DELETE ON samples BEGIN
                INSERT INTO samples_fts(samples_fts, rowid, sample_id, researcher, expressed, protocol_name)
                VALUES('delete', old.id, old.sample_id, old.researcher, old.expressed, old.protocol_name);
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS samples_au AFTER UPDATE ON samples BEGIN
                INSERT INTO samples_fts(samples_fts, rowid, sample_id, researcher, expressed, protocol_name)
                VALUES('delete', old.id, old.sample_id, old.researcher, old.expressed, old.protocol_name);
                INSERT INTO samples_fts(rowid, sample_id, researcher, expressed, protocol_name)
                VALUES (new.id, new.sample_id, new.researcher, new.expressed, new.protocol_name);
            END
        """)
        
        conn.commit()
        
        # Migration: Add protocol_name column if it doesn't exist
        cursor.execute("PRAGMA table_info(samples)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'protocol_name' not in columns:
            cursor.execute("ALTER TABLE samples ADD COLUMN protocol_name TEXT")
            conn.commit()
            
            # Rebuild FTS index to include protocol_name for existing rows
            cursor.execute("DELETE FROM samples_fts")
            cursor.execute("""
                INSERT INTO samples_fts(rowid, sample_id, researcher, expressed, protocol_name)
                SELECT id, sample_id, researcher, expressed, protocol_name FROM samples
            """)
            conn.commit()
        
        conn.close()
    
    def add_sample(self, sample_id: str, researcher: str, expressed: str, date: str, protocol_name: str = None) -> int:
        """Add a new sample to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO samples (sample_id, researcher, expressed, date, protocol_name)
            VALUES (?, ?, ?, ?, ?)
        """, (sample_id, researcher, expressed, date, protocol_name))
        
        sample_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return sample_id
    
    def get_all_samples(self) -> List[Dict]:
        """Get all samples from the database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM samples ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
    
    def search_samples(self, query: str) -> List[Dict]:
        """Full-text search across all fields with partial matching"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Add wildcard for partial matching - split query into words and add * to each
        search_terms = query.strip().split()
        fts_query = ' OR '.join([f'{term}*' for term in search_terms])
        
        # Search in FTS table and join with main table
        cursor.execute("""
            SELECT samples.* FROM samples
            JOIN samples_fts ON samples.id = samples_fts.rowid
            WHERE samples_fts MATCH ?
            ORDER BY rank
        """, (fts_query,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def filter_samples(self, person: Optional[str] = None, 
                       antibiotic: Optional[str] = None,
                       location: Optional[str] = None) -> List[Dict]:
        """Filter samples by specific fields"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM samples WHERE 1=1"
        params = []
        
        if person:
            query += " AND researcher LIKE ?"
            params.append(f"%{person}%")
        
        if antibiotic:
            query += " AND sample_id LIKE ?"
            params.append(f"%{antibiotic}%")
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
