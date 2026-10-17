#!/usr/bin/env python3
"""TradePulse Pro — servidor local com proxy de trading Binance Spot.

SEGURANÇA
- As chaves da API existem SOMENTE em variáveis de ambiente (nunca em disco, log ou frontend).
- Por padrão todas as ordens vão para o SPOT TESTNET (testnet.binance.vision).
- O modo REAL exige: TRADEPULSE_ALLOW_LIVE=1 no ambiente E confirmação explícita
  na requisição (confirm=true), além da troca de modo na interface.
- Vinculado apenas a 127.0.0.1 (localhost).
- Antes de enviar qualquer ordem, o servidor valida LOT_SIZE, NOTIONAL e PRICE_FILTER
  usando o /exchangeInfo da própria Binance.

Somente rotas GET de leitura + rotas de ordem explícitas. Nada de saque (withdraw).
"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from decimal import Decimal, ROUND_DOWN, InvalidOperation
import os, time, hmac, hashlib, json, threading

ROOT = Path(__file__).resolve().parent
HOST = '127.0.0.1'
PORT = int(os.environ.get('TRADEPULSE_PORT', '8765'))

BASE_TESTNET = 'https://testnet.binance.vision'
BASE_LIVE = 'https://api.binance.com'

# Estado do modo de negociação (em memória; padrão = TESTNET)
LIVE_MODE = False
_LIVE_LOCK = threading.Lock()

_INFO_CACHE = {}   # symbol -> (timestamp, filters)
INFO_TTL = 3600    # 1 hora


def _env_key():
    return os.environ.get('BINANCE_API_KEY', '').strip()

def _env_secret():
    return os.environ.get('BINANCE_API_SECRET', '').strip()

def _allow_live():
    return os.environ.get('TRADEPULSE_ALLOW_LIVE', '0') == '1'

def _base():
    return BASE_LIVE if LIVE_MODE else BASE_TESTNET


def public_get(path, params=None):
    qs = ('?' + urlencode(params)) if params else ''
    req = Request(_base() + path + qs, headers={'Accept': 'application/json'}, method='GET')
    with urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode('utf-8'))


def signed_request(method, path, params=None):
    """Requisição assinada (HMAC SHA256) com as chaves do ambiente."""
    key, secret = _env_key(), _env_secret()
    if not key or not secret:
        raise RuntimeError('Credenciais não configuradas no ambiente do servidor.')
    params = dict(params or {})
    params['timestamp'] = int(time.time() * 1000)
    params['recvWindow'] = 5000
    qs = urlencode(params)
    sig = hmac.new(secret.encode('utf-8'), qs.encode('utf-8'), hashlib.sha256).hexdigest()
    url = _base() + path + '?' + qs + '&signature=' + sig
    req = Request(url, headers={'X-MBX-APIKEY': key, 'Accept': 'application/json'}, method=method)
    try:
        with urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        try:
            detail = json.loads(e.read().decode('utf-8'))
        except Exception:
            detail = {}
        code = detail.get('code'); msg = detail.get('msg', '')
        if code == -1021:
            raise RuntimeError('Relógio fora de sincronia (-1021). Ajuste a hora do dispositivo e tente de novo.')
        if code == -2015:
            raise RuntimeError('Chave recusada (-2015). Verifique a chave, as permissões de trading e o IP liberado na Binance.')
        if code == -1003:
            raise RuntimeError('Limite de requisições atingido (-1003). Aguarde um instante e tente novamente.')
        if code == -2010:
            raise RuntimeError('Ordem rejeitada pela Binance (-2010): ' + str(msg))
        raise RuntimeError('Erro da Binance (HTTP %s, código %s): %s' % (e.code, code, msg or 'sem detalhes'))
    except (URLError, TimeoutError, OSError) as e:
        raise RuntimeError('Falha de rede ao falar com a Binance: %s' % e)


def _dec(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def symbol_rules(symbol):
    """Busca (com cache) os filtros de um símbolo no exchangeInfo."""
    now = time.time()
    hit = _INFO_CACHE.get(symbol)
    if hit and now - hit[0] < INFO_TTL:
        return hit[1]
    info = public_get('/api/v3/exchangeInfo', {'symbol': symbol})
    symbols = info.get('symbols') or []
    if not symbols:
        raise RuntimeError('Símbolo %s não encontrado no exchangeInfo da Binance.' % symbol)
    filters = {f['filterType']: f for f in symbols[0].get('filters', [])}
    _INFO_CACHE[symbol] = (now, filters)
    return filters


def round_step(value: Decimal, step: str) -> Decimal:
    step_d = _dec(step) or Decimal('1')
    if step_d <= 0:
        step_d = Decimal('1')
    # Passos da Binance são potências de 10 (0.0001, 0.01...). quantize() usa o
    # expoente do argumento, então normalizamos o step (0.00010000 -> 0.0001)
    # para truncar na casa decimal correta.
    exp = step_d.normalize().as_tuple().exponent
    if exp > 0:
        exp = 0
    return value.quantize(Decimal(1).scaleb(exp), rounding=ROUND_DOWN)


def validate_order(symbol, side, otype, quantity, quote_qty, price, tif):
    """Valida a ordem contra LOT_SIZE / NOTIONAL / PRICE_FILTER.
    Retorna (params_prontos, avisos). Levanta RuntimeError em erro bloqueante."""
    filters = symbol_rules(symbol)
    warnings = []
    lot = filters.get('LOT_SIZE', {})
    notional = filters.get('NOTIONAL', {}) or filters.get('MIN_NOTIONAL', {})
    price_f = filters.get('PRICE_FILTER', {})

    params = {'symbol': symbol, 'side': side, 'type': otype}

    if otype == 'LIMIT':
        if not price:
            raise RuntimeError('Ordem LIMIT exige preço.')
        p = _dec(price)
        tick = _dec(price_f.get('tickSize', '0'))
        if p is None or p <= 0:
            raise RuntimeError('Preço inválido.')
        if tick and tick > 0:
            p2 = round_step(p, str(tick))
            if p2 != p:
                warnings.append('Preço ajustado ao tickSize: %s → %s' % (p, p2))
                p = p2
        params['price'] = format(p, 'f')
        params['timeInForce'] = tif if tif in ('GTC', 'IOC', 'FOK') else 'GTC'
        if quote_qty:
            raise RuntimeError('Ordem LIMIT usa quantity (não quoteOrderQty).')

    ref_price = None
    if otype == 'LIMIT':
        ref_price = _dec(params['price'])
    else:  # MARKET: usa preço público atual para checar notional
        try:
            ref_price = _dec(public_get('/api/v3/ticker/price', {'symbol': symbol})['price'])
        except Exception:
            ref_price = None

    if quote_qty and otype == 'MARKET':
        q = _dec(quote_qty)
        if q is None or q <= 0:
            raise RuntimeError('quoteOrderQty inválido.')
        params['quoteOrderQty'] = format(q, 'f')
        qty = (q / ref_price) if ref_price else None
    else:
        if not quantity:
            raise RuntimeError('Informe a quantidade (quantity).')
        q = _dec(quantity)
        if q is None or q <= 0:
            raise RuntimeError('Quantidade inválida.')
        step = lot.get('stepSize', '1')
        q2 = round_step(q, step)
        if q2 != q:
            warnings.append('Quantidade ajustada ao stepSize (%s): %s → %s' % (step, q, q2))
            q = q2
        minq = _dec(lot.get('minQty', '0'))
        if minq is not None and q < minq:
            raise RuntimeError('Quantidade abaixo do mínimo do par (LOT_SIZE minQty = %s).' % minq)
        params['quantity'] = format(q, 'f')
        qty = q

    if ref_price and qty is not None:
        mn = _dec(notional.get('minNotional', notional.get('minVal', '0')))
        if mn is not None and mn > 0 and ref_price * qty < mn:
            raise RuntimeError('Valor da ordem abaixo do mínimo do par (NOTIONAL minNotional = %s US$).' % mn)
    return params, warnings


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        # Nunca registra headers, chaves ou payloads de conta.
        print('%s - %s' % (self.address_string(), fmt % args))

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
            if n <= 0:
                return {}
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:
            return {}

    # ---------------- GET ----------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        if path == '/api/health':
            return self.send_json(200, {
                'ok': True, 'app': 'TradePulse Pro',
                'accountConfigured': bool(_env_key() and _env_secret()),
                'mode': 'live' if LIVE_MODE else 'testnet',
                'allowLive': _allow_live(),
                'base': _base(), 'exchange': 'Binance Spot'})
        if path == '/api/account':
            try:
                data = signed_request('GET', '/api/v3/account')
                balances = []
                for it in data.get('balances', []):
                    free = float(it.get('free') or 0); locked = float(it.get('locked') or 0)
                    if free or locked:
                        balances.append({'asset': it.get('asset', ''), 'free': free, 'locked': locked, 'total': free + locked})
                balances.sort(key=lambda x: x['total'], reverse=True)
                return self.send_json(200, {'ok': True, 'exchange': 'Binance', 'mode': 'live' if LIVE_MODE else 'testnet',
                                            'accountType': data.get('accountType', '—'), 'canTrade': data.get('canTrade', False),
                                            'permissions': data.get('permissions', []), 'balances': balances[:100],
                                            'readAt': int(time.time() * 1000)})
            except RuntimeError as e:
                return self.send_json(502, {'ok': False, 'error': str(e)})
        if path == '/api/openOrders':
            params = {}
            if qs.get('symbol'):
                params['symbol'] = qs['symbol'][0]
            try:
                data = signed_request('GET', '/api/v3/openOrders', params)
                return self.send_json(200, {'ok': True, 'orders': data, 'mode': 'live' if LIVE_MODE else 'testnet'})
            except RuntimeError as e:
                return self.send_json(502, {'ok': False, 'error': str(e)})
        if path == '/api/exchangeInfo':
            symbol = (qs.get('symbol') or [''])[0]
            if not symbol:
                return self.send_json(400, {'ok': False, 'error': 'Informe ?symbol=BTCUSDT'})
            try:
                f = symbol_rules(symbol)
                return self.send_json(200, {'ok': True, 'symbol': symbol, 'filters': f})
            except Exception as e:
                return self.send_json(502, {'ok': False, 'error': str(e)})
        if path.startswith('/api/'):
            return self.send_json(404, {'ok': False, 'error': 'Endpoint não encontrado.'})
        return super().do_GET()

    # ---------------- POST ----------------
    def do_POST(self):
        global LIVE_MODE
        path = urlparse(self.path).path
        if path == '/api/mode':
            body = self.read_body()
            mode = body.get('mode')
            if mode == 'live':
                if not _allow_live():
                    return self.send_json(403, {'ok': False, 'error': 'Modo REAL bloqueado: inicie o servidor com TRADEPULSE_ALLOW_LIVE=1 para habilitar.'})
                if not body.get('confirm'):
                    return self.send_json(400, {'ok': False, 'error': 'Confirmação obrigatória para ativar o modo REAL.'})
                with _LIVE_LOCK:
                    LIVE_MODE = True
                return self.send_json(200, {'ok': True, 'mode': 'live', 'base': _base()})
            if mode == 'testnet':
                with _LIVE_LOCK:
                    LIVE_MODE = False
                return self.send_json(200, {'ok': True, 'mode': 'testnet', 'base': _base()})
            return self.send_json(400, {'ok': False, 'error': "mode deve ser 'testnet' ou 'live'."})
        if path == '/api/order':
            body = self.read_body()
            if not body.get('confirm'):
                return self.send_json(400, {'ok': False, 'error': 'Confirmação obrigatória (confirm=true) para enviar ordens.'})
            symbol = str(body.get('symbol', '')).upper().strip()
            side = str(body.get('side', '')).upper()
            otype = str(body.get('type', '')).upper()
            if side not in ('BUY', 'SELL') or otype not in ('MARKET', 'LIMIT'):
                return self.send_json(400, {'ok': False, 'error': 'Campos obrigatórios: symbol, side (BUY/SELL), type (MARKET/LIMIT).'})
            if not symbol.endswith('USDT'):
                symbol += 'USDT'
            try:
                params, warnings = validate_order(symbol, side, otype,
                                                  body.get('quantity'), body.get('quoteOrderQty'),
                                                  body.get('price'), body.get('timeInForce'))
                result = signed_request('POST', '/api/v3/order', params)
                return self.send_json(200, {'ok': True, 'warnings': warnings, 'order': result, 'mode': 'live' if LIVE_MODE else 'testnet'})
            except RuntimeError as e:
                return self.send_json(400, {'ok': False, 'error': str(e)})
        if path.startswith('/api/'):
            return self.send_json(404, {'ok': False, 'error': 'Endpoint não encontrado.'})
        return self.send_json(405, {'ok': False, 'error': 'Método não permitido.'})

    # ---------------- DELETE ----------------
    def do_DELETE(self):
        path, qs = urlparse(self.path).path, parse_qs(urlparse(self.path).query)
        if path == '/api/order':
            symbol = (qs.get('symbol') or [''])[0].upper()
            order_id = (qs.get('orderId') or [''])[0]
            if not symbol or not order_id:
                return self.send_json(400, {'ok': False, 'error': 'Informe symbol e orderId para cancelar.'})
            try:
                result = signed_request('DELETE', '/api/v3/order', {'symbol': symbol, 'orderId': int(order_id)})
                return self.send_json(200, {'ok': True, 'cancel': result})
            except RuntimeError as e:
                return self.send_json(400, {'ok': False, 'error': str(e)})
        return self.send_json(405, {'ok': False, 'error': 'Método não permitido.'})


if __name__ == '__main__':
    print(f'TradePulse Pro disponível em http://{HOST}:{PORT}/index.html')
    print('Backend vinculado somente a localhost.')
    print('Modo inicial das ordens: %s (%s)' % ('TESTNET' if not LIVE_MODE else 'LIVE', _base()))
    print('Chaves: BINANCE_API_KEY / BINANCE_API_SECRET no ambiente (nunca em arquivos).')
    print('Modo REAL: exige TRADEPULSE_ALLOW_LIVE=1 + troca de modo confirmada na interface.')
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
