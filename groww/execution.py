"""Private, durable attempt journal. Approval itself is never restored into a session."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from .approval import ACTIONS, approval_valid, parse_receipt
from .outputs import fingerprint


class ExecutionJournal:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, '
                       'approval_json TEXT NOT NULL, states_json TEXT NOT NULL, updated_at TEXT NOT NULL)')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def find(self, run_id: str) -> dict:
        with self._connect() as db:
            row = db.execute('SELECT payload_hash, approval_json, states_json, updated_at FROM runs WHERE run_id=?',
                             (run_id,)).fetchone()
        return {} if not row else dict(payload_hash=row[0], approval=json.loads(row[1]),
                                       states=json.loads(row[2]), updated_at=row[3])

    @staticmethod
    def _read(db, payload):
        row = db.execute('SELECT payload_hash, approval_json, states_json FROM runs WHERE run_id=?',
                         (payload['run_id'],)).fetchone()
        if row and row[0] != fingerprint(payload):
            raise ValueError('This run already has attempts for different content or a different document. Reconcile it first.')
        return (json.loads(row[1]), json.loads(row[2])) if row else ({}, {})

    @staticmethod
    def _write(db, payload, approval, states):
        db.execute('INSERT INTO runs VALUES (?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET '
                   'approval_json=excluded.approval_json, states_json=excluded.states_json, updated_at=excluded.updated_at',
                   (payload['run_id'], fingerprint(payload), json.dumps(approval), json.dumps(states),
                    datetime.now(timezone.utc).isoformat()))

    def load(self, payload: dict) -> dict:
        with self._connect() as db:
            return self._read(db, payload)[1]

    def claim(self, payload: dict, action: str, approval: dict) -> tuple[bool, dict]:
        if action not in ACTIONS or not approval_valid(payload, approval):
            raise ValueError('Current explicit approval is required to record an attempt.')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            _, states = self._read(db, payload)
            previous = states.get(action, {})
            if previous and not (previous.get('status') == 'failed' and previous.get('safe_to_retry') is True):
                return False, states
            if action == ACTIONS[1] and states.get(ACTIONS[0], {}).get('status') != 'succeeded':
                raise ValueError('The document append must be confirmed before drafting.')
            states[action] = dict(run_id=payload['run_id'], payload_hash=fingerprint(payload), action=action,
                                  status='in_progress', message='Attempt recorded before MCP call; verify the remote result if interrupted.')
            self._write(db, payload, approval, states)
            return True, states

    def reconcile(self, payload: dict, recovered: dict) -> dict:
        checked = {a: parse_receipt(SimpleNamespace(structuredContent=r), a, payload) for a, r in recovered.items()}
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            approval, states = self._read(db, payload)
            for action, receipt in checked.items():
                prior = states.get(action, {})
                if prior.get('status') == 'succeeded' and receipt != prior:
                    raise ValueError('A confirmed successful receipt cannot be replaced or downgraded.')
                states[action] = receipt
            if checked:
                self._write(db, payload, approval, states)
            return states
