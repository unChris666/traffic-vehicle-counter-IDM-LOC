"""Single-device FP32 experiment helpers, with bounded frame batches."""
from contextlib import contextmanager
from collections import defaultdict
import json
import os
import time
from pathlib import Path


def batch_size(request):
    value = request.get('performance', {}).get('batch_size', 1)
    if type(value) is not int or not 1 <= value <= 150:
        raise ValueError('Experimental FP32 batch_size must be an integer from 1 to 150')
    return value


def decode_batches(cap, count, size):
    """Decode every frame once; never skip or change tracker chronology."""
    for start in range(0, count, size):
        images = []
        for _ in range(min(size, count - start)):
            ok, image = cap.read()
            if not ok:
                raise ValueError('Decode failed within requested scope')
            images.append(image)
        yield start, images


class Progress:
    """CPU wall times plus sampled CUDA event times (not additive to CPU times)."""
    def __init__(self, path=None, *, clock=time.monotonic):
        self.path = Path(path) if path else None
        self.clock = clock
        self.started = clock()
        self.seconds = defaultdict(float)
        self.cuda_ms = defaultdict(float)
        self.cuda_samples = defaultdict(int)
        self.pending = []

    @contextmanager
    def stage(self, name):
        started = self.clock()
        try:
            yield
        finally:
            self.seconds[name] += self.clock() - started

    @contextmanager
    def cuda_sample(self, name, torch, enabled):
        # Samples default Torch stream only. ORT streams need a separate profiler.
        if not enabled:
            yield
            return
        first, last = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        first.record()
        try:
            yield
        finally:
            last.record()
            self.pending.append((name, first, last))

    def snapshot(self, stage, *, completed=None, total=None):
        waiting = []
        for name, first, last in self.pending:
            if last.query():
                self.cuda_ms[name] += first.elapsed_time(last)
                self.cuda_samples[name] += 1
            else:
                waiting.append((name, first, last))
        self.pending = waiting
        elapsed = max(self.clock() - self.started, 1e-9)
        fps = completed / elapsed if completed else None
        value = {'stage': stage, 'elapsed_seconds': round(elapsed, 3),
                 'wall_seconds': dict(self.seconds), 'cuda_sample_ms': dict(self.cuda_ms),
                 'cuda_sample_count': dict(self.cuda_samples),
                 'cuda_timing_scope': 'TORCH_CURRENT_STREAM_ONLY_NOT_ORT',
                 'cuda_pending_samples': len(self.pending),
                 'completed': completed, 'total': total, 'fps_actual': fps,
                 'eta_seconds': (total - completed) / fps if fps and total is not None else None}
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_name(self.path.name + '.tmp')
            temp.write_text(json.dumps(value, allow_nan=False))
            os.replace(temp, self.path)
        return value


# Caller may route counting timings without changing the frozen request schema.
from contextvars import ContextVar
_ACTIVE = ContextVar('traffic_performance_path', default=None)

@contextmanager
def profile_to(path):
    token = _ACTIVE.set(Progress(path))
    try:
        yield
    finally:
        _ACTIVE.reset(token)

def active_progress():
    return _ACTIVE.get() or Progress()
