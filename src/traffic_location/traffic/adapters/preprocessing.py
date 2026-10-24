"""The frozen fresh worker supports RAW only; no silent enhancement fallback."""
def apply(image, settings):
    if settings != 'RAW':
        raise ValueError('Fresh worker supports RAW only; night filtering needs a separate validated profile')
    return image
