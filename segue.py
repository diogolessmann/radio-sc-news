# -*- coding: utf-8 -*-
"""
segue.py — Post recorrente "SEGUE a Rádio" (conversão view→seguidor).
99k views/mês mas poucos seguem = vazamento. Este post lembra a galera de SEGUIR, em cadência
fixa (2x/semana), usando o card de marca já pronto (static/brand/card_segue.png).
Instagram-first: o pedido é SEGUIR (não WhatsApp).
"""
import os

import distribuidor as dist

CARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "brand", "card_segue.png")


def caption():
    tags = ("#nortedesc #valedoitapocu #jaraguadosul #schroeder #guaramirim "
            "#joinville #corupa #noticias #radioscnews")
    return (
        "➕ SEGUE @radiosc.news e não perca NADA do que acontece no Vale!\n\n"
        "📍 Jaraguá · Schroeder · Guaramirim · Joinville · Corupá\n"
        "🚨 Plantão · ☀️ Bom dia, Vale · 📅 Agenda do Vale\n\n"
        "O Norte de SC em 1 minuto. 🔔\n"
        "🔁 Marca um amigo da região pra seguir também!\n\n" + tags
    )


def run(post=False):
    """Posta (ou só checa) o card 'SEGUE'. Pula sem erro se o card não existir."""
    if not os.path.exists(CARD):
        return {"ok": False, "motivo": "card_segue.png não existe (gere o card de marca)"}
    if post:
        dist.publish_single("segue", CARD, caption())
    return {"ok": True, "postado": bool(post)}


if __name__ == "__main__":
    print(run(post=False))
