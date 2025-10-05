"""Helper to check the configuration file."""

from __future__ import annotations

from collections import OrderedDict
import logging
import os
from pathlib import Path
from typing import NamedTuple, Self

from annotatedyaml import loader as yaml_loader
import voluptuous as vol

from homeassistant import loader
from homeassistant.config import (  # type: ignore[attr-defined]
    CONF_PACKAGES,
    YAML_CONFIG_FILE,
    config_per_platform,
    extract_domain_configs,
    format_homeassistant_error,
    format_schema_error,
    load_yaml_config_file,
    merge_packages_config,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.core_config import CORE_CONFIG_SCHEMA
from homeassistant.exceptions import HomeAssistantError
from homeassistant.requirements import (
    RequirementsNotFound,
    async_clear_install_history,
    async_get_integration_with_requirements,
)

from . import config_validation as cv
from .typing import ConfigType


class CheckConfigError(NamedTuple):
    """Configuration check error."""

    message: str
    domain: str | None
    config: ConfigType | None


class HomeAssistantConfig(OrderedDict):
    """Configuration result with errors attribute."""

    def __init__(self) -> None:
        """Initialize HA config."""
        super().__init__()
        self.errors: list[CheckConfigError] = []
        self.warnings: list[CheckConfigError] = []

    def add_error(
        self,
        message: str,
        domain: str | None = None,
        config: ConfigType | None = None,
    ) -> Self:
        """Add an error."""
        self.errors.append(CheckConfigError(str(message), domain, config))
        return self

    @property
    def error_str(self) -> str:
        """Concatenate all errors to a string."""
        return "\n".join([err.message for err in self.errors])

    def add_warning(
        self,
        message: str,
        domain: str | None = None,
        config: ConfigType | None = None,
    ) -> Self:
        """Add a warning."""
        self.warnings.append(CheckConfigError(str(message), domain, config))
        return self

    @property
    def warning_str(self) -> str:
        """Concatenate all warnings to a string."""
        return "\n".join([err.message for err in self.warnings])


async def async_check_ha_config_file(hass: HomeAssistant) -> HomeAssistantConfig:
    """Load and validate Home Assistant configuration file."""
    result = HomeAssistantConfig()
    async_clear_install_history(hass)

    # ---------------- Helper Functions ---------------- #

    def pack_error(package: str, component: str | None, config: ConfigType, message: str) -> None:
        """Handle errors from packages."""
        msg = f"Setup of package '{package}' failed: {message}"
        domain = f"homeassistant.packages.{package}{'.' + component if component else ''}"
        pack_config = core_config.get(CONF_PACKAGES, {}).get(package, config)
        result.add_warning(msg, domain, pack_config)

    def comp_error(ex: vol.Invalid | HomeAssistantError, domain: str, component_config: ConfigType, config_to_attach: ConfigType) -> None:
        """Handle errors from components."""
        if isinstance(ex, vol.Invalid):
            msg = format_schema_error(hass, ex, domain, component_config)
        else:
            msg = format_homeassistant_error(hass, ex, domain, component_config)

        if domain in frontend_dependencies:
            result.add_error(msg, domain, config_to_attach)
        else:
            result.add_warning(msg, domain, config_to_attach)

    async def get_integration(domain: str) -> loader.Integration | None:
        """Fetch an integration safely."""
        try:
            return await async_get_integration_with_requirements(hass, domain)
        except (loader.IntegrationNotFound, RequirementsNotFound) as ex:
            if not hass.config.recovery_mode and not hass.config.safe_mode:
                result.add_warning(f"Integration error: {domain} - {ex}")
            return None

    async def validate_component(domain: str, integration: loader.Integration) -> None:
        """Validate component and platform configs."""
        try:
            component = await integration.async_get_component()
        except ImportError as ex:
            result.add_warning(f"Component error: {domain} - {ex}")
            return

        # Validate config platform if exists
        config_validator = None
        if integration.platforms_exists(("config",)):
            try:
                config_validator = await integration.async_get_platform("config")
            except ImportError as err:
                if err.name != f"{integration.pkg_path}.config":
                    result.add_error(f"Error importing config platform {domain}: {err}")
                    return

        if config_validator and hasattr(config_validator, "async_validate_config"):
            try:
                validated = await config_validator.async_validate_config(hass, config)
                result[domain] = validated[domain]
                return
            except (vol.Invalid, HomeAssistantError) as ex:
                comp_error(ex, domain, config, config[domain])
                return
            except Exception as err:
                logging.getLogger(__name__).exception("Unexpected error validating config")
                result.add_error(f"Unexpected error calling config validator: {err}", domain, config.get(domain))
                return

        # Fallback to component-level validation
        config_schema = getattr(component, "CONFIG_SCHEMA", None)
        if config_schema:
            try:
                validated = await cv.async_validate(hass, config_schema, config)
                if domain in validated:
                    result[domain] = validated[domain]
            except vol.Invalid as ex:
                comp_error(ex, domain, config, config[domain])

        # Validate per-platform schema
        component_platform_schema = getattr(component, "PLATFORM_SCHEMA_BASE", getattr(component, "PLATFORM_SCHEMA", None))
        if component_platform_schema:
            platforms = []
            for p_name, p_config in config_per_platform(config, domain):
                try:
                    p_validated = await cv.async_validate(hass, component_platform_schema, p_config)
                except vol.Invalid as ex:
                    comp_error(ex, domain, p_config, p_config)
                    continue

                if p_name is None:
                    platforms.append(p_validated)
                    continue

                try:
                    p_integration = await async_get_integration_with_requirements(hass, p_name)
                    platform = await p_integration.async_get_platform(domain)
                except (loader.IntegrationNotFound, RequirementsNotFound, ImportError) as ex:
                    if not hass.config.recovery_mode and not hass.config.safe_mode:
                        result.add_warning(f"Platform error '{domain}' from integration '{p_name}' - {ex}")
                    continue

                platform_schema = getattr(platform, "PLATFORM_SCHEMA", None)
                if platform_schema:
                    try:
                        p_validated = platform_schema(p_validated)
                    except vol.Invalid as ex:
                        comp_error(ex, f"{domain}.{p_name}", p_config, p_config)
                        continue
                platforms.append(p_validated)

            for filter_comp in extract_domain_configs(config, domain):
                del config[filter_comp]
            result[domain] = platforms

    # ---------------- Load Configuration ---------------- #

    config_path = hass.config.path(YAML_CONFIG_FILE)
    try:
        if not await hass.async_add_executor_job(os.path.isfile, config_path):
            return result.add_error("File configuration.yaml not found.")
        config = await hass.async_add_executor_job(load_yaml_config_file, config_path, yaml_loader.Secrets(Path(hass.config.config_dir)))
    except FileNotFoundError:
        return result.add_error(f"File not found: {config_path}")
    except HomeAssistantError as err:
        return result.add_error(f"Error loading {config_path}: {err}")

    # ---------------- Core Config Validation ---------------- #
    core_config = config.pop(HOMEASSISTANT_DOMAIN, {})
    try:
        core_config = CORE_CONFIG_SCHEMA(core_config)
        result[HOMEASSISTANT_DOMAIN] = core_config
        await merge_packages_config(hass, config, core_config.get(CONF_PACKAGES, {}), pack_error)
    except vol.Invalid as err:
        result.add_error(format_schema_error(hass, err, HOMEASSISTANT_DOMAIN, core_config), HOMEASSISTANT_DOMAIN, core_config)
        core_config = {}
    core_config.pop(CONF_PACKAGES, None)

    # ---------------- Frontend Dependencies ---------------- #
    components = {cv.domain_key(key) for key in config}
    frontend_dependencies: set[str] = set()
    if "frontend" in components or "default_config" in components:
        frontend = await get_integration("frontend")
        if frontend:
            await frontend.resolve_dependencies()
            frontend_dependencies = frontend.all_dependencies | {"frontend"}

    # ---------------- Validate Components ---------------- #
    for domain in components:
        integration = await get_integration(domain)
        if integration:
            await validate_component(domain, integration)

    return result