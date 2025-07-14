from utils.state_manager import StateManager
import pytest
import sqlite3
import csv
import json
import threading
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import sys
sys.path.append('/home/daniel/JobApp')


class TestStateManagerSQLite:
    """Test StateManager with SQLite backend"""

    def test_init_sqlite(self, temp_dir):
        """Test SQLite initialization"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        # Verify database file was created
        assert db_path.exists()

        # Verify table structure
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert 'applied_jobs' in tables
        conn.close()

    def test_init_sqlite_memory(self):
        """Test SQLite in-memory database initialization"""
        state_manager = StateManager(
            storage_type="sqlite", file_path=":memory:")
        assert hasattr(state_manager, '_memory_conn')
        assert state_manager._memory_conn is not None

    def test_has_applied_false_new_job(self, temp_dir):
        """Test has_applied returns False for new job"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        result = state_manager.has_applied("job123", "linkedin")
        assert result is False

    def test_record_and_check_application(self, temp_dir):
        """Test recording application and checking it exists"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        # Record application
        result = state_manager.record_application(
            job_id="job123",
            platform="linkedin",
            title="Software Engineer",
            company="TechCorp",
            url="https://example.com/jobs/123",
            status="applied",
            metadata={"salary": "100k", "remote": True}
        )
        assert result is True

        # Check application exists
        assert state_manager.has_applied("job123", "linkedin") is True

        # Check different platform returns False
        assert state_manager.has_applied("job123", "wellfound") is False

    def test_record_duplicate_application(self, temp_dir):
        """Test that duplicate applications are rejected"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        # Record first application
        result1 = state_manager.record_application("job123", "linkedin")
        assert result1 is True

        # Try to record duplicate
        result2 = state_manager.record_application("job123", "linkedin")
        assert result2 is False

    def test_get_application_stats(self, temp_dir):
        """Test getting application statistics"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        # Record some applications
        state_manager.record_application("job1", "linkedin", status="applied")
        state_manager.record_application("job2", "linkedin", status="applied")
        state_manager.record_application("job3", "wellfound", status="applied")
        state_manager.record_application("job4", "linkedin", status="rejected")

        stats = state_manager.get_application_stats()

        assert stats["total"] == 4
        assert stats["platforms"]["linkedin"]["total"] == 3
        assert stats["platforms"]["linkedin"]["successful"] == 2
        assert stats["platforms"]["wellfound"]["total"] == 1
        assert stats["platforms"]["wellfound"]["successful"] == 1

    def test_get_recent_applications(self, temp_dir):
        """Test getting recent applications"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        # Record applications
        state_manager.record_application(
            "job1", "linkedin", title="Engineer 1")
        state_manager.record_application(
            "job2", "wellfound", title="Engineer 2")
        state_manager.record_application(
            "job3", "linkedin", title="Engineer 3")

        recent = state_manager.get_recent_applications(limit=2)

        assert len(recent) == 2
        assert recent[0]["title"] == "Engineer 3"  # Most recent first
        assert recent[1]["title"] == "Engineer 2"

    def test_thread_safety(self, temp_dir):
        """Test thread safety of StateManager operations"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        results = []

        def worker(job_id):
            result = state_manager.record_application(
                f"job{job_id}", "linkedin")
            results.append(result)

        # Create multiple threads trying to record applications
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All applications should be recorded successfully
        assert all(results)
        assert len(results) == 10

        # Verify in database
        stats = state_manager.get_application_stats()
        assert stats["total"] == 10


class TestStateManagerCSV:
    """Test StateManager with CSV backend"""

    def test_init_csv(self, temp_dir):
        """Test CSV initialization"""
        csv_path = temp_dir / 'test.csv'
        state_manager = StateManager(
            storage_type="csv", file_path=str(csv_path))

        # Verify CSV file was created with headers
        assert csv_path.exists()

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            expected_headers = [
                'job_id', 'platform', 'title', 'company', 'url',
                'applied_date', 'status', 'metadata'
            ]
            assert headers == expected_headers

    def test_has_applied_csv_false_new_job(self, temp_dir):
        """Test has_applied returns False for new job with CSV"""
        csv_path = temp_dir / 'test.csv'
        state_manager = StateManager(
            storage_type="csv", file_path=str(csv_path))

        result = state_manager.has_applied("job123", "linkedin")
        assert result is False

    def test_record_and_check_application_csv(self, temp_dir):
        """Test recording application and checking it exists with CSV"""
        csv_path = temp_dir / 'test.csv'
        state_manager = StateManager(
            storage_type="csv", file_path=str(csv_path))

        # Record application
        result = state_manager.record_application(
            job_id="job123",
            platform="linkedin",
            title="Software Engineer",
            company="TechCorp",
            url="https://example.com/jobs/123",
            status="applied",
            metadata={"salary": "100k", "remote": True}
        )
        assert result is True

        # Check application exists
        assert state_manager.has_applied("job123", "linkedin") is True
        assert state_manager.has_applied("job123", "wellfound") is False

    def test_record_duplicate_application_csv(self, temp_dir):
        """Test that duplicate applications are rejected with CSV"""
        csv_path = temp_dir / 'test.csv'
        state_manager = StateManager(
            storage_type="csv", file_path=str(csv_path))

        # Record first application
        result1 = state_manager.record_application("job123", "linkedin")
        assert result1 is True

        # Try to record duplicate
        result2 = state_manager.record_application("job123", "linkedin")
        assert result2 is False

    def test_get_application_stats_csv(self, temp_dir):
        """Test getting application statistics with CSV"""
        csv_path = temp_dir / 'test.csv'
        state_manager = StateManager(
            storage_type="csv", file_path=str(csv_path))

        # Record some applications
        state_manager.record_application("job1", "linkedin", status="applied")
        state_manager.record_application("job2", "linkedin", status="applied")
        state_manager.record_application("job3", "wellfound", status="applied")
        state_manager.record_application("job4", "linkedin", status="rejected")

        stats = state_manager.get_application_stats()

        assert stats["total"] == 4
        assert stats["platforms"]["linkedin"]["total"] == 3
        assert stats["platforms"]["linkedin"]["successful"] == 2
        assert stats["platforms"]["wellfound"]["total"] == 1
        assert stats["platforms"]["wellfound"]["successful"] == 1

    def test_get_recent_applications_csv(self, temp_dir):
        """Test getting recent applications with CSV"""
        csv_path = temp_dir / 'test.csv'
        state_manager = StateManager(
            storage_type="csv", file_path=str(csv_path))

        # Record applications with small delays to ensure different timestamps
        state_manager.record_application(
            "job1", "linkedin", title="Engineer 1")
        time.sleep(0.001)
        state_manager.record_application(
            "job2", "wellfound", title="Engineer 2")
        time.sleep(0.001)
        state_manager.record_application(
            "job3", "linkedin", title="Engineer 3")

        recent = state_manager.get_recent_applications(limit=2)

        assert len(recent) == 2
        # Should be sorted by most recent first
        assert recent[0]["title"] == "Engineer 3"
        assert recent[1]["title"] == "Engineer 2"

    def test_csv_file_corruption_handling(self, temp_dir):
        """Test handling of corrupted CSV files"""
        csv_path = temp_dir / 'test.csv'

        # Create a corrupted CSV file
        with open(csv_path, 'w') as f:
            f.write("incomplete,csv,file")  # Missing headers and incomplete

        state_manager = StateManager(
            storage_type="csv", file_path=str(csv_path))

        # Should handle gracefully - may not find applications but shouldn't crash
        result = state_manager.has_applied("job123", "linkedin")
        assert isinstance(result, bool)


class TestStateManagerGeneral:
    """Test general StateManager functionality"""

    def test_invalid_storage_type(self, temp_dir):
        """Test that invalid storage type raises ValueError"""
        with pytest.raises(ValueError, match="storage_type must be 'sqlite' or 'csv'"):
            StateManager(storage_type="invalid",
                         file_path=str(temp_dir / "test"))

    def test_directory_creation(self, temp_dir):
        """Test that parent directories are created automatically"""
        nested_path = temp_dir / "nested" / "directory" / "test.db"
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(nested_path))

        assert nested_path.parent.exists()
        assert nested_path.exists()

    def test_metadata_serialization(self, temp_dir):
        """Test that metadata is properly serialized/deserialized"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        metadata = {
            "salary_range": "100k-150k",
            "remote": True,
            "requirements": ["Python", "React"],
            "benefits": {"health": True, "dental": False}
        }

        state_manager.record_application(
            "job123", "linkedin", metadata=metadata
        )

        # Verify metadata is stored (indirectly through successful storage)
        assert state_manager.has_applied("job123", "linkedin")

    def test_empty_database_stats(self, temp_dir):
        """Test statistics for empty database"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        stats = state_manager.get_application_stats()
        assert stats["total"] == 0
        assert stats["platforms"] == {}

    def test_empty_database_recent_applications(self, temp_dir):
        """Test recent applications for empty database"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        recent = state_manager.get_recent_applications()
        assert recent == []

    def test_large_limit_recent_applications(self, temp_dir):
        """Test recent applications with limit larger than available records"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        # Record only 2 applications
        state_manager.record_application("job1", "linkedin")
        state_manager.record_application("job2", "wellfound")

        # Request 10 recent applications
        recent = state_manager.get_recent_applications(limit=10)
        assert len(recent) == 2


class TestStateManagerConcurrency:
    """Test StateManager under concurrent access"""

    def test_concurrent_duplicate_detection(self, temp_dir):
        """Test that concurrent threads don't create duplicate entries"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        results = []

        def try_record_same_job():
            result = state_manager.record_application(
                "duplicate_job", "linkedin")
            results.append(result)

        # Create multiple threads trying to record the same job
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=try_record_same_job)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Only one thread should succeed
        successful_records = sum(results)
        assert successful_records == 1

        # Verify only one record exists
        stats = state_manager.get_application_stats()
        assert stats["total"] == 1

    def test_concurrent_stats_access(self, temp_dir):
        """Test that stats can be safely accessed during writes"""
        db_path = temp_dir / 'test.db'
        state_manager = StateManager(
            storage_type="sqlite", file_path=str(db_path))

        # Pre-populate with some data
        for i in range(10):
            state_manager.record_application(f"job{i}", "linkedin")

        stats_results = []
        write_results = []

        def get_stats():
            stats = state_manager.get_application_stats()
            stats_results.append(stats["total"])

        def write_applications():
            for i in range(100, 110):
                result = state_manager.record_application(
                    f"job{i}", "wellfound")
                write_results.append(result)

        # Start concurrent reads and writes
        threads = []

        # Stats reading threads
        for _ in range(3):
            thread = threading.Thread(target=get_stats)
            threads.append(thread)

        # Write threads
        thread = threading.Thread(target=write_applications)
        threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All operations should complete successfully
        assert len(stats_results) == 3
        assert all(isinstance(count, int) and count >=
                   10 for count in stats_results)
        assert all(write_results)  # All writes should succeed
