# TOR3 technical regression annotation

This is an actual GPU-free replay/annotation check on the retained TOR3-MALAM
raw cache. It is **not** a TGDI dataset result or a completed eight-video batch.
No detector, tracker or ReID inference was rerun.

The full temporary MP4 `/tmp/phase8-tor3-fullscope-annotated.mp4` contains 9,590
frames at native 1280×720. The writer output was decoded completely, then a
separate decode checked the first frame, frame898, middle frame4795 and last
frame9589. `annotation_report.json` records the actual hash, runtime, resource
usage and presentation timing limits. The MP4 is external temporary output;
it is not retained in GitHub and does not preserve audio or authoritative PTS.

The retained native PNG at frame898 was opened for an overlay check. It shows
the yellow finite line, blue A outline, orange B outline, ID202 labelled
`motorcycle accepted`, ID185 labelled `person track`, and ID198 labelled
`car track`. The vehicle anchors use measured raw detector-box bottom-centers;
the person box does not supply a vehicle crossing anchor. The source pixel hash
for frame898 exactly matches its actual retained detector-input hash.

These checks establish file/annotation/source linkage. They do not establish
physical identity, category correctness, missed-passage rate or counting accuracy.
The full-scope machine snapshot has seven accepted motorcycle candidates and
49 pending candidates; these are different passages from the old Phase7
five-window reviewed subtotal. A new full-scope physical audit remains pending.
