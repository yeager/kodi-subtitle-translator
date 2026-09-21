"""Offline regression tests; no Kodi installation or paid API calls required."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

for name in ('xbmc', 'xbmcgui', 'xbmcaddon', 'xbmcvfs'):
    sys.modules[name] = types.ModuleType(name)
xbmc = sys.modules['xbmc']
xbmc.LOGINFO, xbmc.LOGERROR, xbmc.LOGWARNING, xbmc.LOGDEBUG = range(4)
xbmc.Player = type('Player', (), {})
xbmc.Monitor = type('Monitor', (), {})
xbmc.log = Mock()
xbmc.sleep = Mock()
xbmc.getCondVisibility = Mock(return_value=False)
xbmc.getInfoLabel = Mock(return_value='')
sys.modules['xbmcgui'].NOTIFICATION_INFO = 'info'
sys.modules['xbmcgui'].NOTIFICATION_ERROR = 'error'
sys.modules['xbmcgui'].NOTIFICATION_WARNING = 'warning'
sys.modules['xbmcaddon'].Addon = Mock()
vfs = sys.modules['xbmcvfs']
vfs.exists = Mock(return_value=False)
vfs.translatePath = lambda path: path
vfs.File = Mock()
vfs.listdir = Mock()

from lib.subtitle_parser import SubtitleParser
from lib import translators
from lib.subtitle_extractor import SubtitleExtractor
from lib.mkv_streaming import MKVStreamingParser, BufferedReader
from lib.advanced_features import GlossaryManager, SubtitleLineBreaker, SubtitleTimingAdjuster, RateLimiter
import service


class ParserTests(unittest.TestCase):
    def test_bom_and_windows_newlines(self):
        content = '\ufeff1\r\n00:00:01,000 --> 00:00:02,000\r\nHello\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\nWorld\r\n'
        entries = SubtitleParser().parse(content)
        self.assertEqual([e['text'] for e in entries], ['Hello', 'World'])

    def test_long_dialogue_is_not_deleted_in_any_format(self):
        text = ' '.join('word%d' % i for i in range(60)) + ' ' + 'x' * 100
        parser = SubtitleParser()
        for fmt in ('srt', 'vtt', 'ass'):
            with self.subTest(fmt=fmt):
                output = parser.generate([{'index': 1, 'start': 1000, 'end': 8000, 'text': text}], fmt)
                self.assertEqual(parser.parse(output, fmt)[0]['text'], text)
        self.assertEqual(' '.join(SubtitleLineBreaker().break_lines(text).split()), text)

    def test_fixture_round_trip(self):
        parser = SubtitleParser()
        entries = parser.parse(Path('tests/fixtures/sample.srt').read_text())
        self.assertEqual(len(entries), 7)
        self.assertEqual(parser.parse(parser.generate(entries)), entries)


class TranslationTests(unittest.TestCase):
    def test_microsoft_sends_json_array(self):
        response = Mock()
        response.read.return_value = b'[{"translations":[{"text":"Hej"}]}]'
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with patch('urllib.request.urlopen', return_value=context) as request:
            result = translators.MicrosoftTranslator({'api_key': 'fixture'}).translate_batch(['Hello'], 'en', 'sv')
        self.assertEqual(result, ['Hej'])
        req = request.call_args.args[0]
        self.assertEqual(json.loads(req.data), [{'Text': 'Hello'}])
        self.assertEqual(req.get_header('Content-type'), 'application/json')

    def test_provider_failures_reach_fallback_layer(self):
        for cls in (translators.DeepLTranslator, translators.GoogleTranslator,
                    translators.MicrosoftTranslator, translators.LibreTranslateTranslator,
                    translators.MyMemoryTranslator, translators.OpenAITranslator,
                    translators.AnthropicTranslator):
            with self.subTest(provider=cls.__name__):
                translator = cls({'api_key': 'fixture'})
                translator._request = Mock(side_effect=OSError('offline'))
                with self.assertRaises(OSError):
                    translator.translate_batch(['Hello'], 'en', 'sv')

    def test_batch_validation_rejects_bad_alignment(self):
        for result in ([], ['Hej'], ['Hej', None], ['Hej', ''], 'Hej'):
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    service.SubtitleTranslatorPlayer._translate_batch(Mock(translate_batch=Mock(return_value=result)), ['Hello', 'World'], 'en', 'sv')
        self.assertEqual(service.SubtitleTranslatorPlayer._translate_batch(Mock(translate_batch=Mock(return_value=['Paris'])), ['Paris'], 'en', 'sv'), ['Paris'])

    def test_deepl_counts_escaped_json_and_preserves_order(self):
        translator = translators.DeepLTranslator({'api_key': 'fixture'})
        texts = [str(i) + '界' * 1000 for i in range(51)]
        batches = []
        def request(url, data, headers):
            self.assertLessEqual(len(json.dumps(data).encode()), translator.MAX_REQUEST_BYTES)
            self.assertLessEqual(len(data['text']), 50)
            batches.append(data['text'])
            return {'translations': [{'text': text} for text in data['text']]}
        translator._request = request
        self.assertEqual(translator.translate_batch(texts, 'en', 'sv'), texts)
        self.assertGreater(len(batches), 1)
        with self.assertRaises(ValueError):
            translator.translate_batch(['界' * 100000], 'en', 'sv')
        self.assertEqual(translator.translate_batch([], 'en', 'sv'), [])

    def test_unknown_service_does_not_silently_send_text_elsewhere(self):
        with self.assertRaises(ValueError):
            translators.get_translator('typo', {})

    def test_lingva_encodes_slash_in_subtitle(self):
        translator = translators.LingvaTranslator({})
        translator._request = Mock(return_value={'translation': 'och/eller'})
        translator.translate('and/or', 'en', 'sv')
        self.assertTrue(translator._request.call_args.args[0].endswith('/and%2For'))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.player = object.__new__(service.SubtitleTranslatorPlayer)
        self.player.current_file = '/videos/movie.mkv'
        self.player.translation_service = 'lingva'
        self.player.target_language = 'sv'
        self.player.subtitle_format = 'srt'
        self.player.save_alongside = True

    def test_native_extraction_does_not_require_ffmpeg(self):
        extractor = Mock(ffmpeg_path=None)
        extractor.extract.return_value = 'native subtitles'
        self.player._ensure_ffmpeg_available = Mock(side_effect=AssertionError('must not ask'))
        with patch.object(service, 'SubtitleExtractor', return_value=extractor), patch.object(service, 'get_setting', return_value=''):
            self.assertEqual(self.player._extract_subtitle_content({'index': 2}), 'native subtitles')
        extractor.extract.assert_called_once_with('/videos/movie.mkv', 2)

    def test_fallback_uses_its_configured_credentials(self):
        settings = {'deepl_api_key': 'fixture', 'deepl_formality': 'default'}
        with patch.object(service, 'get_setting', side_effect=lambda key: settings.get(key, '')), patch.object(service, 'get_setting_int', return_value=30), patch.object(service, 'get_addon_data', return_value='/unused'):
            self.assertEqual(self.player._get_fallback_config('deepl')['api_key'], 'fixture')
            self.assertEqual(self.player.translation_service, 'lingva')

    def test_external_discovery_requires_filename_boundary(self):
        with patch.object(vfs, 'listdir', return_value=([], ['movie.sv.srt', 'movie2.sv.srt', 'movie.en.forced.srt'])):
            subs = self.player._list_external_subtitles()
        self.assertEqual([s['filename'] for s in subs], ['movie.sv.srt', 'movie.en.forced.srt'])
        self.assertEqual(subs[-1]['language'], 'en')

    def test_existing_sidecar_is_never_overwritten(self):
        with patch.object(vfs, 'exists', return_value=True), patch.object(vfs, 'File') as file:
            self.player._copy_to_alongside('/cache/new.srt')
            file.assert_not_called()

    def test_rpc_subtitle_selection_uses_actual_stream_index(self):
        self.player.isPlaying = Mock(return_value=True)
        self.player.getPlayingFile = Mock(return_value=self.player.current_file)
        self.player.setSubtitles = Mock()
        self.player.showSubtitles = Mock()
        with patch.object(service, 'execute_jsonrpc', return_value={'subtitles': [{'index': 8, 'name': 'new.srt'}]}) as rpc:
            self.player.load_subtitle('/cache/new.srt')
            self.assertEqual(rpc.call_args.args[1]['subtitle'], 8)

    def test_changed_playback_does_not_receive_old_subtitle(self):
        self.player.isPlaying = Mock(return_value=True)
        self.player.getPlayingFile = Mock(return_value='/videos/next.mkv')
        self.player.setSubtitles = Mock()
        self.player.load_subtitle('/cache/old.srt')
        self.player.setSubtitles.assert_not_called()


class ExtractionTests(unittest.TestCase):
    def test_ffprobe_path_only_replaces_the_binary_name(self):
        extractor = object.__new__(SubtitleExtractor)
        extractor.ffmpeg_path = '/opt/ffmpeg-tools/bin/ffmpeg'
        extractor._is_mkv_file = Mock(return_value=False)
        extractor._resolve_path = Mock(return_value=('/videos/movie.mp4', False, None))
        extractor._test_ffmpeg = Mock(return_value=True)
        extractor._log = Mock()
        completed = Mock(returncode=0, stdout='{"streams": []}', stderr='')
        with patch('lib.subtitle_extractor.subprocess.run', return_value=completed) as run:
            self.assertEqual(extractor.get_subtitle_streams('/videos/movie.mp4'), [])
        self.assertEqual(run.call_args.args[0][0], '/opt/ffmpeg-tools/bin/ffprobe')

    def test_native_parser_method_is_callable_through_extractor(self):
        extractor = object.__new__(SubtitleExtractor)
        extractor._is_android = False
        extractor.ffmpeg_path = None
        extractor._mkv_parser = Mock(spec=MKVStreamingParser)
        extractor._mkv_parser.extract_subtitles.return_value = 'native subtitle content'
        self.assertEqual(extractor.extract('movie.mkv', 2), 'native subtitle content')
        extractor._mkv_parser.extract_subtitles.assert_called_once_with('movie.mkv', 2, 'srt')

    def test_temp_file_is_reserved_not_just_named(self):
        extractor = object.__new__(SubtitleExtractor)
        with tempfile.TemporaryDirectory() as directory, patch('lib.subtitle_extractor.get_kodi_temp_path', return_value=directory):
            one, two = extractor._make_temp_file(), extractor._make_temp_file()
            self.assertNotEqual(one, two)
            self.assertTrue(os.path.isfile(one))

    def test_failed_seek_and_oversized_read_stop_parser(self):
        reader = BufferedReader(Mock(seek=Mock(return_value=-1)))
        with self.assertRaises(OSError):
            reader.seek(100)
        with self.assertRaises(ValueError):
            reader.read(2**40)

    def test_video_cues_do_not_omit_subtitle_only_clusters(self):
        parser = MKVStreamingParser()
        parser._cues = [(0, 1, 100)]
        parser._scan_clusters_linear = Mock()
        parser._extract_from_clusters(Mock(), Mock(number=2), 10, 1000)
        parser._scan_clusters_linear.assert_called_once()


class AdvancedTests(unittest.TestCase):
    def test_glossary_backslashes_are_literal(self):
        glossary = object.__new__(GlossaryManager)
        glossary.glossary = {'en_sv': [{'original': 'path', 'translation': r'C:\new\1', 'case_sensitive': False}]}
        self.assertEqual(glossary.apply_glossary('PATH', 'en', 'sv'), r'C:\new\1')

    def test_timing_can_be_formatted_after_adjustment(self):
        entries = SubtitleTimingAdjuster().adjust_timing([{'index': 1, 'start': 0, 'end': 10, 'text': 'Hello'}])
        SubtitleParser().generate(entries)
        self.assertIsInstance(entries[0]['end'], int)

    def test_unbounded_rate_limit_period_does_not_crash(self):
        limiter = RateLimiter('/unused')
        self.assertTrue(limiter.can_request('deepl_free', 1))
        self.assertEqual(limiter.get_wait_time('deepl_free'), 0)


class PackageTests(unittest.TestCase):
    def test_package_excludes_cache_and_developer_files(self):
        import hashlib
        import zipfile
        from scripts.build_addon import build_addon
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'source'
            (root / 'lib/__pycache__').mkdir(parents=True)
            (root / 'lib/__pycache__/junk.pyc').write_bytes(b'cache')
            (root / 'lib/core.py').write_text('pass\n')
            (root / 'addon.xml').write_text('<addon id="service.fixture" version="1.0.0"/>')
            for name in ('service.py', 'LICENSE', '.env', 'test_debug.py'):
                (root / name).write_text('fixture')
            package = build_addon(root, Path(directory) / 'out')
            with zipfile.ZipFile(package) as archive:
                self.assertEqual(set(archive.namelist()), {'service.fixture/addon.xml', 'service.fixture/service.py', 'service.fixture/LICENSE', 'service.fixture/lib/core.py'})
                self.assertIsNone(archive.testzip())
            self.assertEqual(package.with_suffix('.zip.md5').read_text().strip(), hashlib.md5(package.read_bytes()).hexdigest())
            original = package.read_bytes()
            self.assertEqual(build_addon(root, package.parent).read_bytes(), original)


class RealMKVTests(unittest.TestCase):
    def test_ffmpeg_generated_mkv_extracts_without_ffmpeg_fallback(self):
        import shutil
        import subprocess
        if not shutil.which('ffmpeg'):
            self.skipTest('FFmpeg is needed to generate the test fixture')
        class File:
            def __init__(self, path, mode='r'):
                self.file = open(path, 'rb')
            def readBytes(self, size):
                return self.file.read(size)
            def seek(self, offset, whence):
                return self.file.seek(offset, whence)
            def close(self):
                self.file.close()
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'fixture.mkv')
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=size=16x16:rate=1:duration=38', '-i', 'tests/fixtures/sample.srt', '-map', '0', '-map', '1', '-c:v', 'ffv1', '-c:s', 'srt', path], check=True, capture_output=True, timeout=30)
            extractor = object.__new__(SubtitleExtractor)
            extractor.ffmpeg_path = None
            extractor._is_android = False
            extractor._mkv_parser = MKVStreamingParser()
            with patch.object(vfs, 'File', File):
                result = extractor.extract(path)
            parser = SubtitleParser()
            self.assertEqual(parser.parse(result), parser.parse(Path('tests/fixtures/sample.srt').read_text()))

class DiagnosticsTests(unittest.TestCase):
    def test_credentials_removed_at_log_sink(self):
        from lib.safe_logging import log, redact
        log('smb://alice:fixture-password@nas/movie.mkv\x00 https://example.test/?key=fixture-key&lang=sv')
        output = xbmc.log.call_args.args[0]
        self.assertNotIn('alice', output)
        self.assertNotIn('fixture-password', output)
        self.assertNotIn('fixture-key', output)
        self.assertNotIn('\x00', output)
        self.assertIn('&lang=sv', output)
        self.assertEqual(redact({'api_key': 'fixture', 'details': [{'password': 'fixture'}]}), {'api_key': '[redacted]', 'details': [{'password': '[redacted]'}]})


class SettingsAndCacheTests(unittest.TestCase):
    def test_input_encoding_honors_bom_and_selected_encoding(self):
        with patch.object(service, 'get_setting', return_value='utf-8'):
            self.assertEqual(service.SubtitleTranslatorPlayer._decode_subtitle('Hej åäö'.encode('utf-16')), 'Hej åäö')
        with patch.object(service, 'get_setting', return_value='cp1252'):
            self.assertEqual(service.SubtitleTranslatorPlayer._decode_subtitle('“Hej”'.encode('cp1252')), '“Hej”')

    def test_disabled_cache_creates_only_temporary_subtitles(self):
        player = object.__new__(service.SubtitleTranslatorPlayer)
        player.cache_translations = False
        player.subtitle_format = 'srt'
        player.save_alongside = False
        player._temporary_subtitles = []
        with tempfile.TemporaryDirectory() as directory, patch.object(service, 'get_addon_data', return_value=directory):
            path = player.save_subtitle('Hej', 'unused')
            self.assertEqual(Path(path).read_text(), 'Hej')
            self.assertEqual(len(list(Path(directory).iterdir())), 1)
            player.onPlayBackStopped()
            self.assertFalse(Path(path).exists())

    def test_cache_identity_includes_source_and_provider_settings(self):
        player = object.__new__(service.SubtitleTranslatorPlayer)
        player.source_language, player.target_language = 'en', 'sv'
        player.translation_service, player.subtitle_format = 'deepl', 'srt'
        player.get_service_config = Mock(return_value={'formality': 'less'})
        first = player.get_cache_key_external('/movie.srt')
        player.source_language = 'de'
        self.assertNotEqual(first, player.get_cache_key_external('/movie.srt'))
        player.source_language = 'en'
        player.get_service_config.return_value = {'formality': 'more'}
        self.assertNotEqual(first, player.get_cache_key_external('/movie.srt'))

    def test_profiles_do_not_mutate_shared_defaults(self):
        from lib.advanced_features import TranslationProfiles
        profiles = TranslationProfiles('/unused')
        profile = profiles.get_profile('anime')
        profile['preserve_terms'].append('fixture')
        self.assertNotIn('fixture', profiles.get_profile('anime')['preserve_terms'])
        player = object.__new__(service.SubtitleTranslatorPlayer)
        player._get_profile = Mock(return_value={'max_line_length': 35, 'censor_profanity': True})
        player.target_language = 'en'
        parser = SubtitleParser()
        with patch.object(service, 'get_addon_data', return_value='/unused'):
            entries = player._apply_profile([{'text': 'damn this test'}], parser)
        self.assertEqual(entries[0]['text'], '*** this test')
        self.assertEqual(parser.MAX_CHARS_PER_LINE, 35)

    def test_progress_and_notifications_are_independent(self):
        from lib.progress_dialog import TranslationProgress
        progress = TranslationProgress(show_dialog=False, show_notification=False)
        progress.start()
        progress.complete()
        self.assertIsNone(progress.dialog)

    def test_retry_only_transient_http_errors(self):
        import urllib.error
        translator = translators.BaseTranslator({'max_retries': 2, 'retry_delay': 0})
        for status, count in ((503, 3), (401, 1)):
            error = urllib.error.HTTPError('https://example.test', status, 'fixture', {}, None)
            with patch('urllib.request.urlopen', side_effect=error) as request:
                with self.assertRaises(urllib.error.HTTPError):
                    translator._request('https://example.test', {})
                self.assertEqual(request.call_count, count)

    def test_request_rate_limit_is_applied(self):
        translator = translators.BaseTranslator({'rate_limit': 30})
        translator._last_request = 10
        response = Mock()
        response.read.return_value = b'{}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('lib.translators.time.monotonic', return_value=11), patch('lib.translators.time.sleep') as sleep, patch('urllib.request.urlopen', return_value=response):
            translator._request('https://example.test', {})
            sleep.assert_called_once_with(1)

    def test_default_profile_preserves_explicit_deepl_formality(self):
        translator = translators.DeepLTranslator({'formality': 'more', 'profile': {'formality': 'default'}})
        self.assertEqual(translator.formality, 'more')

    def test_android_download_rejects_checksum_mismatch(self):
        from lib.subtitle_extractor import download_ffmpeg_android
        with tempfile.TemporaryDirectory() as directory:
            response = io.BytesIO(b'not the reviewed release binary')
            with patch('platform.machine', return_value='aarch64'), patch('lib.subtitle_extractor.xbmcaddon.Addon') as addon, patch('urllib.request.urlopen', return_value=response):
                addon.return_value.getAddonInfo.return_value = directory
                self.assertIsNone(download_ffmpeg_android())
            self.assertEqual(list((Path(directory) / 'bin').iterdir()), [])

    def test_bitmap_track_keeps_its_stream_index(self):
        def element(identifier, data):
            tag = identifier.to_bytes((identifier.bit_length() + 7) // 8, 'big')
            if len(data) >= 127:
                raise AssertionError('Fixture element too big')
            return tag + bytes([0x80 | len(data)]) + data
        def track(number, codec):
            return element(0xAE, element(0xD7, bytes([number])) + element(0x83, b'\x11') + element(0x86, codec))
        body = track(1, b'S_HDMV/PGS') + track(2, b'S_TEXT/UTF8')
        file = io.BytesIO(body)
        file.readBytes = file.read
        parser = MKVStreamingParser()
        parser._parse_tracks(BufferedReader(file), len(body))
        self.assertEqual([t.number for t in parser._tracks], [1, 2])
        self.assertEqual([t.global_index for t in parser._tracks], [0, 1])
        self.assertEqual(parser._tracks[1].format, 'srt')


class PlaybackFlowTests(unittest.TestCase):
    def test_failed_provider_uses_fallback_in_both_translation_flows(self):
        from contextlib import ExitStack
        source = '1\n00:00:01,000 --> 00:00:02,000\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld\n'
        for external in (True, False):
            with self.subTest(external=external), ExitStack() as stack:
                player = object.__new__(service.SubtitleTranslatorPlayer)
                for key, value in {'current_file': '/movie.mkv', 'save_alongside': False, 'source_language': 'en', 'target_language': 'sv', 'batch_size': 20, 'show_notification': False, 'show_progress_dialog': False, 'translation_service': 'deepl', 'subtitle_format': 'srt'}.items():
                    setattr(player, key, value)
                player.isPlaying = Mock(return_value=False)
                player.get_cache_key = Mock(return_value='fixture')
                player.get_cache_key_external = Mock(return_value='fixture')
                player.get_cached_subtitle = Mock(return_value=None)
                player.read_external_subtitle = Mock(return_value=source)
                player._extract_subtitle_content = Mock(return_value=source)
                player._auto_fallback_if_needed = Mock(return_value='deepl')
                primary = Mock(translate_batch=Mock(side_effect=OSError('offline')))
                fallback = Mock(translate_batch=Mock(return_value=['Hej', 'Världen']))
                player._prepare_translator = Mock(side_effect=lambda name: primary if name == 'deepl' else fallback)
                player._apply_profile = lambda entries, parser: entries
                player._make_disclaimer = Mock(return_value=[])
                player.save_subtitle = Mock(return_value='/translated.srt')
                player.load_subtitle = Mock()
                progress = Mock(dialog=None, is_cancelled=Mock(return_value=False))
                stack.enter_context(patch.object(service, 'TranslationProgress', return_value=progress))
                stack.enter_context(patch.object(service, 'SubtitleParser', SubtitleParser))
                stack.enter_context(patch.object(service, 'get_debug_logger', return_value=Mock()))
                stack.enter_context(patch.object(service, 'get_error_reporter', return_value=Mock()))
                stack.enter_context(patch.object(service, 'get_string', return_value='status'))
                stack.enter_context(patch.object(service, 'get_setting_bool', return_value=True))
                stack.enter_context(patch.object(service, 'get_setting', return_value='mymemory'))
                stack.enter_context(patch.object(service, 'get_addon_data', return_value='/unused'))
                stack.enter_context(patch('lib.advanced_features.SubtitleStatistics'))
                if external:
                    player.translate_external_subtitle('/movie.srt')
                else:
                    player.translate_subtitle({'index': 0})
                player.save_subtitle.assert_called_once()
                result = SubtitleParser().parse(player.save_subtitle.call_args.args[0])
                self.assertEqual([entry['text'] for entry in result], ['Hej', 'Världen'])
                player.load_subtitle.assert_called_once_with('/translated.srt')
                self.assertTrue(progress.complete.call_args.args[0])
                self.assertFalse(player.translation_in_progress)


class FinalReviewTests(unittest.TestCase):
    def test_incomplete_llm_output_is_not_accepted(self):
        cases = [(translators.OpenAITranslator, {'choices': [{'finish_reason': 'length', 'message': {'content': 'partial'}}]}),
                 (translators.AnthropicTranslator, {'stop_reason': 'max_tokens', 'content': [{'text': 'partial'}]})]
        for cls, response in cases:
            translator = cls({'api_key': 'fixture'})
            translator._request = Mock(return_value=response)
            with self.assertRaises(ValueError):
                translator.translate_batch(['Hello'], 'en', 'sv')

    def test_retired_claude_defaults_migrate_but_custom_models_remain(self):
        self.assertEqual(translators.AnthropicTranslator({'model': 'claude-3-haiku-20240307'}).model, 'claude-haiku-4-5-20251001')
        self.assertEqual(translators.AnthropicTranslator({'model': 'custom-fixture'}).model, 'custom-fixture')

    def test_google_entities_are_decoded(self):
        translator = translators.GoogleTranslator({'api_key': 'fixture'})
        translator._request = Mock(return_value={'data': {'translations': [{'translatedText': 'du &amp; jag'}]}})
        self.assertEqual(translator.translate_batch(['you and me'], 'en', 'sv'), ['du & jag'])

    def test_mkv_codec_metadata_excludes_bitmap_before_translation(self):
        player = object.__new__(service.SubtitleTranslatorPlayer)
        player.current_file, player.source_language = '/movie.mkv', 'en'
        native = [{'index': 0, 'codec': 'hdmv_pgs_subtitle', 'language': 'en'}, {'index': 1, 'codec': 'subrip', 'language': 'en'}]
        with patch.object(service, 'execute_jsonrpc', return_value={'subtitles': [{'index': 0}, {'index': 1}]}), patch('lib.mkv_streaming.MKVStreamingParser') as parser:
            parser.return_value.get_subtitle_streams.return_value = native
            self.assertEqual(player.find_source_subtitle(player.get_available_subtitles())['index'], 1)

    def test_disabling_auto_translation_prevents_playback_work(self):
        player = object.__new__(service.SubtitleTranslatorPlayer)
        player.enabled, player.auto_translate = True, False
        player.check_and_translate_subtitles = Mock()
        player.onAVStarted()
        player.check_and_translate_subtitles.assert_not_called()


if __name__ == '__main__':
    unittest.main()
