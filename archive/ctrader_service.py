#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cTrader Service - микросервис для сбора данных с cTrader
Собирает данные с cTrader и отправляет их в Spread Service через WebSocket
"""

import os
import sys
import time
import json
import threading
import logging
import asyncio
import websockets
from datetime import datetime, timezone, timedelta

# Добавляем путь к ctrader-open-api
sys.path.insert(0, os.path.dirname(__file__))

try:
    from ctrader_open_api import Client, Protobuf, TcpProtocol, Auth, EndPoints
    from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
    from ctrader_open_api.messages.OpenApiMessages_pb2 import *
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import *
    from twisted.internet import reactor
    CTRADER_AVAILABLE = True
except ImportError:
    CTRADER_AVAILABLE = False

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Московское время
def now_moscow():
    moscow_tz = timezone(timedelta(hours=3))
    return datetime.now(moscow_tz)

def timestamp_to_moscow(timestamp):
    moscow_tz = timezone(timedelta(hours=3))
    if timestamp > 1e15:  # микросекунды
        return datetime.fromtimestamp(timestamp / 1000000, tz=moscow_tz)
    elif timestamp > 1e9:  # миллисекунды
        return datetime.fromtimestamp(timestamp / 1000, tz=moscow_tz)
    else:  # секунды
        return datetime.fromtimestamp(timestamp, tz=moscow_tz)

class cTraderService:
    def __init__(self):
        # Кеш данных cTrader символов (только bid, ask, last_update)
        self.symbols_data = {
            'XPDUSD': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # Палладий
            'XPTUSD': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # Платина
            'XAGUSD': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # Серебро
            'XAUUSD': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # Золото
            '#Coffee_Z25': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # Кофе
            'USDCNH': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # USD/CNH
            'EURCNH': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # EUR/CNH
            'EURUSD': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # EUR/USD
            '#USNDAQ100': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # NASDAQ 100
            '#USSPX500': {'bid': 0.0, 'ask': 0.0, 'last_update': None},  # S&P 500
        }
        
        # cTrader настройки
        self.ctrader_config = {
            'client_id': os.getenv('CTRADER_CLIENT_ID'),
            'client_secret': os.getenv('CTRADER_CLIENT_SECRET'),
            'access_token': os.getenv('CTRADER_ACCESS_TOKEN'),
            'refresh_token': os.getenv('CTRADER_REFRESH_TOKEN')
        }
        self.ctrader_client = None
        self.ctrader_connected = False
        self.ctrader_account_id = None
        self.ctrader_symbol_ids = {}
        
        # WebSocket клиент для Spread Service
        # В Docker используем имя контейнера, локально - localhost
        spread_host = os.getenv('SPREAD_SERVICE_HOST', 'localhost')
        self.spread_service_ws_url = f"ws://{spread_host}:8093/ctrader"
        self.websocket = None
        self.websocket_connected = False
        self.websocket_loop = None
        
        # WebSocket клиент для TradingView Bridge
        self.tradingview_bridge_ws_url = "ws://localhost:8096/ctrader"
        self.tradingview_websocket = None
        self.tradingview_connected = False
        
        # Флаг для остановки
        self.running = False
        
        # Мониторинг обновлений
        self.last_quote_time = {}  # Время последнего обновления для каждого символа
        self.stale_data_threshold = 60  # Секунд без обновления = устаревшие данные
        self.reconnect_flag = False  # Флаг необходимости переподключения

    def start_ctrader_client(self):
        """Запуск cTrader клиента"""
        if not CTRADER_AVAILABLE:
            logger.warning("❌ cTrader SDK недоступен")
            return
            
        try:
            logger.info("🔧 Инициализация cTrader клиента...")
            
            # Создаем клиент
            self.ctrader_client = Client("live.ctraderapi.com", 5035, TcpProtocol)
            
            # Настраиваем callbacks
            self.ctrader_client.setConnectedCallback(self._ctrader_connected_callback)
            self.ctrader_client.setDisconnectedCallback(self._ctrader_disconnected_callback)
            self.ctrader_client.setMessageReceivedCallback(self._ctrader_message_received_callback)
            
            # Запускаем в отдельном потоке
            def run_client():
                try:
                    self.ctrader_client.startService()
                    reactor.run(installSignalHandlers=False)
                except Exception as e:
                    logger.error(f"❌ Ошибка cTrader клиента: {e}")
            
            self.client_thread = threading.Thread(target=run_client, daemon=True)
            self.client_thread.start()
            
            logger.info("✅ cTrader клиент запущен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска cTrader клиента: {e}")

    def _ctrader_connected_callback(self, client):
        """Callback подключения cTrader"""
        logger.info("🌐 cTrader подключено!")
        self.ctrader_connected = True
        
        # Аутентификация приложения
        request = ProtoOAApplicationAuthReq()
        request.clientId = self.ctrader_config['client_id']
        request.clientSecret = self.ctrader_config['client_secret']
        
        deferred = client.send(request)
        deferred.addErrback(self._ctrader_on_error)

    def _ctrader_disconnected_callback(self, client, reason):
        """Callback отключения cTrader"""
        logger.warning(f"🛑 cTrader отключено: {reason}")
        self.ctrader_connected = False
        self.reconnect_flag = True
        
        # Переподключение через 5 секунд
        logger.info("🔄 Переподключение к cTrader через 5 секунд...")
        time.sleep(5)
        if self.running:
            try:
                logger.info("🔄 Попытка переподключения к cTrader...")
                self.start_ctrader_client()
            except Exception as e:
                logger.error(f"❌ Ошибка переподключения к cTrader: {e}")

    def _ctrader_message_received_callback(self, client, message):
        """Callback получения сообщений cTrader"""
        try:
            if message.payloadType == ProtoOAApplicationAuthRes().payloadType:
                self._ctrader_on_application_auth_response(message)
            elif message.payloadType == ProtoOAGetAccountListByAccessTokenRes().payloadType:
                self._ctrader_on_account_list_response(message)
            elif message.payloadType == ProtoOAAccountAuthRes().payloadType:
                self._ctrader_on_account_auth_response(message)
            elif message.payloadType == ProtoOASymbolsListRes().payloadType:
                self._ctrader_on_symbols_list_response(message)
            elif message.payloadType == ProtoOASubscribeSpotsRes().payloadType:
                self._ctrader_on_subscribe_spots_response(message)
            elif message.payloadType == ProtoOASpotEvent().payloadType:
                self._ctrader_on_spot_event(message)
            elif message.payloadType == ProtoErrorRes().payloadType:
                self._ctrader_on_error_response(message)
        except Exception as e:
            logger.error(f"❌ Ошибка обработки cTrader сообщения: {e}")

    def _ctrader_on_error(self, failure):
        """Обработчик ошибок cTrader"""
        logger.error(f"❌ cTrader ошибка: {failure}")

    def _ctrader_on_application_auth_response(self, message):
        """Обработка аутентификации приложения"""
        logger.info("✅ cTrader приложение авторизовано!")
        
        # Запрашиваем список аккаунтов
        request = ProtoOAGetAccountListByAccessTokenReq()
        request.accessToken = self.ctrader_config['access_token']
        deferred = self.ctrader_client.send(request)
        deferred.addErrback(self._ctrader_on_error)

    def _ctrader_on_account_list_response(self, message):
        """Обработка списка аккаунтов"""
        extracted = Protobuf.extract(message)
        accounts = extracted.ctidTraderAccount
        
        if accounts:
            # Ищем аккаунт с номером 8235436
            target_account_number = 8235436
            target_account = None
            
            logger.info(f"📋 Получено аккаунтов: {len(accounts)}")
            for account in accounts:
                # Проверяем доступные атрибуты
                logger.info(f"   - ID: {account.ctidTraderAccountId}")
                logger.info(f"   - Атрибуты: {[attr for attr in dir(account) if not attr.startswith('_')]}")
                
                # Пробуем разные возможные атрибуты для номера аккаунта
                account_num = None
                if hasattr(account, 'traderLogin'):
                    account_num = account.traderLogin
                elif hasattr(account, 'accountNumber'):
                    account_num = account.accountNumber
                elif hasattr(account, 'account_number'):
                    account_num = account.account_number
                elif hasattr(account, 'accountId'):
                    account_num = account.accountId
                elif hasattr(account, 'account_id'):
                    account_num = account.account_id
                
                logger.info(f"   - Номер аккаунта: {account_num}")
                
                if account_num == target_account_number:
                    target_account = account
                    break
            
            if target_account:
                self.ctrader_account_id = target_account.ctidTraderAccountId
                logger.info(f"🎯 Найден целевой cTrader аккаунт: {self.ctrader_account_id} (номер: {target_account_number})")
                
                # Авторизуемся в аккаунте
                request = ProtoOAAccountAuthReq()
                request.ctidTraderAccountId = self.ctrader_account_id
                request.accessToken = self.ctrader_config['access_token']
                deferred = self.ctrader_client.send(request)
                deferred.addErrback(self._ctrader_on_error)
            else:
                logger.error(f"❌ Не найден аккаунт с номером {target_account_number}")
                logger.info(f"📋 Доступные аккаунты:")
                for account in accounts:
                    logger.info(f"   - ID: {account.ctidTraderAccountId}")
        else:
            logger.error("❌ Аккаунты не найдены!")

    def _ctrader_on_account_auth_response(self, message):
        """Обработка авторизации аккаунта"""
        logger.info("✅ cTrader аккаунт авторизован!")
        
        # Запрашиваем список символов
        request = ProtoOASymbolsListReq()
        request.ctidTraderAccountId = self.ctrader_account_id
        deferred = self.ctrader_client.send(request)
        deferred.addErrback(self._ctrader_on_error)

    def _ctrader_on_symbols_list_response(self, message):
        """Обработка списка символов"""
        extracted = Protobuf.extract(message)
        symbols = extracted.symbol
        
        # Ищем нужные символы
        ctrader_symbols = [
            'XPDUSD', 'XPTUSD', 'XAGUSD', 'XAUUSD', '#Coffee_Z25',
            'USDCNH', 'EURCNH', 'EURUSD', '#USNDAQ100', '#USSPX500'
        ]
        symbols_found = {}
        
        for symbol in symbols:
            if symbol.symbolName in ctrader_symbols:
                self.ctrader_symbol_ids[symbol.symbolName] = symbol.symbolId
                symbols_found[symbol.symbolName] = symbol.symbolId
                logger.info(f"🎯 Найден cTrader {symbol.symbolName}! ID: {symbol.symbolId}")
        
        if symbols_found:
            # Подписываемся на котировки
            request = ProtoOASubscribeSpotsReq()
            request.ctidTraderAccountId = self.ctrader_account_id
            request.subscribeToSpotTimestamp = True
            
            for symbol_id in symbols_found.values():
                request.symbolId.append(symbol_id)
                
            deferred = self.ctrader_client.send(request)
            deferred.addErrback(self._ctrader_on_error)

    def _ctrader_on_subscribe_spots_response(self, message):
        """Обработка ответа на подписку"""
        logger.info("📡 Подписка на котировки cTrader успешна!")

    def _ctrader_on_spot_event(self, message):
        """Обработка real-time котировок cTrader"""
        try:
            extracted = Protobuf.extract(message)
            symbol_id = extracted.symbolId
            
            # Находим символ по ID
            symbol_name = None
            for name, sid in self.ctrader_symbol_ids.items():
                if sid == symbol_id:
                    symbol_name = name
                    break
            
            if not symbol_name or symbol_name not in self.symbols_data:
                return
                
            bid = extracted.bid / 100000
            ask = extracted.ask / 100000
            
            # Умная фильтрация (только bid, ask, last_update)
            if bid > 0:
                self.symbols_data[symbol_name]['bid'] = bid
            if ask > 0:
                self.symbols_data[symbol_name]['ask'] = ask
                
            # Обновляем время
            try:
                timestamp = extracted.timestamp
                self.symbols_data[symbol_name]['last_update'] = timestamp_to_moscow(timestamp)
            except Exception:
                self.symbols_data[symbol_name]['last_update'] = now_moscow()
            
            current_bid = self.symbols_data[symbol_name]['bid']
            current_ask = self.symbols_data[symbol_name]['ask']
            
            # Обновляем время последнего обновления для мониторинга
            self.last_quote_time[symbol_name] = time.time()
            
            # Логируем каждое обновление для мгновенного мониторинга
            logger.info(f"🔄 {symbol_name} обновлен: Bid={current_bid}, Ask={current_ask}")
            
            # Отправляем данные в Spread Service через WebSocket
            self.send_data_to_spread_service(symbol_name)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки cTrader Spot Event: {e}")
    
    def check_stale_data(self):
        """Проверка устаревших данных и переподключение при необходимости"""
        try:
            current_time = time.time()
            stale_symbols = []
            
            for symbol in self.symbols_data.keys():
                if symbol in self.last_quote_time:
                    time_since_update = current_time - self.last_quote_time[symbol]
                    if time_since_update > self.stale_data_threshold:
                        stale_symbols.append(symbol)
            
            if stale_symbols:
                logger.warning(f"⚠️ Устаревшие данные для cTrader символов: {stale_symbols}")
                
                # Если cTrader не подключен, пытаемся переподключиться
                if not self.ctrader_connected:
                    logger.info("🔄 cTrader отключен, попытка переподключения...")
                    try:
                        self.start_ctrader_client()
                    except Exception as e:
                        logger.error(f"❌ Ошибка переподключения cTrader: {e}")
                else:
                    logger.info("⚠️ cTrader подключен, но данные не обновляются")
                    # Можно добавить принудительную переподписку
                            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки устаревших данных: {e}")

    async def connect_to_spread_service(self):
        """Подключение к Spread Service через WebSocket"""
        self.websocket_loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                logger.info(f"🔌 Подключение к Spread Service: {self.spread_service_ws_url}")
                async with websockets.connect(self.spread_service_ws_url) as websocket:
                    self.websocket = websocket
                    self.websocket_connected = True
                    logger.info("✅ Подключен к Spread Service")
                    
                    # Отправляем начальные данные
                    await self.send_all_data_to_spread_service()
                    
                    # Ждем сообщения (keep-alive)
                    async for message in websocket:
                        # Обрабатываем сообщения от Spread Service если нужно
                        pass
                        
            except Exception as e:
                logger.error(f"❌ Ошибка WebSocket подключения: {e}")
                self.websocket_connected = False
                await asyncio.sleep(5)  # Переподключение через 5 секунд

    def send_data_to_spread_service(self, symbol):
        """Отправка данных символа в Spread Service"""
        if not self.websocket_connected or not self.websocket or not self.websocket_loop:
            return
        
        # Мгновенная отправка без ограничений частоты
        try:
            symbol_data = self.symbols_data[symbol].copy()
            if symbol_data['last_update'] and hasattr(symbol_data['last_update'], 'isoformat'):
                symbol_data['last_update'] = symbol_data['last_update'].isoformat()
            
            message = {
                'type': 'ctrader_data',
                'symbol': symbol,
                'data': symbol_data
            }
            
            # Отправляем в event loop
            future = asyncio.run_coroutine_threadsafe(
                self.websocket.send(json.dumps(message, ensure_ascii=False)), 
                self.websocket_loop
            )
            # Не ждем результата, чтобы не блокировать
            future.add_done_callback(lambda f: None)  # Игнорируем результат
            
        except Exception as e:
            # Не логируем каждую ошибку, чтобы не засорять память
            pass
    
    def send_data_to_tradingview_bridge(self, symbol, message):
        """Отправка данных в TradingView Bridge (для платформы Горячие Парни)"""
        # Проверяем, включен ли TradingView Bridge через env переменную
        if not os.getenv('ENABLE_TRADINGVIEW_BRIDGE', 'false').lower() == 'true':
            return
        
        if not self.tradingview_connected or not self.tradingview_websocket or not self.websocket_loop:
            return
            
        try:
            # Отправляем в event loop
            asyncio.run_coroutine_threadsafe(
                self.tradingview_websocket.send(json.dumps(message)), 
                self.websocket_loop
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки данных в TradingView Bridge: {e}")

    async def send_all_data_to_spread_service(self):
        """Отправка всех данных в Spread Service"""
        if not self.websocket_connected or not self.websocket:
            return
            
        try:
            for symbol in self.symbols_data:
                self.send_data_to_spread_service(symbol)
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки всех данных в Spread Service: {e}")

    def _ctrader_on_error_response(self, message):
        """Обработка ошибок cTrader"""
        extracted = Protobuf.extract(message)
        logger.error(f"❌ cTrader API ошибка: {extracted.errorCode} - {extracted.description}")

    def get_symbol_data(self, symbol):
        """Получение данных символа"""
        return self.symbols_data.get(symbol)

    def get_all_data(self):
        """Получение всех данных"""
        return self.symbols_data.copy()

    def start(self):
        """Запуск сервиса"""
        logger.info("🚀 Запуск cTrader Service...")
        self.running = True
        
        # Запускаем cTrader клиент
        self.start_ctrader_client()
        
        # Запускаем WebSocket клиент для Spread Service
        def run_websocket_client():
            asyncio.run(self.connect_to_spread_service())
        
        websocket_thread = threading.Thread(target=run_websocket_client, daemon=True)
        websocket_thread.start()
        
        # TradingView Bridge функция (только если включен)
        async def connect_to_tradingview_bridge():
            while self.running:
                try:
                    logger.info(f"🔌 Подключение к TradingView Bridge: {self.tradingview_bridge_ws_url}")
                    async with websockets.connect(self.tradingview_bridge_ws_url) as websocket:
                        self.tradingview_websocket = websocket
                        self.tradingview_connected = True
                        logger.info("✅ Подключен к TradingView Bridge")
                        
                        # Отправляем начальные данные напрямую через WebSocket
                        for symbol, symbol_data in self.symbols_data.items():
                            try:
                                data_copy = symbol_data.copy()
                                if data_copy['last_update'] and hasattr(data_copy['last_update'], 'isoformat'):
                                    data_copy['last_update'] = data_copy['last_update'].isoformat()
                                
                                message = {
                                    'type': 'ctrader_data',
                                    'symbol': symbol,
                                    'data': data_copy
                                }
                                await websocket.send(json.dumps(message))
                                logger.info(f"📤 Отправлены начальные данные {symbol} в TradingView Bridge")
                            except Exception as e:
                                logger.error(f"❌ Ошибка отправки начальных данных {symbol}: {e}")
                        
                        # Ждем сообщения (keep-alive)
                        async for message in websocket:
                            pass
                            
                except Exception as e:
                    logger.error(f"❌ Ошибка подключения к TradingView Bridge: {e}")
                    self.tradingview_connected = False
                    await asyncio.sleep(5)  # Переподключение через 5 секунд
        
        # TradingView Bridge (для платформы Горячие Парни) - включается через ENABLE_TRADINGVIEW_BRIDGE=true в .env
        # TradingView Bridge отключен по умолчанию
        if os.getenv('ENABLE_TRADINGVIEW_BRIDGE', 'false').lower() == 'true':
            def run_tradingview_websocket_client():
                asyncio.run(connect_to_tradingview_bridge())
            
            tradingview_thread = threading.Thread(target=run_tradingview_websocket_client, daemon=True)
            tradingview_thread.start()
            logger.info("🔥 TradingView Bridge для Горячих Парней включен")
        else:
            logger.info("💤 TradingView Bridge отключен (для включения: ENABLE_TRADINGVIEW_BRIDGE=true)")
            # НЕ запускаем TradingView Bridge - функция не вызывается
        
        logger.info("🌐 cTrader Service запущен")
        logger.info(f"🔍 Мониторинг устаревших данных: порог {self.stale_data_threshold} секунд")
        
        try:
            # Основной цикл с мониторингом
            check_interval = 60  # Проверяем каждые 60 секунд (было 30)
            counter = 0
            while self.running:
                time.sleep(1)
                counter += 1
                
                # Каждые 60 секунд проверяем устаревшие данные
                if counter >= check_interval:
                    self.check_stale_data()
                    counter = 0
                    
        except KeyboardInterrupt:
            logger.info("🛑 Остановка cTrader Service...")
            self.running = False

# HTTP API больше не нужен - используем только WebSocket

def main():
    """Главная функция"""
    print("🚀 Запуск cTrader Service...")
    print("📊 WebSocket клиент для Spread Service")
    print("🛑 Для остановки нажмите Ctrl+C")
    print()
    
    service = cTraderService()
    try:
        service.start()
    except KeyboardInterrupt:
        print("\n🛑 cTrader Service остановлен")

if __name__ == "__main__":
    main()
