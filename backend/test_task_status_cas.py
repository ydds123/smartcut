import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.tasks import _rollback_task_claim, _update_task_when_status_matches
from app.models.models import Base, Task


class TestTaskStatusCas(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "cas_test.db"
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        with self.Session() as db:
            db.add(
                Task(
                    id="task-cas-1",
                    display_name="cas-test.mp4",
                    file_path="/tmp/cas-test.mp4",
                    status="PENDING",
                    progress=0,
                )
            )
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()
        self._tmpdir.cleanup()

    def test_only_one_cas_update_can_claim_pending(self):
        with self.Session() as db1:
            claimed = _update_task_when_status_matches(
                db1,
                task_id="task-cas-1",
                expected_statuses={"PENDING"},
                updates={
                    "status": "QUEUED",
                    "active_operation": "process",
                    "active_job_id": "job-1",
                },
            )
            self.assertTrue(claimed)

        with self.Session() as db2:
            claimed_again = _update_task_when_status_matches(
                db2,
                task_id="task-cas-1",
                expected_statuses={"PENDING"},
                updates={
                    "status": "QUEUED",
                    "active_operation": "process",
                    "active_job_id": "job-2",
                },
            )
            self.assertFalse(claimed_again)

        with self.Session() as db3:
            task = db3.query(Task).filter(Task.id == "task-cas-1").first()
            self.assertIsNotNone(task)
            self.assertEqual(task.status, "QUEUED")
            self.assertEqual(task.active_job_id, "job-1")

    def test_rollback_task_claim_reverts_state(self):
        with self.Session() as db:
            claimed = _update_task_when_status_matches(
                db,
                task_id="task-cas-1",
                expected_statuses={"PENDING"},
                updates={
                    "status": "REVIEW_APPROVED",
                    "active_operation": "split",
                    "active_job_id": "job-split-1",
                },
            )
            self.assertTrue(claimed)

        with self.Session() as db:
            _rollback_task_claim(
                db,
                task_id="task-cas-1",
                operation="split",
                active_job_id="job-split-1",
                rollback_updates={
                    "status": "PENDING",
                    "active_operation": None,
                    "active_job_id": None,
                },
            )

        with self.Session() as db:
            task = db.query(Task).filter(Task.id == "task-cas-1").first()
            self.assertIsNotNone(task)
            self.assertEqual(task.status, "PENDING")
            self.assertIsNone(task.active_operation)
            self.assertIsNone(task.active_job_id)


if __name__ == "__main__":
    unittest.main()
