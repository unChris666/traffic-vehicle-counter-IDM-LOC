"""Render-only entry points: no imports from the counting/identity pipeline."""
from copy import deepcopy
from ._kernel import render_kernel
from ..artifacts import semantic_hash,require

def frame(image,measurement,native_result,geometry,*,fps,video_id,frame_index=None):
 before=semantic_hash(native_result)
 canvas,state=render_kernel.render_b_v6_frame(image,measurement,deepcopy(native_result),geometry,
   fps=fps,video_id=video_id,frame_index=frame_index,
   unit_assignments=native_result.get('frame_assignments',[]),component_relations=native_result.get('component_links',[]))
 require(semantic_hash(native_result)==before,'Renderer modified counting result')
 return canvas,state

def timeline(native_result,geometry=None,frame_count=None):
 before=semantic_hash(native_result)
 value=render_kernel.build_b_v6_timeline(deepcopy(native_result),geometry,frame_count=frame_count,
   unit_assignments=native_result.get('frame_assignments',[]),component_relations=native_result.get('component_links',[]))
 require(semantic_hash(native_result)==before,'Timeline mutated result')
 return value

def video(video_path,measurement_path,native_result,geometry,output_path,*,fps,frame_count,source_identity,progress=None):
 before=semantic_hash(native_result)
 report=render_kernel.render_b_v6_video(video_path,measurement_path,deepcopy(native_result),geometry,output_path,
   fps=fps,expected_frame_count=frame_count,source_identity=source_identity,
   unit_assignments=native_result.get('frame_assignments',[]),component_relations=native_result.get('component_links',[]),progress=progress)
 require(semantic_hash(native_result)==before,'Video render mutated counting result')
 return report
