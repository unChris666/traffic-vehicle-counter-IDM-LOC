"""Measured-anchor variation diagnostics, NOT state-machine replay or traffic count."""
import argparse, collections, gzip, hashlib, json, math, pathlib, statistics


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantiles(values):
    v=sorted(values)
    if not v: return {'n':0}
    def q(p):
        k=(len(v)-1)*p; a=int(k); b=min(a+1,len(v)-1)
        return v[a]+(v[b]-v[a])*(k-a)
    return {'n':len(v),'min':v[0],'p25':q(.25),'median':q(.5),'p75':q(.75),'p90':q(.9),'max':v[-1]}


def roi(p,poly):
    inside=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        cross=(p[0]-a[0])*(b[1]-a[1])-(p[1]-a[1])*(b[0]-a[0])
        if abs(cross)<=1e-7 and min(a[0],b[0])-1e-9<=p[0]<=max(a[0],b[0])+1e-9 and min(a[1],b[1])-1e-9<=p[1]<=max(a[1],b[1])+1e-9:
            return 'boundary'
        if (a[1]>p[1]) != (b[1]>p[1]):
            x=a[0]+(p[1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if p[0]<x: inside=not inside
    return 'inside' if inside else 'outside'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',default='/workspace/traffic-vehicle-counter-IDM-LOC');ap.add_argument('--output',default='/tmp/phase5_record_variation_analysis.json');args=ap.parse_args()
    root=pathlib.Path(args.root)
    rpath=root/'docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz'
    gpath=root/'docs/evidence/phase_5/review_drafts/G3/candidate_geometry.json'
    g=json.loads(gpath.read_text())['rendered_native_pixels'];p1=g['line']['P1'];p2=g['line']['P2'];dx=p2[0]-p1[0];dy=p2[1]-p1[1];length=math.hypot(dx,dy)
    tracks=collections.defaultdict(list);row_count=0;byclass=collections.Counter();regions=collections.Counter();bad=[]
    with gzip.open(rpath,'rt') as f:
        for ln,line in enumerate(f,1):
            row=json.loads(line);row_count+=1
            if row['frame_index']!=ln-1 or (row['width'],row['height'])!=(1280,720):bad.append({'line':ln,'frame':row['frame_index'],'dimensions':[row['width'],row['height']]})
            for o in row['emitted_tracks']:
                if o['measurement_provenance']!='retained_phase_2_detection' or o['frame_index']!=row['frame_index']:raise ValueError('measurement mismatch')
                source=row['raw_detections'][o['original_detection_index']]
                if source['bbox_xyxy_pixels']!=o['raw_bbox'] or source['class_id']!=o['class_id'] or source['class_name']!=o['class_name']:raise ValueError('raw detection link mismatch')
                bb=o['raw_bbox'];p=[(bb[0]+bb[2])/2,bb[3]];d=(dx*(p[1]-p1[1])-dy*(p[0]-p1[0]))/length;t=((p[0]-p1[0])*dx+(p[1]-p1[1])*dy)/length**2
                a=roi(p,g['side_a_polygon']);b=roi(p,g['side_b_polygon']);region='A' if a=='inside' else 'B' if b=='inside' else 'boundary' if a=='boundary' or b=='boundary' else 'outside'
                if a=='inside' and b=='inside':raise ValueError('overlapping interiors encountered')
                obs={'frame':row['frame_index'],'track_id':o['track_id'],'point':p,'distance_px':d,'line_projection':t,'region':region,'raw_class':o['class_name'],'detection_index':o['original_detection_index'],'raw_bbox':bb}
                tracks[o['track_id']].append(obs);byclass[o['class_name']]+=1;regions[region]+=1
    sign=lambda x: -1 if x<0 else 1 if x>0 else 0
    pairs=[];gaps=[];nearsteps=[];excursions=[];regionruns=[];line_sign_runs=[]
    for tid,obs in tracks.items():
        for a,b in zip(obs,obs[1:]):
            gap=b['frame']-a['frame'];different=sign(a['distance_px'])!=sign(b['distance_px'])
            if gap>1:
                gaps.append({'track_id':tid,'before':a,'after':b,'missing_observed_frames':gap-1,'line_sign_change':different})
                continue
            if 0<=a['line_projection']<=1 and 0<=b['line_projection']<=1:
                if abs(a['distance_px'])<=10 or abs(b['distance_px'])<=10:
                    nearsteps.append(abs(b['distance_px']-a['distance_px']))
                if different and sign(a['distance_px'])*sign(b['distance_px'])<0:
                    alpha=-a['distance_px']/(b['distance_px']-a['distance_px']);cross=[a['point'][i]+alpha*(b['point'][i]-a['point'][i]) for i in [0,1]]
                    t=((cross[0]-p1[0])*dx+(cross[1]-p1[1])*dy)/length**2
                    if 0<t<1:pairs.append({'track_id':tid,'before':a,'after':b,'crossing_point':cross,'signed_step_px':b['distance_px']-a['distance_px'],'classes_differ':a['raw_class']!=b['raw_class']})
        # Runs never bridge missing frames. All sign flips here are measurements, not labelled jitter.
        runs=[];rr=[]
        for o in obs:
            sg=sign(o['distance_px'])
            if runs and o['frame']==runs[-1][-1]['frame']+1 and sg==sign(runs[-1][0]['distance_px']):runs[-1].append(o)
            else:runs.append([o])
            if rr and o['frame']==rr[-1][-1]['frame']+1 and o['region']==rr[-1][0]['region']:rr[-1].append(o)
            else:rr.append([o])
        for r in rr:
            if r[0]['region'] in ('A','B'):regionruns.append({'track_id':tid,'region':r[0]['region'],'start_frame':r[0]['frame'],'end_frame':r[-1]['frame'],'observations':len(r),'max_abs_distance_px':max(abs(o['distance_px']) for o in r)})
        for r in runs:line_sign_runs.append(len(r))
        for i in range(1,len(runs)-1):
            prev,r,nxt=runs[i-1],runs[i],runs[i+1]
            if prev[-1]['frame']+1!=r[0]['frame'] or r[-1]['frame']+1!=nxt[0]['frame']:continue
            if sign(prev[-1]['distance_px'])!=sign(nxt[0]['distance_px']):continue
            if not all(0<=o['line_projection']<=1 for o in [prev[-1],*r,nxt[0]]):continue
            excursions.append({'track_id':tid,'start_frame':r[0]['frame'],'end_frame':r[-1]['frame'],'observations':len(r),'max_abs_distance_px':max(abs(o['distance_px']) for o in r),'raw_classes':sorted(set(o['raw_class'] for o in r)),'before':prev[-1],'first':r[0],'last':r[-1],'after':nxt[0]})
    short=[e for e in excursions if e['observations']<=3]
    stats=quantiles([e['max_abs_distance_px'] for e in short])
    # Explicit experimental control plus data-derived brackets, no accepted production setting.
    bands=[0.0]
    if short:bands += sorted(set([stats['median'],stats['max']]))
    lens=sorted(set(e['observations'] for e in short))
    confirmations=sorted(set([1]+[n+1 for n in lens]))
    burst_intervals=[(0,29),(2555,2584),(5125,5154),(7696,7725),(10252,10281)]
    burst_contact_frames=sorted({a+i for a,b in burst_intervals for i in [0,5,10,15,20,29]})
    # Focused red-scooter contact sheet has all six frames; full-resolution
    # tracked samples retain7711..7718. Broad burst sheets are SIX samples,
    # not pixel evidence for every frame in their named30-frame interval.
    exact_visual_frames=set(burst_contact_frames)|set(range(5125,5131))|set(range(7711,7719))|{0,2570,5140,10281}
    coverage_pairs=[p for p in pairs if p['before']['frame'] in exact_visual_frames and p['after']['frame'] in exact_visual_frames]
    burst_bracket_pairs=[p for p in pairs if any(a<=p['before']['frame'] and p['after']['frame']<=b for a,b in burst_intervals)]
    raw_frames=[0,2570,5140,7711,10281]
    output={
        'claim_type':'EXPERIMENT_RESULT_MEASURED_ANCHOR_DIAGNOSTICS_ONLY',
        'method':'Emitted linked raw_bbox bottom-center; signed perpendicular distance to native finite G3 line; sign pairs require consecutive frames and proper finite-line intersection. Excursion = contiguous measured sign run bracketed by opposite sign and return. No state-machine replay, object counts or classification evaluation.',
        'files':{'records':str(rpath.relative_to(root)),'records_sha256':sha(rpath),'geometry':str(gpath.relative_to(root)),'geometry_sha256':sha(gpath),'script_sha256':sha(pathlib.Path(__file__))},
        'alignment_errors':bad,'frame_rows':row_count,'software_track_ids':len(tracks),'measured_emitted_observations':sum(map(len,tracks.values())),'raw_class_observation_frequency':dict(byclass),'anchor_region_observation_frequency':dict(regions),
        'contiguous_proper_finite_line_sign_change_pairs':len(pairs),'sign_change_pair_raw_class_change_frequency':sum(p['classes_differ'] for p in pairs),'sign_change_signed_step_abs_px':quantiles([abs(p['signed_step_px']) for p in pairs]),
        'measurement_gaps':len(gaps),'gap_missing_observations':quantiles([g['missing_observed_frames'] for g in gaps]),'gap_line_sign_changes':sum(g['line_sign_change'] for g in gaps),
        'near_line_step_scope_px':10,'near_line_abs_perpendicular_step_px':quantiles(nearsteps),
        'contiguous_returning_sign_excursions':len(excursions),'short_excursion_scope_observations_max':3,'short_sign_excursions':len(short),'short_excursion_amplitude_px':stats,'short_excursion_runlength_frequency':dict(collections.Counter(e['observations'] for e in short)),
        'region_runlength_by_roi':{r:quantiles([e['observations'] for e in regionruns if e['region']==r]) for r in ['A','B']},
        'proposed_sensitivity_candidates':{'claim_type':'PROPOSAL_DIAGNOSTIC_ONLY_NOT_SELECTED_DEFAULT','neutral_band_px':bands,'confirmation_observations':confirmations,'reason':'0/1 geometric control. Positive bands are observed median and maximum absolute distance of measured <=3-observation return excursions (n=3). Maximum is a stress sensitivity value, not a noise/default estimate. Confirmation values one greater than observed short excursion run lengths. This tests suppression/retention sensitivity; excursions are not ground-truth jitter, and real reversals/class handoff may be present.'},
        'short_excursion_cases':sorted(short,key=lambda e:(e['start_frame'],e['track_id'])),
        'all_contiguous_finite_line_sign_pairs':pairs,
        'gap_sign_change_cases':[g for g in gaps if g['line_sign_change']],
        'sign_pair_raw_class_frequency':dict(collections.Counter(p['after']['raw_class'] for p in pairs)),
        'source_review_sign_pairs':coverage_pairs,
        'source_review_bracketed_sign_pairs':burst_bracket_pairs,
        'source_review_coverage':{'retained_raw_frame_indices':raw_frames,'retained_tracked_full_resolution_frame_indices':[0,2570,5140,*range(7711,7719),10281], 'contact_sheet_burst_named_intervals':[list(i) for i in burst_intervals],'burst_contact_sheet_actual_frame_indices':burst_contact_frames,'focused_red_scooter_contact_sheet_actual_frame_indices':list(range(5125,5131)),'proper_pair_cases_with_both_exact_frames_retained_as_pixels':len(coverage_pairs),'proper_pairs_within_broad_burst_intervals_not_necessarily_pixel_retained':len(burst_bracket_pairs),'raw_video_available_in_current_workspace':(pathlib.Path('/tmp/traffic-review-input/TOR3-PAGI.mp4').is_file()),'repository_retained_mp4_files':sorted(str(p.relative_to(root)) for p in (root/'docs/evidence/phase_4').rglob('*.mp4')),'limits':'Broad burst contact sheets contain six sample frames, not all30frames. Contact sheets are reduced annotated evidence, not full-resolution raw temporal frames; no complete video pixel replay available locally. Cached measurement diagnostics cover every aligned frame.'},
        'interpretation_limits':['Measured sign reversals do not prove jitter or actual physical-object reversals.','Tracker IDs can represent components/duplicate identities; raw detector classes are not accepted product categories.','No accuracy, traffic count, physical-identity count, best threshold or Phase6 business policy is established.']
    }
    pathlib.Path(args.output).write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k not in ['short_excursion_cases','source_review_sign_pairs','source_review_bracketed_sign_pairs','all_contiguous_finite_line_sign_pairs','gap_sign_change_cases']},indent=2))


if __name__=='__main__':main()
