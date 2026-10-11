# Phase 2 detection report

Run: `20261011T052950_360560Z_ed399fb8`; status: `completed_decoder_stream_manual_review_pending`.

This report contains executed observations only when a run has actually completed.

## Input identity / metadata

```json
{
  "filename": "TOR3-PAGI.mp4",
  "path": "/kaggle/input/datasets/chrisbiran/traffic-tracker-videos/TOR3-PAGI.mp4",
  "file_size_bytes": 53173467,
  "sha256": "606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c",
  "hash_seconds": 0.8686952819998623,
  "expected_hash_matches": true,
  "recording_period_assignment": "unknown: filename is not authoritative metadata",
  "store_location_assignment": "unknown",
  "ffprobe": {
    "returncode": 0,
    "data": {
      "programs": [],
      "streams": [
        {
          "codec_name": "h264",
          "width": 1280,
          "height": 720,
          "r_frame_rate": "30000/1001",
          "avg_frame_rate": "46269000/1551869",
          "duration": "344.859778",
          "nb_frames": "10282"
        }
      ],
      "format": {
        "duration": "344.860000"
      }
    },
    "stderr": ""
  },
  "opencv_metadata": {
    "width": 1280.0,
    "height": 720.0,
    "fps": 29.81501660256117,
    "frame_count": 10282.0,
    "fourcc_integer": 875967080.0,
    "backend": "FFMPEG",
    "duration_seconds_estimate_from_count_fps": 344.85977777777777,
    "fourcc_text": "h264"
  }
}
```

## Environment

```json
{
  "python": "3.12.13 (main, Mar  4 2026, 09:23:07) [GCC 11.4.0]",
  "platform": "Linux-6.18.48+-x86_64-with-glibc2.35",
  "cpu_count": 4,
  "package_versions": {
    "ultralytics": "8.4.175",
    "torch": "2.10.0+cu128",
    "torchvision": "0.25.0+cu128",
    "numpy": "2.0.2",
    "opencv-python": "4.13.0.92",
    "opencv-python-headless": "4.13.0.92",
    "Pillow": "11.3.0"
  },
  "opencv_version": "4.13.0",
  "ultralytics_settings_directory": "/kaggle/working/yolo_detection/.ultralytics_settings",
  "torch_cuda_build": "12.8",
  "cuda_available": true,
  "visible_cuda_device_count": 2,
  "cuda_devices": [
    {
      "index": 0,
      "name": "Tesla T4",
      "total_memory_bytes": 15636037632,
      "compute_capability": [
        7,
        5
      ]
    },
    {
      "index": 1,
      "name": "Tesla T4",
      "total_memory_bytes": 15636037632,
      "compute_capability": [
        7,
        5
      ]
    }
  ],
  "nvidia_smi": {
    "returncode": 0,
    "stdout": "0, Tesla T4, 15360, 580.178.04\n1, Tesla T4, 15360, 580.178.04",
    "stderr": ""
  },
  "reproducibility": {
    "seed": 0,
    "deterministic_algorithms_enabled": false,
    "cudnn_deterministic": false,
    "cudnn_benchmark": false,
    "exact_repeatability_claimed": false
  }
}
```

## Actual model / class labels

```json
{
  "task": "detect",
  "class_names": {
    "0": "person",
    "1": "bicycle",
    "2": "car",
    "3": "motorcycle",
    "4": "airplane",
    "5": "bus",
    "6": "train",
    "7": "truck",
    "8": "boat",
    "9": "traffic light",
    "10": "fire hydrant",
    "11": "stop sign",
    "12": "parking meter",
    "13": "bench",
    "14": "bird",
    "15": "cat",
    "16": "dog",
    "17": "horse",
    "18": "sheep",
    "19": "cow",
    "20": "elephant",
    "21": "bear",
    "22": "zebra",
    "23": "giraffe",
    "24": "backpack",
    "25": "umbrella",
    "26": "handbag",
    "27": "tie",
    "28": "suitcase",
    "29": "frisbee",
    "30": "skis",
    "31": "snowboard",
    "32": "sports ball",
    "33": "kite",
    "34": "baseball bat",
    "35": "baseball glove",
    "36": "skateboard",
    "37": "surfboard",
    "38": "tennis racket",
    "39": "bottle",
    "40": "wine glass",
    "41": "cup",
    "42": "fork",
    "43": "knife",
    "44": "spoon",
    "45": "bowl",
    "46": "banana",
    "47": "apple",
    "48": "sandwich",
    "49": "orange",
    "50": "broccoli",
    "51": "carrot",
    "52": "hot dog",
    "53": "pizza",
    "54": "donut",
    "55": "cake",
    "56": "chair",
    "57": "couch",
    "58": "potted plant",
    "59": "bed",
    "60": "dining table",
    "61": "toilet",
    "62": "tv",
    "63": "laptop",
    "64": "mouse",
    "65": "remote",
    "66": "keyboard",
    "67": "cell phone",
    "68": "microwave",
    "69": "oven",
    "70": "toaster",
    "71": "sink",
    "72": "refrigerator",
    "73": "book",
    "74": "clock",
    "75": "vase",
    "76": "scissors",
    "77": "teddy bear",
    "78": "hair drier",
    "79": "toothbrush"
  },
  "model_python_type": "ultralytics.nn.tasks.DetectionModel",
  "checkpoint_head_python_type": "ultralytics.nn.modules.head.Detect",
  "checkpoint_head_end2end": false,
  "checkpoint_head_reg_max": 1,
  "active_predictor_backend": {
    "python_type": "ultralytics.nn.autobackend.AutoBackend",
    "device": "cuda:0",
    "format": "pt",
    "end2end": false,
    "fp16": false,
    "actual_imgsz": [
      640,
      640
    ]
  },
  "observed_labels_related_to_product": {
    "0": "person",
    "2": "car",
    "3": "motorcycle",
    "5": "bus",
    "7": "truck"
  },
  "product_category_mapping": "OPEN; raw model classes are retained, no bus-to-angkot inference"
}
```

## Configuration

```json
{
  "video_path": "/kaggle/input/datasets/chrisbiran/traffic-tracker-videos/TOR3-PAGI.mp4",
  "expected_video_sha256": "606cfdd26c2d0a6892f5680d6a35d7e4d372efd76dd6bc56e2e4cbed7a74754c",
  "device": 0,
  "frame_limit": null,
  "seed": 0,
  "package_version": "8.4.175",
  "baseline_status": "PROPOSAL: pinned published defaults; not tuned product settings",
  "overrides": {
    "conf": null,
    "imgsz": null,
    "iou": null,
    "max_det": null,
    "nms": null,
    "quantize": null
  },
  "class_filter": null,
  "detection_roi": null,
  "enhancement": null,
  "sample_indices": [
    0,
    2570,
    5140,
    7711,
    10281
  ],
  "sampling_basis": "configured prefix / metadata frame count; actual last processed frame is also saved"
}
```

## Effective predictor arguments

```json
{
  "task": "detect",
  "mode": "predict",
  "model": "/kaggle/working/yolo_detection/weights/yolo26m.pt",
  "data": "/home/lq/codes/ultralytics/ultralytics/cfg/datasets/coco.yaml",
  "epochs": 100,
  "time": null,
  "patience": 100,
  "batch": 1,
  "imgsz": 640,
  "save": false,
  "save_period": -1,
  "cache": false,
  "device": 0,
  "workers": 8,
  "project": null,
  "name": null,
  "exist_ok": false,
  "pretrained": true,
  "cls_remap": true,
  "optimizer": "auto",
  "verbose": false,
  "seed": 0,
  "deterministic": true,
  "single_cls": false,
  "rect": true,
  "cos_lr": false,
  "close_mosaic": 10,
  "resume": false,
  "amp": true,
  "fraction": 1.0,
  "profile": false,
  "freeze": null,
  "multi_scale": 0.0,
  "compile": false,
  "channels_last": null,
  "overlap_mask": true,
  "mask_ratio": 4,
  "dropout": 0.0,
  "val": true,
  "split": "val",
  "save_json": false,
  "conf": 0.25,
  "iou": 0.7,
  "max_det": 300,
  "quantize": null,
  "dnn": false,
  "plots": true,
  "nms": null,
  "source": null,
  "vid_stride": 1,
  "stream_buffer": false,
  "visualize": false,
  "augment": false,
  "agnostic_nms": false,
  "classes": null,
  "retina_masks": false,
  "embed": null,
  "show": false,
  "save_frames": false,
  "save_txt": false,
  "save_conf": false,
  "save_crop": false,
  "show_labels": true,
  "show_conf": true,
  "show_boxes": true,
  "line_width": null,
  "format": "torchscript",
  "optimize": false,
  "dynamic": false,
  "simplify": true,
  "opset": null,
  "workspace": null,
  "lr0": 0.01,
  "lrf": 0.01,
  "momentum": 0.937,
  "weight_decay": 0.0005,
  "warmup_epochs": 3.0,
  "warmup_momentum": 0.8,
  "warmup_bias_lr": 0.1,
  "distill_model": null,
  "dis": 6.0,
  "box": 7.5,
  "cls": 0.5,
  "cls_pw": 0.0,
  "dfl": 1.5,
  "pose": 12.0,
  "kobj": 1.0,
  "rle": 1.0,
  "angle": 1.0,
  "dlog": 1.0,
  "dgrad": 0.5,
  "dlam": 1.0,
  "nbs": 64,
  "hsv_h": 0.015,
  "hsv_s": 0.7,
  "hsv_v": 0.4,
  "degrees": 0.0,
  "translate": 0.1,
  "scale": 0.5,
  "shear": 0.0,
  "perspective": 0.0,
  "flipud": 0.0,
  "fliplr": 0.5,
  "bgr": 0.0,
  "mosaic": 1.0,
  "mixup": 0.0,
  "cutmix": 0.0,
  "copy_paste": 0.0,
  "copy_paste_mode": "flip",
  "auto_augment": "randaugment",
  "erasing": 0.4,
  "cfg": null,
  "tracker": "tracktrack.yaml"
}
```

## Execution / measured timings

```json
{
  "frames_processed": 10282,
  "decode_stop": "opencv_read_false_eof_or_decode_failure_unknown",
  "metadata_frame_count": 10282,
  "processed_frames_match_metadata": true,
  "configured_frame_limit": null,
  "scope": "all_frames_returned_by_decoder",
  "loop_wall_seconds": 195.9344462219999,
  "decode_read_wall_seconds": 12.72246106201078,
  "first_prediction_seconds_including_setup_warmup": 3.0871243840001625,
  "subsequent_prediction_calls": 10281,
  "subsequent_prediction_wall_ms_mean": 16.97970492461831,
  "subsequent_prediction_wall_ms_median": 17.028865999918708,
  "subsequent_library_speed_ms_mean": {
    "preprocess": 1.2354453885793384,
    "inference": 13.89547494271111,
    "postprocess": 1.3948794280727066
  },
  "whole_loop_throughput_frames_per_second": 52.47673493996135,
  "cuda_peak_allocated_bytes": 166716416,
  "cuda_peak_reserved_bytes": 207618048,
  "timing_limits": "Loop includes decoder/predict/JSONL/sample IO; first-call wall includes predictor setup and warmup. Library stage timings are separate.",
  "jsonl_rows_verified": 10282,
  "serialization_validation": "passed"
}
```

## Artifacts

```json
{
  "frame_detections": "frame_detections.jsonl",
  "frame_detections_sha256": "033a2815d3abbd23327936a1b9d948b2b9b7d312796516e5ee46aec5685be345",
  "annotated_contact_sheet": {
    "path": "annotated_contact_sheet.png",
    "sha256": "65837105936d7bb49bc259ec396a5afeaa64452683fedf0c4c338f6ef22b8e4c",
    "purpose": "display-only resized preview; native PNGs retained"
  }
}
```

## Manual detection review

```json
{
  "visible_detections": {
    "observation": null,
    "evidence": []
  },
  "missed_or_ambiguous_objects": {
    "observation": null,
    "evidence": []
  },
  "class_ambiguities": {
    "observation": null,
    "evidence": []
  },
  "overlay_and_occlusion_cases": {
    "observation": null,
    "evidence": []
  },
  "questions_for_later_experiments": {
    "observation": null,
    "evidence": [],
    "claim_type": "OPEN"
  }
}
```

## Limitations

- No ground truth; detector scores and plausible boxes do not establish accuracy.
- Detection records describe individual frames, not unique vehicles or traffic counts.
- CAP_PROP_POS_MSEC is backend-reported, not verified source presentation timestamps.
- Frame-index / FPS estimates are separate from backend timestamps and may disagree.
- OpenCV read=False alone cannot distinguish genuine end-of-file from decode failure.
- Matching a metadata frame total is a consistency check, not proof of source integrity.
- No bus/angkot reporting-category mapping is accepted by this experiment.
- One morning video does not establish night or multi-video performance.
