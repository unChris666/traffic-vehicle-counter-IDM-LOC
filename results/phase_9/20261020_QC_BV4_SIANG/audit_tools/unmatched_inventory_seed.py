import csv,json
from pathlib import Path
r=Path('/workspace/traffic-vehicle-counter-IDM-LOC/results/phase_9/20261020_QC_BV4_SIANG/unmatched')
items=[
('RAW-B01',0,30,'Black pickup already travelling away at clip start','B_TO_A','vehicle','CLIP_START_PARTIAL'),
('RAW-B02',33,140,'Man walking while pushing blue vending cart','B_TO_A','pedestrian','SOURCE_ROLE_POSITIVE_KNOWN_CASE54'),
('RAW-B03',180,285,'Black compact MPV approaching camera from road background to right foreground','A_TO_B','car','SOURCE_PASSAGE_POSITIVE'),
('RAW-B04',285,330,'Red motorcycle with blue floral shirt rider moving away','B_TO_A','motorcycle','SOURCE_PASSAGE_POSITIVE'),
('RAW-M01',4400,4460,'Grey MPV moving from right foreground toward left distance','B_TO_A','car','SOURCE_PASSAGE_POSITIVE'),
('RAW-M02',4430,4480,'Light scooter with pale yellow helmet rider moving away behind grey MPV','B_TO_A','motorcycle','SOURCE_PASSAGE_POSITIVE'),
('RAW-M03',4475,4520,'Light scooter rider wearing patterned white shirt moving away','B_TO_A','motorcycle','SOURCE_PASSAGE_POSITIVE'),
('RAW-M04',4490,4550,'Motorcycle carrying dark driver and passenger in bright yellow top moving away','B_TO_A','motorcycle','SOURCE_PASSAGE_POSITIVE'),
('RAW-M05',4520,4580,'Light scooter black helmet dark top beige trousers rider moving away','B_TO_A','motorcycle','SOURCE_PASSAGE_POSITIVE'),
('RAW-M06',4595,4655,'Red motorcycle rider in brown-pink outerwear moving away','B_TO_A','motorcycle','SOURCE_PASSAGE_POSITIVE'),
('RAW-M07',4670,4745,'White small flatbed truck approaching camera in opposite lane','A_TO_B','truck','WINDOW_END_PARTIAL'),
('RAW-E01',8750,8830,'Light front scooter approaching from background then exiting right foreground','A_TO_B','motorcycle','SOURCE_PASSAGE_POSITIVE'),
('RAW-E02',8835,8880,'Blue-orange front scooter with dark-shirt rider approaching camera','A_TO_B','motorcycle','SOURCE_PASSAGE_POSITIVE'),
('RAW-E03',8900,8970,'Dark scooter rider grey top light trousers approaching camera','A_TO_B','motorcycle','SOURCE_PASSAGE_POSITIVE')]
rows=[dict(source_inventory_id=i,start_frame=s,end_frame=e,physical_description=d,direction=di,category=c,source_review_status=st,machine_matching_status='NOT_YET_MATCHED',blind_review=False,review_basis='Chronological raw-only contact sheets; reviewer knew project cases beforehand; not blind GT') for i,s,e,d,di,c,st in items]
with (r/'source_inventory.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(r/'source_inventory_raw_first.json').write_text(json.dumps(rows,indent=2)+'\n')
print(len(rows))
