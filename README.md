# OrderBookPlotter

## Description

Ce projet fournit une application graphique en Python pour "reconstruire" en temps réel le carnet d'ordres (order book) à partire des données L3 sur la plateforme Kraken. Il récupère les mises à jour via WebSocket et les affiche sous forme de courbes de profondeur pour les ordres d'achat (bids) et de vente (asks) en utilisant PyQtGraph.

## Fonctionnalités

* Authentification sécurisée via l'API Kraken (REST) pour obtenir le jeton WebSocket.
* Connexion WebSocket authentifiée pour souscrire au flux L3 (`level3`).
* Traitement des événements : ajout, suppression d'ordres et `heartbeat` pour rafraîchissement régulier.
* Visualisation interactive avec PyQtGraph : courbes séparées pour bids et asks, mise à jour en continu.
* Filtrage de profondeur configurable (50 niveaux par défaut).

## Prérequis

* Python 3.7+
* Bibliothèques Python :

  * `asyncio`
  * `requests`
  * `websockets`
  * `PyQt5`
  * `pyqtgraph`

## Installation

1. Clonez ce dépôt :

   ```bash
   git clone https://github.com/Tuturj/OrderBookPlotter.git
   cd OrderBookPlotter
   ```
2. (Optionnel) Créez et activez un environnement virtuel :

   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate   # Windows
   ```
3. Installez les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. Renommez (ou créez) le fichier `config_example.py` en `config.py`.
2. Remplacez les valeurs par vos propres clés API :

   ```python
   API_KEY = "votre_api_key"
   API_SECRET = "votre_api_secret"
   ```

## Utilisation

Lancez l'application depuis la ligne de commande :

```bash
python orderbook_plotter.py
```

Par défaut, l'application s'abonne au symbole `['BTC/USD']`. Pour modifier la paire de trading, éditez la variable `pairs` dans la section `if __name__ == '__main__'`.

## Structure du code

* `orderbook_plotter.py` : logique principale pour l'authentification, la connexion WebSocket, et le traitement des messages.
* `OrderBookPlotter` (classe) : gère l'interface graphique, le traitement des événements et le rafraîchissement du tracé.
* `get_ws_token` : obtention sécurisée du jeton WebSocket via l'API REST.
* `subscribe_l3`, `handle_messages`, `_ws_loop` : fonctions asynchrones pour la gestion du flux L3.

## Personnalisation

* **Profondeur d'affichage** : modifiez le paramètre `depth` de `_update_plot` pour ajuster le nombre de niveaux.
* **Intervalle de rafraîchissement** : changez la valeur du timer `self.check_timer.start(50)` pour adapter la fréquence de rafraîchissement.


---
