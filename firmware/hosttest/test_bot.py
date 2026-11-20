#!/usr/bin/env python3
"""End-to-end test of the Telegram bot firmware code on a PC.

Runs hosttest/build/harness (telegram.cpp + tls_link.cpp + BearSSL, compiled for the host)
against a fake Bot API server over real TLS, and injects the network faults a relay sees on a
phone hotspot: connections that die silently (VPN switched on, mobile data lost), servers that
refuse or hang new connections, Wi-Fi loss, HTTP errors, odd responses. Each scenario checks
that commands keep being answered and how long recovery takes.

Usage: hosttest/build.sh && python3 hosttest/test_bot.py   (from firmware/)
"""
import asyncio
import json
import os
import ssl
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
TOKEN = "123456789:" + "A" * 35
USER = 111
POLL = 4  # TELEGRAM_POLL_SEC in build.sh
DEADLINE = POLL + 8  # long-poll response timeout in telegram.cpp


class FakeTelegram:
    def __init__(self):
        self.ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ctx.load_cert_chain(os.path.join(BUILD, "server.pem"), os.path.join(BUILD, "server.key"))
        self.updates, self.next_id, self.sent = [], 1, []
        self.cond = asyncio.Condition()
        self.epoch = 0             # bumping it makes every open connection go silent
        self.accept = "ok"         # ok | hang (TCP accepted, TLS never answered)
        self.close_each = False    # "Connection: close" after every response
        self.chunked = False
        self.fail_next = 0         # answer the next N requests with 502
        self.stall_next = 0        # send half of the next N responses, then go silent
        self.connections = 0
        self.methods = {}
        self.servers = {}
        self.port = None
        self.portal = None
        self.zombies = []
        self.tasks = []

    async def start(self, host="127.0.0.1"):
        srv = await asyncio.start_server(self.handle, host, self.port or 0, reuse_address=True)
        self.port = srv.sockets[0].getsockname()[1]
        self.servers[host] = srv

    async def stop_listening(self, host="127.0.0.1"):  # new connections are refused (RST)
        srv = self.servers.pop(host)
        srv.close()
        await srv.wait_closed()

    async def start_portal(self, host="127.0.0.2"):
        """A carrier's top-up portal: answers HTTPS with its own certificate."""
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(os.path.join(BUILD, "portal.pem"), os.path.join(BUILD, "portal.key"))

        async def page(reader, writer):
            try:
                await writer.start_tls(ctx)
                await reader.readuntil(b"\r\n\r\n")
                writer.write(b"HTTP/1.1 302 Found\r\nLocation: http://recargas.example/\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
            except Exception:
                pass
            writer.close()
        self.portal = await asyncio.start_server(page, host, self.port, reuse_address=True)

    def blackhole(self):  # open connections stop answering, without closing them
        self.epoch += 1

    async def silent(self, writer):
        self.zombies.append(writer)
        self.tasks.append(asyncio.current_task())  # keep a reference until the end
        await asyncio.Event().wait()

    async def handle(self, reader, writer):
        self.connections += 1
        if self.accept == "hang":
            return await self.silent(writer)
        try:
            await writer.start_tls(self.ctx)
        except Exception:
            writer.close()
            return
        epoch = self.epoch
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                if self.epoch != epoch:
                    return await self.silent(writer)
                lines = head.decode().split("\r\n")
                method = lines[0].split()[1].rsplit("/", 1)[1]
                length = next(int(l.split(":")[1]) for l in lines if l.lower().startswith("content-length"))
                body = json.loads(await reader.readexactly(length)) if length else {}
                self.methods[method] = self.methods.get(method, 0) + 1
                token = lines[0].split()[1].split("/")[1][3:]
                status, result = await self.api(method, body, token, epoch)
                if self.epoch != epoch:
                    return await self.silent(writer)
                await self.respond(writer, status, result)
                if self.close_each:
                    writer.close()
                    return
        except (asyncio.IncompleteReadError, ConnectionError, ssl.SSLError):
            writer.close()

    async def respond(self, writer, status, result):
        data = json.dumps(result).encode()
        hdr = "HTTP/1.1 %d %s\r\nServer: fake\r\nContent-Type: application/json\r\n" % (
            status, "OK" if status == 200 else "Error")
        if self.chunked:
            mid = len(data) // 2
            payload = b"".join(b"%x\r\n%s\r\n" % (len(c), c) for c in (data[:mid], data[mid:])) + b"0\r\n\r\n"
            hdr += "Transfer-Encoding: chunked\r\n"
        else:
            payload = data
            hdr += "Content-Length: %d\r\n" % len(data)
        hdr += "Connection: %s\r\n\r\n" % ("close" if self.close_each else "keep-alive")
        msg = hdr.encode() + payload
        if self.stall_next:
            self.stall_next -= 1
            writer.write(msg[: len(msg) // 2])
            await writer.drain()
            return await self.silent(writer)
        writer.write(msg)
        await writer.drain()

    async def api(self, method, body, token, epoch):
        if token != TOKEN:
            return 401, {"ok": False, "error_code": 401, "description": "Unauthorized"}
        if self.fail_next:
            self.fail_next -= 1
            return 502, {"ok": False, "error_code": 502, "description": "Bad Gateway"}
        if method == "getMe":
            return 200, {"ok": True, "result": {"id": 1, "is_bot": True, "username": "prueba_bot"}}
        if method == "setMyCommands":
            return 200, {"ok": True, "result": True}
        if method == "sendMessage":
            self.sent.append((time.time(), body["chat_id"], body["text"]))
            return 200, {"ok": True, "result": {"message_id": len(self.sent)}}
        if method == "getUpdates":
            off = body.get("offset", 0)
            self.updates = [u for u in self.updates if u["update_id"] >= off]
            if not self.updates and body.get("timeout"):
                async with self.cond:
                    try:
                        await asyncio.wait_for(self.cond.wait(), body["timeout"])
                    except asyncio.TimeoutError:
                        pass
                self.updates = [u for u in self.updates if u["update_id"] >= off]
            return 200, {"ok": True, "result": self.updates[: body.get("limit", 100)]}
        return 404, {"ok": False, "error_code": 404, "description": "Not Found"}

    async def say(self, text, user=USER, age=0):
        u = {"update_id": self.next_id, "message": {
            "message_id": self.next_id, "from": {"id": user, "is_bot": False, "first_name": "Ana"},
            "chat": {"id": user, "first_name": "Ana", "type": "private"},
            "date": int(time.time()) - age, "text": text}}
        self.next_id += 1
        self.updates.append(u)
        async with self.cond:
            self.cond.notify_all()
        return time.time()

    async def wait_reply(self, pred, since, timeout):
        end = time.time() + timeout
        while time.time() < end:
            for t, chat, text in self.sent:
                if t >= since and pred(chat, text):
                    return t
            await asyncio.sleep(0.05)
        return None


class Device:
    async def start(self, port, binary=None, **extra):
        env = dict(os.environ, TEST_PORT=str(port), TEST_TOKEN=TOKEN)
        env.update(extra)
        self.log = open(os.path.join(BUILD, "device.log"), "w")
        self.proc = await asyncio.create_subprocess_exec(
            os.path.join(BUILD, binary or os.environ.get("HARNESS", "harness")), env=env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=self.log)
        self.events = []
        asyncio.get_running_loop().create_task(self.read())

    async def read(self):
        while line := await self.proc.stdout.readline():
            self.events.append(line.decode().strip())

    async def cmd(self, c):
        self.proc.stdin.write((c + "\n").encode())
        await self.proc.stdin.drain()

    async def stats(self):
        n = len(self.events)
        await self.cmd("stats")
        for _ in range(100):
            for e in self.events[n:]:
                if e.startswith("EVENT stats "):
                    js, heap = e[12:].rsplit(" heap=", 1)
                    return json.loads(js), int(heap)
            await asyncio.sleep(0.02)

    async def stop(self):
        await self.cmd("quit")
        await self.proc.wait()


results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("%s  %-62s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)


async def command(tg, text, expect, timeout, user=USER, age=0):
    t0 = await tg.say(text, user=user, age=age)
    t = await tg.wait_reply(lambda c, x: c == user and expect in x, t0, timeout)
    return None if t is None else t - t0


async def main():
    tg = FakeTelegram()
    await tg.start()
    dev = Device()
    await dev.start(tg.port)

    # 1. Start-up: getMe, command menu, "en línea" notification
    t = await tg.wait_reply(lambda c, x: "está en línea" in x, 0, 15)
    check("arranque: aviso «en línea» enviado", t is not None,
          "methods=%s" % {k: v for k, v in tg.methods.items()})

    # 2. Basic commands
    d = await command(tg, "/estado", "Apagado", 5)
    check("/estado responde", d is not None, "%.2f s" % (d or -1))
    d = await command(tg, "Encender", "Encendido", 5)
    check("botón «Encender» enciende y responde", d is not None and "EVENT relay on telegram" in dev.events,
          "%.2f s" % (d or -1))
    d = await command(tg, "/start", "Tu ID de Telegram es 999", 5, user=999)
    check("usuario no autorizado recibe solo su ID", d is not None)
    d = await command(tg, "/apagar", "ignorada", 5, age=300)
    check("orden atrasada 5 min: no se ejecuta y se avisa",
          d is not None and "EVENT relay off telegram" not in dev.events)

    # 3. VPN switched on and off on the hotspot phone: the open connection dies silently
    tg.blackhole()
    await asyncio.sleep(0.5)
    d = await command(tg, "/apagar", "Apagado", DEADLINE + 15)
    check("conexión muerta en silencio (VPN): se recupera sola", d is not None,
          "respuesta en %.1f s (límite %d s)" % (d or -1, DEADLINE + 15))

    # 4. Internet lost for 60 s: old connection silent, new connections refused
    tg.blackhole()
    await tg.stop_listening()
    await asyncio.sleep(60)
    await tg.start()
    d = await command(tg, "/estado", "Apagado", 45)
    check("sin internet 60 s (conexiones rechazadas): vuelve", d is not None,
          "respuesta %.1f s después de volver internet" % (d or -1))

    # 5. Same, but new connections hang (TCP accepted, TLS never answers)
    tg.blackhole()
    tg.accept = "hang"
    await asyncio.sleep(60)
    tg.accept = "ok"
    d = await command(tg, "/estado", "Apagado", 60)
    check("sin internet 60 s (conexiones colgadas): vuelve", d is not None,
          "respuesta %.1f s después de volver internet" % (d or -1))

    # 5b. Phone out of credit: no Internet, and the carrier's DNS answers every name with its
    # top-up portal. After the top-up, the DNS answer stays wrong for a while (cache, TTL).
    await tg.start_portal()
    tg.blackhole()
    await tg.stop_listening()
    await dev.cmd("dns 127.0.0.2")
    await asyncio.sleep(90)
    await tg.start()  # credit topped up: Telegram reachable again, DNS still says "portal"
    d = await command(tg, "/estado", "Apagado", 60)
    check("sin saldo + DNS del portal en caché: vuelve tras recargar", d is not None,
          "respuesta %.1f s después de recargar" % (d or -1))
    await dev.cmd("dns 127.0.0.1")

    # 5c. Telegram moves to a new address: the old one stops answering, DNS gives the new one
    tg.blackhole()
    await tg.stop_listening()
    await tg.start("127.0.0.3")
    await dev.cmd("dns 127.0.0.3")
    d = await command(tg, "/estado", "Apagado", 60)
    check("Telegram cambia de dirección: la encuentra por DNS", d is not None, "%.1f s" % (d or -1))
    check("guarda la dirección nueva como verificada", "EVENT saved tgIp=127.0.0.3" in dev.events)
    await tg.start()
    await dev.cmd("dns 127.0.0.1")

    # 5d. DNS completely down but the internet works: the verified address is enough
    await dev.cmd("dns fail")
    tg.blackhole()
    d = await command(tg, "/estado", "Apagado", DEADLINE + 25)
    check("DNS caído: usa la dirección verificada", d is not None, "%.1f s" % (d or -1))
    await dev.cmd("dns 127.0.0.1")

    # 6. Wi-Fi lost and back
    await dev.cmd("wifi 0")
    await asyncio.sleep(10)
    await dev.cmd("wifi 1")
    d = await command(tg, "/estado", "Apagado", 15)
    check("Wi-Fi perdido 10 s y recuperado", d is not None, "%.1f s" % (d or -1))

    # 7. Server closes the connection after every response (keep-alive limit)
    tg.close_each = True
    oks = [await command(tg, "/estado", "Apagado", 10) for _ in range(5)]
    tg.close_each = False
    check("servidor cierra tras cada respuesta", all(oks), "%s" % ["%.2f" % (x or -1) for x in oks])

    # 8. Chunked responses
    tg.chunked = True
    d = await command(tg, "/estado", "Apagado", 10)
    tg.chunked = False
    check("respuestas «chunked»", d is not None)

    # 9. 502 errors from Telegram
    tg.fail_next = 3
    d = await command(tg, "/estado", "Apagado", 30)
    check("tres errores 502 seguidos: se recupera", d is not None, "%.1f s" % (d or -1))

    # 10. Response cut in the middle, then silence
    tg.stall_next = 1
    d = await command(tg, "/estado", "Apagado", DEADLINE + 15)
    check("respuesta cortada a medias: se recupera", d is not None, "%.1f s" % (d or -1))

    # 11. Very long message: skipped, sender told, next command fine
    d = await command(tg, "x" * 5000, "demasiado largo", 10)
    d2 = await command(tg, "/estado", "Apagado", 10)
    check("mensaje enorme: se descarta con aviso y sigue funcionando", d is not None and d2 is not None)

    # 12. Each command answered exactly once (no duplicates after all the reconnections)
    n = len(tg.sent)
    t0 = await tg.say("/id")
    await asyncio.sleep(POLL + 2)
    replies = [s for s in tg.sent[n:] if "Tu ID" in s[2]]
    check("cada orden se responde una sola vez", len(replies) == 1, "%d respuestas" % len(replies))

    # 13. Memory: many reconnections must not grow the heap (TLS memory is reserved once)
    st0, heap0 = await dev.stats()
    soak = int(os.environ.get("SOAK", "40"))
    tg.close_each = True
    for _ in range(soak):
        await command(tg, "/estado", "Apagado", 10)
    tg.close_each = False
    st1, heap1 = await dev.stats()
    check("%d reconexiones más: memoria estable" % soak,
          heap1 - heap0 < 4096 and st1["connects"] - st0["connects"] >= soak,
          "conexiones %d→%d, heap en uso %d→%d B" % (st0["connects"], st1["connects"], heap0, heap1))
    allocs = sum("TLS memory reserved" in l for l in open(os.path.join(BUILD, "device.log")))
    check("memoria TLS reservada una sola vez", allocs == 1, "%d veces" % allocs)

    # 14. /reiniciar: acknowledged to Telegram before restarting, so it is not repeated
    d = await command(tg, "/reiniciar", "Reiniciando", 10)
    await asyncio.sleep(3)
    restarts = dev.events.count("EVENT restart")
    check("/reiniciar: confirma y reinicia una vez", d is not None and restarts == 1,
          "%d reinicios" % restarts)

    st, heap = await dev.stats()
    print("\nestadísticas finales:", st)
    await dev.stop()
    failed = [r for r in results if not r[1]]
    print("\n%d/%d pruebas superadas" % (len(results) - len(failed), len(results)))
    for w in tg.zombies:
        w.transport.abort()
    for t in asyncio.all_tasks():
        if t is not asyncio.current_task():
            t.cancel()
    return 1 if failed else 0


async def watchdog_suite():
    """Watchdog, with harness_wd: 5 s bot reset, 10 s Wi-Fi rejoin (then every 30 s), 60 s restart."""
    tg = FakeTelegram()
    await tg.start()
    dev = Device()
    await dev.start(tg.port, "harness_wd")
    t = await tg.wait_reply(lambda c, x: "está en línea" in x, 0, 15)
    check("vigilante: arranque normal", t is not None)
    await dev.cmd("relay 1")
    await asyncio.sleep(0.5)

    # No Internet for 75 s with the relay ON: bot reset, Wi-Fi rejoins, never a restart
    tg.blackhole()
    await tg.stop_listening()
    await asyncio.sleep(75)
    log = open(os.path.join(BUILD, "device.log")).read()
    rejoins = dev.events.count("EVENT wifi-reconnect")
    check("vigilante: reinicia la conexión del bot", "watchdog: restarting the bot connection" in log)
    check("vigilante: reconecta el Wi-Fi (10 s, luego cada 30 s)", 2 <= rejoins <= 3, "%d veces" % rejoins)
    check("vigilante: con el relé encendido nunca reinicia", "EVENT restart" not in dev.events)

    # Internet back: answers again and the watchdog counter starts over
    await tg.start()
    d = await command(tg, "/estado", "Encendido", 30)
    st, _ = await dev.stats()
    check("vigilante: vuelve a responder y pone el contador a cero", d is not None and st["silentSec"] < 5,
          "%.1f s, silentSec=%s" % (d or -1, st["silentSec"]))

    # No Internet again, relay OFF: restart after 60 s of silence, not before
    await dev.cmd("relay 0")
    await asyncio.sleep(0.5)
    tg.blackhole()
    await tg.stop_listening()
    t0 = time.time()
    while "EVENT restart" not in dev.events and time.time() - t0 < 120:
        await asyncio.sleep(0.2)
    took = time.time() - t0
    check("vigilante: con el relé apagado reinicia a los 60 s", "EVENT restart" in dev.events and 55 <= took <= 80,
          "%.0f s" % took)
    check("vigilante: deja la marca en la memoria RTC", any(e.startswith("EVENT rtc restarts=1") for e in dev.events))
    await dev.stop()

    # A wrong token gets HTTP 401 answers: Telegram is reachable, so no Wi-Fi rejoin, no restart
    await tg.start()
    dev3 = Device()
    await dev3.start(tg.port, "harness_wd", TEST_TOKEN="999:" + "B" * 35)
    await asyncio.sleep(70)
    check("token incorrecto: el vigilante no actúa (Telegram sí responde)",
          "EVENT wifi-reconnect" not in dev3.events and "EVENT restart" not in dev3.events)
    await dev3.stop()

    # Boot after a safety restart: relay kept off, notice says why
    dev2 = Device()
    await dev2.start(tg.port, "harness_wd", TEST_RTC="1,61")
    t = await tg.wait_reply(lambda c, x: "reinicio de seguridad" in x and "1 h 1 min" in x, time.time() - 1, 15)
    check("tras el reinicio de seguridad: lo detecta y lo explica en el aviso",
          t is not None and "EVENT safety-boot" in dev2.events)
    await dev2.stop()
    for w in tg.zombies:
        w.transport.abort()


async def run_all():
    code = 0
    if "--watchdog-only" not in sys.argv:
        code = await main()
    if "--no-watchdog" not in sys.argv:
        await watchdog_suite()
        failed = [r for r in results if not r[1]]
        print("\n%d/%d pruebas superadas en total" % (len(results) - len(failed), len(results)))
        code = 1 if failed else 0
    for t in asyncio.all_tasks():
        if t is not asyncio.current_task():
            t.cancel()
    return code


if __name__ == "__main__":
    sys.exit(asyncio.run(run_all()))
