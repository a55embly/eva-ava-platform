'''Idempotently restrict the pinned Hermes Telegram gateway configuration.'''

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml


class UniqueKeyLoader(yaml.SafeLoader):
    '''Safe YAML loader that rejects duplicate mapping keys.'''


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f'duplicate YAML key: {key}')
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_config(path: Path) -> dict[str, Any]:
    parsed = yaml.load(path.read_text(encoding='utf-8'), Loader=UniqueKeyLoader)
    if not isinstance(parsed, dict):
        raise ValueError('Hermes config must be a YAML mapping')
    return parsed


def validate_config(config: dict[str, Any]) -> None:
    plugins = config.get('plugins')
    enabled = plugins.get('enabled') if isinstance(plugins, dict) else None
    if not isinstance(enabled, list) or 'aitegrate-auth-bridge' not in enabled:
        raise ValueError('Aitegrate bridge plugin is not enabled')
    platform_toolsets = config.get('platform_toolsets')
    telegram = (
        platform_toolsets.get('telegram') if isinstance(platform_toolsets, dict) else None
    )
    if telegram != ['aitegrate']:
        raise ValueError('Telegram must expose exactly the aitegrate toolset')


def configure(path: Path, *, check_only: bool = False) -> bool:
    config = load_config(path)
    if check_only:
        validate_config(config)
        return False

    plugins = config.setdefault('plugins', {})
    if not isinstance(plugins, dict):
        raise ValueError('plugins config must be a mapping')
    enabled = plugins.setdefault('enabled', [])
    if not isinstance(enabled, list):
        raise ValueError('plugins.enabled must be a list')
    if 'aitegrate-auth-bridge' not in enabled:
        enabled.append('aitegrate-auth-bridge')
    plugins['enabled'] = sorted({str(value) for value in enabled})

    platform_toolsets = config.setdefault('platform_toolsets', {})
    if not isinstance(platform_toolsets, dict):
        raise ValueError('platform_toolsets config must be a mapping')
    platform_toolsets['telegram'] = ['aitegrate']
    validate_config(config)

    rendered = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
    if rendered == path.read_text(encoding='utf-8'):
        return False
    backup = path.with_suffix(path.suffix + '.aitegrate-backup')
    shutil.copy2(path, backup)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(rendered)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    validate_config(load_config(path))
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('config', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    configure(args.config, check_only=args.check)


if __name__ == '__main__':
    main()
