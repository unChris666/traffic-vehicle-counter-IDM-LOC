"""Select Colab's authenticated kernel proxy or explicit Gradio share access."""
from urllib.parse import urlsplit

def options(mode,proxy_url):
    if mode=='gradio':return {'share':True,'server_port':7860},None
    if mode!='colab':raise ValueError('COLAB_ACCESS_INVALID')
    p=urlsplit(proxy_url or '')
    if p.scheme!='https' or not any((p.hostname or '').endswith(suffix) for suffix in ('.colab.googleusercontent.com','.colab.dev')) or p.username or p.password or p.query or p.fragment:
        raise ValueError('COLAB_PROXY_REQUIRED: jalankan cell server dari notebook Colab untuk mendapatkan proxyPort resmi.')
    root=proxy_url.rstrip('/')
    return {'share':False,'server_port':7860,'root_path':root},root
