import sqlite3
import csv
import json
from typing import Set, Dict, Any, Optional, List, Tuple
from pathlib import Path
import threading
from datetime import datetime


class StateManager:
    """
    Manages application state to prevent duplicate job applications
    Supports both SQLite database and CSV file backends
    """

    def __init__(self, storage_type: str = "sqlite", file_path: str = "job_applications.db"):
        self.storage_type = storage_type
        self.file_path = Path(file_path)
        self.lock = threading.Lock()

        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        if storage_type == "sqlite":
            self._init_sqlite()
        elif storage_type == "csv":
            self._init_csv()
        else:
            raise ValueError("storage_type must be 'sqlite' or 'csv'")

    def _init_sqlite(self):
        """Initialize SQLite database with connection pooling"""
        # Store connection for in-memory databases
        if str(self.file_path) == ':memory:':
            self._memory_conn = sqlite3.connect(self.file_path)
            self._use_pool = False
        else:
            self._use_pool = True
            with sqlite3.connect(self.file_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS applied_jobs (
                        job_id TEXT,
                        platform TEXT NOT NULL,
                        title TEXT,
                        company TEXT,
                        url TEXT,
                        applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'applied',
                        metadata TEXT,
                        PRIMARY KEY (job_id, platform)
                    )
                """)
                conn.commit()

    def _get_connection(self):
        """Get database connection with proper resource management"""
        if hasattr(self, '_memory_conn'):
            return self._memory_conn
        else:
            return sqlite3.connect(self.file_path)

    def _init_csv(self):
        """Initialize CSV file if it doesn't exist"""
        if not self.file_path.exists():
            with open(self.file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    'job_id', 'platform', 'title', 'company', 'url',
                    'applied_date', 'status', 'metadata'
                ])

    def has_applied(self, job_id: str, platform: str) -> bool:
        """
        Check if we've already applied to this job
        Uses composite key of job_id + platform for uniqueness
        """
        with self.lock:
            if self.storage_type == "sqlite":
                return self._has_applied_sqlite(job_id, platform)
            else:
                return self._has_applied_csv(job_id, platform)

    def _has_applied_sqlite(self, job_id: str, platform: str) -> bool:
        """Check application status using SQLite with connection reuse"""
        if hasattr(self, '_memory_conn'):
            conn = self._memory_conn
            cursor = conn.execute(
                "SELECT 1 FROM applied_jobs WHERE job_id = ? AND platform = ?",
                (job_id, platform)
            )
            return cursor.fetchone() is not None
        else:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM applied_jobs WHERE job_id = ? AND platform = ?",
                    (job_id, platform)
                )
                return cursor.fetchone() is not None

    def _has_applied_csv(self, job_id: str, platform: str) -> bool:
        """Check application status using CSV"""
        if not self.file_path.exists():
            return False

        with open(self.file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['job_id'] == job_id and row['platform'] == platform:
                    return True
        return False

    def record_application(self, job_id: str, platform: str,
                           title: str = "", company: str = "", url: str = "",
                           status: str = "applied", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Record a job application
        Returns True if successfully recorded, False if already exists
        """
        if self.has_applied(job_id, platform):
            return False

        with self.lock:
            if self.storage_type == "sqlite":
                return self._record_application_sqlite(
                    job_id, platform, title, company, url, status, metadata
                )
            else:
                return self._record_application_csv(
                    job_id, platform, title, company, url, status, metadata
                )

    def _record_application_sqlite(self, job_id: str, platform: str,
                                   title: str, company: str, url: str,
                                   status: str, metadata: Optional[Dict[str, Any]]) -> bool:
        """Record application using SQLite with connection reuse"""
        if hasattr(self, '_memory_conn'):
            conn = self._memory_conn
            try:
                conn.execute("""
                    INSERT INTO applied_jobs 
                    (job_id, platform, title, company, url, status, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id, platform, title, company, url, status,
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
        else:
            with self._get_connection() as conn:
                try:
                    conn.execute("""
                        INSERT INTO applied_jobs 
                        (job_id, platform, title, company, url, status, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job_id, platform, title, company, url, status,
                        json.dumps(metadata) if metadata else None
                    ))
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False

    def _record_application_csv(self, job_id: str, platform: str,
                                title: str, company: str, url: str,
                                status: str, metadata: Optional[Dict[str, Any]]) -> bool:
        """Record application using CSV"""
        try:
            with open(self.file_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    job_id, platform, title, company, url,
                    datetime.now().isoformat(), status,
                    json.dumps(metadata) if metadata else ""
                ])
            return True
        except Exception:
            return False

    def get_application_stats(self) -> Dict[str, Any]:
        """Get statistics about job applications"""
        with self.lock:
            if self.storage_type == "sqlite":
                return self._get_stats_sqlite()
            else:
                return self._get_stats_csv()

    def _get_stats_sqlite(self) -> Dict[str, Any]:
        """Get statistics using SQLite with connection reuse"""
        if hasattr(self, '_memory_conn'):
            conn = self._memory_conn
            cursor = conn.execute("""
                SELECT 
                    platform,
                    COUNT(*) as total_applications,
                    COUNT(CASE WHEN status = 'applied' THEN 1 END) as successful_applications
                FROM applied_jobs 
                GROUP BY platform
            """)

            stats = {"platforms": {}, "total": 0}
            for row in cursor.fetchall():
                platform, total, successful = row
                stats["platforms"][platform] = {
                    "total": total,
                    "successful": successful
                }
                stats["total"] += total

            return stats
        else:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        platform,
                        COUNT(*) as total_applications,
                        COUNT(CASE WHEN status = 'applied' THEN 1 END) as successful_applications
                    FROM applied_jobs 
                    GROUP BY platform
                """)

                stats = {"platforms": {}, "total": 0}
                for row in cursor.fetchall():
                    platform, total, successful = row
                    stats["platforms"][platform] = {
                        "total": total,
                        "successful": successful
                    }
                    stats["total"] += total

                return stats

    def _get_stats_csv(self) -> Dict[str, Any]:
        """Get statistics using CSV"""
        if not self.file_path.exists():
            return {"platforms": {}, "total": 0}

        stats = {"platforms": {}, "total": 0}

        with open(self.file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                platform = row['platform']
                if platform not in stats["platforms"]:
                    stats["platforms"][platform] = {
                        "total": 0, "successful": 0}

                stats["platforms"][platform]["total"] += 1
                if row['status'] == 'applied':
                    stats["platforms"][platform]["successful"] += 1
                stats["total"] += 1

        return stats

    def get_recent_applications(self, limit: int = 10) -> list:
        """Get most recent applications"""
        with self.lock:
            if self.storage_type == "sqlite":
                return self._get_recent_sqlite(limit)
            else:
                return self._get_recent_csv(limit)

    def _get_recent_sqlite(self, limit: int) -> list:
        """Get recent applications using SQLite with connection reuse"""
        if hasattr(self, '_memory_conn'):
            conn = self._memory_conn
            cursor = conn.execute("""
                SELECT job_id, platform, title, company, url, applied_date, status
                FROM applied_jobs 
                ORDER BY applied_date DESC, rowid DESC
                LIMIT ?
            """, (limit,))

            return [
                {
                    "job_id": row[0],
                    "platform": row[1],
                    "title": row[2],
                    "company": row[3],
                    "url": row[4],
                    "applied_date": row[5],
                    "status": row[6]
                }
                for row in cursor.fetchall()
            ]
        else:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT job_id, platform, title, company, url, applied_date, status
                    FROM applied_jobs 
                    ORDER BY applied_date DESC, rowid DESC
                    LIMIT ?
                """, (limit,))

                return [
                    {
                        "job_id": row[0],
                        "platform": row[1],
                        "title": row[2],
                        "company": row[3],
                        "url": row[4],
                        "applied_date": row[5],
                        "status": row[6]
                    }
                    for row in cursor.fetchall()
                ]

    def _get_recent_csv(self, limit: int) -> list:
        """Get recent applications using CSV"""
        if not self.file_path.exists():
            return []

        applications = []
        with open(self.file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            applications = list(reader)

        # Sort by applied_date (newest first) and limit
        applications.sort(key=lambda x: x.get(
            'applied_date', ''), reverse=True)
        return applications[:limit]

    def has_applied_batch(self, job_platform_pairs: List[Tuple[str, str]]) -> Dict[Tuple[str, str], bool]:
        """
        Check multiple job applications in a single query for better performance
        
        Args:
            job_platform_pairs: List of (job_id, platform) tuples to check
            
        Returns:
            Dictionary mapping (job_id, platform) tuples to boolean results
        """
        if not job_platform_pairs:
            return {}
        
        with self.lock:
            if self.storage_type == "sqlite":
                return self._has_applied_batch_sqlite(job_platform_pairs)
            else:
                return {pair: self.has_applied(pair[0], pair[1]) for pair in job_platform_pairs}

    def _has_applied_batch_sqlite(self, job_platform_pairs: List[Tuple[str, str]]) -> Dict[Tuple[str, str], bool]:
        """Check multiple applications using SQLite with a single query"""
        if not job_platform_pairs:
            return {}
            
        placeholders = ','.join(['(?,?)'] * len(job_platform_pairs))
        query = f"""
            SELECT job_id, platform 
            FROM applied_jobs 
            WHERE (job_id, platform) IN ({placeholders})
        """
        
        params = []
        for job_id, platform in job_platform_pairs:
            params.extend([job_id, platform])
        
        if hasattr(self, '_memory_conn'):
            conn = self._memory_conn
            cursor = conn.execute(query, params)
            found_pairs = {(row[0], row[1]) for row in cursor.fetchall()}
        else:
            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                found_pairs = {(row[0], row[1]) for row in cursor.fetchall()}
        
        return {pair: pair in found_pairs for pair in job_platform_pairs}
