import asyncio
import json
import time
import hmac
import hashlib
import base64
import requests
import websockets
from urllib.parse import urlencode
from collections import defaultdict
import queue
import threading

# PyQtGraph imports
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

API_KEY = "zblZKXordajJr2FhfFyLcWJwjAQFBrqUEmuUAnwEfWS2B9izXqGdf7/C"
API_SECRET = "8WSXoS+qCjbKLDxcKgXAlK2V6ES3JrFRabuQd+eS0l4a1h3Z7GgOdJXgDl1SQPjbZAflrDAuTkrPWPeMkKljUA=="
REST_URL = "https://api.kraken.com/0/private/GetWebSocketsToken"
WS_URL = "wss://ws-auth.kraken.com/v2"

# Central queue for incoming L3 updates
event_queue = queue.Queue()

class OrderBookPlotter(QtCore.QObject):
    def __init__(self, pairs):
        super().__init__()
        self.app = QtWidgets.QApplication([])
        self.win = pg.GraphicsLayoutWidget(show=True, title="Order Book L3 Depth")
        self.plot = self.win.addPlot(title=pairs)
        self.plot.addLegend()
        self.plot.showGrid(x=True, y=True)

        # Curves for bids (red) and asks (blue)
        self.bid_curve = self.plot.plot([], [], pen=pg.mkPen(color='r', width=2), name="Bids")
        self.ask_curve = self.plot.plot([], [], pen=pg.mkPen(color='b', width=2), name="Asks")

        # Internal book: price -> quantity
        self.bids = defaultdict(float)
        self.asks = defaultdict(float)
        
        # Flag pour suivre les heartbeats
        self.heartbeat_received = False

    def process_events(self):
        updated = False
        # D'abord traiter tous les événements de la queue
        while True:
            try:
                pair, side, entries = event_queue.get_nowait()
                if side in ('b', 'a'):
                    for entry in entries:
                        self._process_event(entry, side)
                        updated = True
                elif side == 'h':
                    # Marquer qu'on a reçu un heartbeat
                    self.heartbeat_received = True
            except queue.Empty:
                break
        
        # Ensuite, si un heartbeat a été reçu et qu'il y a eu des mises à jour, actualiser le graphique
        if hasattr(self, 'heartbeat_received') and self.heartbeat_received:
            if updated or True:  # Forcer la mise à jour même sans nouvelles données
                self._update_plot()
            # Réinitialiser le flag heartbeat
            self.heartbeat_received = False

    def _process_event(self, entry, side):
        price = entry['limit_price']
        qty = entry['order_qty']
        book = self.bids if side == 'b' else self.asks
        if entry['event'] == 'add':
            book[price] += qty
        elif entry['event'] == 'delete':
            book[price] = max(0, book[price] - qty)
            if book[price] == 0:
                del book[price]

    def _update_plot(self, depth=50):
        # Préparer agrégation
        bids_sorted = sorted(self.bids.items(), key=lambda x: x[0])[-depth:]
        asks_sorted = sorted(self.asks.items(), key=lambda x: x[0])[:depth]
        # Extraire données
        x_b, y_b = zip(*bids_sorted) if bids_sorted else ([], [])
        x_a, y_a = zip(*asks_sorted) if asks_sorted else ([], [])
        # Mettre à jour les deux courbes simultanément
        self.bid_curve.setData(x=list(x_b), y=list(y_b))
        self.ask_curve.setData(x=list(x_a), y=list(y_a))
        # Forcer redraw
        self.win.repaint()
        QtWidgets.QApplication.processEvents()

    def start(self):
        # Créer un timer simple pour vérifier la queue d'événements
        self.check_timer = QtCore.QTimer()
        self.check_timer.timeout.connect(self.process_events)
        self.check_timer.start(50)  # Vérifier la queue toutes les 50ms
        QtWidgets.QApplication.instance().exec_()


def get_ws_token():
    nonce = str(int(time.time() * 1000))
    data = {'nonce': nonce}
    postdata = urlencode(data)
    sha = hashlib.sha256((nonce + postdata).encode('utf-8')).digest()
    path = "/0/private/GetWebSocketsToken"
    msg = path.encode('utf-8') + sha
    padded_secret = API_SECRET + '=' * (-len(API_SECRET) % 4)
    secret = base64.b64decode(padded_secret)
    signature = base64.b64encode(hmac.new(secret, msg, hashlib.sha512).digest()).decode()
    headers = {'API-Key': API_KEY, 'API-Sign': signature}

    resp = requests.post(REST_URL, data=data, headers=headers, timeout=10)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"[ERROR] HTTP error fetching WS token: {e}")
        return None
    resp_json = resp.json()
    if 'error' in resp_json and resp_json['error']:
        print(f"[ERROR] Kraken API error: {resp_json['error']}")
        return None
    result = resp_json.get('result', {})
    token = result.get('token')
    if not token:
        print(f"[ERROR] No token in response: {resp_json}")
        return None
    return token

async def subscribe_l3(ws, token, pairs):
    msg = {"method": "subscribe", "params": {"channel": "level3", "symbol": pairs, "snapshot": True, "token": token}}
    await ws.send(json.dumps(msg))
    print(f"[INFO] Subscribed to L3 for {pairs}")

async def handle_messages(ws):
    async for raw in ws:
        data = json.loads(raw)
        # L3 updates
        if isinstance(data, dict) and data.get('channel') == 'level3':
            for entry in data.get('data', []):
                for key in ('bids', 'asks'):
                    if entry.get(key):
                        event_queue.put((entry['symbol'], 'b' if key=='bids' else 'a', entry[key]))
        # L3 shorthand updates
        elif isinstance(data, list) and len(data) >= 3:
            _, payload, pair = data
            for key in ('b', 'a'):
                if key in payload:
                    event_queue.put((pair, key, payload[key]))
        # Subscription status
        elif isinstance(data, dict) and data.get('event') == 'subscriptionStatus':
            print(f"[STATUS] {data}")
        # Heartbeat: trigger plot update - toujours mettre à la fin de la queue
        elif isinstance(data, dict) and data.get('channel') == 'heartbeat':
            # S'assurer que le heartbeat est traité après toutes les mises à jour en cours
            event_queue.put((None, 'h', []))
        else:
            print(f"[OTHER] {data}")

async def _ws_loop(token, pairs):
    async with websockets.connect(WS_URL) as ws:
        await subscribe_l3(ws, token, pairs)
        await handle_messages(ws)

if __name__ == '__main__':
    pairs = ['BTC/USD']
    token = get_ws_token()
    if not token:
        print("[ERROR] Could not retrieve WS token, exiting.")
        exit(1)
    print(f"[INFO] Token obtenu: {token}")

    # Instantiate plotter globally so handle_messages can enqueue heartbeat triggers
    plotter = OrderBookPlotter(f"{pairs}")
    ws_thread = threading.Thread(target=lambda: asyncio.run(_ws_loop(token, pairs)), daemon=True)
    ws_thread.start()
    plotter.start()
