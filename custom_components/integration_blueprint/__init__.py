"""
Point d'entrée du custom component 'subscriptions'.

Source de vérité unique : subscriptions.json dans /config/
Les abonnements ne sont PLUS déclarés dans configuration.yaml.

Services disponibles :
  subscriptions.add_subscription    → ajoute un abonnement
  subscriptions.update_subscription → modifie un abonnement existant
  subscriptions.remove_subscription → supprime par nom
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date, timedelta
from urllib.parse import urlparse

import requests

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

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
    DEFAULT_CURRENCY,
    DEFAULT_BILLING_CYCLE,
    DEFAULT_ACTIVE,
    SERVICE_ADD,
    SERVICE_UPDATE,
    SERVICE_REMOVE,
)

_LOGGER = logging.getLogger(__name__)

# Pas de configuration YAML requise — la config est dans subscriptions.json
CONFIG_SCHEMA = lambda config: config  # noqa: E731


# ─── Lecture / écriture JSON ──────────────────────────────────────────────────

def _json_path(hass: HomeAssistant) -> str:
    return hass.config.path("subscriptions.json")


def _load_subscriptions(hass: HomeAssistant) -> list[dict]:
    path = _json_path(hass)
    if not os.path.exists(path):
        _LOGGER.warning("subscriptions.json introuvable dans /config/ — fichier créé vide.")
        _save_subscriptions(hass, [])
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get(CONF_SUBSCRIPTIONS, [])
    except (OSError, json.JSONDecodeError) as err:
        _LOGGER.error("Impossible de lire subscriptions.json : %s", err)
        return []


def _save_subscriptions(hass: HomeAssistant, subscriptions: list[dict]) -> None:
    path = _json_path(hass)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({CONF_SUBSCRIPTIONS: subscriptions}, f, ensure_ascii=False, indent=2)
    except OSError as err:
        _LOGGER.error("Impossible d'écrire subscriptions.json : %s", err)


# ─── Auto-avancement de la date de paiement ───────────────────────────────────

def _advance_next_payment(sub: dict) -> dict:
    """
    Si la date next_payment est passée, calcule la prochaine occurrence
    selon le billing_cycle et met à jour le dict (sans écrire le JSON).
    Retourne le dict modifié (ou inchangé si date encore dans le futur).
    """
    next_payment_str = sub.get(CONF_NEXT_PAYMENT)
    if not next_payment_str:
        return sub

    try:
        next_date = date.fromisoformat(next_payment_str)
    except ValueError:
        return sub

    today = date.today()
    if next_date > today:
        return sub  # Pas encore passée, rien à faire

    cycle = sub.get(CONF_BILLING_CYCLE, DEFAULT_BILLING_CYCLE)

    # Avance jusqu'à avoir une date future
    while next_date <= today:
        if cycle == "monthly":
            # Même jour, mois suivant
            month = next_date.month + 1
            year  = next_date.year
            if month > 12:
                month, year = 1, year + 1
            # Gestion des mois courts (31 → 28 fév)
            from calendar import monthrange
            last = monthrange(year, month)[1]
            next_date = next_date.replace(year=year, month=month, day=min(next_date.day, last))

        elif cycle == "yearly":
            next_date = next_date.replace(year=next_date.year + 1)

        elif cycle == "weekly":
            next_date += timedelta(weeks=1)

        else:
            break  # Cycle inconnu → on ne touche pas

    sub = dict(sub)
    sub[CONF_NEXT_PAYMENT] = next_date.isoformat()
    return sub


# ─── Téléchargement des favicons ──────────────────────────────────────────────

def _download_favicons_thread(hass: HomeAssistant) -> None:
    """
    Télécharge les favicons manquants via l'API Google.
    Exécuté dans un thread daemon pour ne pas bloquer le démarrage de HA.
    """
    subscriptions = _load_subscriptions(hass)
    favicon_dir = hass.config.path("www", "favicons")
    os.makedirs(favicon_dir, exist_ok=True)
    changed = False

    for sub in subscriptions:
        url = sub.get(CONF_URL, "")
        if not url:
            continue

        slug     = re.sub(r"[^a-z0-9]", "_", sub.get(CONF_NAME, "unknown").lower())
        filename = f"{slug}.png"
        filepath = os.path.join(favicon_dir, filename)
        local_url = f"/local/favicons/{filename}"

        # Déjà téléchargé et référencé → skip
        if sub.get(CONF_FAVICON) == local_url and os.path.exists(filepath):
            continue

        try:
            hostname = urlparse(url).hostname
            api_url  = f"https://www.google.com/s2/favicons?domain={hostname}&sz=64"
            resp     = requests.get(api_url, timeout=5)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            sub[CONF_FAVICON] = local_url
            changed = True
            _LOGGER.info("Favicon téléchargé : %s → %s", hostname, filename)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Favicon impossible pour %s : %s", sub.get(CONF_NAME), err)

    if changed:
        _save_subscriptions(hass, subscriptions)
        # Signale aux sensors de se rafraîchir
        hass.bus.fire(f"{DOMAIN}_updated")


# ─── Enregistrement des services ──────────────────────────────────────────────

def _register_services(hass: HomeAssistant) -> None:
    """
    Enregistre les trois services HA pour gérer les abonnements depuis la carte.

    Appel depuis la carte Lovelace :
      this._hass.callService('subscriptions', 'add_subscription', { name: 'Netflix', ... })
    """

    def handle_add(call: ServiceCall) -> None:
        """
        Ajoute un nouvel abonnement.
        Champs obligatoires : name, amount, next_payment
        """
        subs = _load_subscriptions(hass)
        new_sub = {
            CONF_NAME:          call.data.get(CONF_NAME, ""),
            CONF_AMOUNT:        float(call.data.get(CONF_AMOUNT, 0)),
            CONF_CURRENCY:      call.data.get(CONF_CURRENCY, DEFAULT_CURRENCY),
            CONF_CATEGORY:      call.data.get(CONF_CATEGORY, ""),
            CONF_BILLING_CYCLE: call.data.get(CONF_BILLING_CYCLE, DEFAULT_BILLING_CYCLE),
            CONF_NEXT_PAYMENT:  call.data.get(CONF_NEXT_PAYMENT, date.today().isoformat()),
            CONF_COLOR:         call.data.get(CONF_COLOR, "#6366f1"),
            CONF_URL:           call.data.get(CONF_URL, ""),
            CONF_NOTE:          call.data.get(CONF_NOTE, ""),
            CONF_ACTIVE:        call.data.get(CONF_ACTIVE, DEFAULT_ACTIVE),
        }
        subs.append(new_sub)
        _save_subscriptions(hass, subs)
        hass.bus.fire(f"{DOMAIN}_updated")
        _LOGGER.info("Abonnement ajouté : %s", new_sub[CONF_NAME])

    def handle_update(call: ServiceCall) -> None:
        """
        Met à jour un abonnement existant identifié par son nom.
        Seuls les champs fournis sont modifiés (patch partiel).
        """
        target_name = call.data.get(CONF_NAME, "")
        subs = _load_subscriptions(hass)
        updated = False

        for sub in subs:
            if sub.get(CONF_NAME, "").lower() == target_name.lower():
                # Mise à jour partielle : on ne touche qu'aux clés fournies
                for key, value in call.data.items():
                    if key != CONF_NAME:  # Le nom est la clé de lookup, on ne le change pas
                        sub[key] = value
                updated = True
                break

        if updated:
            _save_subscriptions(hass, subs)
            hass.bus.fire(f"{DOMAIN}_updated")
            _LOGGER.info("Abonnement mis à jour : %s", target_name)
        else:
            _LOGGER.warning("update_subscription : '%s' introuvable", target_name)

    def handle_remove(call: ServiceCall) -> None:
        """
        Supprime un abonnement par son nom (insensible à la casse).
        """
        target_name = call.data.get(CONF_NAME, "")
        subs = _load_subscriptions(hass)
        before = len(subs)
        subs = [s for s in subs if s.get(CONF_NAME, "").lower() != target_name.lower()]

        if len(subs) < before:
            _save_subscriptions(hass, subs)
            hass.bus.fire(f"{DOMAIN}_updated")
            _LOGGER.info("Abonnement supprimé : %s", target_name)
        else:
            _LOGGER.warning("remove_subscription : '%s' introuvable", target_name)

    hass.services.register(DOMAIN, SERVICE_ADD,    handle_add)
    hass.services.register(DOMAIN, SERVICE_UPDATE, handle_update)
    hass.services.register(DOMAIN, SERVICE_REMOVE, handle_remove)


# ─── Point d'entrée principal ─────────────────────────────────────────────────

def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """
    Initialise l'intégration Subscriptions Tracker.

    1. Charge subscriptions.json
    2. Enregistre les services
    3. Lance le téléchargement des favicons en arrière-plan
    4. Crée les sensors via la plateforme sensor
    """
    # Chargement initial (valide que le JSON est lisible)
    subscriptions = _load_subscriptions(hass)

    # Auto-avancement des dates passées et mise à jour du JSON si besoin
    updated_subs = [_advance_next_payment(s) for s in subscriptions]
    if updated_subs != subscriptions:
        _save_subscriptions(hass, updated_subs)

    # Stockage dans hass.data pour que sensor.py y accède
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["json_path"] = _json_path(hass)

    # Enregistrement des services
    _register_services(hass)

    # Téléchargement des favicons en arrière-plan (non-bloquant)
    threading.Thread(
        target=_download_favicons_thread,
        args=(hass,),
        daemon=True,
        name="subscriptions_favicons",
    ).start()

    # Chargement de la plateforme sensor
    hass.helpers.discovery.load_platform("sensor", DOMAIN, {}, config)

    _LOGGER.info(
        "Subscriptions Tracker initialisé — %d abonnement(s) chargés",
        len(updated_subs),
    )
    return True
