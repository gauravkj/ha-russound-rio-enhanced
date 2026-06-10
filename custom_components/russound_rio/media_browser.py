"""Support for Russound media browsing."""

import logging

from aiorussound import CommandError, RussoundClient, Zone
from aiorussound.const import FeatureFlag
from aiorussound.util import is_feature_supported

from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_SYSTEM_FAVORITE_COUNT = 32


async def async_browse_media(
    hass: HomeAssistant,
    client: RussoundClient,
    media_content_id: str | None,
    media_content_type: str | None,
    zone: Zone,
) -> BrowseMedia:
    """Browse media."""
    if media_content_type == "system_favorites":
        favorites = await _load_system_favorites(client)
        return _system_favorites_payload(favorites)

    if media_content_type == "presets":
        return await _presets_payload(_find_presets_by_zone(client, zone))

    favorites = await _load_system_favorites(client)
    return await _root_payload(hass, _find_presets_by_zone(client, zone), favorites)


async def _root_payload(
    hass: HomeAssistant,
    presets_by_zone: dict[int, dict[int, str]],
    favorites: dict[int, str],
) -> BrowseMedia:
    """Return root payload for Russound RIO."""
    children: list[BrowseMedia] = []

    if favorites:
        children.append(
            BrowseMedia(
                title="System Favorites",
                media_class=MediaClass.DIRECTORY,
                media_content_id="",
                media_content_type="system_favorites",
                thumbnail="/api/brands/integration/russound_rio/logo.png",
                can_play=False,
                can_expand=True,
            )
        )

    if presets_by_zone:
        children.append(
            BrowseMedia(
                title="Presets",
                media_class=MediaClass.DIRECTORY,
                media_content_id="",
                media_content_type="presets",
                thumbnail="/api/brands/integration/russound_rio/logo.png",
                can_play=False,
                can_expand=True,
            )
        )

    return BrowseMedia(
        title="Russound",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="root",
        can_play=False,
        can_expand=True,
        children=children,
    )


async def _presets_payload(presets_by_zone: dict[int, dict[int, str]]) -> BrowseMedia:
    """Create payload to list presets."""
    children: list[BrowseMedia] = []
    for source_id, presets in presets_by_zone.items():
        for preset_id, preset_name in presets.items():
            children.append(
                BrowseMedia(
                    title=preset_name,
                    media_class=MediaClass.CHANNEL,
                    media_content_id=f"{source_id},{preset_id}",
                    media_content_type="preset",
                    can_play=True,
                    can_expand=False,
                )
            )

    return BrowseMedia(
        title="Presets",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="presets",
        can_play=False,
        can_expand=True,
        children=children,
    )


def _system_favorites_payload(favorites: dict[int, str]) -> BrowseMedia:
    """Create payload to list system favorites."""
    children: list[BrowseMedia] = [
        BrowseMedia(
            title=name,
            media_class=MediaClass.MUSIC,
            media_content_id=str(fav_num),
            media_content_type="system_favorite",
            can_play=True,
            can_expand=False,
        )
        for fav_num, name in favorites.items()
    ]

    return BrowseMedia(
        title="System Favorites",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="system_favorites",
        can_play=False,
        can_expand=True,
        children=children,
    )


async def _load_system_favorites(client: RussoundClient) -> dict[int, str]:
    """Return {slot_num: name} for all valid system favorites.

    Reads on demand during browse only — no caching, no polling.
    Returns empty dict gracefully on any error or unsupported firmware.
    """
    if not client.rio_version:
        return {}
    if not is_feature_supported(client.rio_version, FeatureFlag.SUPPORT_FAVORITES):
        return {}

    result: dict[int, str] = {}
    for i in range(1, _SYSTEM_FAVORITE_COUNT + 1):
        try:
            valid = await client.get_variable("System", f"favorite[{i}].valid")
            if valid != "TRUE":
                continue
            name = await client.get_variable("System", f"favorite[{i}].name")
            if name:
                result[i] = name
        except CommandError:
            _LOGGER.debug("System favorite slot %d not available, stopping scan", i)
            break
        except Exception:
            _LOGGER.debug("Unexpected error reading system favorite slot %d", i, exc_info=True)
            break

    return result


def _find_presets_by_zone(
    client: RussoundClient, zone: Zone
) -> dict[int, dict[int, str]]:
    """Returns a dict by {source_id: {preset_id: preset_name}}."""
    assert client.rio_version
    return {
        source_id: source.presets
        for source_id, source in client.sources.items()
        if source.presets
        and (
            not is_feature_supported(
                client.rio_version, FeatureFlag.SUPPORT_ZONE_SOURCE_EXCLUSION
            )
            or source_id in zone.enabled_sources
        )
    }
