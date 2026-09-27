"""Image entities for Health-e Pro Menu: one per upcoming recipe photo."""
from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_INCLUDE_RECIPE_DETAILS, DEFAULT_INCLUDE_RECIPE_DETAILS, DOMAIN
from .coordinator import HealtheProCoordinator
from .models import RecipeDetail


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HealtheProCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Photos come from the recipe details request, so they need that option.
    enabled = entry.options.get(CONF_INCLUDE_RECIPE_DETAILS, DEFAULT_INCLUDE_RECIPE_DETAILS)
    entities: dict[int, RecipePhotoImage] = {}

    @callback
    def _sync() -> None:
        """Match entities to the recipes with photos in the coming days."""
        data = coordinator.data
        wanted = data.upcoming_photos(dt_util.now().date()) if enabled and data else {}

        for rid, (recipe, menu_name) in wanted.items():
            if rid in entities:
                entities[rid].set_recipe(recipe, menu_name)
        new = {
            rid: RecipePhotoImage(hass, entry, recipe, menu_name)
            for rid, (recipe, menu_name) in wanted.items()
            if rid not in entities
        }
        entities.update(new)
        if new:
            async_add_entities(new.values())

        # Remove photos no longer upcoming, including ones registered by a
        # previous run, so entities don't pile up over the school year.
        wanted_ids = {_unique_id(entry, rid) for rid in wanted}
        registry = er.async_get(hass)
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if reg_entry.domain == "image" and reg_entry.unique_id not in wanted_ids:
                registry.async_remove(reg_entry.entity_id)
        for rid in [rid for rid in entities if rid not in wanted]:
            del entities[rid]

    _sync()
    if enabled:
        entry.async_on_unload(coordinator.async_add_listener(_sync))


def _unique_id(entry: ConfigEntry, recipe_id: int) -> str:
    return f"{entry.entry_id}_recipe_{recipe_id}"


class RecipePhotoImage(ImageEntity):
    """Photo of one recipe, as published by the district."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        recipe: RecipeDetail,
        menu_name: str,
    ) -> None:
        super().__init__(hass)
        cfg = entry.data
        self._attr_unique_id = _unique_id(entry, recipe.id)
        self._attr_name = menu_name.strip()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{cfg['org_id']}:{cfg['site_id']}:{cfg['menu_id']}")}
        )
        self._updated_at: str | None = None
        self.set_recipe(recipe, menu_name)

    @callback
    def set_recipe(self, recipe: RecipeDetail, menu_name: str) -> None:
        # The signed URL changes on every refresh and expires after 24 hours.
        # Take the fresh one, but keep the cached image unless the recipe
        # itself changed, so each photo downloads once.
        self._attr_image_url = recipe.image_url
        if recipe.updated_at != self._updated_at:
            self._updated_at = recipe.updated_at
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()
        self._attr_extra_state_attributes = {
            "recipe_id": recipe.id,
            # Exactly as the menu displays it, so templates can match `sections`.
            "menu_name": menu_name,
            "category": recipe.category,
        }
        if self.hass is not None:
            self.async_write_ha_state()
