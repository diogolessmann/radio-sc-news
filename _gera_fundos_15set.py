# -*- coding: utf-8 -*-
# 15/set/26 — fundos novos pros temas mais repetidos (auditoria: 5 artes de IA em 200 posts). Roda 1x.
import sys, os, glob, re
sys.path.insert(0, r"C:\Users\Diogo\.claude\skills\criativo-dl\scripts")
from dlkit import gerar_imagem
from PIL import Image
BG = r"C:\Users\Diogo\Desktop\motor radio\static\bg"
EST = ("Fotografia jornalística realista, formato retrato 4:5, luz natural, cores frias com toque dourado, "
       "cidade pequena do sul do Brasil (Santa Catarina), SEM texto, SEM logotipo, SEM rosto reconhecível, "
       "sem sangue, sem vítima, sem placa de carro legível.")
CENAS = {
 "economia": ["Galpão industrial visto de fora ao amanhecer, caminhões carregando, bandeira do Brasil",
              "Mãos de trabalhador com luvas apertando parafuso em linha de montagem, foco raso"],
 "policial": ["Viatura da polícia estacionada em rua residencial à noite, luzes azuis refletindo no asfalto molhado, sem pessoas",
              "Fita de isolamento amarela em rua de bairro de dia, ao fundo casas simples, sem pessoas"],
 "saude": ["Corredor de posto de saúde público vazio, luz clara, cadeiras azuis", "Enfermeira de costas preparando vacina em sala de UBS"],
 "temporal": ["Rua de bairro alagada com chuva forte, carros com água na roda, céu escuro", "Árvore caída sobre fio elétrico em rua de cidade pequena depois de temporal"],
 "sol": ["Vale verde com colinas e casas de colonização alemã ao amanhecer, céu limpo", "Ciclovia arborizada ao pôr do sol em cidade pequena, sem pessoas"],
 "neblina_frio": ["Manhã de geada em campo com cerca de madeira e neblina baixa, sul do Brasil", "Rua de cidade pequena com neblina densa ao amanhecer, poste aceso"],
 "animais": ["Cachorro vira-lata caramelo sentado em calçada de cidade pequena olhando pra câmera", "Serpente sendo resgatada por bombeiro com luva, foco na cobra, sem rosto"],
 "evento": ["Praça de cidade pequena com barracas de festa e bandeirinhas, fim de tarde, gente de costas", "Palco de festa comunitária vazio sendo montado, luzes quentes"],
}
def proximo(slug):
    ns = [int(m.group(1)) for f in glob.glob(os.path.join(BG, slug + "-*.jpg")) for m in [re.search(r"-(\d+)\.jpg$", f)] if m]
    return max(ns, default=0) + 1
for slug, cenas in CENAS.items():
    for cena in cenas:
        n = proximo(slug); dst = os.path.join(BG, f"{slug}-{n}.jpg")
        try:
            tmp = dst + ".webp"; gerar_imagem(cena, tmp, estilo=EST, largura_max=1350)
            Image.open(tmp).convert("RGB").save(dst, "JPEG", quality=88); os.remove(tmp); print("ok", os.path.basename(dst), flush=True)
        except Exception as e:
            print("FALHOU", slug, str(e)[:120], flush=True)
print("FIM", flush=True)
