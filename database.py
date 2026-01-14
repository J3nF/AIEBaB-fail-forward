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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create full-text search virtual table
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS samples_fts USING fts5(
                sample_id, researcher, expressed,
                content=samples,
                content_rowid=id
            )
        """)
        
        # Create triggers to keep FTS table in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS samples_ai AFTER INSERT ON samples BEGIN
                INSERT INTO samples_fts(rowid, sample_id, researcher, expressed)
                VALUES (new.id, new.sample_id, new.researcher, new.expressed);
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS samples_ad AFTER DELETE ON samples BEGIN
                INSERT INTO samples_fts(samples_fts, rowid, sample_id, researcher, expressed)
                VALUES('delete', old.id, old.sample_id, old.researcher, old.expressed);
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS samples_au AFTER UPDATE ON samples BEGIN
                INSERT INTO samples_fts(samples_fts, rowid, sample_id, researcher, expressed)
                VALUES('delete', old.id, old.sample_id, old.researcher, old.expressed);
                INSERT INTO samples_fts(rowid, sample_id, researcher, expressed)
                VALUES (new.id, new.sample_id, new.researcher, new.expressed);
            END
        """)
        
        conn.commit()
        conn.close()
    
    def add_sample(self, sample_id: str, researcher: str, expressed: str, date: str) -> int:
        """Add a new sample to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO samples (sample_id, researcher, expressed, date)
            VALUES (?, ?, ?, ?)
        """, (sample_id, researcher, expressed, date))
        
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
        """Full-text search across all fields"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Search in FTS table and join with main table
        cursor.execute("""
            SELECT samples.* FROM samples
            JOIN samples_fts ON samples.id = samples_fts.rowid
            WHERE samples_fts MATCH ?
            ORDER BY rank
        """, (query,))
        
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
