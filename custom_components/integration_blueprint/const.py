"""
Constantes partagées dans tout le custom component subscriptions.
"""

DOMAIN = "subscriptions"

# ─── Champs JSON ───────────────────────────────────────────────────────────────
CONF_SUBSCRIPTIONS  = "subscriptions"
CONF_NAME           = "name"
CONF_AMOUNT         = "amount"
CONF_CURRENCY       = "currency"
CONF_CATEGORY       = "category"
CONF_BILLING_CYCLE  = "billing_cycle"
CONF_NEXT_PAYMENT   = "next_payment"   # Date ISO "YYYY-MM-DD" (source de vérité)
CONF_COLOR          = "color"
CONF_URL            = "url"
CONF_FAVICON        = "favicon"
CONF_NOTE           = "note"
CONF_ACTIVE         = "active"

# ─── Cycles acceptés ──────────────────────────────────────────────────────────
BILLING_CYCLES = ["monthly", "yearly", "weekly"]

# ─── Attributs des sensors ────────────────────────────────────────────────────
ATTR_AMOUNT             = "amount"
ATTR_CURRENCY           = "currency"
ATTR_CATEGORY           = "category"
ATTR_BILLING_CYCLE      = "billing_cycle"
ATTR_NEXT_PAYMENT       = "next_payment"
ATTR_DAYS_REMAINING     = "days_remaining"
ATTR_MONTHLY_EQUIVALENT = "monthly_equivalent"
ATTR_URL                = "url"
ATTR_NOTE               = "note"
ATTR_COLOR              = "color"
ATTR_FAVICON            = "favicon"
ATTR_ACTIVE             = "active"

# Attributs du sensor de résumé
ATTR_TOTAL_MONTHLY      = "total_monthly"
ATTR_TOTAL_ANNUAL       = "total_annual"
ATTR_SUBSCRIPTION_COUNT = "count"
ATTR_UPCOMING           = "upcoming"
ATTR_SUBSCRIPTIONS      = "subscriptions"

# ─── Noms des services HA ─────────────────────────────────────────────────────
SERVICE_ADD    = "add_subscription"
SERVICE_UPDATE = "update_subscription"
SERVICE_REMOVE = "remove_subscription"

# ─── Valeurs par défaut ───────────────────────────────────────────────────────
DEFAULT_CURRENCY      = "EUR"
DEFAULT_BILLING_CYCLE = "monthly"
DEFAULT_ACTIVE        = True

# ─── Icônes MDI par catégorie ─────────────────────────────────────────────────
CATEGORY_ICONS = {
    "streaming":  "mdi:television-play",
    "musique":    "mdi:music",
    "music":      "mdi:music",
    "logiciel":   "mdi:application",
    "software":   "mdi:application",
    "gaming":     "mdi:gamepad-variant",
    "cloud":      "mdi:cloud",
    "news":       "mdi:newspaper",
    "actualités": "mdi:newspaper",
    "fitness":    "mdi:dumbbell",
    "service":    "mdi:briefcase-outline",
    "logement":   "mdi:home-outline",
    "default":    "mdi:credit-card-outline",
}
