import os
import unittest
from unittest.mock import patch
import tempfile
import orchestrator.state

class OrchestratorTestCase(unittest.TestCase):
    def setUp(self):
        # Create a temp file for state
        self.state_fd, self.state_path = tempfile.mkstemp(suffix=".json")
        os.close(self.state_fd)
        
        # Patch STATE_FILE in orchestrator.state
        # We patch it where it is used.
        self.patcher = patch("orchestrator.state.STATE_FILE", self.state_path)
        self.patcher.start()
        
        # Reset in-memory state globals in orchestrator.state
        orchestrator.state._state_cache = None
        orchestrator.state._last_written_json = None
        orchestrator.state._task_locks.clear()
        orchestrator.state._running_processes.clear()

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.state_path):
            os.remove(self.state_path)
        if os.path.exists(f"{self.state_path}.bak"):
            os.remove(f"{self.state_path}.bak")
