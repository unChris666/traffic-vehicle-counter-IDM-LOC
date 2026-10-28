import unittest,urllib.error
from unittest.mock import patch
from traffic_location.integration.colab_access import options
from traffic_location.integration.server_watchdog import probe
class AccessTests(unittest.TestCase):
    def test_native_proxy_disables_share_and_sets_root_and_fixed_port(self):
        args,url=options('colab','https://7860-fixture.colab.googleusercontent.com/')
        self.assertFalse(args['share']);self.assertEqual(args['root_path'],url);self.assertEqual(args['server_port'],7860)
    def test_modern_colab_dev_proxy_supported(self):
        args,url=options('colab','https://7860-fixture.us-east1-1.prod.colab.dev/')
        self.assertFalse(args['share']);self.assertEqual(args['root_path'],url)
    def test_external_or_credential_urls_rejected(self):
        for url in (None,'https://evil.invalid/','https://example.colab.googleusercontent.com@evil.invalid/','https://x.colab.googleusercontent.com/?token=secret','http://x.colab.googleusercontent.com/'):
            with self.assertRaises(ValueError):options('colab',url)
    def test_share_is_explicit(self):
        args,url=options('gradio',None);self.assertTrue(args['share']);self.assertIsNone(url)
    def test_gateway_502_is_preserved_in_evidence(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=urllib.error.HTTPError('https://fixture.gradio.live/config',502,'Bad Gateway',{},None)
            result=probe('https://fixture.gradio.live/config',public=True)
        self.assertEqual(result['code'],502);self.assertEqual(result['status'],'HTTP_ERROR')
