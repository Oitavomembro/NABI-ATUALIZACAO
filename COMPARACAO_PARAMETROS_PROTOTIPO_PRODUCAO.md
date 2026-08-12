# Comparação de parâmetros — protótipo × produção — Checkpoint 38

| Parâmetro | Protótipo aprovado | Produção Checkpoint 38 | Situação |
|---|---:|---:|---|
| Espaço lógico | 1280×720 | 1280×720 | idêntico |
| Proporção | 16:9 | 16:9 | idêntico |
| FPS alvo | 60 | 60 | idêntico |
| Duração | 12,2 s | 12,2 s | idêntico |
| Fundo | RGB 0,1,5 | RGB 0,1,5 | idêntico |
| Estrelas de fundo | 2.050 | 2.050 | idêntico |
| Estrelas do nome | máximo 1.500 | 1.500 | idêntico |
| Estrelas raras | 8 | 8 | idêntico |
| Fonte/máscara | Segoe UI Bold 96, passo 3 | Segoe UI Bold 96, passo 3 | equivalente direto |
| Fade-in | `smooth(t/1.0)` | `smooth(t/1.0)` | idêntico |
| Fade-out | `1-smooth((t-11)/1.2)` | mesma expressão | idêntico |
| Aceleração | `smooth((t-2)/3.6)` | mesma expressão | idêntico |
| Desaceleração | `smooth((t-6.35)/2.35)` | mesma expressão | idêntico |
| Limpeza do fundo | `smooth((t-4.55)/1.45)` | mesma expressão | idêntico |
| Formação do nome | `smooth((t-4.70)/2.85)` | mesma expressão | idêntico |
| Velocidade | `40+540*(warp**2.60)` | mesma expressão | idêntico |
| Probabilidade-base de linha | 0,10 | 0,10 | idêntico |
| Início das linhas | warp > 0,08 | warp > 0,08 | idêntico |
| Comprimento | `1+warp**1.65*2.85` | mesma expressão | idêntico |
| Origem do nome | raio 2–42 no centro | raio 2–42 no centro | idêntico |
| Delay | 0–0,72 | 0–0,72 | idêntico |
| Curvatura | −0,38 a 0,38 | −0,38 a 0,38 | idêntico |
| Travel | expoente 2,25 | expoente 2,25 | idêntico |
| Rastro do nome | somente p 0,82–0,90 | somente p 0,82–0,90 | idêntico |
| Sweep | 245 px/s, faixa 620, raio 78 | mesmos valores | idêntico |
| Vignette | 32 contornos | 32 contornos alpha | equivalente direto |
| Cor final do nome | branco no protótipo | marfim neon `#FFFCEB` | alteração explicitamente exigida |
| Texto adicional | nenhum | nenhum | idêntico |

## Adaptações arquiteturais sem alteração visual intencional

- pygame foi substituído por Tk/Pillow para manter o empacotamento já estabilizado;
- primitivas alpha do pygame foram reproduzidas por `ImageDraw` em modo RGBA;
- a imagem é reduzida proporcionalmente somente quando a tela física não comporta 1280×720;
- o helper permanece em processo separado, sem segundo loop Tk no processo principal;
- após 11 s, se `MAIN_WINDOW_READY` ainda não chegou, o estado visual permanece vivo; ao chegar, a sequência 11–12,2 s é concluída normalmente.

Nenhuma contagem foi reduzida por performance.

