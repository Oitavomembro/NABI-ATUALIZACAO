# Validação manual Windows — Checkpoint 38

Todos os itens começam como **PENDENTE DE VALIDAÇÃO FÍSICA**.

## Build

```powershell
cd C:\NB\NabiCode
powershell -ExecutionPolicy Bypass -File build_tools\build_offline_windows.ps1
```

Não executar o `.iss` separadamente e não reutilizar instalador anterior.

## Checklist visual

- [ ] Splash ocupa 1280×720 em tela compatível e permanece 16:9 em tela menor.
- [ ] DPI 100%, 125% e 150% não distorce nem reduz indevidamente o conteúdo.
- [ ] Animação progride sem depender de minimizar/maximizar.
- [ ] Campo inicial possui profundidade e densidade equivalentes ao protótipo.
- [ ] Aceleração começa em aproximadamente 2 s.
- [ ] Lightspeed atinge velocidade convincente entre aproximadamente 4,5 e 5 s.
- [ ] Apenas uma parcela baixa das estrelas vira rastro.
- [ ] Rastros não dominam a tela.
- [ ] Formação começa na janela temporal do protótipo, sem atraso adicional.
- [ ] Não existe aglomerado/círculo evidente no centro.
- [ ] NABICODE fica claramente legível, com tamanho, posição e espaçamento corretos.
- [ ] Letras são formadas por estrelas, sem texto comum subjacente.
- [ ] Cor é marfim neon `#FFFCEB`, sem amarelo forte, cinza ou cores aleatórias.
- [ ] Glow é quente e discreto; centro permanece quase branco.
- [ ] Não existe nome da loja, slogan, versão, “carregando” ou qualquer texto adicional.
- [ ] Desaceleração e fade final seguem a sequência aprovada.
- [ ] Se a aplicação estiver pronta cedo, a sequência mínima não é acelerada.
- [ ] Se a aplicação atrasar, o campo continua vivo em vez de congelar.
- [ ] Transição para a janela principal continua suave.
- [ ] Nenhum helper permanece após o startup.

## Medição

Após o teste, consultar o log de startup do perfil `PRODUCAO` e registrar a linha `Splash concluída`, contendo FPS real, render médio, pior render, frames e resolução exibida. Anotar também Windows, CPU/GPU, RAM, resolução, escala DPI e hash do instalador.

Critério de aprovação: fidelidade visual aceita pelo responsável no Windows real, sem freeze e sem regressão estrutural do startup.

