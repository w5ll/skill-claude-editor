"""Senha de sessão e conferência de origem do painel.

O painel passou a executar a edição, então não basta ouvir só em 127.0.0.1: uma página aberta em outro
site do mesmo navegador poderia falar com ele. Cada vez que o painel abre, nasce um código aleatório; o
endereço com o código aparece no terminal e abre sozinho, o código vira um cookie (HttpOnly, SameSite=Strict)
e sai do endereço. Sem o cookie, a API e os arquivos respondem 401.

Conferências por pedido:
- Host: tem que ser localhost ou 127.0.0.1 com a porta do painel (barra o truque de trocar o nome da máquina).
- Origin, se vier: tem que ser a do próprio painel.
- Pedidos que mudam algo (POST e PUT): têm que trazer o cabeçalho X-Painel: 1.
"""

from __future__ import annotations

import hmac
import secrets
from http.cookies import SimpleCookie

NOME_DO_COOKIE = "painel"
CABECALHO = "X-Painel"


class Sessao:
    def __init__(self, porta: int, codigo: str | None = None):
        self.porta = porta
        self.codigo = codigo or secrets.token_urlsafe(24)
        self.hosts = {f"localhost:{porta}", f"127.0.0.1:{porta}"}
        self.origens = {f"http://{h}" for h in self.hosts}

    def host_ok(self, host: str | None) -> bool:
        return (host or "").strip().lower() in self.hosts

    def origem_ok(self, origem: str | None) -> bool:
        """Sem Origin (curl, o próprio navegador em pedido simples) passa; com Origin, só a do painel."""
        return origem is None or origem.strip().lower() in self.origens

    def codigo_ok(self, codigo: str | None) -> bool:
        return bool(codigo) and hmac.compare_digest(str(codigo), self.codigo)

    def cookie_ok(self, cabecalho_cookie: str | None) -> bool:
        if not cabecalho_cookie:
            return False
        try:
            c = SimpleCookie()
            c.load(cabecalho_cookie)
        except Exception:  # noqa: BLE001  (cookie malformado é só "sem sessão")
            return False
        m = c.get(NOME_DO_COOKIE)
        return bool(m) and self.codigo_ok(m.value)

    @staticmethod
    def cabecalho_ok(valor: str | None) -> bool:
        return valor == "1"

    def set_cookie(self) -> str:
        return f"{NOME_DO_COOKIE}={self.codigo}; Path=/; HttpOnly; SameSite=Strict"

    def endereco(self) -> str:
        return f"http://localhost:{self.porta}/?s={self.codigo}"
