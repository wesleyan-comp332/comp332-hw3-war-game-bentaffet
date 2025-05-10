"""
war card game client and server
"""
import asyncio
from collections import namedtuple
from enum import Enum
import logging
import random
import socket
import socketserver
import threading
import sys


"""
Namedtuples work like classes, but are much more lightweight so they end
up being faster. It would be a good idea to keep objects in each of these
for each game which contain the game's state, for instance things like the
socket, the cards given, the cards still available, etc.
"""
Game = namedtuple("Game", ["p1", "p2"])

# Stores the clients waiting to get connected to other clients
waiting_clients = []


class Command(Enum):
    """
    The byte values sent as the first byte of any message in the war protocol.
    """
    WANTGAME = 0
    GAMESTART = 1
    PLAYCARD = 2
    PLAYRESULT = 3


class Result(Enum):
    """
    The byte values sent as the payload byte of a PLAYRESULT message.
    """
    WIN = 0
    DRAW = 1
    LOSE = 2

def run_game(game):
    try:
        # Step 1: Both clients must send WANTGAME
        msg1 = readexactly(game.p1, 2)
        msg2 = readexactly(game.p2, 2)
        if msg1[0] != Command.WANTGAME.value or msg2[0] != Command.WANTGAME.value:
            raise ValueError("Bad command received")

        # Step 2: Deal and send GAMESTART + 26 cards to each player
        hand1, hand2 = deal_cards()

        game.p1.sendall(bytes([Command.GAMESTART.value]) + bytes(hand1))
        game.p2.sendall(bytes([Command.GAMESTART.value]) + bytes(hand2))

        # Step 3: Play 26 rounds
        for i in range(26):
            # Read one card from each
            move1 = readexactly(game.p1, 2)
            move2 = readexactly(game.p2, 2)

            if move1[0] != Command.PLAYCARD.value or move2[0] != Command.PLAYCARD.value:
                raise ValueError("Bad play command")

            card1 = move1[1]
            card2 = move2[1]

            result = compare_cards(card1, card2)

            if result == 1:
                game.p1.sendall(bytes([Command.PLAYRESULT.value, Result.WIN.value]))
                game.p2.sendall(bytes([Command.PLAYRESULT.value, Result.LOSE.value]))
            elif result == -1:
                game.p1.sendall(bytes([Command.PLAYRESULT.value, Result.LOSE.value]))
                game.p2.sendall(bytes([Command.PLAYRESULT.value, Result.WIN.value]))
            else:
                game.p1.sendall(bytes([Command.PLAYRESULT.value, Result.DRAW.value]))
                game.p2.sendall(bytes([Command.PLAYRESULT.value, Result.DRAW.value]))

    except Exception as e:
        logging.error(f"Game error: {e}")
        kill_game(game)

def readexactly(sock, numbytes):
    """
    Accumulate exactly `numbytes` from `sock` and return those. If EOF is found
    before numbytes have been received, be sure to account for that here or in
    the caller.
    """
    data = b""
    while len(data) < numbytes:
        chunk = sock.recv(numbytes - len(data))
        if not chunk:
            raise ConnectionError
        data += chunk

    return data


def kill_game(game):
    """
    If either client sends a bad message, immediately nuke the game.
    """
    try:
        game.p1.close()
    except Exception:
        pass
    try:
        game.p1.close()
    except Exception:
        pass


def compare_cards(card1, card2):
    """
    TODO: Given an integer card representation, return -1 for card1 < card2,
    0 for card1 = card2, and 1 for card1 > card2
    """
    card1_rank = card1 % 13
    card2_rank = card2 % 13

    if (card1_rank < card2_rank):
        return -1
    elif (card1_rank > card2_rank):
        return 1
    else:
        return 0
    

    

def deal_cards():
    """
    TODO: Randomize a deck of cards (list of ints 0..51), and return two
    26 card "hands."
    """
    cards = list(range(52))
    random.shuffle(cards)
    hand1 = cards[:26]
    hand2 = cards[26:]

    return hand1, hand2


def serve_game(host, port):
    """
    TODO: Open a socket for listening for new connections on host:port, and
    perform the war protocol to serve a game of war between each client.
    This function should run forever, continually serving clients.

    1. Open socket
    2. If 2 or more players are connected, create a game 
    3. Thread

    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((host, port))
        server_sock.listen()

        while True:
                print("Waiting for Player 1...")
                p1, addr1 = server_sock.accept()
                print(f"Player 1 connected from {addr1}")

                print("Waiting for Player 2...")
                p2, addr2 = server_sock.accept()
                print(f"Player 2 connected from {addr2}")

                game = Game(p1, p2)
                print("game start")
                run_game(game)
                
                
    
    

async def limit_client(host, port, loop, sem):
    """
    Limit the number of clients currently executing.
    You do not need to change this function.
    """
    async with sem:
        return await client(host, port, loop)

async def client(host, port, loop):
    """
    Run an individual client on a given event loop.
    You do not need to change this function.
    """
    try:
        reader, writer = await asyncio.open_connection(host, port)
        # send want game
        writer.write(b"\0\0")
        card_msg = await reader.readexactly(27)
        myscore = 0
        for card in card_msg[1:]:
            writer.write(bytes([Command.PLAYCARD.value, card]))
            result = await reader.readexactly(2)
            if result[1] == Result.WIN.value:
                myscore += 1
            elif result[1] == Result.LOSE.value:
                myscore -= 1
        if myscore > 0:
            result = "won"
        elif myscore < 0:
            result = "lost"
        else:
            result = "drew"
        logging.debug("Game complete, I %s", result)
        writer.close()
        return 1
    except ConnectionResetError:
        logging.error("ConnectionResetError")
        return 0
    except asyncio.streams.IncompleteReadError:
        logging.error("asyncio.streams.IncompleteReadError")
        return 0
    except OSError:
        logging.error("OSError")
        return 0

def main(args):
    """
    launch a client/server
    """
    host = args[1]
    port = int(args[2])
    if args[0] == "server":
        try:
            # your server should serve clients until the user presses ctrl+c
            serve_game(host, port)
        except KeyboardInterrupt:
            pass
        return
    else:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        
        asyncio.set_event_loop(loop)
        
    if args[0] == "client":
        loop.run_until_complete(client(host, port, loop))
    elif args[0] == "clients":
        sem = asyncio.Semaphore(1000)
        num_clients = int(args[3])
        clients = [limit_client(host, port, loop, sem)
                   for x in range(num_clients)]
        async def run_all_clients():
            """
            use `as_completed` to spawn all clients simultaneously
            and collect their results in arbitrary order.
            """
            completed_clients = 0
            for client_result in asyncio.as_completed(clients):
                completed_clients += await client_result
            return completed_clients
        res = loop.run_until_complete(
            asyncio.Task(run_all_clients(), loop=loop))
        logging.info("%d completed clients", res)

    loop.close()

if __name__ == "__main__":
    # Changing logging to DEBUG
    logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1:])
