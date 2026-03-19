"""
Plateforme sensor pour le custom component 'subscriptions'.

Source de données : subscriptions.json (via hass.data[DOMAIN] ou lecture directe).
Le sensor se rafraîchit automatiquement et à chaque événement 'subscriptions_updated'
déclenché par les services add/update/remove.

Entités créées :
  - SubscriptionSensor      : 1 par abonnement (state = jours restants)
  - SubscriptionSummarySensor : résumé global (state = total mensuel en €)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util
from datetime import timedelta

from .const import (
    DOMAIN,
    CONF_SUBSCRIPTIONS,
    CONF_NAME,
    CONF_AMOUNT,
    CONF_CURRENCY,
    CONF_CATEGORY,
    CONF_BILLING_CYCLE,
    CONF_NEXT_PAYMENT,
    CONF_COLOR,
    CONF_URL,
    CONF_FAVICON,
    CONF_NOTE,
    CONF_ACTIVE,
    ATTR_AMOUNT,
    ATTR_CURRENCY,
    ATTR_CATEGORY,
    ATTR_BILLING_CYCLE,
    ATTR_NEXT_PAYMENT,
    ATTR_DAYS_REMAINING,
    ATTR_MONTHLY_EQUIVALENT,
    ATTR_URL,
    ATTR_NOTE,
    ATTR_COLOR,
    ATTR_FAVICON,
    ATTR_ACTIVE,
    ATTR_TOTAL_MONTHLY,
    ATTR_TOTAL_ANNUAL,
    ATTR_SUBSCRIPTION_COUNT,
    ATTR_UPCOMING,
    ATTR_SUBSCRIPTIONS,
    CATEGORY_ICONS,
    DEFAULT_CURRENCY,
    DEFAULT_BILLING_CYCLE,
    DEFAULT_ACTIVE,
)

_LOGGER = logging.getLogger(__name__)

# Intervalle de rafraîchissement automatique (1 heure)
SCAN_INTERVAL = timedelta(hours=1)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _days_until(date_str: str | None) -> int | None:
    """Retourne le nombre de jours entre aujourd'hui et date_str (peut être négatif)."""
    if not date_str:
        return None
    try:
        target = date.fromisoformat(date_str)
        return (target - date.today()).days
    except ValueError:
        return None


def _monthly_equivalent(amount: float, billing_cycle: str) -> float:
    """Ramène n'importe quel cycle à un coût mensuel équivalent."""
    if billing_cycle == "yearly":
        return round(amount / 12, 2)
    if billing_cycle == "weekly":
        return round(amount * 52 / 12, 2)
    return round(amount, 2)  # monthly


# ─── Lecture du JSON ──────────────────────────────────────────────────────────

def _read_json(hass: HomeAssistant) -> list[dict]:
    json_path = hass.data.get(DOMAIN, {}).get("json_path")
    if not json_path or not os.path.exists(json_path):
        return []
    try:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f).get(CONF_SUBSCRIPTIONS, [])
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Impossible de lire subscriptions.json : %s", err)
        return []


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Crée les entités sensor au démarrage."""
    subscriptions_raw = _read_json(hass)

    # Un sensor individuel par abonnement actif
    individual = [
        SubscriptionSensor(hass, sub)
        for sub in subscriptions_raw
        if sub.get(CONF_ACTIVE, DEFAULT_ACTIVE)
    ]

    # Un sensor de résumé global
    summary = SubscriptionSummarySensor(hass)

    entities = individual + [summary]
    add_entities(entities, update_before_add=True)

    # ── Écoute l'événement 'subscriptions_updated' (déclenché par les services) ──
    # Quand le JSON change, on force la mise à jour de tous les sensors existants.
    def _on_subscriptions_updated(event):
        for entity in entities:
            entity.schedule_update_ha_state(force_refresh=True)

    hass.bus.listen(f"{DOMAIN}_updated", _on_subscriptions_updated)


# ─── Sensor individuel ────────────────────────────────────────────────────────

class SubscriptionSensor(SensorEntity):
    """
    Représente un abonnement individuel.
    state = jours avant le prochain paiement (entier, peut être négatif).
    """

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self._hass_ref = hass
        self._config   = config
        self._name_val = config[CONF_NAME]

        slug = self._name_val.lower().replace(" ", "_")
        slug = "".join(c if c.isalnum() or c == "_" else "_" for c in slug)
        self._unique_id_val = f"subscription_{slug}"

        self._days_remaining: int | None = None
        self._next_payment:   str | None = None
        self._monthly_eq:     float | None = None

    @property
    def name(self) -> str:
        return f"Subscription {self._name_val}"

    @property
    def unique_id(self) -> str:
        return self._unique_id_val

    @property
    def state(self) -> int | None:
        return self._days_remaining

    @property
    def unit_of_measurement(self) -> str:
        return "days"

    @property
    def icon(self) -> str:
        cat = self._config.get(CONF_CATEGORY, "").lower()
        return CATEGORY_ICONS.get(cat, CATEGORY_ICONS["default"])

    @property
    def available(self) -> bool:
        return self._config.get(CONF_ACTIVE, DEFAULT_ACTIVE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            ATTR_AMOUNT:             self._config.get(CONF_AMOUNT),
            ATTR_CURRENCY:           self._config.get(CONF_CURRENCY, DEFAULT_CURRENCY),
            ATTR_CATEGORY:           self._config.get(CONF_CATEGORY, ""),
            ATTR_BILLING_CYCLE:      self._config.get(CONF_BILLING_CYCLE, DEFAULT_BILLING_CYCLE),
            ATTR_NEXT_PAYMENT:       self._next_payment,
            ATTR_DAYS_REMAINING:     self._days_remaining,
            ATTR_MONTHLY_EQUIVALENT: self._monthly_eq,
            ATTR_URL:                self._config.get(CONF_URL, ""),
            ATTR_NOTE:               self._config.get(CONF_NOTE, ""),
            ATTR_COLOR:              self._config.get(CONF_COLOR, "#6366f1"),
            ATTR_FAVICON:            self._config.get(CONF_FAVICON, ""),
            ATTR_ACTIVE:             self._config.get(CONF_ACTIVE, DEFAULT_ACTIVE),
        }

    def update(self) -> None:
        """
        Relit le JSON pour avoir les dernières données,
        puis recalcule les jours restants.
        """
        # Relit le JSON → récupère la version à jour de cet abonnement
        all_subs = _read_json(self._hass_ref)
        for sub in all_subs:
            if sub.get(CONF_NAME) == self._name_val:
                self._config = sub
                break

        self._next_payment   = self._config.get(CONF_NEXT_PAYMENT)
        self._days_remaining = _days_until(self._next_payment)
        self._monthly_eq     = _monthly_equivalent(
            amount        = self._config.get(CONF_AMOUNT, 0.0),
            billing_cycle = self._config.get(CONF_BILLING_CYCLE, DEFAULT_BILLING_CYCLE),
        )


# ─── Sensor de résumé global ──────────────────────────────────────────────────

class SubscriptionSummarySensor(SensorEntity):
    """
    Sensor de résumé qui agrège tous les abonnements actifs.
    state = coût mensuel total.

    L'attribut 'subscriptions' contient la liste COMPLÈTE des champs
    (color, favicon, url, note…) pour que la carte Lovelace puisse tout afficher.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass_ref      = hass
        self._total_monthly : float      = 0.0
        self._subs_data     : list[dict] = []

    @property
    def name(self) -> str:
        return "Subscriptions Summary"

    @property
    def unique_id(self) -> str:
        return "subscriptions_summary"

    @property
    def state(self) -> float:
        return self._total_monthly

    @property
    def unit_of_measurement(self) -> str:
        return "EUR"

    @property
    def icon(self) -> str:
        return "mdi:chart-pie"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        upcoming = [
            s for s in self._subs_data
            if s.get(ATTR_DAYS_REMAINING) is not None and 0 <= s[ATTR_DAYS_REMAINING] <= 7
        ]
        return {
            ATTR_TOTAL_MONTHLY:      self._total_monthly,
            ATTR_TOTAL_ANNUAL:       round(self._total_monthly * 12, 2),
            ATTR_SUBSCRIPTION_COUNT: len(self._subs_data),
            ATTR_UPCOMING:           upcoming,
            ATTR_SUBSCRIPTIONS:      self._subs_data,
        }

    def update(self) -> None:
        """Relit le JSON et recalcule le résumé complet."""
        all_subs = _read_json(self._hass_ref)
        total    = 0.0
        data     = []

        for sub in all_subs:
            if not sub.get(CONF_ACTIVE, DEFAULT_ACTIVE):
                continue

            days_remaining = _days_until(sub.get(CONF_NEXT_PAYMENT))
            monthly_eq     = _monthly_equivalent(
                amount        = sub.get(CONF_AMOUNT, 0.0),
                billing_cycle = sub.get(CONF_BILLING_CYCLE, DEFAULT_BILLING_CYCLE),
            )
            total += monthly_eq

            # ── Tous les champs sont inclus pour la carte Lovelace ──────────
            data.append({
                CONF_NAME:               sub.get(CONF_NAME, ""),
                ATTR_AMOUNT:             sub.get(CONF_AMOUNT, 0.0),
                ATTR_CURRENCY:           sub.get(CONF_CURRENCY, DEFAULT_CURRENCY),
                ATTR_CATEGORY:           sub.get(CONF_CATEGORY, ""),
                ATTR_BILLING_CYCLE:      sub.get(CONF_BILLING_CYCLE, DEFAULT_BILLING_CYCLE),
                ATTR_NEXT_PAYMENT:       sub.get(CONF_NEXT_PAYMENT),
                ATTR_DAYS_REMAINING:     days_remaining,
                ATTR_MONTHLY_EQUIVALENT: monthly_eq,
                ATTR_URL:                sub.get(CONF_URL, ""),
                ATTR_NOTE:               sub.get(CONF_NOTE, ""),
                ATTR_COLOR:              sub.get(CONF_COLOR, "#6366f1"),   # ← champ manquant avant
                ATTR_FAVICON:            sub.get(CONF_FAVICON, ""),        # ← champ manquant avant
                ATTR_ACTIVE:             sub.get(CONF_ACTIVE, DEFAULT_ACTIVE),
            })

        # Tri : les plus urgents en premier (jours None → infini pour le tri)
        data.sort(key=lambda x: x[ATTR_DAYS_REMAINING] if x[ATTR_DAYS_REMAINING] is not None else 9999)

        self._total_monthly = round(total, 2)
        self._subs_data     = data
