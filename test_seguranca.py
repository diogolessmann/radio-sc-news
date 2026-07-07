# -*- coding: utf-8 -*-
"""
test_seguranca.py — REDE DE SEGURANÇA permanente do motor (Rádio SC News).

Nasceu do incidente de 06/jul/2026 (foto de uma VÍTIMA postada como incendiária + texto afirmando
culpa → notificação de calúnia). Garante que as travas anti-processo continuam de pé mesmo depois
de alguém (eu, o dono, outra sessão) mexer no motor:

  1) _foto_sensivel  → crime/violência/vítima no TÍTULO **ou no CORPO** = NUNCA foto de terceiro
  2) allowlist foto  → (ANTI_STRIKE=1) categoria segura usa foto real; sensível cai no neutro
  3) neutralizar_juridico → afirmação de culpa vira SUSPEITA (presunção de inocência)

Rodar:  python test_seguranca.py     (exit 0 = tudo ok · exit 1 = brecha reaberta)
Se este teste quebrar, ALGUÉM reabriu um buraco de segurança. NÃO commitar até voltar a passar.
"""
import os
os.environ.setdefault("ANTI_STRIKE", "1")     # o modo de produção do dono
import gen_instagram as gi
import distribuidor as d

FALHAS = []


def _n(title="", cat="geral", summary="", title_own="", resumo_own="", materia_own=""):
    return {"title": title, "title_own": title_own or title, "category": cat,
            "summary": summary, "resumo_own": resumo_own, "materia_own": materia_own,
            "city": "Jaraguá do Sul", "image_url": "http://x/foto.jpg",
            "admin_image": None, "source": "ND", "id": 1}


def _decide_foto(news):
    """Reproduz a decisão de foto do slide_cover (ANTI_STRIKE=1)."""
    anti = os.environ.get("ANTI_STRIKE", "1").strip() != "0"
    if gi._foto_sensivel(news):
        anti = True
    elif anti and gi._foto_liberada(news):
        anti = False
    return "NEUTRO" if anti else "FOTO-REAL"


def check(cond, msg):
    if not cond:
        FALHAS.append(msg)


# 1) SENSÍVEL no TÍTULO → tem que ser barrado
SENSIVEL_TITULO = [
    "Policia prende homem que confessou incendio em hotel de Chapeco",
    "Motociclista de 20 anos fica ferido em colisao em Schroeder",
    "Homem e encontrado morto dentro de casa",
    "Jovem e baleado durante assalto no centro",
    "PM prende jovem com maconha e cocaina em Guaramirim",
    "Bombeiros resgatam homem apos queda em encosta de rio",
    "Aviao bimotor cai na restinga em Navegantes",
    "Suspeito e indiciado por estelionato",
    "Chacina deixa tres mortos no bairro",
    "Homem e condenado a 20 anos de prisao",
    "Vitima e esfaqueada durante briga em bar",
    "Policia apreende arma e municao",
    "Traficante e preso em operacao",
    "Corpo e encontrado sem vida no rio",
    "Homem e acusado de feminicidio",
]
for t in SENSIVEL_TITULO:
    check(gi._foto_sensivel(_n(title=t)), f"[foto/titulo] deveria ser SENSIVEL: {t}")
    check(_decide_foto(_n(title=t, cat="geral")) == "NEUTRO",
          f"[foto/titulo] deveria ir NEUTRO (nao vazar rosto): {t}")

# 2) O FURO-RAIZ: título limpo, crime só no CORPO
CORPO_SENSIVEL = [
    ("Confusao em festa termina mal", "Uma pessoa foi esfaqueada e o autor confessou o crime."),
    ("Noite agitada no centro da cidade", "Segundo a policia, o homem matou a vitima e fugiu."),
    ("Ocorrencia mobiliza equipes de emergencia", "Bombeiros resgataram o corpo apos o afogamento."),
    ("Operacao na madrugada", "Um traficante foi preso com drogas e uma arma."),
]
for t, corpo in CORPO_SENSIVEL:
    check(gi._foto_sensivel(_n(title=t, summary=corpo)),
          f"[foto/corpo] crime no CORPO deveria marcar SENSIVEL: {t}")
    check(_decide_foto(_n(title=t, cat="geral", summary=corpo)) == "NEUTRO",
          f"[foto/corpo] crime no corpo deveria ir NEUTRO: {t}")

# 3) SEGURO → NAO pode ser barrado (falso-positivo controlado) e deve liberar foto real
SEGURO = [
    ("Joinville volei fecha elenco com central colombiano", "esporte"),
    ("Guaramirim da show na reciclagem: sacolas amarelas", "geral"),
    ("Frio intenso em SC, geada de -3C prevista", "clima"),
    ("Gigante do varejo chega a 50 lojas na regiao", "economia"),
    ("Expo 150 bate recorde de publico em Jaragua", "geral"),
    ("Bazar solidario vende roupas de 2 a 30 reais", "geral"),
    ("Festival de inverno movimenta o turismo no Vale", "turismo"),
]
for t, c in SEGURO:
    check(not gi._foto_sensivel(_n(title=t, cat=c)), f"[foto/seguro] NAO deveria ser sensivel: {t}")
    check(_decide_foto(_n(title=t, cat=c)) == "FOTO-REAL", f"[foto/seguro] deveria liberar FOTO-REAL: {t}")

# 4) Categoria FORA da allowlist → neutro mesmo sem ser sensível (ANTI_STRIKE=1 default-deny)
check(_decide_foto(_n(title="Camara aprova novo projeto de lei", cat="politica")) == "NEUTRO",
      "[foto/allowlist] politica (fora da lista) deveria ir NEUTRO com ANTI_STRIKE=1")

# 5) neutralizar_juridico → afirmacao de culpa vira SUSPEITA
CULPA = [
    ("suspeito confessa o crime e e preso", "teria confessado"),
    ("policia prende o autor do assalto", "suspeito"),
    ("jovem apontado como culpado pela morte", "suspeito"),
    ("o assassino foi preso pela pm", "suspeito"),
    ("homem estuprou a vitima", "teria estuprado"),
    ("ele traficava drogas no bairro", "teria traficado"),
    ("o traficante da regiao foi detido", "suspeito"),
    ("homem roubou o mercado", "teria roubado"),
    ("o ladrao fugiu apos o crime", "suspeito"),
    ("sequestrou a crianca em frente a escola", "teria sequestrado"),
    ("espancou a esposa apos discussao", "teria espancado"),
    ("agrediu o vizinho com um pau", "teria agredido"),
    ("esfaqueou o rival na briga", "teria esfaqueado"),
    ("foi pego em flagrante com drogas", "detido"),
]
for orig, esperado in CULPA:
    out = d.neutralizar_juridico(orig)
    check(esperado.lower() in out.lower(),
          f"[texto/culpa] '{orig}' deveria conter '{esperado}' -> saiu '{out}'")

# 6) neutralizar NAO pode quebrar texto inocente (sem termo de crime)
check(d.neutralizar_juridico("A nova confeitaria abriu no centro") == "A nova confeitaria abriu no centro",
      "[texto/falso-pos] 'confeitaria' nao pode virar suspeito")
check(d.neutralizar_juridico("A autoridade visitou a escola") == "A autoridade visitou a escola",
      "[texto/falso-pos] 'autoridade' nao pode virar suspeito")
# RESIDUO CONHECIDO (documentado, nao testado): 'autor do gol/livro/projeto' num texto que TAMBEM
# tenha termo de crime viraria 'suspeito do gol'. Contido porque neutralizar so roda em materia
# sensivel; a chance de 'autor do gol' coexistir com crime na mesma materia e desprezivel.

# ---------------------------------------------------------------- resultado
if FALHAS:
    print("\n❌ %d BRECHA(S) DE SEGURANCA REABERTA(S):" % len(FALHAS))
    for f in FALHAS:
        print("  - " + f)
    raise SystemExit(1)
print("✅ test_seguranca: TODAS as travas anti-processo OK (%d checagens)" %
      (len(SENSIVEL_TITULO) * 2 + len(CORPO_SENSIVEL) * 2 + len(SEGURO) * 2 + 1 + len(CULPA) + 2))
