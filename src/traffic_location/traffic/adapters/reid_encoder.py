"""Experimental ReID profiling, transfer variants and ordered embedding prefetch.

Crop and resize math intentionally follow Ultralytics8.4.175. No association,
feature smoothing or identity decisions are performed here.
"""
from collections import deque
import time
from ...artifacts import require


class EncoderProfile:
    def __init__(self, encoder, timing, mode='original', crop_batch=32):
        self.encoder=encoder;self.timing=timing;self.mode=mode;self.crop_batch=crop_batch
        self.queue=None;self.encoder_seconds=0.;self.calls=0
        require(mode in ('original','cpu_input','io_binding'),'Unknown encoder transport')
        require(not encoder.is_pt and encoder.batch_size is None,'Trial expects dynamic exported ReID')

    def __getattr__(self,name):return getattr(self.encoder,name)

    def tensor(self,crops):
        import numpy as np
        import torch
        with self.timing.stage('reid_resize_normalize_cpu'):
            batch=torch.empty(len(crops),3,*self.encoder.imgsz,dtype=torch.float32)
            for i,c in enumerate(crops):
                t=torch.from_numpy(np.ascontiguousarray(c[...,::-1])).permute(2,0,1).unsqueeze(0).float()/255.0
                batch[i]=torch.nn.functional.interpolate(t,size=self.encoder.imgsz,mode='bilinear',align_corners=False)[0]
        if self.mode!='cpu_input':
            with self.timing.stage('reid_host_to_device'):
                batch=batch.to(self.encoder.device)
        if self.encoder.fp16:batch=batch.half()
        return batch

    def infer(self,crops):
        import numpy as np
        if not crops:return []
        batch=self.tensor(crops)
        if self.mode=='original':
            with self.timing.stage('reid_backend_inference_and_internal_copies'):
                feats=self.encoder.model(batch)
            with self.timing.stage('reid_features_to_cpu'):
                return [f.cpu().numpy() for f in feats]
        session=self.encoder.model.session
        if self.mode=='cpu_input':
            with self.timing.stage('reid_ort_inference_with_host_io'):
                outs=session.run(None,{session.get_inputs()[0].name:batch.numpy()})
        else:
            with self.timing.stage('reid_ort_io_binding_and_output_copy'):
                io=session.io_binding()
                io.bind_input(session.get_inputs()[0].name,'cuda',0,np.float16 if self.encoder.fp16 else np.float32,
                              tuple(batch.shape),batch.data_ptr())
                for output in session.get_outputs():io.bind_output(output.name,'cuda',0)
                session.run_with_iobinding(io)
                outs=io.copy_outputs_to_cpu()
        require(len(outs)==1 and len(outs[0])==len(crops),'Encoder output mapping differs')
        return list(outs[0])

    def crop(self,image,boxes):
        with self.timing.stage('reid_crop_cpu'):
            crops=self.encoder._crop_detections(image,boxes)
        return crops

    def encode_group(self,image,boxes):
        crops=self.crop(image,boxes);valid=[bool(c.size) for c in crops]
        feats=iter(self.infer([c for c,v in zip(crops,valid) if v]))
        return [next(feats) if v else None for v in valid]

    def __call__(self,image,boxes):
        import numpy as np
        if self.queue is not None:
            require(bool(self.queue),'Unexpected encoder request beyond prefetched candidates')
            expected,features=self.queue.popleft()
            require(np.array_equal(expected,boxes),'Frame/detection mapping changed during tracker update')
            return features
        start=time.monotonic();self.calls+=1
        try:return self.encode_group(image,boxes)
        finally:self.encoder_seconds+=time.monotonic()-start

    def prepare(self,tracker,frames):
        """Prefetch only stateless embeddings; tracker state is untouched."""
        from ultralytics.trackers.utils.stracks import parse_bboxes
        groups=[];crops=[]
        with self.timing.stage('reid_prefetch_prepare'):
            for image,raw in frames:
                per_frame=[]
                high,low,_,_=tracker._split_detections(raw)
                for selected in (high,low):
                    if not len(selected):continue
                    boxes=parse_bboxes(selected);batch=self.crop(image,boxes)
                    per_frame.append((boxes.copy(),len(crops),len(batch)))
                    crops.extend(batch)
                groups.append(per_frame)
        valid_indices=[i for i,c in enumerate(crops) if c.size]
        features=[None]*len(crops)
        for offset in range(0,len(valid_indices),self.crop_batch):
            indices=valid_indices[offset:offset+self.crop_batch]
            for i,feat in zip(indices,self.infer([crops[i] for i in indices])):features[i]=feat
        return [deque((boxes,features[start:start+n]) for boxes,start,n in group) for group in groups]
