"""Audit-only eligibility view. The counting kernel remains the decision authority."""
def unresolved(native):
    return tuple(row for row in native['decisions'] if row.get('status') == 'pending')
