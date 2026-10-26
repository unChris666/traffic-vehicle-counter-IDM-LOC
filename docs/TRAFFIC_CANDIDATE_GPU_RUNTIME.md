# Traffic candidate FP32 and one-video-per-GPU execution

Owner instruction, 27 October 2026: adopt the tested candidate and allow one
active video on each available GPU. This explicitly supersedes the earlier
single-GPU-only preference. Counting rules and model hashes are unchanged.

CUDA fresh inference now defaults to `execution_profile=candidate_fp32`:
YOLO26M FP32 batch4, same ReID ONNX FP32, IO binding, eight-frame feature
prefetch and chunks of at most32 valid crops. BoT-SORT is updated once per
source frame in original order, including empty detections. Tail batches keep
all frames. This reuses the same implementation as the benchmark rather than
maintaining an experimental and adopted copy. CPU and an explicitly selected
`baseline_fp32` keep the original path. Unsupported profiles fail explicitly.

Observed one-video evidence: [report](evidence/traffic_performance/pair_fp32/report.json).
Baseline714.84s; candidate477.79s, 33.16% less time in one run. Both counted133
vehicles with identical category/direction totals, pending28, invalid11 and
cancelled10. Track/detection links and event identities differed. Adoption is
owner-authorized despite this failed strict equivalence gate; vehicle identity
accuracy, precision/recall, other-scene quality and repeatability remain unknown.
Existing baseline artifacts are retained and never relabelled as candidate.

`KaggleRuntime.execute` prepares runtime/model files once, then uses
`traffic.gpu_scheduler.run_video_jobs` for independent video jobs. Area runs
independently before Traffic; PPAC retains its required-result validation.
One visible GPU means sequential videos; two visible GPUs allow two concurrent
videos. A free GPU takes the next queued video. Each lane remains reserved
through that video's inference/counting. A failed job produces a receipt and
does not cancel other lanes. Resources such as CPU/disk are shared; a2x batch
speedup is not established. Completed results are collected in input order.

Each inference is a new subprocess. Only that child's `CUDA_VISIBLE_DEVICES`
is set to the assigned GPU; the parent environment is never mutated. Within
the child both Torch and ONNX Runtime use local `cuda:0`. Existing visibility
masks, including GPU UUIDs, are respected. No GPU means a clear failure, never
a silent CPU fallback. GPU assignment and effective execution profile enter
request/cache identity; new code invalidates earlier inference cache entries.
Per-video progress and worker logs remain separate.

For non-Kaggle callers:

```python
from traffic_location.traffic.gpu_scheduler import run_video_jobs
from traffic_location.traffic.orchestration import fresh_inference
import sys

def process(job, gpu_id):
    return fresh_inference(job['request'], job['output'],
                           python_executable=sys.executable, gpu_id=gpu_id)

receipts = run_video_jobs(jobs, process)  # request/output must be unique per video
```

The request's device remains `cuda:0`; select `baseline_fp32` explicitly for
comparison. This API performs inference; counting remains a separate module.
KaggleRuntime performs both. Install the checkout or its built wheel; an older
installed wheel does not acquire these changes automatically. Notebook11 now
embeds exact wheel0.4.7rc1 and stays setup/engine OFF until explicitly enabled.
The two-config benchmark notebook is preserved as historical evidence.

Validation: local unit tests cover candidate routing, FP32 controls, fresh
process invocation, per-child GPU masks, one/two-lane exclusion, failure
continuation, visibility discovery, cache behavior and independent engine
failures. No real dual-GPU execution was performed in this development session.
