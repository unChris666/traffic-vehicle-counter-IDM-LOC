"""Immutable result exports; no counting/resolver imports."""
def aggregate_csv(batch):
    import csv, io
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(('category', 'direction', 'measured', 'estimated', 'execution_status', 'videos_completed', 'videos_expected', 'counts_scope'))
    for category, directions in sorted(batch['pivot'].items()):
        for direction, counts in sorted(directions.items()):
            writer.writerow((category, direction, counts['measured'], counts['estimated'], batch['execution_status'], batch['videos_completed'], batch['videos_expected'], 'COMPLETE_RECORDED_SAMPLES' if batch['videos_completed'] == batch['videos_expected'] else 'OBSERVED_SUBTOTAL_ONLY'))
    return stream.getvalue()


def batch_files(batch):
    """JSON/CSV/HTML share one immutable selected snapshot; never sum branches."""
    from html import escape
    from ..contracts.source import FrozenDocument
    if not isinstance(batch, FrozenDocument):
        raise TypeError('Frozen finalized batch required')
    value = batch.object()
    csv_text = aggregate_csv(value)
    rows = []
    for category, directions in sorted(value['pivot'].items()):
        for direction, counts in sorted(directions.items()):
            rows.append('<tr>' + ''.join('<td>' + escape(str(v)) + '</td>' for v in
                (category, direction, counts['measured'], counts['estimated'])) + '</tr>')
    html = ('<!doctype html><html lang="id"><meta charset="utf-8"><title>Traffic review</title>'
        '<body><h1>Traffic — skenario eksperimen</h1>'
        '<p>Status: ' + escape(value['execution_status']) + '; quality: ' + escape(value['result_quality']) + '</p>'
        '<p>Video selesai: ' + str(value['videos_completed']) + '/8. '
        'Pending ' + str(value['pending']) + '; invalid ' + str(value['invalid']) + ' tidak masuk accepted.</p>'
        '<p>Total kendaraan lengkap: ' + escape('UNKNOWN' if value['complete_vehicle_total'] is None else str(value['complete_vehicle_total'])) + '.</p>'
        '<table><thead><tr><th>Kategori</th><th>Arah</th><th>Measured</th><th>Estimated</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table>'
        '<p>Passage pada sampel rekaman; bukan kendaraan unik atau traffic harian.</p></body></html>')
    return {'combined.json': value, 'combined.csv': csv_text.encode(), 'review.html': html.encode()}
