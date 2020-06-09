import sys, os, atexit, pickle, pdb
import socket, socketserver
from concurrent.futures import ThreadPoolExecutor, wait
from func import DictDB

PROMT = "%s> "
# Список текущих чат-клиентов. Key-Value БД формата port: username
peers_db = DictDB("client.txt")

stop = False  #остановка потоков
cl = {}  #люди в сети
threads = []


# Вспомогательные классы и функции

class Event:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    event_type = None  #REGISTER или MESSAGE
    username = None  #имя пользователя
    server_port = None  #Адрес слушающего порта нового клиента
    message = None  #Текст сообщения


#Участник чата
class ChatPeer:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    username = None
    port = None  #номер сокета
    socket = None  #открытый сокет


def create_socket(port):
    sock = socket.socket(socket.AF_INET)
    sock.connect(("localhost", port))
    return sock

#передать сообщение
def broadcast(event):
    for c in cl.values():
        c.socket.send(pickle.dumps(event))


#ввод и рассылка сообщений
def input_message_thread():
    while not stop:
        message = input()
        broadcast(Event(
            event_type="MESSAGE", username=username, message=message))


def read_data(rsock):
    CHUNK_SIZE = 16 * 1024
    data = b""
    chunk = rsock.recv(CHUNK_SIZE)
    return chunk

#слушает поступающие события
def server_thread(sock):
    sock.listen(1)

    def process_event(event):
        if event.event_type == "REGISTER":
            port = event.server_port
            socket = create_socket(port)
            cl[port] = ChatPeer(
                username=event.username, server_port=port, socket=socket)
            print("Пользователь %s вошел в чат." % event.username)
        elif event.event_type == "MESSAGE":
            print(PROMT % event.username + event.message.strip())
        else:
            raise RuntimeError("Пришло сообщение с некорректным типом %s" % event.event_type)

    def client_listen_thread(csock):
        while not stop:
            event = pickle.loads(read_data(csock))
            process_event(event)

    while not stop:
        csock, addr = sock.accept()
        thread = executor.submit(client_listen_thread, csock)
        threads.append(thread)

    sock.close()


# Управление поднятием и остановкой нашего чат-клиента
#Определяем имя пользователя
def input_username():
    used_usernames = peers_db.keys()

    while True:
        username = input("Введите логин: ")

        # Проверяем, что оно не занято %TODO
        if username not in used_usernames:
            print("Добро пожаловать!")
            break
    return username

#входим в чаь
def connect_to_people(server_port):
    # Соединяемся с пользователями в файле

    for port, user in list(peers_db.items()):
        port = int(port)
        try:
            socket = create_socket(port)
            cl[port] = ChatPeer(username=user,
                                   port=port,
                                   socket=socket)

        except ConnectionError:
            # Такого пира уже нет в сети
            del peers_db[str(port)]

    #добавляем себя в список клиентов
    peers_db[server_port] = username

    #представляемся другим клиентам
    broadcast(Event(
        event_type="REGISTER", username=username, server_port=server_port))




if __name__ == "__main__":

    executor = ThreadPoolExecutor(max_workers=100)
    port = None

    #cпрашиваем имя юзера
    username = input_username()

    #однимаем сервер для приема сообщений
    sock = socket.socket()
    sock.bind(("localhost", 0))
    server_future = executor.submit(server_thread, sock)
    port = sock.getsockname()[1]

    #Пользователь вошел в чат
    connect_to_people(port)

    #запускаем прием и отправку сообщений
    input_future = executor.submit(input_message_thread)

    threads.extend([server_future, input_future])
    wait([server_future, input_future])
