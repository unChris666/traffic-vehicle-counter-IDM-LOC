"""Publish verified Phase 8 browser copies as GitHub Release assets.

Requires `gh` authenticated externally; never stores credentials. Creates a new
release as a draft, verifies all upload sizes/digests, then publishes. An existing
tag/release is deliberately refused rather than overwritten. No model execution.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import subprocess


def gh(*args: str, parse: bool = False):
    value = subprocess.check_output(['gh', *args], text=True)
    return json.loads(value) if parse else value.strip()


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def verify_remote_asset(repo: str, asset: dict, expected_sha: str, expected_size: int) -> str:
    if asset['size'] != expected_size or asset['state'] != 'uploaded':
        raise ValueError('Release asset upload incomplete')
    digest = asset.get('digest')
    if digest is not None:
        if digest != 'sha256:' + expected_sha:
            raise ValueError('GitHub server digest mismatch')
        return 'GITHUB_SERVER_SHA256'
    # Older API responses may omit digest. Verify the actual returned bytes;
    # matching size alone is insufficient. No response bytes enter tool output.
    process = subprocess.Popen(['gh', 'api', f"repos/{repo}/releases/assets/{asset['id']}",
        '-H', 'Accept: application/octet-stream'], stdout=subprocess.PIPE)
    downloaded, value = 0, hashlib.sha256()
    assert process.stdout is not None
    for block in iter(lambda: process.stdout.read(1024 * 1024), b''):
        downloaded += len(block)
        value.update(block)
    if process.wait() != 0 or downloaded != expected_size or value.hexdigest() != expected_sha:
        raise ValueError('Release download SHA/size verification failed')
    return 'ACTUAL_GITHUB_ASSET_DOWNLOAD_SHA256'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--notes-file', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--video-root', type=Path)
    parser.add_argument('--publish', action='store_true', help='Actually upload; default validates locally only')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.source_commit):
        parser.error('--source-commit requires a full 40-character Git commit')
    manifest = json.loads(args.manifest.read_text())
    assets = manifest['assets']
    expected_ids = {f'{day}_{period}' for day in ('weekday', 'weekend') for period in ('pagi', 'siang', 'sore', 'malam')}
    if len(assets) != 8 or {a['video_id'] for a in assets} != expected_ids:
        raise ValueError('Exactly eight complete TGDI delivery assets required')
    checked = []
    for asset in assets:
        name = asset['filename']
        if Path(name).name != name or not name.endswith('.mp4'):
            raise ValueError('Invalid release asset filename')
        path = args.video_root / name if args.video_root else Path(asset['path'])
        if path.stat().st_size != asset['size_bytes'] or sha(path) != asset['sha256']:
            raise ValueError(f'Unverified video: {name}')
        checked.append((asset, path))
    if not args.notes_file.is_file():
        raise FileNotFoundError(args.notes_file)
    if not args.publish:
        print(json.dumps({'status': 'LOCAL_VALIDATION_PASS_NO_UPLOAD', 'verified_videos': 8, 'source_commit': args.source_commit}))
        return
    remote = gh('api', f'repos/{args.repo}/commits/{args.source_commit}', parse=True)
    if remote['sha'] != args.source_commit:
        raise ValueError('Source commit is not available on GitHub')
    releases = gh('api', f'repos/{args.repo}/releases?per_page=100', parse=True)
    if any(r['tag_name'] == args.tag for r in releases):
        raise ValueError('Release already exists; inspect it instead of overwriting')
    existing_tag = subprocess.run(['gh', 'api', f'repos/{args.repo}/git/ref/tags/{args.tag}'], capture_output=True, text=True)
    if existing_tag.returncode == 0:
        raise ValueError('Tag already exists; do not reuse a previous source binding')
    if '404' not in existing_tag.stderr:
        raise RuntimeError('Could not verify that the release tag is unused')
    checksums = args.manifest.parent / 'SHA256SUMS'
    checksums.write_text(''.join(f"{a['sha256']}  {a['filename']}\n" for a, _ in checked))
    gh('release', 'create', args.tag, '--repo', args.repo, '--draft', '--target', args.source_commit,
       '--title', 'Phase 8 — TGDI annotated video review v1', '--notes-file', str(args.notes_file))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(gh, 'release', 'upload', args.tag, str(path), '--repo', args.repo): asset
                   for asset, path in checked}
        for future in as_completed(futures):
            future.result()
            print(f"Uploaded {futures[future]['filename']}", flush=True)
    gh('release', 'upload', args.tag, str(args.manifest), str(checksums), '--repo', args.repo)
    release = gh('api', f'repos/{args.repo}/releases/tags/{args.tag}', parse=True)
    uploaded = {a['name']: a for a in release['assets']}
    receipt_assets = []
    for asset, path in checked:
        remote_asset = uploaded[asset['filename']]
        digest = remote_asset.get('digest')
        verification_method = verify_remote_asset(args.repo, remote_asset, asset['sha256'], asset['size_bytes'])
        receipt_assets.append({'video_id': asset['video_id'], 'filename': asset['filename'],
            'id': remote_asset['id'], 'name': asset['filename'], 'size': remote_asset['size'],
            'asset_id': remote_asset['id'], 'size_bytes': remote_asset['size'],
            'uploaded_file_sha256': asset['sha256'], 'verified_remote_sha256': asset['sha256'],
            'verification_method': verification_method,
            'github_digest': digest, 'digest': digest,
            'browser_download_url': remote_asset['browser_download_url'], 'state': remote_asset['state']})
    supplemental = []
    for extra in (args.manifest, checksums):
        remote_asset = uploaded[extra.name]
        method = verify_remote_asset(args.repo, remote_asset, sha(extra), extra.stat().st_size)
        supplemental.append({'id': remote_asset['id'], 'name': extra.name, 'size': remote_asset['size'],
            'digest': remote_asset.get('digest'), 'uploaded_file_sha256': sha(extra), 'verified_remote_sha256': sha(extra),
            'verification_method': method, 'browser_download_url': remote_asset['browser_download_url']})
    gh('release', 'edit', args.tag, '--repo', args.repo, '--draft=false', '--latest')
    release = gh('api', f'repos/{args.repo}/releases/tags/{args.tag}', parse=True)
    if release['draft'] or release['target_commitish'] != args.source_commit:
        raise ValueError('Published release/source binding differs')
    resolved = gh('api', f'repos/{args.repo}/commits/{args.tag}', parse=True)['sha']
    if resolved != args.source_commit:
        raise ValueError('Published tag resolves to a different source commit')
    receipt = {'claim_type': 'ACTUAL_GITHUB_RELEASE_PUBLICATION_NOT_MODEL_EVALUATION',
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'repository': args.repo,
        'release_id': release['id'], 'tag_name': args.tag, 'html_url': release['html_url'],
        'source_commit': args.source_commit, 'target_commitish': release['target_commitish'],
        'resolved_tag_commit_sha': resolved,
        'release': {key: release[key] for key in ('id', 'tag_name', 'target_commitish', 'html_url', 'draft', 'prerelease')},
        'draft': release['draft'], 'published_at': release['published_at'],
        'delivery_manifest_sha256': sha(args.manifest), 'video_asset_count': len(receipt_assets),
        'assets': receipt_assets, 'supplemental_assets': supplemental, 'large_videos_committed_to_git': False,
        'new_detector_tracker_reid_or_counting_execution': False}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': 'PUBLISHED', 'url': release['html_url'], 'verified_videos': 8}))


if __name__ == '__main__':
    main()
