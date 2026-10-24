"""Crossing evidence inspection cannot infer measured samples across a gap."""
def evidence_kind(event):
    if event.get('accepted_count_event') is not True:
        raise ValueError('Expected accepted event')
    return 'measured' if event['evidence']['measured_crossing'] is True else 'estimated'
