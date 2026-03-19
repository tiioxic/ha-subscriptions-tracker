# 📅 Subscriptions Tracker — Intégration HACS

Suivez et gérez vos abonnements directement depuis Home Assistant.

## Fonctionnalités

- **Carte Lovelace** fidèle à votre design actuel
- **Ajout / modification / suppression** d'abonnements depuis la carte (bouton +, ✏️, 🗑️)
- **Sensors HA** : un par abonnement + un sensor de résumé global
- **Auto-avancement** des dates passées (mensuel, annuel, hebdo)
- **Téléchargement automatique** des favicons au démarrage
- **Services HA** : `subscriptions.add_subscription`, `update_subscription`, `remove_subscription`

---

## Structure du dépôt

```
ha-subscriptions-tracker/
├── hacs.json
├── README.md
├── custom_components/
│   └── subscriptions/
│       ├── __init__.py
│       ├── sensor.py
│       ├── const.py
│       └── manifest.json
└── www/
    └── subscriptions-card.js
```

---

## Installation

### Via HACS (méthode recommandée)

1. HACS → ⋮ → **Custom repositories**
2. URL : `https://github.com/tiioxic/ha-subscriptions-tracker`
3. Type : **Integration**
4. Installer **Subscriptions Tracker**
5. Redémarrer Home Assistant

### Fichier de données

Créer `/config/subscriptions.json` :

```json
{
  "subscriptions": [
    {
      "name": "Netflix",
      "amount": 13.99,
      "currency": "EUR",
      "category": "streaming",
      "billing_cycle": "monthly",
      "next_payment": "2026-04-15",
      "color": "#e50914",
      "url": "https://www.netflix.com"
    }
  ]
}
```

### Carte Lovelace

Copier `www/subscriptions-card.js` dans `/config/www/`

Ajouter dans **Tableau de bord → Ressources** :
```
/local/subscriptions-card.js
```

Ajouter la carte :
```yaml
type: custom:subscriptions-card
entity: sensor.subscriptions_summary
title: Mes Abonnements
```

---

## Services disponibles

```yaml
# Ajouter
service: subscriptions.add_subscription
data:
  name: Spotify
  amount: 9.99
  billing_cycle: monthly
  next_payment: "2026-04-10"
  category: musique
  color: "#1db954"
  url: https://www.spotify.com

# Modifier
service: subscriptions.update_subscription
data:
  name: Spotify
  amount: 10.99

# Supprimer
service: subscriptions.remove_subscription
data:
  name: Spotify
```

---

## Champs du JSON

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `name` | string | ✅ | Nom affiché |
| `amount` | float | ✅ | Montant |
| `next_payment` | date ISO | ✅ | Prochain paiement `YYYY-MM-DD` |
| `billing_cycle` | string | — | `monthly` / `yearly` / `weekly` |
| `currency` | string | — | `EUR` par défaut |
| `category` | string | — | streaming, logiciel, gaming… |
| `color` | hex | — | Couleur du point |
| `url` | string | — | URL du service |
| `favicon` | string | — | Chemin local `/local/favicons/xxx.png` |
| `note` | string | — | Note libre |
| `active` | bool | — | `true` par défaut |
