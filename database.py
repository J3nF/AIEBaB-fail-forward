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
                strain TEXT,
                plasmid TEXT,
                antibiotic TEXT,
                person TEXT,
                location TEXT,
                date TEXT,
                notes TEXT,
                image_path TEXT,
                raw_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create full-text search virtual table
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS samples_fts USING fts5(
                strain, plasmid, antibiotic, person, location, notes, raw_text,
                content=samples,
                content_rowid=id
            )
        """)
        
        # Create triggers to keep FTS table in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS samples_ai AFTER INSERT ON samples BEGIN
                INSERT INTO samples_fts(rowid, strain, plasmid, antibiotic, person, location, notes, raw_text)
                VALUES (new.id, new.strain, new.plasmid, new.antibiotic, new.person, new.location, new.notes, new.raw_text);
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS samples_ad AFTER DELETE ON samples BEGIN
                INSERT INTO samples_fts(samples_fts, rowid, strain, plasmid, antibiotic, person, location, notes, raw_text)
                VALUES('delete', old.id, old.strain, old.plasmid, old.antibiotic, old.person, old.location, old.notes, old.raw_text);
            END
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS samples_au AFTER UPDATE ON samples BEGIN
                INSERT INTO samples_fts(samples_fts, rowid, strain, plasmid, antibiotic, person, location, notes, raw_text)
                VALUES('delete', old.id, old.strain, old.plasmid, old.antibiotic, old.person, old.location, old.notes, old.raw_text);
                INSERT INTO samples_fts(rowid, strain, plasmid, antibiotic, person, location, notes, raw_text)
                VALUES (new.id, new.strain, new.plasmid, new.antibiotic, new.person, new.location, new.notes, new.raw_text);
            END
        """)
        
        conn.commit()
        conn.close()
    
    def add_sample(self, strain: str, plasmid: str, antibiotic: str, 
                   person: str, location: str, date: str, notes: str,
                   image_path: str, raw_text: str) -> int:
        """Add a new sample to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO samples (strain, plasmid, antibiotic, person, location, date, notes, image_path, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (strain, plasmid, antibiotic, person, location, date, notes, image_path, raw_text))
        
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
            query += " AND person LIKE ?"
            params.append(f"%{person}%")
        
        if antibiotic:
            query += " AND antibiotic LIKE ?"
            params.append(f"%{antibiotic}%")
        
        if location:
            query += " AND location LIKE ?"
            params.append(f"%{location}%")
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
